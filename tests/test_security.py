import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.security import API_KEY_NAME, get_api_key, get_settings
from app.settings import Settings


def test_get_api_key_accepts_valid_key():
    settings = Settings(TACOS_API_KEY="secret")
    assert get_api_key("secret", settings) == "secret"


def test_get_api_key_rejects_invalid_key():
    settings = Settings(TACOS_API_KEY="secret")
    with pytest.raises(HTTPException) as exc:
        get_api_key("wrong", settings)
    assert exc.value.status_code == 403


def test_get_api_key_rejects_missing_header():
    settings = Settings(TACOS_API_KEY="secret")
    with pytest.raises(HTTPException) as exc:
        get_api_key(None, settings)
    assert exc.value.status_code == 403


def test_dependency_in_route_accepts_valid_key():
    settings = Settings(TACOS_API_KEY="secret")

    app = FastAPI()

    @app.get("/secure")
    def secure(key=Depends(get_api_key)):
        return {"ok": True}

    app.dependency_overrides[get_settings] = lambda: settings

    client = TestClient(app)
    res = client.get("/secure", headers={API_KEY_NAME: "secret"})
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_dependency_in_route_rejects_invalid_key():
    settings = Settings(TACOS_API_KEY="secret")

    app = FastAPI()

    @app.get("/secure")
    def secure(key=Depends(get_api_key)):
        return {"ok": True}

    app.dependency_overrides[get_settings] = lambda: settings

    client = TestClient(app)
    res = client.get("/secure", headers={API_KEY_NAME: "wrong"})
    assert res.status_code == 403
