import logging

import pycouchdb

logger = logging.getLogger(__name__)


class ContentParser:
    def __init__(self, db):
        self.db = db

    def get_content(self, doc: dict, all_docs: list[dict] | None = None) -> str:
        """Get the full markdown content from a document."""
        # Direct content
        for key in ("data", "content"):
            if key in doc:
                return doc[key]

        # Reconstruct from children
        children = doc.get("children")
        if not children:
            return ""

        if all_docs:
            doc_lookup = {
                row.get("doc", row)["_id"]: row.get("doc", row) for row in all_docs
            }
            return "".join(
                doc_lookup[c]["data"]
                for c in children
                if doc_lookup.get(c, {}).get("type") == "leaf"
                and "data" in doc_lookup[c]
            )
        else:
            # Fetch from DB
            content_parts = []
            for c in children:
                try:
                    child_doc = self.db.get(c)
                    if child_doc.get("type") == "leaf" and "data" in child_doc:
                        content_parts.append(child_doc["data"])
                except pycouchdb.exceptions.NotFound:
                    continue
                except Exception as e:
                    logger.error(f"Error fetching child {c}: {e}")
            return "".join(content_parts)
