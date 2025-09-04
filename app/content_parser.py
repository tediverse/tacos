import base64
import logging

import pycouchdb

logger = logging.getLogger(__name__)


class ContentParser:
    def __init__(self, db):
        self.db = db

    def get_markdown_content(self, doc: dict) -> str:
        """Get the full markdown content from a document (decoded as text)."""
        raw = self._get_raw_content(doc, is_binary=False)
        if isinstance(raw, bytes):
            # If somehow bytes slipped in, decode to string
            return raw.decode("utf-8", errors="ignore")
        return raw or ""

    def get_binary_content(self, doc: dict) -> bytes | None:
        """Get binary content from a document (decode base64 if needed)."""
        return self._get_raw_content(doc, is_binary=True)

    def _get_raw_content(
        self, doc: dict, is_binary: bool = False
    ) -> str | bytes | None:
        """Reconstruct from children (string or bytes)."""
        children = doc.get("children")
        if not children:
            return None

        parts = []
        for c in children:
            try:
                child_doc = self.db.get(c)
                if child_doc.get("type") == "leaf" and "data" in child_doc:
                    if is_binary:
                        # For binary content, decode each chunk
                        try:
                            parts.append(base64.b64decode(child_doc["data"]))
                        except Exception:
                            logger.warning(
                                f"Failed to decode base64 chunk {c}, skipping"
                            )
                    else:
                        parts.append(child_doc["data"])
            except pycouchdb.exceptions.NotFound:
                continue
            except Exception as e:
                logger.error(f"Error fetching child {c}: {e}")

        if is_binary:
            return b"".join(parts) if parts else None
        else:
            return "".join(parts) if parts else None
