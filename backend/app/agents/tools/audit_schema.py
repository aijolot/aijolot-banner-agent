"""ADK Tool: JSON-LD / Schema.org validation. Lands in GH-16."""

from __future__ import annotations


async def validate(html: str) -> dict:
    """Return {'valid': bool, 'type': str|None, 'errors': [...]}."""
    raise NotImplementedError("Lands in services/audit/schema_ld.py + GH-16.")
