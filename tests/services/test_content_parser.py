import base64
from unittest.mock import patch

import pycouchdb
import pytest

from app.services.content_parser import ContentParser


class MockDB:
    """Minimal CouchDB stand-in returning preloaded docs by id."""

    def __init__(self, docs: dict[str, dict]):
        self.docs = docs

    def get(self, doc_id: str) -> dict:
        if doc_id not in self.docs:
            raise pycouchdb.exceptions.NotFound(doc_id)
        return self.docs[doc_id]


def test_get_markdown_content_concatenates_blog_chunks():
    parent = {
        "_id": "blog:2024/intro-to-rag",
        "type": "plain",
        "children": ["chunk-1", "chunk-2", "chunk-3"],
    }
    docs = {
        "chunk-1": {"type": "leaf", "data": "# Intro\n"},
        "chunk-2": {"type": "leaf", "data": "RAG pipelines are useful because "},
        "chunk-3": {"type": "leaf", "data": "they blend search with LLMs."},
    }

    parser = ContentParser(MockDB(docs))

    result = parser.get_markdown_content(parent)

    assert (
        result
        == "# Intro\nRAG pipelines are useful because they blend search with LLMs."
    )


def test_get_binary_content_decodes_base64_chunks():
    parent = {
        "_id": "kb:images/logo.png",
        "type": "plain",
        "children": ["img-1", "img-2"],
    }
    docs = {
        "img-1": {"type": "leaf", "data": base64.b64encode(b"\x89PNG").decode()},
        "img-2": {"type": "leaf", "data": base64.b64encode(b"\x0d\x0aEND").decode()},
    }

    parser = ContentParser(MockDB(docs))

    result = parser.get_binary_content(parent)

    assert result == b"\x89PNG\x0d\x0aEND"


def test_get_markdown_content_skips_missing_children():
    parent = {
        "_id": "blog:2024/partials",
        "type": "plain",
        "children": ["chunk-1", "missing-child", "chunk-2"],
    }
    docs = {
        "chunk-1": {"type": "leaf", "data": "alpha "},
        "chunk-2": {"type": "leaf", "data": "omega"},
    }

    parser = ContentParser(MockDB(docs))

    result = parser.get_markdown_content(parent)

    assert result == "alpha omega"


def test_get_markdown_content_returns_empty_when_no_children():
    parent = {"_id": "blog:empty", "type": "plain", "children": []}

    parser = ContentParser(MockDB({}))

    result = parser.get_markdown_content(parent)

    assert result == ""


def test_get_binary_content_skips_bad_base64_chunk():
    parent = {"_id": "kb:img/partial", "type": "plain", "children": ["good", "bad"]}
    docs = {
        "good": {"type": "leaf", "data": base64.b64encode(b"OK").decode()},
        "bad": {"type": "leaf", "data": "!!not-base64!!"},
    }
    parser = ContentParser(MockDB(docs))

    result = parser.get_binary_content(parent)

    assert result == b"OK"


def test_get_markdown_content_skips_erroring_child():
    class ErrorDB(MockDB):
        def get(self, doc_id: str) -> dict:
            if doc_id == "boom":
                raise RuntimeError("transient error")
            return super().get(doc_id)

    parent = {"_id": "blog:errors", "type": "plain", "children": ["ok", "boom", "ok2"]}
    docs = {
        "ok": {"type": "leaf", "data": "first "},
        "ok2": {"type": "leaf", "data": "last"},
    }

    parser = ContentParser(ErrorDB(docs))

    result = parser.get_markdown_content(parent)

    assert result == "first last"


def test_get_markdown_content_decodes_bytes_leaf():
    parent = {"_id": "blog:bytes", "type": "plain", "children": ["b1"]}
    docs = {"b1": {"type": "leaf", "data": b"hello \xffworld"}}
    parser = ContentParser(MockDB(docs))

    result = parser.get_markdown_content(parent)

    assert result == "hello world"  # \xff is dropped


def test_get_markdown_content_decodes_bytes_from_raw():
    parser = ContentParser(MockDB({}))
    with patch.object(parser, "_get_raw_content", return_value=b"hi \xffthere"):
        result = parser.get_markdown_content({})
    assert result == "hi there"


def test_get_markdown_ignores_non_leaf_child():
    parent = {"_id": "blog:meta", "type": "plain", "children": ["meta", "leaf"]}
    docs = {
        "meta": {"type": "meta", "info": "skip me"},
        "leaf": {"type": "leaf", "data": "kept"},
    }
    parser = ContentParser(MockDB(docs))
    assert parser.get_markdown_content(parent) == "kept"
