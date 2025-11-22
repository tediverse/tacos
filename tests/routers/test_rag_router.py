import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import rag


def build_client(rag_service):
    app = FastAPI()
    app.dependency_overrides[rag.get_rag_service] = lambda: rag_service
    app.include_router(rag.router)
    return TestClient(app)


def test_prompt_requires_messages():
    client = build_client(SimpleNamespace(stream_chat_response=None))

    res = client.post("/prompt", json={"messages": []})

    assert res.status_code == 400
    assert res.json()["detail"] == "No messages provided"


def test_prompt_streams_response():
    async def fake_stream(messages, limit, threshold):
        yield "hello"

    rag_service = SimpleNamespace(stream_chat_response=fake_stream)
    client = build_client(rag_service)

    res = client.post(
        "/prompt",
        json={"messages": [{"role": "user", "content": "Hi"}]},
        params={"limit": 2, "threshold": 0.5},
    )

    assert res.status_code == 200
    assert res.text == "hello"


def test_query_returns_debug_truncated():
    rag_service = SimpleNamespace(
        get_relevant_documents=lambda query, limit, threshold: [
            SimpleNamespace(
                id=uuid.uuid4(), title="T", content="x" * 120, similarity=0.9
            )
        ]
    )
    client = build_client(rag_service)

    res = client.get("/query", params={"q": "hi", "debug": True})

    assert res.status_code == 200
    body = res.json()
    assert body[0]["content"].endswith("...")
    assert len(body[0]["content"]) == 103  # 100 chars + ellipsis


def test_query_returns_normal_results():
    doc = SimpleNamespace(id=uuid.uuid4(), title="T", content="short", similarity=0.8)
    rag_service = SimpleNamespace(
        get_relevant_documents=lambda query, limit, threshold: [doc]
    )
    client = build_client(rag_service)

    res = client.get("/query", params={"q": "hi"})

    assert res.status_code == 200
    body = res.json()
    assert body[0]["title"] == "T"
    assert body[0]["similarity"] == 0.8


def test_update_portfolio_content_returns_stats():
    rag_service = SimpleNamespace(
        update_portfolio_content=lambda content: {
            "processed": 1,
            "updated": 1,
            "skipped": 0,
            "errors": [],
        }
    )
    client = build_client(rag_service)

    request = {
        "timestamp": "now",
        "content": [
            {"slug": "s", "title": "t", "content": "c", "metadata": {"a": 1}}
        ],
    }
    res = client.post("/update", json=request)

    assert res.status_code == 200
    assert res.json() == {"processed": 1, "updated": 1, "skipped": 0, "errors": []}


def test_reingest_calls_ingest_all():
    calls = {}

    def fake_ingest_all(db, parser):
        calls["ingest_all"] = (db, parser)

    app = FastAPI()
    app.dependency_overrides[rag.get_db] = lambda: "db"
    app.dependency_overrides[rag.get_couch] = lambda: ("db", "parser")
    app.dependency_overrides[rag.get_ingest_all] = lambda: fake_ingest_all
    app.include_router(rag.router)
    client = TestClient(app)

    res = client.post("/reingest")

    assert res.status_code == 200
    assert calls["ingest_all"] == ("db", "parser")
