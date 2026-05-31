"""ADK Tool: Lighthouse headless audit. Lands in GH-16."""

from __future__ import annotations


async def run(html_url: str) -> dict[str, float]:
    """Return {'performance': 0-100, 'lcp_ms': int, 'cls': float}."""
    raise NotImplementedError("Lands in services/audit/lighthouse.py + GH-16.")
