"""Mock Travio client providing local demo data."""

from __future__ import annotations

import asyncio
import json
import random
import string
from datetime import datetime, timedelta
from math import ceil
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.app.config import Settings


def _random_id(prefix: str) -> str:
    token = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}_{token}"


class MockTravioClient:
    """In-memory mock client mimicking Travio API behaviour."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._token = "mock-token"
        self._clients: List[Dict[str, Any]] = [
            {
                "id": 101,
                "name": "Alice",
                "surname": "Example",
                "profiles": ["customer"],
                "profile_type": "private",
                "language": "en",
                "vat_country": "IT",
                "categories": [1],
                "contacts": [
                    {
                        "name": "Primary",
                        "email": ["alice@example.com"],
                        "phone": ["+3900000001"],
                        "fax": [],
                    }
                ],
            },
            {
                "id": 102,
                "name": "Bob",
                "surname": "Sample",
                "profiles": ["customer"],
                "profile_type": "private",
                "language": "en",
                "vat_country": "US",
                "categories": [2],
                "contacts": [
                    {
                        "name": "Primary",
                        "email": ["bob@example.com"],
                        "phone": ["+3900000002"],
                        "fax": [],
                    }
                ],
            },
        ]
        self._next_client_id = 103
        self._search_results: Dict[str, Dict[str, Any]] = {}
        self._carts: Dict[str, Dict[str, Any]] = {}
        self._reservations: Dict[str, Dict[str, Any]] = {}
        self._master_data_categories: List[Dict[str, Any]] = [
            {"id": 1, "code": "CLI", "name": "Clienti privati"},
            {"id": 2, "code": "CORP", "name": "Clienti corporate"},
            {"id": 3, "code": "SUP", "name": "Fornitori"},
        ]

    async def close(self) -> None:
        """Mock close to align with TravioClient interface."""
        await asyncio.sleep(0)

    async def authenticate(self) -> str:
        """Return mock token."""
        return self._token

    async def get_profile(self) -> Dict[str, Any]:
        """Return static profile."""
        return {
            "user": {
                "id": 1,
                "name": "Mock User",
                "email": "mock.user@example.com",
            },
            "roles": ["demo"],
            "language": self._settings.travio_language,
        }

    async def login(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return mock login result."""
        username = payload.get("username", "demo")
        self._token = f"mock-token-{username}"
        return {
            "token": self._token,
            "expires_in": 3600,
            "user": {"username": username, "roles": ["demo"]},
        }

    # --- CRM endpoints ---
    async def search_clients(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Filter mock clients by simple attributes."""
        results = list(self._clients)
        filters_raw = params.get("filters")
        filter_defs: List[Dict[str, Any]] = []
        if isinstance(filters_raw, str) and filters_raw:
            try:
                filter_defs = json.loads(filters_raw)
            except json.JSONDecodeError:
                filter_defs = []

        def matches(item: Dict[str, Any], flt: Dict[str, Any]) -> bool:
            field = flt.get("field")
            operator = (flt.get("operator") or "like").lower()
            value = str(flt.get("value", ""))
            if operator == "like":
                needle = value.strip("%").lower()
            else:
                needle = value.lower()

            if field == "contacts.email":
                contacts = item.get("contacts", [])
                emails = [
                    mail.lower()
                    for contact in contacts
                    for mail in contact.get("email") or []
                ]
                if operator == "like":
                    return any(needle in email for email in emails)
                return value.lower() in emails
            if field == "surname":
                surname = item.get("lastname") or item.get("surname", "")
                if operator == "like":
                    return needle in surname.lower()
                return surname.lower() == needle
            if field == "id":
                target = str(item.get("id", "")).lower()
                if operator == "like":
                    return needle in target
                return target == needle
            return True

        for flt in filter_defs:
            results = [item for item in results if matches(item, flt)]

        phone_filter = params.get("_phone_filter")
        if phone_filter:
            results = [
                item
                for item in results
                if any(
                    phone_filter in phone
                    for contact in item.get("contacts", [])
                    for phone in (contact.get("phone") or [])
                )
            ]

        page = int(params.get("page", 1) or 1)
        per_page = int(params.get("per_page", 20) or 20)
        total = len(results)
        pages = ceil(total / per_page) if per_page else 1
        start = (page - 1) * per_page
        end = start + per_page if per_page else None
        page_items = results[start:end]

        return {
            "items": page_items,
            "list": page_items,
            "total": total,
            "tot": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    async def get_client(self, client_id: int) -> Dict[str, Any]:
        """Retrieve mock client."""
        for client in self._clients:
            if client["id"] == client_id:
                return client
        raise ValueError("Client not found")

    async def create_client(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create mock client."""
        payload = payload.copy()
        payload.setdefault("firstname", payload.get("name", "New").split(" ")[0])
        payload.setdefault("lastname", payload.get("name", "Client").split(" ")[-1])
        payload["id"] = self._next_client_id
        self._next_client_id += 1
        contacts: List[Dict[str, Any]] = []
        email = payload.get("email")
        phone = payload.get("phone")
        if email or phone:
            contacts.append(
                {
                    "name": "Primary",
                    "email": [email] if email else [],
                    "phone": [phone] if phone else [],
                    "fax": [],
                }
            )
        payload.setdefault("contacts", contacts)
        if phone is not None:
            payload["phone"] = phone
        if email is not None:
            payload["email"] = email
        payload.setdefault("profiles", ["customer"])
        payload.setdefault("profile_type", "private")
        payload.setdefault("language", self._settings.travio_language)
        if "categories" in payload:
            categories = [
                cat for cat in payload.get("categories", []) if isinstance(cat, int)
            ]
            if categories:
                payload["categories"] = categories
            else:
                payload.pop("categories", None)
        self._clients.append(payload)
        logger.debug("Mock client created: {client}", client=payload)
        return payload

    async def update_client(self, client_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update mock client."""
        for idx, client in enumerate(self._clients):
            if client["id"] == client_id:
                updated = client | payload
                email = updated.get("email")
                phone = updated.get("phone")
                if email or phone:
                    updated["contacts"] = [
                        {
                            "name": "Primary",
                            "email": [email] if email else [],
                            "phone": [phone] if phone else [],
                            "fax": [],
                        }
                    ]
                if email is not None:
                    updated["email"] = email
                if phone is not None:
                    updated["phone"] = phone
                if "categories" in payload:
                    categories = [
                        cat for cat in payload.get("categories", []) if isinstance(cat, int)
                    ]
                    if categories:
                        updated["categories"] = categories
                    else:
                        updated.pop("categories", None)
                self._clients[idx] = updated
                return updated
        raise ValueError("Client not found")

    async def list_master_data_categories(
        self, *, page: int = 1, per_page: int = 200
    ) -> Dict[str, Any]:
        """Return mock master-data categories."""
        total = len(self._master_data_categories)
        start = (page - 1) * per_page
        end = start + per_page if per_page else None
        items = self._master_data_categories[start:end]
        return {
            "items": items,
            "list": items,
            "total": total,
            "tot": total,
            "page": page,
            "per_page": per_page,
            "pages": ceil(total / per_page) if per_page else 1,
        }

    # --- Booking endpoints ---

    async def booking_search(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return canned search results."""
        search_id = _random_id("search")
        check_in = payload.get("from")
        check_out = payload.get("to")
        service_type = payload.get("type", "hotels")
        sample_item = {
            "id": 501,
            "name": "Mock Resort",
            "price": 420.0,
            "currency": "EUR",
            "board": "BB",
            "supplier": "Mock Supplier",
            "cancellation": "Free cancellation up to 48h",
        }
        groups = [
            {
                "group": 0,
                "type": "pick",
                "pick_type": "one",
                "items": [
                    {
                        "idx": 0,
                        "title": f"{sample_item['name']} ({service_type})",
                        "price": sample_item["price"],
                        "currency": sample_item["currency"],
                        "supplier": sample_item["supplier"],
                        "board": sample_item["board"],
                        "dates": [{"idx": 0, "from": check_in, "to": check_out}],
                    }
                ],
            }
        ]
        response = {
            "search_id": search_id,
            "final": False,
            "step": 0,
            "groups": groups,
        }
        self._search_results[search_id] = response
        return response

    async def booking_results(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return same mock results."""
        search_id = payload["search_id"]
        return self._search_results.get(search_id, {"search_id": search_id, "groups": []})

    async def booking_picks(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return final step after picks."""
        search_id = payload["search_id"]
        response = self._search_results.get(search_id)
        if not response:
            return {"search_id": search_id, "groups": [], "final": True}
        response = response.copy()
        response["final"] = True
        response["step"] = payload.get("step", 0) + 1
        return response

    async def cart_add(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Add selections to mock cart."""
        search_id = payload["search_id"]
        cart_id = _random_id("cart")
        cart = {
            "id": cart_id,
            "searches": [self._search_results.get(search_id, {})],
            "pax": [
                {"id": 1, "name": "John", "surname": "Doe"},
                {"id": 2, "name": "Jane", "surname": "Doe"},
            ],
        }
        self._carts[cart_id] = cart
        return cart

    async def cart_get(self, cart_id: str) -> Dict[str, Any]:
        """Return cart by id."""
        return self._carts.get(cart_id, {"id": cart_id, "searches": [], "pax": []})

    async def cart_remove(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """No-op remove."""
        return {"status": "removed", "search_id": payload.get("search_id")}

    async def place_reservation(self, cart_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create mock reservation."""
        reservation_id = random.randint(1000, 9999)
        reservation = {
            "id": reservation_id,
            "cart_id": cart_id,
            "status": payload.get("status", 0),
            "pax": payload.get("pax", []),
            "reference": payload.get("reference"),
            "description": payload.get("description"),
            "payment_link": f"https://payments.example.com/{reservation_id}",
            "created_at": datetime.utcnow().isoformat(),
            "due": payload.get("due")
            or (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d 12:00:00"),
        }
        self._reservations[str(reservation_id)] = reservation
        return reservation

    async def send_quote(self, reservation_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return mock send quote response."""
        return {
            "reservation_id": reservation_id,
            "template": payload.get("template"),
            "archived": payload.get("archive", False),
            "email_sent": payload.get("send", False),
            "pdf_url": f"https://cdn.example.com/quotes/{reservation_id}.pdf",
        }
