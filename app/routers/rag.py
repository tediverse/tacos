import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.postgres import get_db
from app.models.doc import Doc
from app.schemas.doc import DocResult
from app.services.text_embedder import embed_text

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/query", response_model=List[DocResult])
def query_docs(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=50),
    threshold: float = Query(0.2, ge=0.0, le=1.0),
    debug: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Perform semantic search with cosine similarity.
    Returns ranked document chunks above the similarity threshold.
    """
    try:
        query_embedding = get_query_embedding(q)

        distance = Doc.embedding.cosine_distance(query_embedding)
        similarity = (1 - distance).label("similarity")

        results = (
            db.query(Doc, similarity)
            .filter(Doc.embedding.isnot(None))
            .filter(similarity >= threshold)
            .order_by(similarity.desc())
            .limit(limit)
            .all()
        )

        if debug:
            # lightweight debug output
            return [
                {
                    "id": str(doc.id),
                    "title": doc.title,
                    "content": truncate(doc.content, 100),
                    "similarity": round(sim, 4),
                }
                for doc, sim in results
            ]

        # normal API output (validated)
        return [
            DocResult.model_validate(
                {
                    "id": doc.id,
                    "slug": doc.slug,
                    "title": doc.title,
                    "content": doc.content,
                    "doc_metadata": doc.doc_metadata,
                    "similarity": round(sim, 4),
                }
            )
            for doc, sim in results
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during vector search: {e}")
        raise HTTPException(500, "Internal error during search")


def get_query_embedding(q: str) -> list[float]:
    embedding = embed_text(q)
    if not embedding or len(embedding) != 1536:
        raise HTTPException(400, "Invalid embedding for query")
    return embedding


def truncate(text: str | None, length: int) -> str | None:
    if not text:
        return None
    return text if len(text) <= length else text[:length] + "..."
