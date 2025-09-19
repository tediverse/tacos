import logging
from typing import AsyncGenerator, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.db.postgres.base import get_db
from app.models.doc import Doc
from app.schemas.doc import DocResult
from app.services.text_embedder import embed_text

router = APIRouter()
logger = logging.getLogger(__name__)
client = AsyncOpenAI()


@router.post("/prompt")
async def prompt_rag(
    question: str = Query(..., min_length=1), db: Session = Depends(get_db)
):
    """
    Prompt endpoint for RAG-powered chatbot.
    Streams the OpenAI response using relevant blog context.
    """
    try:
        # Get query embedding
        embedding = embed_text(question)

        # Fetch top 5 relevant docs
        distance = Doc.embedding.cosine_distance(embedding)
        similarity = (1 - distance).label("similarity")
        results = (
            db.query(Doc, similarity)
            .filter(Doc.embedding.isnot(None))
            .order_by(similarity.desc())
            .limit(5)
            .all()
        )

        context = "\n\n".join([doc.content for doc, _ in results])

        # Prepare system + user prompt
        system_prompt = f"You are an AI assistant. Use the following blog content to answer the question:\n{context}"
        user_prompt = question

        # 4️⃣ Stream OpenAI response
        async def streamer() -> AsyncGenerator[str, None]:
            try:
                stream = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    stream=True,
                )
                async for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        yield chunk.choices[0].delta.content
            except Exception as e:
                logger.error(f"Error streaming OpenAI response: {e}")
                yield f"\n[Error: {e}]"

        return StreamingResponse(streamer(), media_type="text/plain")

    except Exception as e:
        logger.error(f"Error in prompt_rag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
