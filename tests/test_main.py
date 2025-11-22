from fastapi.testclient import TestClient

import app.main as main_module
from app import dependencies as deps
from app.main import app
from app.routers import rag as rag_router
from app.schemas.blog import PostSummary
from app.security import API_KEY_NAME
from app.settings import Settings
from tests.conftest import FakePostsService


class DummyThread:
    def __init__(self):
        self.join_called = False
        self.join_timeout = None

    def join(self, timeout=None):
        self.join_called = True
        self.join_timeout = timeout


def test_root_endpoint_runs_lifespan(monkeypatch):
    thread = DummyThread()
    started = []
    stopped = []

    def fake_start_listener():
        started.append(True)
        return thread

    def fake_stop_listener():
        stopped.append(True)

    monkeypatch.setattr(main_module, "start_listener", fake_start_listener)
    monkeypatch.setattr(main_module, "stop_listener", fake_stop_listener)

    with TestClient(app) as client:
        res = client.get("/")
        assert res.status_code == 200
        assert res.json() == {"message": "TACOS API is running"}

    assert started == [True]
    assert stopped == [True]
    assert thread.join_called is True
    assert thread.join_timeout == 10


def test_posts_routes_enforce_api_key(monkeypatch):
    monkeypatch.setattr(main_module, "start_listener", lambda: DummyThread())
    monkeypatch.setattr(main_module, "stop_listener", lambda: None)

    import app.security as security

    monkeypatch.setattr(security, "settings", Settings(TACOS_API_KEY="secret"))

    fake_post = PostSummary(
        id="blog/hello.md",
        slug="hello",
        title="Hello World",
        summary=None,
        image=None,
        publishedAt=None,
        updatedAt=None,
        tags=[],
        readingTime="1 min",
        draft=False,
        coAuthors=[],
        views=0,
    )

    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[deps.get_posts_service] = lambda: FakePostsService(
        list_posts_return=[fake_post]
    )
    try:
        with TestClient(app) as client:
            res = client.get("/posts")
            assert res.status_code == 403

            res = client.get("/posts", headers={API_KEY_NAME: "secret"})
            assert res.status_code == 200
            assert res.json() == [fake_post.dict()]
    finally:
        app.dependency_overrides = original_overrides


def test_rag_routes_require_api_key(monkeypatch):
    monkeypatch.setattr(main_module, "start_listener", lambda: DummyThread())
    monkeypatch.setattr(main_module, "stop_listener", lambda: None)

    import app.security as security

    monkeypatch.setattr(security, "settings", Settings(TACOS_API_KEY="secret"))

    class FakeRagService:
        def get_relevant_documents(self, query: str, limit: int, threshold: float):
            return []

    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[rag_router.get_rag_service] = lambda: FakeRagService()
    try:
        with TestClient(app) as client:
            res = client.get("/query", params={"q": "hi"})
            assert res.status_code == 403

            res = client.get(
                "/query", params={"q": "hi"}, headers={API_KEY_NAME: "secret"}
            )
            assert res.status_code == 200
            assert res.json() == []
    finally:
        app.dependency_overrides = original_overrides
