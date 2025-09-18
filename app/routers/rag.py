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
    q: str = Query(..., description="The search query text.", min_length=1),
    limit: int = Query(
        5, ge=1, le=50, description="Maximum number of documents to return."
    ),
    threshold: float = Query(
        0.2, ge=0.0, le=1.0, description="Minimum similarity threshold for results."
    ),
    db: Session = Depends(get_db),
) -> List[DocResult]:
    """
    Performs semantic search for documents based on the query 'q'.

    This uses cosine similarity to find the most relevant document chunks.
    It returns a list of documents ordered by their similarity score, highest first.
    """
    try:
        # Generate an embedding for the user's query.
        query_embedding = embed_text(q)
        if not query_embedding or len(query_embedding) != 1536:
            raise HTTPException(
                status_code=400,
                detail="Failed to generate a valid embedding for the query.",
            )

        # Use Sqlalchemy to perform the vector search.
        # We use cosine_distance (<->), which is the standard for semantic search.
        # Similarity is calculated as 1 - cosine_distance.
        distance = Doc.embedding.cosine_distance(query_embedding)
        similarity = (1 - distance).label("similarity")

        results = (
            db.query(Doc, similarity)
            .filter(Doc.embedding.isnot(None))
            # Filter in the database for efficiency, before fetching data.
            # We filter by similarity score directly.
            .filter(similarity >= threshold)
            .order_by(distance.asc())  # Order by distance (closest first)
            .limit(limit)
            .all()
        )

        # Format the results into our DocResult schema.
        # We process the list of (Doc, similarity) tuples returned by the query.
        response_data = []
        for doc, sim_score in results:
            doc_data = doc.__dict__
            doc_data["similarity"] = sim_score
            response_data.append(DocResult.model_validate(doc_data))

        return response_data

    except Exception as e:
        logger.error(f"An error occurred during vector search: {e}")
        raise HTTPException(
            status_code=500, detail=f"An internal error occurred during the search."
        )


@router.get("/query-debug", include_in_schema=False)  # hide from public API docs
def query_docs_debug(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    """
    Same as the /query endpoint, but returns raw results with similarity scores.
    """
    try:
        query_embedding = embed_text(q)
        if not query_embedding:
            return {"error": "Could not generate embedding for query."}

        distance = Doc.embedding.cosine_distance(query_embedding)
        similarity = (1 - distance).label("similarity")

        # No .filter() on the similarity score
        results = (
            db.query(Doc.id, Doc.title, Doc.content, similarity)
            .filter(Doc.embedding.isnot(None))
            .order_by(distance.asc())
            .limit(5)
            .all()
        )

        # Simply return the raw results with their scores
        return [
            {
                "id": str(row.id),
                "title": row.title,
                "content": row.content[:100]
                + "...",  # Truncate content for readability
                "similarity_score": round(row.similarity, 4),
            }
            for row in results
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
