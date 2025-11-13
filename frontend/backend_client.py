"""Utility client for interacting with local FastAPI backend."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx


class BackendClient:
    """Synchronous HTTP client thin wrapper."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform HTTP request to backend and parse JSON response."""
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=httpx.Timeout(10.0, read=30.0)) as client:
            response = client.request(method, url, params=params, json=json)
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()

    def get(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Shortcut for GET requests."""
        return self.request("GET", path, params=params)

    def post(
        self, path: str, *, json: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Shortcut for POST requests."""
        return self.request("POST", path, json=json)

    def put(
        self, path: str, *, json: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Shortcut for PUT requests."""
        return self.request("PUT", path, json=json)

    def delete(
        self, path: str, *, json: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Shortcut for DELETE requests."""
        return self.request("DELETE", path, json=json)

