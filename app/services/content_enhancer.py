import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ContentEnhancer:
    """
    Service for enhancing content with metadata and enrichment before embedding.
    This improves semantic search by providing richer context for embeddings.
    """

    def enhance_content(
        self, title: str, content: str, metadata: Dict[str, Any] = None
    ) -> str:
        if metadata is None:
            metadata = {}

        enhanced_parts = []

        # Add title as context
        if title:
            enhanced_parts.append(f"Title: {title}")

        # Add enrichment metadata
        enrichment = metadata.get("enrichment")
        if enrichment:
            if isinstance(enrichment, list):
                # Join with newlines to maintain readability and semantic separation
                enrichment_text = "\n".join(enrichment)
            else:
                enrichment_text = str(enrichment)
            enhanced_parts.append(f"Additional Context:\n{enrichment_text}")

        # Add additional metadata fields for richer semantic context
        if metadata.get("contentType"):
            enhanced_parts.append(f"Content Type: {metadata.get('contentType')}")

        # Add original content
        enhanced_parts.append(f"Content: {content}")

        # Combine all parts
        enhanced_content = "\n".join(enhanced_parts)

        logger.debug(
            f"Enhanced content from {len(content)} to {len(enhanced_content)} chars"
        )
        return enhanced_content
