import logging
from typing import List

from fastapi import HTTPException
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.models.doc import Doc
from app.schemas.doc import DocResult
from app.schemas.rag import ChatMessage
from app.services.text_embedder import embed_text

logger = logging.getLogger(__name__)

client = AsyncOpenAI()


class RAGService:
    def __init__(self, db: Session):
        self.db = db

    def get_relevant_documents(
        self, query: str, limit: int, threshold: float
    ) -> List[DocResult]:
        """
        Embeds a query and performs semantic search with cosine similarity.
        Retrieves the content of documents with similarity above the threshold.
        """

        try:
            embedding = embed_text(query)
            if not embedding or len(embedding) != 1536:
                raise HTTPException(400, "Invalid embedding for query")

            distance = Doc.embedding.cosine_distance(embedding)
            similarity = (1 - distance).label("similarity")

            results = (
                self.db.query(Doc, similarity)
                .filter(Doc.embedding.isnot(None))
                .filter(similarity >= threshold)
                .order_by(similarity.desc())
                .limit(limit)
                .all()
            )

            return [
                DocResult(
                    id=doc.id,
                    slug=doc.slug,
                    title=doc.title,
                    content=doc.content,
                    doc_metadata=doc.doc_metadata,
                    similarity=round(sim, 4),
                )
                for doc, sim in results
            ]

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error during vector search: {e}")
            # Re-raise as a standard exception for the router to handle
            raise Exception("Internal error during search") from e

    async def stream_chat_response(self, messages: List[ChatMessage]):
        """Streams a chat response, using the retrieval logic to build context."""

        # The last message is always the user's question
        latest_user_question = messages[-1].content

        # 1. Retrieve relevant context
        relevant_docs = self.get_relevant_documents(
            query=latest_user_question, limit=5, threshold=0.2
        )
        context = "\n\n".join([doc.content for doc in relevant_docs if doc.content])

        # 2. Prepare prompts
        system_prompt = (
            "You are Ted Support, a helpful AI chatbot for Ted's developer portfolio. "
            "Use the following blog post content to answer the user's question. "
            "If the context doesn't contain the answer, say that you don't have that information from the blog.\n\n"
            f"Context:\n{context}"
        )

        # We prepend the system prompt
        prompt_messages = [{"role": "system", "content": system_prompt}]

        # Then add the existing chat history
        for message in messages:
            prompt_messages.append({"role": message.role, "content": message.content})

        # 3. Stream response
        try:
            stream = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=prompt_messages,
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content is not None:
                    yield content
        except Exception as e:
            logger.error(f"Error streaming OpenAI response: {e}")
            yield f"\n[Error: Could not get response from the model]"
