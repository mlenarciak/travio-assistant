"""FastAPI dependency helpers."""

from typing import Any, Dict, List

from fastapi import Depends, Request

from backend.app.config import Settings, get_settings


def get_app_settings() -> Settings:
    """Provide application settings."""
    return get_settings()


def get_travio_client(
    request: Request, settings: Settings = Depends(get_app_settings)
) -> Any:
    """Retrieve Travio client from app state."""
    client = request.app.state.travio_client  # type: ignore[attr-defined]
    return client


def get_activity_log(request: Request) -> List[Dict[str, Any]]:
    """Return activity log stored in app state."""
    log: List[Dict[str, Any]] = request.app.state.activity_log  # type: ignore[attr-defined]
    return log
