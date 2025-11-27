"""HTTP client wrapper around the Travio REST API."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, Optional

import httpx
from loguru import logger

from backend.app.config import Settings


class TravioAPIError(Exception):
    """Raised when Travio API returns an unexpected response."""

    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"Travio API request failed with status {status_code}")


class TravioClient:
    """Async client handling auth, retries, and request routing."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._client = httpx.AsyncClient(
            base_url=str(settings.travio_base_url),
            timeout=httpx.Timeout(10.0, read=30.0),
        )
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator["TravioClient"]:
        """Async context manager to ensure resource cleanup."""
        try:
            yield self
        finally:
            await self.close()

    async def authenticate(self) -> str:
        """Retrieve bearer token using id/key credentials."""
        async with self._lock:
            if self._token and self._token_expiry and self._token_expiry > datetime.now(
                timezone.utc
            ):
                return self._token

            payload = {"id": self._settings.travio_id, "key": self._settings.travio_key}
            logger.info("Requesting Travio auth token")
            response = await self._client.post("/auth", json=payload)
            if response.status_code != 200:
                raise TravioAPIError(response.status_code, response.text)

            data = response.json()
            token = data.get("token")
            expires_in = data.get("expires_in", 3600)
            if not token:
                raise TravioAPIError(response.status_code, data)

            self._token = token
            self._token_expiry = datetime.now(timezone.utc) + timedelta(
                seconds=int(expires_in * 0.9)
            )
            return token

    async def _ensure_token(self) -> str:
        """Ensure we have a valid token before issuing API calls."""
        if not self._token or not self._token_expiry or self._token_expiry <= datetime.now(
            timezone.utc
        ):
            return await self.authenticate()
        return self._token

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform authorized Travio API requests."""
        token = await self._ensure_token()
        request_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Lang": self._settings.travio_language,
        }
        if headers:
            request_headers.update(headers)

        logger.debug("Travio request {method} {url}", method=method, url=url)
        response = await self._client.request(
            method, url, headers=request_headers, params=params, json=json
        )
        if response.status_code >= 400:
            logger.error(
                "Travio API error {status} on {url}: {body}",
                status=response.status_code,
                url=url,
                body=response.text,
            )
            raise TravioAPIError(response.status_code, response.text)
        if not response.content:
            return {}
        return response.json()

    # --- Profile & session ---

    async def get_profile(self) -> Dict[str, Any]:
        """Retrieve profile associated with current token."""
        return await self._request("GET", "/profile")

    async def login(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Login as Travio user to obtain enriched token."""
        data = await self._request("POST", "/login", json=payload)
        token = data.get("token")
        expires_in = data.get("expires_in")
        if token:
            self._token = token
            if expires_in:
                self._token_expiry = datetime.now(timezone.utc) + timedelta(
                    seconds=int(expires_in * 0.9)
                )
            else:
                self._token_expiry = None
        return data

    # --- CRM endpoints ---

    async def search_clients(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Search for clients in CRM repository."""
        return await self._request("GET", "/rest/master-data", params=filters)

    async def get_client(self, client_id: int) -> Dict[str, Any]:
        """Retrieve a client by ID."""
        return await self._request("GET", f"/rest/master-data/{client_id}")

    async def create_client(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new client."""
        return await self._request("POST", "/rest/master-data", json={"data": payload})

    async def update_client(self, client_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing client."""
        return await self._request(
            "PUT", f"/rest/master-data/{client_id}", json={"data": payload}
        )

    async def list_master_data_categories(
        self, *, page: int = 1, per_page: int = 200
    ) -> Dict[str, Any]:
        """Retrieve master-data categories (categorie anagrafiche)."""
        params = {"page": page, "per_page": per_page}
        return await self._request("GET", "/rest/master-data-categories", params=params)

    # --- Booking/Property endpoints ---

    async def booking_search(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run booking search."""
        return await self._request("POST", "/booking/search", json=payload)

    async def booking_results(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve additional booking results."""
        return await self._request("POST", "/booking/results", json=payload)

    async def booking_picks(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit picks for booking flow."""
        return await self._request("POST", "/booking/picks", json=payload)

    async def cart_add(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Add selections to cart."""
        return await self._request("PUT", "/booking/cart", json=payload)

    async def cart_get(self, cart_id: str) -> Dict[str, Any]:
        """Fetch cart details."""
        return await self._request("GET", f"/booking/cart/{cart_id}")

    async def cart_remove(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Remove search from cart."""
        return await self._request("DELETE", "/booking/cart", json=payload)

    async def place_reservation(self, cart_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize reservation/quote."""
        return await self._request("POST", f"/booking/place/{cart_id}", json=payload)

    async def send_quote(self, reservation_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger quote PDF/email generation."""
        return await self._request(
            "POST", f"/tools/print/reservation/{reservation_id}", json=payload
        )
