"""Authentication-related endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.activity import record_activity
from backend.app.api.deps import get_activity_log, get_travio_client
from backend.app.services.travio_client import TravioAPIError

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token")
async def issue_token(
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Fetch a bearer token using configured credentials."""
    try:
        token = await client.authenticate()
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="authenticate",
            method="POST",
            endpoint="/auth",
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Travio authentication failed",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="authenticate",
            method="POST",
            endpoint="/auth",
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected authentication error",
        ) from exc

    record_activity(
        activity_log,
        action="authenticate",
        method="POST",
        endpoint="/auth",
        status="success",
        response={"token": "***redacted***"},
    )
    return {"token": token}


@router.get("/profile")
async def get_profile(
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Return profile data for current token."""
    try:
        profile = await client.get_profile()
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="profile",
            method="GET",
            endpoint="/profile",
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not fetch profile information",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="profile",
            method="GET",
            endpoint="/profile",
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected profile retrieval error",
        ) from exc

    record_activity(
        activity_log,
        action="profile",
        method="GET",
        endpoint="/profile",
        status="success",
        response=profile,
    )
    return profile


@router.post("/login")
async def login(
    credentials: Dict[str, Any],
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Authenticate Travio user credentials and return enriched token."""
    try:
        result = await client.login(credentials)
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="login",
            method="POST",
            endpoint="/login",
            payload=credentials,
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Travio login failed",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="login",
            method="POST",
            endpoint="/login",
            payload=credentials,
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected Travio login error",
        ) from exc

    record_activity(
        activity_log,
        action="login",
        method="POST",
        endpoint="/login",
        payload={"username": credentials.get("username")},
        status="success",
        response={"token": "***redacted***"},
    )
    return result
