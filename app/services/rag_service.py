import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import HTTPException
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.config import config
from app.models.doc import Doc
from app.schemas.doc import DocResult
from app.schemas.rag import ChatMessage, ContentChunk
from app.services.content_enhancer import content_enhancer
from app.services.query_expander import query_expander
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
            # Expand query to improve semantic matching
            expanded_query = query_expander.expand_query(query)
            embedding = embed_text(expanded_query)
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

    async def stream_chat_response(self, messages: List[ChatMessage], limit: int, threshold: float):
        """Streams a chat response, using the retrieval logic to build context."""

        # The last message is always the user's question
        latest_user_question = messages[-1].content

        # 1. Retrieve relevant docs using provided parameters
        relevant_docs = self.get_relevant_documents(
            query=latest_user_question,
            limit=limit,
            threshold=threshold
        )

        # 2. Build enriched context
        context_parts = []
        for doc in relevant_docs:
            md = doc.doc_metadata or {}

            # Generate URL based on document source
            if doc.slug.startswith(config.BLOG_PREFIX):
                url = f"{config.BASE_BLOG_URL}/{doc.slug}"
            elif doc.slug.startswith(config.PORTFOLIO_PREFIX):
                # For portfolio content, use the slug directly (it contains the actual path)
                url = (
                    f"{config.BASE_BLOG_URL}{doc.slug}"
                    if doc.slug.startswith("/")
                    else f"{config.BASE_BLOG_URL}/{doc.slug}"
                )
            else:
                url = "N/A"

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
            "Use the following context from Ted's portfolio content, blog posts and personal knowledge base to answer the user's question:\n\n"
            f"{context_text}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "- Provide specific, actionable answers that directly address the user's question.\n"
            "- Keep responses concise but informative - aim for 2-4 sentences maximum.\n"
            "- ALWAYS include the exact URL from the 'URL' field when referencing any portfolio page or blog post.\n"
            "- Highlight relevant technologies, frameworks, and tools mentioned in the context.\n"
            "- If the context contains project details, mention specific features, accomplishments, or technical implementations.\n"
            "- STRICTLY DO NOT HALLUCINATE: Only use information explicitly present in the provided context.\n"
            "- If the context doesn't contain sufficient information to answer the question, clearly state: 'I don't have enough information about that in my knowledge base.'\n"
            "- Never invent URLs, technologies, or project details that aren't in the context.\n"
            "- Focus on providing accurate, verifiable information from the available documents."
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

    def _generate_content_hash(self, chunk: ContentChunk) -> str:
        """Generate SHA-256 hash for content change detection."""
        content_to_hash = f"{chunk.slug}{chunk.title}{chunk.content}{json.dumps(chunk.metadata or {}, sort_keys=True)}"
        return hashlib.sha256(content_to_hash.encode()).hexdigest()

    def update_portfolio_content(
        self, content_chunks: List[ContentChunk]
    ) -> Dict[str, Any]:
        """
        Update portfolio content with hash-based change detection.
        Only updates documents that have changed and removes deleted ones.
        """
        stats = {"processed": 0, "updated": 0, "skipped": 0, "errors": []}

        try:
            # Get existing portfolio documents for comparison
            existing_docs = (
                self.db.query(Doc)
                .filter(Doc.document_id.like(f"{config.PORTFOLIO_PREFIX}%"))
                .all()
            )

            existing_docs_map = {doc.document_id: doc for doc in existing_docs}
            processed_doc_ids = set()

            # Process each content chunk
            for chunk in content_chunks:
                stats["processed"] += 1

                try:
                    # Generate content hash for change detection
                    content_hash = self._generate_content_hash(chunk)

                    # Create document ID with portfolio prefix (now using unique slugs)
                    document_id = f"{config.PORTFOLIO_PREFIX}{chunk.slug}"
                    processed_doc_ids.add(document_id)

                    # Check if document exists and has same content hash
                    existing_doc = existing_docs_map.get(document_id)
                    if existing_doc:
                        existing_hash = existing_doc.doc_metadata.get("content_hash")
                        if existing_hash == content_hash:
                            # Skip unchanged content
                            stats["skipped"] += 1
                            logger.debug(f"Skipping unchanged content: {document_id}")
                            continue
                        else:
                            logger.debug(
                                f"Content changed for {document_id}: {existing_hash} != {content_hash}"
                            )
                    else:
                        logger.debug(f"New content: {document_id}")

                    # Enhance content with metadata before embedding
                    enhanced_content = content_enhancer.enhance_content(
                        content=chunk.content,
                        title=chunk.title,
                        metadata=chunk.metadata or {}
                    )
                    
                    # Generate embedding for the enhanced content (only for new/changed content)
                    embedding = embed_text(enhanced_content)

                    if existing_doc:
                        # Update existing document
                        existing_doc.title = chunk.title
                        existing_doc.content = chunk.content
                        existing_doc.doc_metadata = {
                            "content_hash": content_hash,
                            "source": "portfolio",
                            "updated_at": datetime.now().isoformat(),
                            **(chunk.metadata or {}),
                        }
                        existing_doc.embedding = embedding
                    else:
                        # Create new document
                        doc = Doc(
                            document_id=document_id,
                            slug=chunk.slug,
                            title=chunk.title,
                            content=chunk.content,
                            doc_metadata={
                                "content_hash": content_hash,
                                "source": "portfolio",
                                "updated_at": datetime.now().isoformat(),
                                **(chunk.metadata or {}),
                            },
                            embedding=embedding,
                        )
                        self.db.add(doc)

                    stats["updated"] += 1

                except Exception as e:
                    error_msg = f"Failed to process chunk {chunk.slug}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append({"slug": chunk.slug, "error": str(e)})
                    continue

            # Remove documents that are no longer in the current content
            doc_ids_to_remove = set(existing_docs_map.keys()) - processed_doc_ids
            if doc_ids_to_remove:
                deleted_count = (
                    self.db.query(Doc)
                    .filter(Doc.document_id.in_(doc_ids_to_remove))
                    .delete(synchronize_session=False)
                )
                logger.info(f"Deleted {deleted_count} removed portfolio documents")

            # Commit all changes
            self.db.commit()
            logger.info(f"Portfolio content update completed: {stats}")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update portfolio content: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to update portfolio content: {str(e)}"
            )

        return stats
