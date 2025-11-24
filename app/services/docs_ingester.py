import logging
from typing import Optional

from llama_index.core import Document
from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding
from sqlalchemy.orm import Session

from app.models.doc import Doc
from app.services.content_enhancer import ContentEnhancer
from app.services.posts_service import parse_post_data
from app.services.text_embedder import embed_text
from app.settings import settings

logger = logging.getLogger(__name__)


def ingest_doc(
    db: Session,
    raw_doc: dict,
    *,
    parser,
    enhance_content=ContentEnhancer().enhance_content,
    embed_text_fn=embed_text,
    parse_post_data_fn=None,
    chunk_text_fn=None,
) -> Optional[str]:
    """Ingest a single CouchDB doc into Postgres with chunking + embedding."""

    parse_post_data_fn = parse_post_data_fn or parse_post_data
    chunk_text_fn = chunk_text_fn or chunk_text

    # Parse via post_service (includes frontmatter handling)
    slug = raw_doc.get("path") or raw_doc["_id"]
    post_data = parse_post_data_fn(raw_doc, slug, include_content=True, parser=parser)
    if not post_data or not post_data.get("content"):
        logger.warning(f"Skipped doc {slug} (no content after parsing)")
        return None

    content = post_data["content"]
    title = post_data.get("title", slug)
    slug = post_data.get("slug")

    # Chunk + embed
    chunks = chunk_text_fn(content)
    new_docs = []
    success_count = 0

    for chunk in chunks:
        try:
            # Enhance content with metadata before embedding
            enhanced_content = enhance_content(
                content=chunk,
                title=title,
                metadata={
                    "tags": post_data.get("tags", []),
                    "summary": post_data.get("summary"),
                },
            )
            embedding = embed_text_fn(enhanced_content)
            new_docs.append(
                Doc(
                    document_id=raw_doc["_id"],
                    slug=slug,
                    title=title,
                    content=chunk,  # Store original content for display
                    embedding=embedding,
                    doc_metadata={
                        "tags": post_data.get("tags", []),
                        "created_at": post_data.get("publishedAt"),
                        "updated_at": post_data.get("updatedAt"),
                        "summary": post_data.get("summary"),
                        "source": (
                            "blog" if slug.startswith(settings.BLOG_PREFIX) else "kb"
                        ),
                    },
                )
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to embed chunk for doc {slug}: {e}")
            continue

    if success_count > 0:
        # only delete old chunks if we have at least one successful embedding
        db.query(Doc).filter(Doc.document_id == raw_doc["_id"]).delete(
            synchronize_session=False
        )
        db.add_all(new_docs)
        db.commit()
        logger.info(f"Ingested {slug}: {success_count}/{len(chunks)} chunks")
        return slug
    else:
        logger.warning(f"Doc {slug} had no successfully embedded chunks")
        return None


def ingest_all(db: Session, *, parser, ingest_fn=None):
    """One-time ingestion of all CouchDB docs. Also removes deleted docs."""
    ingest_fn = ingest_fn or ingest_doc
    all_docs = [row.get("doc", row) for row in parser.db.all(include_docs=True)]
    for doc in all_docs:
        # Remove deleted docs from Postgres
        if doc.get("deleted", False):
            db.query(Doc).filter(Doc.document_id == doc["_id"]).delete()
            db.commit()
            continue

        # Only ingest "plain" types, meaning markdown files
        if doc.get("type") != "plain":
            continue

        # Only ingest docs under specific paths
        path = doc.get("path", "")
        if not (
            path.startswith(settings.BLOG_PREFIX) or path.startswith(settings.KB_PREFIX)
        ):
            continue

        ingest_fn(db, doc, parser=parser)


def chunk_text(
    text: str,
    *,
    embed_model=None,
) -> list[str]:
    """
    Chunk text for embedding using LlamaIndex semantic splitter.
    Keeping the surface area small: supply a custom embed_model in tests to avoid network calls.
    """
    if not text:
        return []

    embed_model = embed_model or OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=settings.OPENAI_API_KEY or None,
    )

    splitter = SemanticSplitterNodeParser(embed_model=embed_model)
    nodes = splitter.get_nodes_from_documents([Document(text=text)])
    return [node.get_content() for node in nodes if node.get_content().strip()]
