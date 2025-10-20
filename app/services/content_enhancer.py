import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class ContentEnhancer:
    """
    Service for enhancing content with metadata and enrichment before embedding.
    This improves semantic search by providing richer context for embeddings.
    """
    
    def enhance_content(self, content: str, title: str, metadata: Dict[str, Any] = None) -> str:
        """
        Enhance content by combining it with title and enrichment metadata.
        
        Args:
            content: Original document content
            title: Document title
            metadata: Document metadata including enrichment fields
            
        Returns:
            Enhanced content with additional context
        """
        if metadata is None:
            metadata = {}
        
        enhanced_parts = []
        
        # Add title as context
        if title:
            enhanced_parts.append(f"Title: {title}")
        
        # Add enrichment metadata if available (handle both string and list formats)
        enrichment = metadata.get("enrichment")
        if enrichment:
            if isinstance(enrichment, list):
                # Join list items with spaces
                enrichment_text = " ".join(enrichment)
            else:
                enrichment_text = str(enrichment)
            enhanced_parts.append(f"Context: {enrichment_text}")
        
        # Add original content
        enhanced_parts.append(f"Content: {content}")
        
        # Combine all parts
        enhanced_content = "\n".join(enhanced_parts)
        
        logger.debug(f"Enhanced content from {len(content)} to {len(enhanced_content)} chars")
        return enhanced_content


# Global instance for easy access
content_enhancer = ContentEnhancer()