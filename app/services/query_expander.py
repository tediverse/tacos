import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class QueryExpander:
    """
    Service for expanding user queries with synonyms and related terms
    to improve semantic search relevance.
    """
    
    def __init__(self):
        # Define expansion rules - can be moved to config file later
        self.expansion_rules: Dict[str, List[str]] = {
            # Work-related terms
            "work": ["work", "job", "employment", "career", "experience", "professional"],
            "job": ["job", "work", "employment", "position", "role"],
            "career": ["career", "work", "professional", "employment"],
            "experience": ["experience", "work", "background", "history"],
            
            # Company-related terms
            "company": ["company", "organization", "firm", "employer", "business"],
            "companies": ["companies", "organizations", "firms", "employers"],
            
            # Time-related terms
            "before": ["before", "previous", "past", "earlier", "prior"],
            "previous": ["previous", "past", "earlier", "prior", "before"],
            "past": ["past", "previous", "earlier", "before"],
            
            # Education-related terms
            "education": ["education", "school", "university", "college", "degree", "study"],
            "school": ["school", "education", "university", "college", "study"],
            "university": ["university", "college", "education", "school", "degree", "study"],
            "study": ["study", "education", "school", "university", "learning", "degree"],
            
            # Project-related terms
            "project": ["project", "work", "development", "build", "create"],
            "built": ["built", "developed", "created", "made", "implemented"],
        }
    
    def expand_query(self, query: str) -> str:
        """
        Expand query with synonyms and related terms to improve semantic matching.
        
        Args:
            query: Original user query
            
        Returns:
            Expanded query with additional related terms
        """
        query_lower = query.lower()
        expanded_terms = []
        
        # Add original query terms
        expanded_terms.extend(query.split())
        
        # Apply expansion rules
        for trigger_term, synonyms in self.expansion_rules.items():
            if trigger_term in query_lower:
                expanded_terms.extend(synonyms)
        
        # Remove duplicates while preserving order
        unique_terms = list(dict.fromkeys(expanded_terms))
        expanded_query = " ".join(unique_terms)
        
        if expanded_query != query:
            logger.debug(f"Query expanded from '{query}' to '{expanded_query}'")
        
        return expanded_query


# Global instance for easy access
query_expander = QueryExpander()