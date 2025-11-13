"""Entrypoint for Travio assistant FastAPI backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List

from fastapi import FastAPI
from loguru import logger

from backend.app.api import auth, booking, crm, quotes, system
from backend.app.config import Settings, get_settings
from backend.app.services.mock_client import MockTravioClient
from backend.app.services.travio_client import TravioClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup/shutdown routines."""
    settings: Settings = get_settings()
    client: TravioClient | MockTravioClient
    if settings.use_mock_data:
        client = MockTravioClient(settings)
    else:
        client = TravioClient(settings)
    activity_log: List[Dict[str, Any]] = []

    app.state.settings = settings  # type: ignore[attr-defined]
    app.state.travio_client = client  # type: ignore[attr-defined]
    app.state.activity_log = activity_log  # type: ignore[attr-defined]

    logger.info(
        "Starting Travio assistant backend (mock mode = {mock})",
        mock=settings.use_mock_data,
    )
    try:
        yield
    finally:
        await client.close()
        logger.info("Travio assistant backend shutdown complete")


app = FastAPI(
    title="Travio Assistant Backend",
    version="0.1.0",
    lifespan=lifespan,
)


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(crm.router)
app.include_router(booking.router)
app.include_router(quotes.router)


@app.get("/")
async def root() -> Dict[str, str]:
    """Simple root endpoint for manual verification."""
    return {"message": "Travio assistant backend is running"}
