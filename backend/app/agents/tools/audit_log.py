"""ADK Tool: emit observability event to Supabase audit_log."""

from __future__ import annotations

from typing import Any


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
    raise NotImplementedError("Lands in services/supabase/audit_log.py.")
