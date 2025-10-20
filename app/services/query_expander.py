import logging
import re
from typing import Dict, List

from app.services.query_expansion_rules import EXPANSION_RULES

logger = logging.getLogger(__name__)


class QueryExpander:
    """
    Service for expanding user queries with synonyms and related terms
    to improve semantic search relevance.
    """

    def __init__(self):
        self.expansion_rules: Dict[str, List[str]] = EXPANSION_RULES
        logger.info(f"Loaded {len(self.expansion_rules)} expansion rules")

    def expand_query(self, query: str) -> str:
        """
        Expand query with synonyms and related terms to improve semantic matching.

        Args:
            query: Original user query

        Returns:
            Expanded query with additional related terms
        """
        if not query.strip():
            return query

        query_lower = query.lower()
        expanded_terms = []

        # Add original query terms
        expanded_terms.extend(query.split())

        # Apply expansion rules with word boundary matching for more precise expansion
        for trigger_term, synonyms in self.expansion_rules.items():
            # Use word boundaries to avoid partial matches
            pattern = r"\b" + re.escape(trigger_term) + r"\b"
            if re.search(pattern, query_lower):
                expanded_terms.extend(synonyms)

        # Remove duplicates while preserving order
        unique_terms = list(dict.fromkeys(expanded_terms))
        expanded_query = " ".join(unique_terms)

        if expanded_query != query:
            logger.debug(f"Query expanded from '{query}' to '{expanded_query}'")

        return expanded_query


# Global instance for easy access
query_expander = QueryExpander()
