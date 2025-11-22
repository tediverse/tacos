from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import images
from app.services.image_service import get_content_type_from_filename
from tests.conftest import FakeCouchDB


def build_client(db, parser):
    app = FastAPI()
    app.dependency_overrides[images.get_couch] = lambda: (db, parser)
    app.include_router(images.router)
    return TestClient(app)


def test_get_image_serves_bytes_and_headers():
    data = b"DATA"
    db = FakeCouchDB({"img/foo.png": {"size": len(data)}}, track_calls=True)
    parser = SimpleNamespace(get_binary_content=lambda doc: data)
    client = build_client(db, parser)

    res = client.get("/images/foo.png")

    assert res.status_code == 200
    assert res.content == data
    assert res.headers["content-type"] == get_content_type_from_filename("foo.png")
    assert res.headers["Content-Length"] == str(len(data))
    assert res.headers["Accept-Ranges"] == "bytes"
    assert db.calls == ["img/foo.png"]


def test_get_image_returns_404_when_missing():
    db = FakeCouchDB({})
    parser = SimpleNamespace(get_binary_content=lambda doc: None)
    client = build_client(db, parser)

    res = client.get("/images/missing.png")

    assert res.status_code == 404
