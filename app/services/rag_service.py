import logging
from datetime import datetime
from typing import List

from fastapi import HTTPException
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.config import config
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
        self, query: str, limit: int = 5, threshold: float = 0.2
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

        # 1. Retrieve relevant docs
        relevant_docs = self.get_relevant_documents(query=latest_user_question)

        # 2. Build enriched context
        context_parts = []
        for doc in relevant_docs:
            md = doc.doc_metadata or {}
            url = (
                f"{config.BASE_BLOG_URL}/{doc.slug}"
                if doc.slug.startswith(config.BLOG_PREFIX)
                else "N/A"
            )
            tags = ", ".join(md.get("tags", [])) or "N/A"
            content_snippet = (
                (doc.content[:500] + "...") if len(doc.content) > 500 else doc.content
            )
            context_parts.append(
                f"Title: {doc.title}\n"
                f"Summary: {md.get('summary', 'N/A')}\n"
                f"Tags: {tags}\n"
                f"Source: {md.get('source', 'N/A')}\n"
                f"Created: {md.get('created_at', 'N/A')}\n"
                f"Updated: {md.get('updated_at', 'N/A')}\n"
                f"URL: {url}\n"
                f"Content: {content_snippet}\n"
                "-----"
            )

        context_text = "\n".join(context_parts) or "No relevant context available."
        logger.debug(f"Context for RAG:\n{context_text}")

        # 3. Prepare system prompt
        system_prompt = (
            f"You are Ted Support, a helpful AI chatbot for Ted's developer portfolio.\n"
            f"The current year is {datetime.now().year}.\n"
            "Use the following context from Ted's blog posts and personal knowledge base to answer the user's question:\n\n"
            f"{context_text}\n\n"
            "Instructions:\n"
            "- Answer clearly and concisely, 2-3 sentences preferred.\n"
            "- Include blog URLs from the 'URL' field whenever you reference a blog post.\n"
            "- If the context doesn't contain the answer, politely indicate you don't know.\n"
            "- Context can be unstructured PKB notes or blog posts with frontmatter.\n"
            "- Do not hallucinate facts outside the context."
        )

        # 4. Build messages with existing chat history
        prompt_messages = [{"role": "system", "content": system_prompt}]
        for message in messages:
            prompt_messages.append({"role": message.role, "content": message.content})

        # 5. Stream response
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
