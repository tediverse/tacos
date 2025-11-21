import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.db.couchdb import get_couch
from app.db.postgres.base import get_db
from app.schemas.doc import DocResult
from app.schemas.rag import PromptRequest, UpdateContentRequest, UpdateContentResponse
from app.services.docs_ingester import ingest_all
from app.services.rag_service import RAGService

router = APIRouter()
logger = logging.getLogger(__name__)
client = AsyncOpenAI()


def get_rag_service(db: Session = Depends(get_db)) -> RAGService:
    return RAGService(db)


@router.post("/prompt")
async def prompt_rag(
    request: PromptRequest,
    limit: int = Query(15, ge=1, le=50, description="Number of documents to retrieve"),
    threshold: float = Query(0.25, ge=0.0, le=1.0, description="Similarity threshold"),
    rag_service: RAGService = Depends(get_rag_service),
):
    """
    Prompt endpoint for RAG chatbot.
    Accepts a list of messages and streams back the response.
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    try:
        logger.debug(f"Received prompt request with {len(request.messages)} messages.")
        streamer = rag_service.stream_chat_response(
            messages=request.messages, limit=limit, threshold=threshold
        )
        return StreamingResponse(streamer, media_type="text/plain")

    except Exception as e:
        logger.error(f"Error in /prompt endpoint: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred.")


@router.post("/reingest")
def reingest(db: Session = Depends(get_db)):
    """
    Full ingestion/reset endpoint.
    Deletes old docs and re-ingests all CouchDB content.
    """
    try:
        couch_db, parser = get_couch()
        ingest_all(db, parser=parser)
        return {"status": "success", "message": "ingestion completed."}
    except Exception as e:
        logger.error(f"Reset ingest failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="ingestion failed")


@router.get("/query", response_model=List[DocResult])
def query_docs(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    threshold: float = Query(0.25, ge=0.0, le=1.0),
    debug: bool = Query(False),
    rag_service: RAGService = Depends(get_rag_service),
):
    """
    Perform semantic search with cosine similarity.
    Returns ranked document chunks above the similarity threshold.
    """
    try:
        results = rag_service.get_relevant_documents(
            query=q, limit=limit, threshold=threshold
        )

        if debug:
            # For debug, we return a list of dicts with truncated content
            return [
                {
                    "id": str(doc.id),
                    "title": doc.title,
                    "content": truncate(doc.content, 100),
                    "similarity": doc.similarity,
                }
                for doc in results
            ]

        # normal API output (validated)
        return results

    except Exception as e:
        logger.error(f"Error in /query endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def truncate(text: str | None, length: int) -> str | None:
    if not text:
        return None
    return text if len(text) <= length else text[:length] + "..."


@router.post("/update", response_model=UpdateContentResponse)
def update_portfolio_content(
    request: UpdateContentRequest,
    rag_service: RAGService = Depends(get_rag_service),
):
    """
    Update portfolio content with complete replacement strategy.
    Accepts portfolio content and manages embeddings for semantic search.
    """
    try:
        logger.info(
            f"Processing portfolio content update with {len(request.content)} chunks"
        )

        # Update portfolio content
        stats = rag_service.update_portfolio_content(request.content)

        return UpdateContentResponse(
            processed=stats["processed"],
            updated=stats["updated"],
            skipped=stats["skipped"],
            errors=stats["errors"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /update endpoint: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to process portfolio content update"
        )
