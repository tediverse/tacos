from llama_index.core.base.embeddings.base import BaseEmbedding

from app.models.doc import Doc
from app.services.docs_ingester import chunk_text, ingest_all, ingest_doc
from app.settings import settings
from tests.conftest import FakeCouchDB, FakeQuery
from tests.conftest import FakeSession as BaseSession


class FakeEmbed(BaseEmbedding):
    """Minimal embedder to avoid external calls in tests."""

    model_name: str = "fake"

    def _get_query_embedding(self, _text: str):
        return [0.0, 0.0]

    async def _aget_query_embedding(self, _text: str):
        return [0.0, 0.0]

    def _get_text_embedding(self, _text: str):
        return [0.0, 0.0]


class IngestFakeQuery(FakeQuery):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.deleted = False
        self.delete_kwargs = None

    def delete(self, synchronize_session=None):
        self.deleted = True
        self.delete_kwargs = {"synchronize_session": synchronize_session}


class IngestFakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.queries = []
        self.commit_calls = 0

    def query(self, *cols):
        self.queried_model = cols[0] if cols else None
        query = IngestFakeQuery(self.rows, first_result=self.first_result)
        self.last_query = query
        self.queries.append(query)
        return query

    def add_all(self, objs):
        self.added.extend(objs)

    def commit(self):
        self.commit_calls += 1
        self.committed = True


def fake_chunk_text(text, *_args, **_kwargs):
    """Return the full text as a single chunk to avoid networked splitters."""
    return [text] if text else []


def test_ingest_doc_returns_none_when_parse_fails():
    db = IngestFakeSession()
    raw_doc = {"_id": "blog/empty.md", "path": "blog/empty.md"}

    result = ingest_doc(
        db,
        raw_doc,
        parser=object(),
        parse_post_data_fn=lambda *args, **kwargs: None,
        chunk_text_fn=fake_chunk_text,
    )

    assert result is None
    assert db.added == []
    assert db.commit_calls == 0
    assert db.queries == []


def test_ingest_doc_returns_none_when_content_missing():
    db = IngestFakeSession()
    raw_doc = {"_id": "blog/no-content.md", "path": "blog/no-content.md"}

    result = ingest_doc(
        db,
        raw_doc,
        parser=object(),
        parse_post_data_fn=lambda *args, **kwargs: {
            "slug": "blog/no-content",
            "title": "No Content",
            "content": None,
        },
        chunk_text_fn=fake_chunk_text,
    )

    assert result is None
    assert db.added == []
    assert db.commit_calls == 0
    assert db.queries == []


def test_ingest_doc_ingests_and_replaces_existing():
    db = IngestFakeSession()
    raw_doc = {"_id": "doc-123", "path": f"{settings.BLOG_PREFIX}hello.md"}

    def fake_parse(raw, slug, include_content, parser):
        return {
            "content": "Alpha Bravo",
            "slug": "blog/hello",
            "title": "Hello Title",
            "tags": ["tech"],
            "summary": "Summary text",
            "publishedAt": "2024-01-01",
            "updatedAt": "2024-02-01",
        }

    calls = []

    def fake_enhance_content(*, content, title, metadata):
        calls.append({"content": content, "title": title, "metadata": metadata})
        return f"enhanced:{title}:{content}"

    result = ingest_doc(
        db,
        raw_doc,
        parser=object(),
        enhance_content=fake_enhance_content,
        embed_text_fn=lambda text: [0.1, 0.2, 0.3],
        parse_post_data_fn=fake_parse,
        chunk_text_fn=fake_chunk_text,
    )

    assert result == "blog/hello"
    assert len(db.added) == 1
    stored = db.added[0]
    assert isinstance(stored, Doc)
    assert stored.document_id == "doc-123"
    assert stored.slug == "blog/hello"
    assert stored.title == "Hello Title"
    assert stored.content == "Alpha Bravo"
    assert stored.embedding == [0.1, 0.2, 0.3]
    assert stored.doc_metadata["source"] == "blog"
    assert stored.doc_metadata["tags"] == ["tech"]
    assert db.queries[0].filtered is not None
    assert db.queries[0].delete_kwargs == {"synchronize_session": False}
    assert db.committed is True
    assert calls[0]["metadata"]["summary"] == "Summary text"


def test_ingest_doc_sets_kb_source_and_metadata_fields():
    db = IngestFakeSession()
    raw_doc = {"_id": "kb-1", "path": f"{settings.KB_PREFIX}note.md"}

    def parse_fn(raw, slug, include_content, parser):
        return {
            "content": "Knowledge base content",
            "slug": "kb/note",
            "title": "KB Note",
            "tags": ["kb"],
            "summary": "kb summary",
            "publishedAt": "2024-03-01",
            "updatedAt": "2024-03-02",
        }

    result = ingest_doc(
        db,
        raw_doc,
        parser=object(),
        parse_post_data_fn=parse_fn,
        chunk_text_fn=lambda *args, **kwargs: ["kb chunk"],
        enhance_content=lambda **kwargs: kwargs["content"],
        embed_text_fn=lambda _text: [9, 9],
    )

    assert result == "kb/note"
    stored = db.added[0]
    assert stored.doc_metadata["source"] == "kb"
    assert stored.doc_metadata["created_at"] == "2024-03-01"
    assert stored.doc_metadata["updated_at"] == "2024-03-02"
    assert stored.doc_metadata["summary"] == "kb summary"


def test_ingest_doc_uses_id_when_path_missing():
    db = IngestFakeSession()
    raw_doc = {"_id": f"{settings.BLOG_PREFIX}no-path.md"}

    def parse_fn(raw, slug, include_content, parser):
        # slug should come from _id fallback
        return {
            "content": "text",
            "slug": slug,
            "title": "No Path",
        }

    result = ingest_doc(
        db,
        raw_doc,
        parser=object(),
        parse_post_data_fn=parse_fn,
        chunk_text_fn=lambda *args, **kwargs: ["chunk"],
        enhance_content=lambda **kwargs: kwargs["content"],
        embed_text_fn=lambda _text: [1, 2, 3],
    )

    assert result == raw_doc["_id"]
    assert db.added[0].slug == raw_doc["_id"]


def test_ingest_doc_skips_failed_chunks_but_commits_success():
    db = IngestFakeSession()
    raw_doc = {"_id": "doc-456", "path": f"{settings.BLOG_PREFIX}mixed.md"}

    parse_fn = lambda *args, **kwargs: {
        "content": "content that will be chunked",
        "slug": "blog/mixed",
        "title": "Mixed Case",
        "tags": [],
        "summary": None,
    }
    chunker = lambda *_args, **_kwargs: ["ok", "boom"]

    def embed_text_fn(text):
        if text == "boom":
            raise RuntimeError("fail embed")
        return ["vec"]

    result = ingest_doc(
        db,
        raw_doc,
        parser=object(),
        enhance_content=lambda **kwargs: kwargs["content"],
        embed_text_fn=embed_text_fn,
        parse_post_data_fn=parse_fn,
        chunk_text_fn=chunker,
    )

    assert result == "blog/mixed"
    assert len(db.added) == 1
    assert db.added[0].content == "ok"
    assert db.committed is True
    assert db.queries[0].delete_kwargs == {"synchronize_session": False}


def test_ingest_doc_returns_none_when_all_chunks_fail():
    db = IngestFakeSession()
    raw_doc = {"_id": "doc-789", "path": f"{settings.BLOG_PREFIX}fail.md"}

    parse_fn = lambda *args, **kwargs: {
        "content": "anything",
        "slug": "blog/fail",
        "title": "Fail Title",
    }
    chunker = lambda *_args, **_kwargs: ["bad"]

    def embed_fail(_content):
        raise RuntimeError("nope")

    result = ingest_doc(
        db,
        raw_doc,
        parser=object(),
        enhance_content=lambda **kwargs: kwargs["content"],
        embed_text_fn=embed_fail,
        parse_post_data_fn=parse_fn,
        chunk_text_fn=chunker,
    )

    assert result is None
    assert db.added == []
    assert db.commit_calls == 0
    assert db.queries == []


def test_ingest_all_filters_docs_and_calls_ingest():
    docs = {
        "keep-blog": {
            "_id": "blog/keep.md",
            "path": f"{settings.BLOG_PREFIX}keep.md",
            "type": "plain",
        },
        "keep-kb": {
            "_id": "kb/keep.md",
            "path": f"{settings.KB_PREFIX}keep.md",
            "type": "plain",
        },
        "skip-type": {
            "_id": "blog/skip.md",
            "path": f"{settings.BLOG_PREFIX}skip.md",
            "type": "binary",
        },
        "skip-path": {
            "_id": "other/skip.md",
            "path": "other/skip.md",
            "type": "plain",
        },
    }
    parser = type("Parser", (), {"db": FakeCouchDB(docs)})()

    ingested = []

    def ingest_fn(db, doc, parser):
        ingested.append(doc["_id"])

    ingest_all(IngestFakeSession(), parser=parser, ingest_fn=ingest_fn)

    assert ingested == ["blog/keep.md", "kb/keep.md"]


def test_ingest_all_deletes_marked_docs():
    docs = {
        "gone": {"_id": "blog/gone.md", "deleted": True, "type": "plain"},
    }
    parser = type("Parser", (), {"db": FakeCouchDB(docs)})()
    db = IngestFakeSession()

    ingest_all(db, parser=parser)

    assert len(db.queries) == 1
    assert db.queries[0].deleted is True
    assert db.committed is True


def test_chunk_text():
    text = "one two three four five six"
    result = chunk_text(text, embed_model=FakeEmbed())

    assert isinstance(result, list)
    assert all(isinstance(chunk, str) and chunk for chunk in result)


def test_chunk_text_handles_empty_string():
    assert chunk_text("", embed_model=FakeEmbed()) == []
