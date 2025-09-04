import base64
import logging
import pycouchdb

logger = logging.getLogger(__name__)


class ContentParser:
    def __init__(self, db):
        self.db = db

    def get_markdown_content(self, doc: dict, all_docs: list[dict] | None = None) -> str:
        """Get the full markdown content from a document (decoded as text)."""
        raw = self._get_raw_content(doc, all_docs)
        if isinstance(raw, bytes):
            # If somehow bytes slipped in, decode to string
            return raw.decode("utf-8", errors="ignore")
        return raw or ""

    def get_binary_content(self, doc: dict, all_docs: list[dict] | None = None) -> bytes | None:
        """Get binary content from a document (decode base64 if needed)."""
        raw = self._get_raw_content(doc, all_docs)
        if isinstance(raw, str):
            try:
                return base64.b64decode(raw)
            except Exception:
                logger.warning("Expected base64 but got plain string, returning utf-8 bytes")
                return raw.encode("utf-8")
        return raw

    def _get_raw_content(self, doc: dict, all_docs: list[dict] | None = None) -> str | bytes | None:
        """Internal helper: reconstruct raw content (string or base64 string)."""
        # Direct content
        for key in ("data", "content"):
            if key in doc:
                return doc[key]

        # Reconstruct from children
        children = doc.get("children")
        if not children:
            return None

        if all_docs:
            doc_lookup = {
                row.get("doc", row)["_id"]: row.get("doc", row) for row in all_docs
            }
            parts = [
                doc_lookup[c]["data"]
                for c in children
                if doc_lookup.get(c, {}).get("type") == "leaf"
                and "data" in doc_lookup[c]
            ]
            return "".join(parts) if parts else None
        else:
            parts = []
            for c in children:
                try:
                    child_doc = self.db.get(c)
                    if child_doc.get("type") == "leaf" and "data" in child_doc:
                        parts.append(child_doc["data"])
                except pycouchdb.exceptions.NotFound:
                    continue
                except Exception as e:
                    logger.error(f"Error fetching child {c}: {e}")
            return "".join(parts) if parts else None