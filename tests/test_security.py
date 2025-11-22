import asyncio

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.security import API_KEY_NAME, get_api_key
from app.settings import Settings


def test_get_api_key_accepts_valid_key(monkeypatch):
    settings = Settings(TACOS_API_KEY="secret")
    # patch the function's module-level settings reference
    monkeypatch.setattr("app.security.settings", settings)

    result = asyncio.run(get_api_key(api_key_header="secret"))
    assert result == "secret"


def test_get_api_key_rejects_invalid_key(monkeypatch):
    settings = Settings(TACOS_API_KEY="secret")
    monkeypatch.setattr("app.security.settings", settings)

    with pytest.raises(Exception):
        asyncio.run(get_api_key(api_key_header="wrong"))


def test_get_api_key_rejects_missing_header(monkeypatch):
    settings = Settings(TACOS_API_KEY="secret")
    monkeypatch.setattr("app.security.settings", settings)

    with pytest.raises(Exception):
        asyncio.run(get_api_key(api_key_header=None))  # type: ignore


def test_dependency_in_route_accepts_valid_key(monkeypatch):
    settings = Settings(TACOS_API_KEY="secret")
    monkeypatch.setattr("app.security.settings", settings)

    app = FastAPI()

    @app.get("/secure")
    async def secure(key=Depends(get_api_key)):
        return {"ok": True}

    client = TestClient(app)
    res = client.get("/secure", headers={API_KEY_NAME: "secret"})
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_dependency_in_route_rejects_invalid_key(monkeypatch):
    settings = Settings(TACOS_API_KEY="secret")
    monkeypatch.setattr("app.security.settings", settings)

    app = FastAPI()

    @app.get("/secure")
    async def secure(key=Depends(get_api_key)):
        return {"ok": True}

    client = TestClient(app)
    res = client.get("/secure", headers={API_KEY_NAME: "wrong"})
    assert res.status_code == 403
