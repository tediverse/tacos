import time

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import dependencies as deps
from app.routers import posts
from tests.conftest import FakePostsService


class FakeCouch:
    def __init__(self, doc):
        self.doc = doc

    def get(self, doc_id):
        key = doc_id.replace("%2F", "/")
        if key == self.doc["_id"]:
            return self.doc
        raise Exception("not found")

    def all(self, include_docs=True):
        return [{"doc": self.doc}] if include_docs else [self.doc]


def make_app(fake_service: FakePostsService):
    app = FastAPI()
    app.dependency_overrides[deps.get_posts_service] = lambda: fake_service
    app.include_router(posts.router)
    return app


def test_list_posts_returns_sorted_posts_with_views():
    fake_posts = [
        {
            "id": "2",
            "slug": "second",
            "title": "Second",
            "views": 1,
            "tags": [],
            "draft": False,
        },
        {
            "id": "1",
            "slug": "first",
            "title": "First",
            "views": 5,
            "tags": [],
            "draft": False,
        },
    ]
    app = make_app(FakePostsService(list_posts_return=fake_posts))
    client = TestClient(app)

    res = client.get("/posts")
    assert res.status_code == 200
    body = res.json()
    assert [p["slug"] for p in body] == ["second", "first"]
    assert body[1]["views"] == 5


def test_get_post_returns_404_when_missing():
    app = make_app(FakePostsService(get_post_return=None))
    client = TestClient(app)

    res = client.get("/posts/missing")
    assert res.status_code == 404


def test_get_post_success():
    app = make_app(
        FakePostsService(
            get_post_return={
                "id": "1",
                "slug": "hello",
                "title": "Hello",
                "summary": None,
                "image": None,
                "publishedAt": None,
                "updatedAt": None,
                "tags": [],
                "readingTime": "1 min",
                "draft": False,
                "coAuthors": [],
                "views": 3,
                "content": "hi",
            }
        )
    )
    client = TestClient(app)

    res = client.get("/posts/hello")
    assert res.status_code == 200
    assert res.json()["slug"] == "hello"


def test_list_posts_passes_through_http_exception():
    class BoomService(FakePostsService):
        def list_posts(self):
            raise HTTPException(status_code=418, detail="teapot")

    app = make_app(BoomService())
    client = TestClient(app)

    res = client.get("/posts")
    assert res.status_code == 418
    assert res.json()["detail"] == "teapot"


def test_list_posts_returns_500_on_unexpected_error():
    class BoomService(FakePostsService):
        def list_posts(self):
            raise RuntimeError("boom")

    app = make_app(BoomService())
    client = TestClient(app)

    res = client.get("/posts")
    assert res.status_code == 500
    assert res.json()["detail"] == "Failed to retrieve posts"


def test_get_post_returns_500_on_unexpected_error():
    class BoomService(FakePostsService):
        def get_post(self, slug: str):
            raise RuntimeError("boom")

    app = make_app(BoomService())
    client = TestClient(app)

    res = client.get("/posts/any")
    assert res.status_code == 500
    assert res.json()["detail"] == "Failed to retrieve post"


def test_increment_views_happy_path():
    app = FastAPI()
    posts._recent_view_hits.clear()
    fake_posts_service = FakePostsService()
    fake_view_service_calls = []

    class FakeViewService:
        def increment_view(self, slug):
            fake_view_service_calls.append(slug)
            return 7

        def get_view_count(self, slug):
            return 0

    doc_id = f"{posts.config.BLOG_PREFIX}slug-1.md"
    fake_couch = FakeCouch({"_id": doc_id, "path": doc_id, "type": "plain"})

    deps_overrides = {
        deps.get_posts_service: lambda: fake_posts_service,
        deps.get_couch: lambda: (fake_couch, None),
        deps.get_db: lambda: object(),
        deps.get_post_view_service: lambda: FakeViewService(),
    }
    for dep, override in deps_overrides.items():
        app.dependency_overrides[dep] = override
    app.include_router(posts.router)
    client = TestClient(app)

    res = client.post("/views/slug-1")
    assert res.status_code == 200
    assert res.json()["views"] == 7
    assert fake_view_service_calls == ["slug-1"]


def test_increment_views_returns_404_when_missing_doc():
    app = FastAPI()
    app.dependency_overrides[deps.get_posts_service] = lambda: FakePostsService()
    app.dependency_overrides[deps.get_db] = lambda: object()
    app.dependency_overrides[deps.get_post_view_service] = lambda: object()
    app.dependency_overrides[deps.get_couch] = lambda: (
        type(
            "Couch",
            (),
            {"get": lambda self, doc_id: {}, "all": lambda self, include_docs=True: []},
        )(),
        None,
    )
    app.include_router(posts.router)
    client = TestClient(app)

    res = client.post("/views/missing")
    assert res.status_code == 404


def test_increment_views_skips_when_recent():
    app = FastAPI()
    posts._recent_view_hits.clear()
    fake_calls = []

    class FakeViewService:
        def increment_view(self, slug):
            fake_calls.append(slug)
            return 5

        def get_view_count(self, slug):
            return 2

    doc_id = f"{posts.config.BLOG_PREFIX}slug.md"
    fake_couch = FakeCouch({"_id": doc_id, "path": doc_id, "type": "plain"})

    deps_overrides = {
        deps.get_posts_service: lambda: FakePostsService(),
        deps.get_couch: lambda: (fake_couch, None),
        deps.get_db: lambda: object(),
        deps.get_post_view_service: lambda: FakeViewService(),
    }
    for dep, override in deps_overrides.items():
        app.dependency_overrides[dep] = override
    app.include_router(posts.router)
    client = TestClient(app)

    # Prime cache
    posts._recent_view_hits["testclient:slug"] = time.monotonic()

    res = client.post("/views/slug", headers={"X-Forwarded-For": "test"})
    assert res.status_code == 200
    assert res.json()["views"] == 2  # returned get_view_count
    assert fake_calls == []


def test_increment_views_returns_500_on_error():
    app = FastAPI()
    posts._recent_view_hits.clear()

    class BoomViewService:
        def increment_view(self, slug):
            raise RuntimeError("boom")

        def get_view_count(self, slug):
            return 0

    doc_id = f"{posts.config.BLOG_PREFIX}slug.md"
    fake_couch = FakeCouch({"_id": doc_id, "path": doc_id, "type": "plain"})

    app.dependency_overrides[deps.get_posts_service] = lambda: FakePostsService()
    app.dependency_overrides[deps.get_couch] = lambda: (fake_couch, None)
    app.dependency_overrides[deps.get_db] = lambda: object()
    app.dependency_overrides[deps.get_post_view_service] = lambda: BoomViewService()
    app.include_router(posts.router)
    client = TestClient(app)

    res = client.post("/views/slug")
    assert res.status_code == 500
    assert res.json()["detail"] == "Failed to record view"


def test_is_valid_blog_doc_helper():
    valid = {"type": "plain", "path": "blog/x", "deleted": False}
    invalid = {"type": "leaf", "path": "blog/x"}
    assert posts._is_valid_blog_doc(valid) is True
    assert posts._is_valid_blog_doc(invalid) is False
    assert posts._is_valid_blog_doc(None) is False


def test_get_blog_doc_by_slug_logs_warning_and_falls_back(caplog):
    doc_id = f"{posts.config.BLOG_PREFIX}slug.md"

    class ErrorCouch(FakeCouch):
        def get(self, doc_id):
            raise RuntimeError("boom")

    couch = ErrorCouch({"_id": doc_id, "path": doc_id, "type": "plain"})

    with caplog.at_level("WARNING"):
        doc = posts._get_blog_doc_by_slug("slug", couch)

    assert doc and doc["_id"] == doc_id
    assert any("Direct fetch failed" in rec.message for rec in caplog.records)


def test_prune_view_cache_removes_stale_entries():
    now = time.monotonic()
    posts._recent_view_hits.clear()
    posts._recent_view_hits["old"] = now - posts.VIEW_GUARD_TTL_SECONDS - 1
    posts._recent_view_hits["fresh"] = now

    posts._prune_view_cache(now)

    assert "old" not in posts._recent_view_hits
    assert "fresh" in posts._recent_view_hits


def test_should_skip_increment_triggers_prune_when_large_cache():
    posts._recent_view_hits.clear()
    now = time.monotonic()
    for i in range(513):
        posts._recent_view_hits[f"ip{i}:slug"] = now - posts.VIEW_GUARD_TTL_SECONDS - 1

    result = posts._should_skip_increment("newip", "slug")

    assert result is False
    assert len(posts._recent_view_hits) <= 513  # prune ran
