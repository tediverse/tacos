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

    def all(self, include_docs: bool = True):
        if self.track_calls:
            self.calls.append(f"all(include_docs={include_docs})")
        if include_docs:
            return [{"doc": doc} for doc in self.docs.values()]
        return list(self.docs.values())


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
        return None


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filtered = None

    def filter(self, expr):
        self.filtered = expr
        return self

    def all(self):
        return self.rows


class FakeSession:
    """
    Lightweight SQLAlchemy Session stand-in for PostViewService tests.
    """

    def __init__(self, rows=None, record_map=None, execute_value=1):
        self.rows = rows or []
        self.record_map = record_map or {}
        self.execute_value = execute_value
        self.executed_stmt = None
        self.committed = False
        self.last_query = None

    def query(self, *cols):
        self.last_query = FakeQuery(self.rows)
        return self.last_query

    def get(self, model, key):
        return self.record_map.get(key)

    def execute(self, stmt):
        from tests.conftest import (  # local import to avoid circular on import
            FakeResult,
        )

        self.executed_stmt = stmt
        return FakeResult(self.execute_value)

    def commit(self):
        self.committed = True


class FakePostsService:
    """
    Minimal posts service stand-in for router tests.
    """

    def __init__(self, list_posts_return=None, get_post_return=None):
        self._list_posts_return = list_posts_return or []
        self._get_post_return = get_post_return

    def list_posts(self):
        return self._list_posts_return

    def get_post(self, slug: str):
        return self._get_post_return


# --- Content and parser helpers ---
import textwrap  # noqa: E402


class FakeParser:
    """
    Minimal markdown/content parser stand-in.
    """

    def __init__(self, content_by_id: dict[str, str]):
        self.content_by_id = content_by_id

    def get_markdown_content(self, doc: dict) -> str | None:
        raw = self.content_by_id.get(doc.get("_id"))
        if raw is None:
            return None
        return textwrap.dedent(raw).lstrip()


class FakeViewService:
    """
    Minimal view service stand-in for post service tests.
    """

    def __init__(self, counts: dict[str, int]):
        self.counts = counts
        self.calls = []

    def get_views_for_slugs(self, slugs):
        slugs_list = list(slugs)
        self.calls.append(tuple(slugs_list))
        return {slug: self.counts.get(slug, 0) for slug in slugs_list}

    def get_view_count(self, slug: str) -> int:
        self.calls.append(slug)
        return self.counts.get(slug, 0)
