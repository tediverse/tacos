import pytest
import pycouchdb
import base64

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
