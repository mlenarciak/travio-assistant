"""CRM endpoints for Travio client repository."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, status

from backend.app.api.activity import record_activity
from backend.app.api.deps import get_activity_log, get_app_settings, get_travio_client
from backend.app.config import Settings
from backend.app.models.crm import CRMClientPayload, CRMSearchRequest
from backend.app.services.travio_client import TravioAPIError

router = APIRouter(prefix="/api/crm", tags=["crm"])


@router.post("/search")
async def search_clients(
    request: CRMSearchRequest,
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Proxy Travio CRM search with flexible filters."""
    params = request.to_params()
    phone_filter = params.pop("_phone_filter", None)
    try:
        response = await client.search_clients(params)
        if isinstance(response, dict) and "items" not in response:
            items = response.get("list")
            if isinstance(items, list):
                response = {**response, "items": items}
        if phone_filter and isinstance(response, dict):
            items = response.get("items") or []
            filtered_items = []
            for item in items:
                contacts = item.get("contacts") or []
                phones = []
                for contact in contacts:
                    phones.extend(contact.get("phone") or [])
                if any(phone_filter in phone for phone in phones):
                    filtered_items.append(item)
            per_page = response.get("per_page") or len(filtered_items)
            per_page = per_page or len(filtered_items) or 1
            response = {
                **response,
                "items": filtered_items,
                "filtered_by_phone": phone_filter,
                "total": len(filtered_items),
                "tot": len(filtered_items),
                "pages": 1,
                "page": 1,
                "per_page": per_page,
            }
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="crm.search",
            method="GET",
            endpoint="/rest/master-data",
            payload=params,
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Travio CRM search failed",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="crm.search",
            method="GET",
            endpoint="/rest/master-data",
            payload=params,
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected CRM search error",
        ) from exc

    record_activity(
        activity_log,
        action="crm.search",
        method="GET",
        endpoint="/rest/master-data",
        payload=params,
        status="success",
        response=response,
    )
    return response


@router.get("/{client_id}")
async def get_client(
    client_id: int = Path(..., ge=0),
    client: Any = Depends(get_travio_client),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Return single Travio client record."""
    try:
        response = await client.get_client(client_id)
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="crm.detail",
            method="GET",
            endpoint=f"/rest/master-data/{client_id}",
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="crm.detail",
            method="GET",
            endpoint=f"/rest/master-data/{client_id}",
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected client retrieval error",
        ) from exc

    record_activity(
        activity_log,
        action="crm.detail",
        method="GET",
        endpoint=f"/rest/master-data/{client_id}",
        status="success",
        response=response,
    )
    return response


@router.post("")
async def create_client(
    payload: CRMClientPayload,
    client: Any = Depends(get_travio_client),
    settings: Settings = Depends(get_app_settings),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Create a new Travio client."""
    normalized = _prepare_client_payload(payload.data, settings, include_defaults=True)
    try:
        response = await client.create_client(normalized)
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="crm.create",
            method="POST",
            endpoint="/rest/master-data",
            payload=payload.data,
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Travio CRM create failed",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="crm.create",
            method="POST",
            endpoint="/rest/master-data",
            payload=payload.data,
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected CRM create error",
        ) from exc

    record_activity(
        activity_log,
        action="crm.create",
        method="POST",
        endpoint="/rest/master-data",
        payload=payload.data,
        status="success",
        response=response,
    )
    return response


@router.put("/{client_id}")
async def update_client(
    payload: CRMClientPayload,
    client_id: int = Path(..., ge=0),
    client: Any = Depends(get_travio_client),
    settings: Settings = Depends(get_app_settings),
    activity_log=Depends(get_activity_log),
) -> Dict[str, Any]:
    """Update an existing Travio client."""
    normalized = _prepare_client_payload(
        payload.data, settings, include_defaults=False
    )
    try:
        response = await client.update_client(client_id, normalized)
    except TravioAPIError as exc:
        record_activity(
            activity_log,
            action="crm.update",
            method="PUT",
            endpoint=f"/rest/master-data/{client_id}",
            payload=payload.data,
            status="error",
            response={"status_code": exc.status_code, "payload": exc.payload},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Travio CRM update failed",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        record_activity(
            activity_log,
            action="crm.update",
            method="PUT",
            endpoint=f"/rest/master-data/{client_id}",
            payload=payload.data,
            status="error",
            response={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected CRM update error",
        ) from exc

    record_activity(
        activity_log,
        action="crm.update",
        method="PUT",
        endpoint=f"/rest/master-data/{client_id}",
        payload=payload.data,
        status="success",
        response=response,
    )
    return response
def _prepare_client_payload(
    data: Dict[str, Any],
    settings: Settings,
    *,
    include_defaults: bool = True,
) -> Dict[str, Any]:
    """Normalize frontend payload into Travio REST master-data format."""
    payload = {k: v for k, v in data.items() if v is not None}

    first = payload.pop("firstname", payload.pop("first_name", None))
    last = payload.pop("lastname", payload.pop("last_name", None))

    name = payload.get("name")
    if first:
        payload["name"] = first
    elif include_defaults and not name:
        payload["name"] = ""
    elif name and include_defaults:
        payload["name"] = name.split(" ", 1)[0]

    if last:
        payload["surname"] = last
    elif "surname" not in payload and name and " " in name:
        payload["surname"] = name.split(" ", 1)[1]

    email = payload.pop("email", None)
    phone = payload.pop("phone", None)
    contacts = payload.get("contacts")
    if not contacts and (email or phone):
        payload["contacts"] = [
            {
                "name": "Primary",
                "email": [email] if email else [],
                "phone": [phone] if phone else [],
                "fax": [],
            }
        ]

    country = payload.pop("country", None)
    if country:
        payload.setdefault("vat_country", country)

    payload.pop("marketing", None)

    if include_defaults:
        payload.setdefault("profiles", ["customer"])
        payload.setdefault("profile_type", "private")
        payload.setdefault("language", settings.travio_language)

    return payload
