"""ADK Tool: W3C HTML validation via html5validator. Lands in GH-16."""

from __future__ import annotations


async def validate(html: str) -> dict:
    """Return {'valid': bool, 'errors': [...]}."""
    raise NotImplementedError("Lands in services/audit/w3c.py + GH-16.")
