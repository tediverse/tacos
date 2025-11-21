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
