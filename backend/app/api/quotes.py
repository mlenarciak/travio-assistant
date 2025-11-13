"""Quote placement and delivery endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, status

from backend.app.api.activity import record_activity
from backend.app.api.deps import get_activity_log, get_travio_client
from backend.app.models.booking import PlaceReservationRequest, QuoteDeliveryRequest
from backend.app.services.travio_client import TravioAPIError

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


@router.post("/place/{cart_id}")
async def place_quote(
    payload: PlaceReservationRequest,
    cart_id: str = Path(...),
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Place a reservation or quote using cart contents."""
    body = payload.to_payload()
    try:
        response = await client.place_reservation(cart_id, body)
    except TravioAPIError as exc:
        detail = "Failed to place reservation"
        if isinstance(exc.payload, str):
            detail = f"{detail}: {exc.payload}"
        record_activity(
            activity_log,
            action="quote.place",
            method="POST",
            endpoint=f"/booking/place/{cart_id}",
            payload=body,
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="quote.place",
            method="POST",
            endpoint=f"/booking/place/{cart_id}",
            payload=body,
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected reservation error",
        ) from exc

    record_activity(
        activity_log,
        action="quote.place",
        method="POST",
        endpoint=f"/booking/place/{cart_id}",
        payload=body,
        status="success",
        response=response,
    )
    return response


@router.post("/send/{reservation_id}")
async def send_quote(
    payload: QuoteDeliveryRequest,
    reservation_id: int = Path(..., ge=0),
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Send reservation quote via Travio print tools."""
    body = payload.to_payload()
    try:
        response = await client.send_quote(reservation_id, body)
    except TravioAPIError as exc:
        detail = "Failed to send quote"
        if isinstance(exc.payload, str):
            detail = f"{detail}: {exc.payload}"
        record_activity(
            activity_log,
            action="quote.send",
            method="POST",
            endpoint=f"/tools/print/reservation/{reservation_id}",
            payload=body,
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="quote.send",
            method="POST",
            endpoint=f"/tools/print/reservation/{reservation_id}",
            payload=body,
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected quote delivery error",
        ) from exc

    record_activity(
        activity_log,
        action="quote.send",
        method="POST",
        endpoint=f"/tools/print/reservation/{reservation_id}",
        payload=body,
        status="success",
        response=response,
    )
    return response
