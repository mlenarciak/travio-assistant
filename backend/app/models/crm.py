"""Pydantic models for CRM-related API interactions."""

import json
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CRMSearchRequest(BaseModel):
    """Request body for CRM search operations."""

    filters: Dict[str, Any] = Field(default_factory=dict)
    page: Optional[int] = None
    per_page: Optional[int] = Field(default=None, validation_alias="page_size")
    unfold: Optional[str] = None

    def to_params(self) -> Dict[str, Any]:
        """Serialize request into Travio query string parameters."""
        params: Dict[str, Any] = {}
        filters: Dict[str, Any] = self.filters or {}
        travio_filters = []

        email = filters.get("filter[email]")
        if email:
            travio_filters.append(
                {"field": "contacts.email", "operator": "like", "value": f"%{email}%"}
            )

        surname = filters.get("filter[surname]")
        if surname:
            travio_filters.append(
                {"field": "surname", "operator": "like", "value": f"%{surname}%"}
            )

        code = filters.get("filter[code]")
        if code:
            operator = "=" if str(code).isdigit() else "like"
            value = code if operator == "=" else f"%{code}%"
            travio_filters.append({"field": "id", "operator": operator, "value": value})

        if travio_filters:
            params["filters"] = json.dumps(travio_filters)
        elif filters:
            params["filters"] = "[]"

        phone = filters.get("filter[phone]")
        if phone:
            params["_phone_filter"] = phone
            params.setdefault("unfold", "contacts")

        if self.page is not None:
            params["page"] = self.page
        if self.per_page is not None:
            params["per_page"] = self.per_page
        if self.unfold:
            params["unfold"] = (
                f"{params['unfold']},{self.unfold}"
                if "unfold" in params and params["unfold"]
                else self.unfold
            )
        elif travio_filters:
            params.setdefault("unfold", "contacts")
        return params


class CRMClientPayload(BaseModel):
    """Generic payload for creating/updating Travio clients."""

    data: Dict[str, Any]
