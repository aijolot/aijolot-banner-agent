from __future__ import annotations

from typing import Any

_EVENTS: list[dict[str, Any]] = []


async def emit(
    *,
    trace_id: str,
    session_id: str,
    brand_id: str,
    node: str,
    event: str,
    duration_ms: int | None = None,
    cost_usd: float | None = None,
    tokens: dict | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Emit a deterministic in-process audit event.

    Persistence is handled by AuditEventRepository when a Supabase client is
    available. This tool remains side-effect-light for unit tests and graph runs.
    """
    _EVENTS.append({
        "trace_id": trace_id,
        "session_id": session_id,
        "brand_id": brand_id,
        "node": node,
        "event_type": event,
        "duration_ms": duration_ms,
        "cost_usd": cost_usd,
        "tokens": tokens or {},
        "payload": payload or {},
    })


def events() -> list[dict[str, Any]]:
    return list(_EVENTS)
