from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import dependencies as deps
from app.routers import posts


class FakePostsService:
    def __init__(self, list_posts_return=None, get_post_return=None):
        self._list_posts_return = list_posts_return or []
        self._get_post_return = get_post_return

    def list_posts(self):
        return self._list_posts_return

    def get_post(self, slug: str):
        return self._get_post_return


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
