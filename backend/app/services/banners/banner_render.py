"""Headless render of the live banner for the visual self-review loop.

SINGLE SOURCE OF TRUTH: the banner markup comes from frontend/banner_template.js
(the same module the Canvas uses in-browser) executed via Node, and the CSS comes
from frontend/banner.css. This file only wraps that output into a full HTML document
and screenshots it with Playwright — so the headless review renders exactly what the
designer sees, with nothing duplicated here.

Desktop → wide banner (≈2.4), %-composed copy + hero.
Tablet/Mobile → taller fold, vertical-flow stack.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

# (width_px, default_aspect_ratio, stacked) per breakpoint — matches the frontend.
BREAKPOINTS: dict[str, tuple[int, float, bool]] = {
    "desktop": (1440, 2.4, False),
    "tablet": (768, 1.0, True),
    "mobile": (390, 0.82, True),
}


def _frontend_dir() -> Path:
    # backend/app/services/banners/banner_render.py → repo root → frontend/
    return Path(__file__).resolve().parents[4] / "frontend"


@lru_cache(maxsize=1)
def _banner_css() -> str:
    try:
        return (_frontend_dir() / "banner.css").read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return ""


def aspect_for(breakpoint: str, layout: dict[str, Any] | None) -> float:
    """Per-breakpoint aspect ratio, overridable from the layout (the review loop
    lowers it to give a taller fold when stacked content overflows)."""
    _, default_ar, _ = BREAKPOINTS.get(breakpoint, BREAKPOINTS["desktop"])
    L = layout or {}
    key = {"desktop": "aspectRatio", "tablet": "aspectRatioTablet", "mobile": "aspectRatioMobile"}.get(breakpoint)
    try:
        v = L.get(key)
        return float(v) if v is not None else default_ar
    except (TypeError, ValueError):
        return default_ar


def _font_link(*families: str) -> str:
    fams = [f for f in dict.fromkeys(families) if f]
    if not fams:
        return ""
    spec = "&".join("family=" + f.replace(" ", "+") + ":wght@400;600;700;800;900" for f in fams)
    return f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{spec}&display=swap">'


def _banner_inner_html(spec: dict[str, Any], breakpoint: str) -> str:
    """Run the shared JS template (frontend/banner_template.js) via Node to produce
    the banner DOM (style + div). Raises on failure so the caller can degrade."""
    template = _frontend_dir() / "banner_template.js"
    proc = subprocess.run(
        ["node", str(template), breakpoint],
        input=json.dumps(spec),
        capture_output=True,
        text=True,
        timeout=20,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"banner template render failed: {proc.stderr[:200]}")
    return proc.stdout


def render_banner_html(spec: dict[str, Any], *, breakpoint: str = "desktop") -> str:
    """Return a self-contained HTML document for one breakpoint, built from the
    single-source JS template + banner.css."""
    width, _default_ar, _ = BREAKPOINTS.get(breakpoint, BREAKPOINTS["desktop"])
    display = spec.get("displayFont") or "Space Grotesk"
    body = spec.get("bodyFont") or "Inter"
    inner = _banner_inner_html(spec, breakpoint)
    return f"""<!doctype html><html><head><meta charset="utf-8">
{_font_link(display, body)}
<style>*{{box-sizing:border-box}}body{{margin:0;background:#eef2f6}}
{_banner_css()}</style></head>
<body><div style="width:{width}px">{inner}</div></body></html>"""


async def screenshot_breakpoints(spec: dict[str, Any], *, breakpoints: list[str] | None = None) -> dict[str, bytes]:
    """Render the banner headlessly at each breakpoint; return {breakpoint: png_bytes}."""
    from playwright.async_api import async_playwright

    bps = breakpoints or ["desktop", "tablet", "mobile"]
    # Build all docs up-front (Node calls) so a render failure surfaces before launch.
    docs = {bp: render_banner_html(spec, breakpoint=bp) for bp in bps}
    out: dict[str, bytes] = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        try:
            for bp, doc in docs.items():
                width, _d, _ = BREAKPOINTS.get(bp, BREAKPOINTS["desktop"])
                ar = aspect_for(bp, spec.get("layout"))
                height = int(width / ar) + 28
                page = await browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                await page.set_content(doc, wait_until="networkidle")
                await page.wait_for_timeout(450)  # let webfonts/hero settle
                el = await page.query_selector(".hb-banner")
                out[bp] = await (el.screenshot(type="png") if el else page.screenshot(type="png"))
                await page.close()
        finally:
            await browser.close()
    return out


__all__ = ["render_banner_html", "screenshot_breakpoints", "BREAKPOINTS", "aspect_for"]
