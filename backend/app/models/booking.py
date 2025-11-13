"""Pydantic models for booking operations."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BookingSearchRequest(BaseModel):
    """Payload for Travio booking search."""

    type: str
    from_date: str = Field(..., alias="from")
    to_date: str = Field(..., alias="to")
    geo: Optional[List[int]] = None
    ids: Optional[List[str]] = None
    codes: Optional[List[str]] = None
    occupancy: List[Dict[str, Any]]
    per_page: Optional[int] = None
    return_filters: Optional[List[str]] = None
    sort_by: Optional[List[Dict[str, Any]]] = None
    cart: Optional[str] = None
    client_country: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        payload = {
            "type": self.type,
            "from": self.from_date,
            "to": self.to_date,
            "occupancy": self.occupancy,
        }
        if self.geo is not None:
            payload["geo"] = self.geo
        if self.ids is not None:
            payload["ids"] = self.ids
        if self.codes is not None:
            payload["codes"] = self.codes
        if self.per_page is not None:
            payload["per_page"] = self.per_page
        if self.return_filters:
            payload["return_filters"] = self.return_filters
        if self.sort_by:
            payload["sort_by"] = self.sort_by
        if self.cart:
            payload["cart"] = self.cart
        if self.client_country:
            payload["client_country"] = self.client_country
        return payload


class BookingResultsRequest(BaseModel):
    """Payload for paging through booking results."""

    search_id: str
    page: int
    per_page: Optional[int] = None
    filters: Optional[List[Dict[str, Any]]] = None
    sort_by: Optional[List[Dict[str, Any]]] = None

    def to_payload(self) -> Dict[str, Any]:
        payload = {"search_id": self.search_id, "page": self.page}
        if self.per_page is not None:
            payload["per_page"] = self.per_page
        if self.filters:
            payload["filters"] = self.filters
        if self.sort_by:
            payload["sort_by"] = self.sort_by
        return payload


class BookingPicksRequest(BaseModel):
    """Payload for submitting booking picks."""

    search_id: str
    step: int
    picks: List[Dict[str, Any]]
    per_page: Optional[int] = None

    def to_payload(self) -> Dict[str, Any]:
        payload = {
            "search_id": self.search_id,
            "step": self.step,
            "picks": self.picks,
        }
        if self.per_page is not None:
            payload["per_page"] = self.per_page
        return payload


class CartMutationRequest(BaseModel):
    """Payload for adding or removing items from cart."""

    search_id: str

    def to_payload(self) -> Dict[str, Any]:
        return {"search_id": self.search_id}


class PlaceReservationRequest(BaseModel):
    """Payload for reserving or quoting selection."""

    pax: List[Dict[str, Any]]
    status: Optional[int] = None
    due: Optional[str] = None
    notes: Optional[List[Dict[str, Any]]] = None
    description: Optional[str] = None
    reference: Optional[str] = None
    payment_link: Optional[bool] = None
    client_id: Optional[int] = None

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"pax": self.pax}
        if self.status is not None:
            payload["status"] = self.status
        if self.due is not None:
            payload["due"] = self.due
        if self.notes:
            payload["notes"] = self.notes
        if self.description:
            payload["description"] = self.description
        if self.reference:
            payload["reference"] = self.reference
        if self.payment_link is not None:
            payload["payment_link"] = self.payment_link
        if self.client_id is not None:
            payload["client"] = self.client_id
        return payload


class QuoteDeliveryRequest(BaseModel):
    """Payload for triggering quote PDF/email."""

    template: int
    archive: Optional[bool] = None
    send: Optional[bool] = None

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"template": self.template}
        if self.archive is not None:
            payload["archive"] = self.archive
        if self.send is not None:
            payload["send"] = self.send
        return payload
