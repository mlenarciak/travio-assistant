"""Helpers to record request/response activity."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def record_activity(
    log: List[Dict[str, Any]],
    *,
    action: str,
    method: str,
    endpoint: str,
    payload: Optional[Dict[str, Any]] = None,
    response: Optional[Any] = None,
    status: str = "success",
    source: str = "live",
) -> None:
    """Append a structured entry to the in-memory activity log."""
    log.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "method": method,
            "endpoint": endpoint,
            "payload": payload,
            "response": response,
            "status": status,
            "source": source,
        }
    )

