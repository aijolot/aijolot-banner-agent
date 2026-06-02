from __future__ import annotations

import re
from typing import Any


def _score_for_html(html: str) -> int:
    length = len(html.encode("utf-8"))
    score = 96
    if length > 120_000:
        score -= 18
    elif length > 60_000:
        score -= 8
    if "loading=\"lazy\"" not in html and "loading='lazy'" not in html and "loading=\"eager\"" not in html:
        score -= 3
    if "srcset" not in html:
        score -= 6
    if re.search(r"<script(?![^>]+application/ld\+json)", html, re.I):
        score -= 5
    return max(0, min(100, score))


async def run(html_url: str | None = None, *, html: str | None = None) -> dict[str, Any]:
    """Return deterministic manual/mock Lighthouse-style metrics.

    Live Lighthouse automation is intentionally not invoked in Task 14 tests. The
    result is labeled so downstream audit and HITL cannot confuse it with a live
    browser trace.
    """
    source = html or ""
    score = _score_for_html(source)
    size_kb = round(len(source.encode("utf-8")) / 1024, 2)
    return {
        "mode": "mock_manual",
        "source_url": html_url,
        "performance": float(score),
        "accessibility": 92.0 if "aria-label" in source or "aria-labelledby" in source else 84.0,
        "best_practices": 95.0,
        "seo": 94.0 if "meta name=\"description\"" in source else 86.0,
        "lcp_ms": 1350 + int(size_kb * 5),
        "cls": 0.02,
        "total_byte_weight_kb": size_kb,
        "label": "Deterministic mock/manual Lighthouse-style metrics; no live browser automation executed.",
    }
