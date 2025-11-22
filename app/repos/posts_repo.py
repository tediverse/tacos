from typing import List, Optional

from app.settings import settings


class CouchPostsRepo:
    def __init__(self, couch_db):
        self.db = couch_db

    def list_blog_docs(self) -> List[dict]:
        all_docs = [row.get("doc", row) for row in self.db.all(include_docs=True)]
        return [
            doc
            for doc in all_docs
            if doc.get("type") == "plain"
            and doc.get("path", "").startswith(settings.BLOG_PREFIX)
            and not doc.get("deleted", False)
        ]

    def get_blog_doc(self, slug: str) -> Optional[dict]:
        doc_id = f"{settings.BLOG_PREFIX}{slug}.md"
        try:
            encoded_doc_id = doc_id.replace("/", "%2F")
            doc = self.db.get(encoded_doc_id)
            if self._is_valid(doc):
                return doc
        except Exception:
            pass

        for doc in self.list_blog_docs():
            if doc.get("_id") == doc_id:
                return doc
        return None

    @staticmethod
    def _is_valid(doc: dict | None) -> bool:
        if not doc:
            return False
        path = doc.get("path", doc.get("_id", ""))
        return (
            doc.get("type") == "plain"
            and path.startswith(settings.BLOG_PREFIX)
            and not doc.get("deleted", False)
        )
