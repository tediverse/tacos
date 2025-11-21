import pycouchdb


class FakeCouchDB:
    """
    Minimal in-memory CouchDB stand-in.
    Set track_calls=True to record the order of get() calls.
    """

    def __init__(self, docs: dict, track_calls: bool = False):
        self.docs = docs
        self.track_calls = track_calls
        self.calls = []

    def get(self, doc_id: str) -> dict:
        if self.track_calls:
            self.calls.append(doc_id)
        if doc_id not in self.docs:
            raise pycouchdb.exceptions.NotFound(doc_id)
        return self.docs[doc_id]


class FakeRepo:
    """
    Minimal repo stand-in used in service tests.
    """

    def __init__(self, docs):
        self.docs = docs

    def list_blog_docs(self):
        return list(self.docs)

    def get_blog_doc(self, _slug):
        if not self.docs:
            return None
        doc_id = f"blog/{_slug}.md"
        for doc in self.docs:
            if doc.get("_id") == doc_id or doc.get("path") == doc_id:
                return doc
        raise AssertionError(f"Unexpected slug requested: {_slug}")
