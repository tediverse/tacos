import logging

from sqlalchemy.orm import Session

from app.config import config
from app.models.doc import Doc
from app.services.content_parser import ContentParser
from app.services.text_embedder import embed_text

logger = logging.getLogger(__name__)


def ingest_doc(db: Session, parser: ContentParser, raw_doc: dict):
    """Ingest a single CouchDB doc into Postgres with chunking + embedding."""

    content = parser.get_markdown_content(raw_doc)
    if not content:
        return None

    slug = raw_doc.get("slug") or raw_doc["_id"]
    title = raw_doc.get("title", slug)

    # Delete old chunks
    db.query(Doc).filter(Doc.document_id == raw_doc["_id"]).delete()

    # Chunk + embed
    chunks = chunk_text(content, chunk_size=500, overlap=50)
    for chunk in chunks:
        try:
            embedding = embed_text(chunk)
            new_doc = Doc(
                document_id=raw_doc["_id"],
                slug=slug,
                title=title,
                content=chunk,
                embedding=embedding,
                doc_metadata={
                    "tags": raw_doc.get("tags"),
                    "created_at": raw_doc.get("created_at"),
                    "updated_at": raw_doc.get("updated_at"),
                },
            )
            db.add(new_doc)

        except Exception as e:
            logger.error(f"Failed to embed chunk for doc {slug}: {e}")
            continue
    db.commit()
    return slug


def ingest_all(db: Session, parser: ContentParser):
    """One-time ingestion of all CouchDB docs (skips deleted)."""
    all_docs = [row.get("doc", row) for row in parser.db.all(include_docs=True)]
    for doc in all_docs:
        # Skip deleted docs
        if doc.get("deleted", False):
            continue

        # Only get blog posts
        if doc.get("type") != "plain" or not doc.get("path", "").startswith(
            config.BLOG_PREFIX
        ):
            continue

        ingest_doc(db, parser, doc)


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
