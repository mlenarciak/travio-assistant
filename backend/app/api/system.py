"""System utilities endpoints."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_activity_log, get_app_settings
from backend.app.config import Settings

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
async def health(
    settings: Settings = Depends(get_app_settings),
) -> Dict[str, Any]:
    """Basic health probe for Streamlit frontend."""
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "use_mock_data": settings.use_mock_data,
        "language": settings.travio_language,
    }


@router.get("/activity")
async def activity_log(
    activity_log=Depends(get_activity_log),
    limit: Optional[int] = Query(default=None, ge=1),
) -> List[Dict[str, Any]]:
    """Return recorded activity entries."""
    if limit is None or limit >= len(activity_log):
        return list(activity_log)
    return list(activity_log)[-limit:]


@router.delete("/activity")
async def clear_activity(
    activity_log=Depends(get_activity_log),
) -> Dict[str, str]:
    """Purge recorded activity."""
    activity_log.clear()
    return {"status": "cleared"}

