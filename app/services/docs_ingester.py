import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.config import config
from app.db.couchdb import parser
from app.models.doc import Doc
from app.services import content_enhancer
from app.services.post_service import parse_post_data
from app.services.text_embedder import embed_text

logger = logging.getLogger(__name__)


def ingest_doc(db: Session, raw_doc: dict) -> Optional[str]:
    """Ingest a single CouchDB doc into Postgres with chunking + embedding."""

    # Parse via post_service (includes frontmatter handling)
    slug = raw_doc.get("path") or raw_doc["_id"]
    post_data = parse_post_data(raw_doc, slug, include_content=True)
    if not post_data or not post_data.get("content"):
        logger.warning(f"Skipped doc {slug} (no content after parsing)")
        return None

    content = post_data["content"]
    title = post_data.get("title", slug)
    slug = post_data.get("slug")

    # Chunk + embed
    chunks = chunk_text(content, chunk_size=500, overlap=50)
    new_docs = []
    success_count = 0

    for chunk in chunks:
        try:
            # Enhance content with metadata before embedding
            enhanced_content = content_enhancer.enhance_content(
                content=chunk,
                title=title,
                metadata={
                    "tags": post_data.get("tags", []),
                    "summary": post_data.get("summary"),
                },
            )
            embedding = embed_text(enhanced_content)
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
                            "blog" if slug.startswith(config.BLOG_PREFIX) else "kb"
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


def ingest_all(db: Session):
    """One-time ingestion of all CouchDB docs. Also removes deleted docs."""
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
            path.startswith(config.BLOG_PREFIX) or path.startswith(config.KB_PREFIX)
        ):
            continue

        ingest_doc(db, doc)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50):
    """Split text into overlapping chunks by words."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks
