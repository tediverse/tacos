from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import image_service
from tests.conftest import FakeCouchDB


def test_get_image_happy_path_returns_bytes_and_content_type():
    fake_db = FakeCouchDB({"img.png": {"size": 4}}, track_calls=True)
    fake_parser = SimpleNamespace(get_binary_content=Mock(return_value=b"DATA"))

    data, content_type = image_service.get_image_from_couchdb(
        "img.png", db=fake_db, parser=fake_parser
    )

    assert data == b"DATA"
    assert content_type == "image/png"
    assert fake_db.calls == ["img.png"]


def test_get_image_tries_urlencoded_when_not_found():
    fake_db = FakeCouchDB({"img%20space.png": {"size": 4}}, track_calls=True)
    fake_parser = SimpleNamespace(get_binary_content=Mock(return_value=b"DATA"))

    data, content_type = image_service.get_image_from_couchdb(
        "img space.png", db=fake_db, parser=fake_parser
    )

    assert data == b"DATA"
    assert content_type == "image/png"
    assert fake_db.calls == ["img space.png", "img%20space.png"]


def test_get_image_returns_none_when_parser_empty():
    fake_db = FakeCouchDB({"img.png": {"size": 1}})
    fake_parser = SimpleNamespace(get_binary_content=Mock(return_value=None))

    data, content_type = image_service.get_image_from_couchdb(
        "img.png", db=fake_db, parser=fake_parser
    )

    assert data is None
    assert content_type is None


def test_get_image_returns_none_on_size_mismatch():
    fake_db = FakeCouchDB({"img.png": {"size": 10}})
    fake_parser = SimpleNamespace(get_binary_content=Mock(return_value=b"SHORT"))

    data, content_type = image_service.get_image_from_couchdb(
        "img.png", db=fake_db, parser=fake_parser
    )

    assert data is None
    assert content_type is None


def test_get_image_returns_none_when_doc_not_found():
    fake_db = FakeCouchDB({})
    fake_parser = SimpleNamespace(get_binary_content=Mock(return_value=b"DATA"))

    data, content_type = image_service.get_image_from_couchdb(
        "missing.png", db=fake_db, parser=fake_parser
    )

    assert data is None
    assert content_type is None


def test_process_image_references_rewrites_obsidian_and_absolute():
    content = "See ![[pic.png]] and ![alt](/img/photo.jpg)"
    result = image_service.process_image_references(
        content, base_url="http://localhost:8000/images"
    )

    assert (
        result
        == "See ![](http://localhost:8000/images/pic.png) and ![alt](http://localhost:8000/images/photo.jpg)"
    )


@pytest.mark.parametrize(
    ("name", "ctype"),
    [
        ("photo.JPG", "image/jpeg"),
        ("photo.jpeg", "image/jpeg"),
        ("logo.PNG", "image/png"),
        ("anim.gif", "image/gif"),
        ("vector.SVG", "image/svg+xml"),
        ("pic.webp", "image/webp"),
        ("unknown.bin", "application/octet-stream"),
    ],
)
def test_get_content_type_from_filename(name, ctype):
    assert image_service.get_content_type_from_filename(name) == ctype


def test_get_image_handles_unexpected_exception():
    fake_db = FakeCouchDB({"img.png": {"size": 4}})

    def boom(doc):
        raise RuntimeError("kaboom")

    fake_parser = SimpleNamespace(get_binary_content=boom)

    data, content_type = image_service.get_image_from_couchdb(
        "img.png", db=fake_db, parser=fake_parser
    )

    assert data is None
    assert content_type is None
