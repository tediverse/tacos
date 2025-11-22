from fastapi import Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN

from app.settings import Settings, settings

API_KEY_NAME = "X-TACOS-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_settings() -> Settings:
    """Small wrapper to allow dependency overrides in tests."""
    return settings


def get_api_key(
    api_key_header: str = Security(api_key_header),
    current_settings: Settings = Depends(get_settings),
):
    if api_key_header == current_settings.TACOS_API_KEY:
        return api_key_header
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN,
        detail="Could not validate API key",
    )
