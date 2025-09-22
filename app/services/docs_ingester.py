import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.config import config
from app.db.couchdb import parser
from app.models.doc import Doc
from app.services.text_embedder import embed_text

logger = logging.getLogger(__name__)


def ingest_doc(db: Session, raw_doc: dict) -> Optional[str]:
    """Ingest a single CouchDB doc into Postgres with chunking + embedding."""

    content = parser.get_markdown_content(raw_doc)
    if not content:
        logger.warning(f"Skipped doc {raw_doc.get('_id')} (no content)")
        return None

    slug = raw_doc.get("slug") or raw_doc["_id"]
    title = raw_doc.get("title", slug)

    # Chunk + embed
    chunks = chunk_text(content, chunk_size=500, overlap=50)
    new_docs = []
    success_count = 0

    for chunk in chunks:
        try:
            embedding = embed_text(chunk)
            new_docs.append(
                Doc(
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

        # Only ingest "plain" type blog posts
        if doc.get("type") != "plain" or not doc.get("path", "").startswith(
            config.BLOG_PREFIX
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
