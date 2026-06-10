"""Adaptive ink + scrim for full-picture banners (C1).

The copy sits over a GENERATED scene, so legibility can't rely on a designed
background. We sample the actual luminance of the copy zone in the image and
derive: ink color (dark/light) and a scrim (direction + alpha) only as strong
as needed to clear WCAG-ish contrast. Deterministic, PIL-only — no LLM.
"""

from __future__ import annotations

import io
from typing import Any

# Zone luminance bands: bright → dark ink, dark → light ink, ambiguous middle →
# light ink + a dark scrim sized to push the zone toward readable contrast.
_BRIGHT_FLOOR = 0.62
_DARK_CEILING = 0.38
_MAX_SCRIM_ALPHA = 0.55


def _zone_box(width: int, height: int, layout: dict[str, Any] | None) -> tuple[int, int, int, int]:
    layout = layout or {}

    def _pct(key: str, default: float) -> float:
        try:
            return max(0.0, min(100.0, float(layout.get(key, default))))
        except (TypeError, ValueError):
            return default

    x = _pct("textX", 6.0)
    y = _pct("textY", 50.0)
    w = _pct("textW", 48.0)
    # The copy block is vertically centered on textY; assume ~52% of the banner height.
    left = int(width * x / 100.0)
    right = int(width * min(100.0, x + w) / 100.0)
    top = int(height * max(0.0, y - 26.0) / 100.0)
    bottom = int(height * min(100.0, y + 26.0) / 100.0)
    if right <= left:
        right = min(width, left + max(1, width // 4))
    if bottom <= top:
        bottom = min(height, top + max(1, height // 4))
    return left, top, right, bottom


def sample_zone_luminance(image_bytes: bytes, layout: dict[str, Any] | None = None) -> float:
    """Mean relative luminance (0..1) of the copy zone in the image."""
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as img:
        rgb = img.convert("RGB")
        zone = rgb.crop(_zone_box(rgb.width, rgb.height, layout))
        # Downsample for speed; mean of per-channel means is enough here.
        zone.thumbnail((64, 64))
        pixels = list(zone.getdata())
    if not pixels:
        return 0.5
    n = len(pixels)
    r = sum(p[0] for p in pixels) / n / 255.0
    g = sum(p[1] for p in pixels) / n / 255.0
    b = sum(p[2] for p in pixels) / n / 255.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def adaptive_ink_and_scrim(image_bytes: bytes, layout: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pick ink + minimal scrim for legible copy over the generated scene.

    Returns {"ink", "scrim_dir", "scrim_alpha", "zone_luminance"}. Alpha 0 means
    no scrim needed; the renderer's glass box remains the last-resort fallback.
    """
    try:
        lum = sample_zone_luminance(image_bytes, layout)
    except Exception:  # noqa: BLE001 — unreadable image → safe defaults
        lum = 0.5
    text_x = float((layout or {}).get("textX") or 6.0)
    # Darken from the copy side so the scrim fades over the subject side.
    scrim_dir = "90deg" if text_x < 50 else "270deg"
    if lum >= _BRIGHT_FLOOR:
        return {"ink": "#111111", "scrim_dir": scrim_dir, "scrim_alpha": 0.0, "zone_luminance": round(lum, 3)}
    if lum <= _DARK_CEILING:
        return {"ink": "#FFFFFF", "scrim_dir": scrim_dir, "scrim_alpha": 0.0, "zone_luminance": round(lum, 3)}
    # Ambiguous mid-tones: light ink + a scrim proportional to how far the zone
    # sits from "dark enough" (lum 0.38 → ~0.1 alpha, lum 0.62 → max alpha).
    span = (_BRIGHT_FLOOR - _DARK_CEILING) or 1.0
    alpha = 0.1 + (lum - _DARK_CEILING) / span * (_MAX_SCRIM_ALPHA - 0.1)
    return {
        "ink": "#FFFFFF",
        "scrim_dir": scrim_dir,
        "scrim_alpha": round(min(_MAX_SCRIM_ALPHA, max(0.1, alpha)), 2),
        "zone_luminance": round(lum, 3),
    }
