"""Booking and property search endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, status

from backend.app.api.activity import record_activity
from backend.app.api.deps import get_activity_log, get_travio_client
from backend.app.models.booking import (
    BookingPicksRequest,
    BookingResultsRequest,
    BookingSearchRequest,
    CartMutationRequest,
)
from backend.app.services.travio_client import TravioAPIError

router = APIRouter(prefix="/api/booking", tags=["booking"])


@router.post("/search")
async def booking_search(
    payload: BookingSearchRequest,
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Execute Travio booking search."""
    body = payload.to_payload()
    try:
        response = await client.booking_search(body)
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="booking.search",
            method="POST",
            endpoint="/booking/search",
            payload=body,
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        detail = "Booking search failed"
        if isinstance(exc.payload, str):
            detail = f"{detail}: {exc.payload}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="booking.search",
            method="POST",
            endpoint="/booking/search",
            payload=body,
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected booking search error",
        ) from exc

    record_activity(
        activity_log,
        action="booking.search",
        method="POST",
        endpoint="/booking/search",
        payload=body,
        status="success",
        response=response,
    )
    return response


@router.post("/results")
async def booking_results(
    payload: BookingResultsRequest,
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Retrieve subsequent booking results pages."""
    body = payload.to_payload()
    try:
        response = await client.booking_results(body)
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="booking.results",
            method="POST",
            endpoint="/booking/results",
            payload=body,
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        detail = "Booking results fetch failed"
        if isinstance(exc.payload, str):
            detail = f"{detail}: {exc.payload}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="booking.results",
            method="POST",
            endpoint="/booking/results",
            payload=body,
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected booking results error",
        ) from exc

    record_activity(
        activity_log,
        action="booking.results",
        method="POST",
        endpoint="/booking/results",
        payload=body,
        status="success",
        response=response,
    )
    return response


@router.post("/picks")
async def booking_picks(
    payload: BookingPicksRequest,
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Submit picks for booking flow."""
    body = payload.to_payload()
    try:
        response = await client.booking_picks(body)
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="booking.picks",
            method="POST",
            endpoint="/booking/picks",
            payload=body,
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        detail = "Booking picks failed"
        if isinstance(exc.payload, str):
            detail = f"{detail}: {exc.payload}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="booking.picks",
            method="POST",
            endpoint="/booking/picks",
            payload=body,
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected booking picks error",
        ) from exc

    record_activity(
        activity_log,
        action="booking.picks",
        method="POST",
        endpoint="/booking/picks",
        payload=body,
        status="success",
        response=response,
    )
    return response


@router.put("/cart")
async def add_to_cart(
    payload: CartMutationRequest,
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Add selection to cart."""
    body = payload.to_payload()
    try:
        response = await client.cart_add(body)
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="booking.cart_add",
            method="PUT",
            endpoint="/booking/cart",
            payload=body,
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        detail = "Failed to add to cart"
        if isinstance(exc.payload, str):
            detail = f"{detail}: {exc.payload}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="booking.cart_add",
            method="PUT",
            endpoint="/booking/cart",
            payload=body,
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected cart add error",
        ) from exc

    record_activity(
        activity_log,
        action="booking.cart_add",
        method="PUT",
        endpoint="/booking/cart",
        payload=body,
        status="success",
        response=response,
    )
    return response


@router.get("/cart/{cart_id}")
async def get_cart(
    cart_id: str = Path(...),
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Retrieve cart details."""
    try:
        response = await client.cart_get(cart_id)
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="booking.cart_get",
            method="GET",
            endpoint=f"/booking/cart/{cart_id}",
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="booking.cart_get",
            method="GET",
            endpoint=f"/booking/cart/{cart_id}",
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected cart retrieval error",
        ) from exc

    record_activity(
        activity_log,
        action="booking.cart_get",
        method="GET",
        endpoint=f"/booking/cart/{cart_id}",
        status="success",
        response=response,
    )
    return response


@router.delete("/cart")
async def remove_from_cart(
    payload: CartMutationRequest,
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Remove search from cart."""
    body = payload.to_payload()
    try:
        response = await client.cart_remove(body)
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="booking.cart_remove",
            method="DELETE",
            endpoint="/booking/cart",
            payload=body,
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove from cart",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="booking.cart_remove",
            method="DELETE",
            endpoint="/booking/cart",
            payload=body,
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected cart removal error",
        ) from exc

    record_activity(
        activity_log,
        action="booking.cart_remove",
        method="DELETE",
        endpoint="/booking/cart",
        payload=body,
        status="success",
        response=response,
    )
    return response
