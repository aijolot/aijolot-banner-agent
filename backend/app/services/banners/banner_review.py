"""Visual self-review loop for the assembled banner.

The assembly agent renders the live banner headlessly at the three breakpoints,
asks a vision model to critique each render (legibility, clipping, overlap, balance),
and — when the wide/desktop composition fails — adjusts the percent layout and
re-renders, up to a small iteration cap. Best-effort: any failure (no Chromium, no
Gemini, errors) returns the input layout unchanged so assembly never breaks.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from app.services.banners.banner_render import screenshot_breakpoints


class BannerCritique(BaseModel):
    """Vision verdict for one rendered breakpoint."""

    ok: bool = Field(description="True if the banner reads well at this breakpoint")
    legible: bool = Field(default=True, description="Headline/copy clearly readable over the background")
    text_clipped: bool = Field(default=False, description="Any copy/CTA cut off or overflowing the banner")
    hero_collision: bool = Field(default=False, description="Hero image overlaps/obscures the copy badly")
    issues: list[str] = Field(default_factory=list, description="Short, concrete problems (<=4)")
    # Suggested ABSOLUTE percent layout for the WIDE/desktop composition (0-100).
    text_x: float | None = None
    text_y: float | None = None
    text_w: float | None = None
    hero_x: float | None = None
    hero_y: float | None = None
    hero_w: float | None = None


_PROMPT = (
    "You are a senior art director reviewing a rendered ecommerce HERO BANNER at the "
    "{bp} breakpoint. Judge it strictly as a finished banner:\n"
    "- Is the headline/copy clearly LEGIBLE over the background?\n"
    "- Is any text or the CTA button CLIPPED / overflowing the banner edges?\n"
    "- Does the product hero COLLIDE with or obscure the copy?\n"
    "- Is the composition balanced (not crammed to one side, good breathing room)?\n"
    "Return JSON: ok (overall), legible, text_clipped, hero_collision, issues[]. "
    "If this is the wide desktop banner and the composition is off, ALSO return improved "
    "ABSOLUTE percent values text_x,text_y,text_w (copy block) and hero_x,hero_y,hero_w "
    "(hero, centered) — copy on one side, hero on the other, no bad collision. "
    "Omit those fields if the layout is already good."
)


def _api_key() -> str | None:
    from app.core.settings import Settings

    s = Settings.from_env()
    return s.require_google_api_key() if s.has_google_api_key() else None


def _critique_sync(png: bytes, breakpoint: str, model: str) -> BannerCritique | None:
    key = _api_key()
    if not key:
        return None
    try:
        from google import genai
        from google.genai import types
    except Exception:  # noqa: BLE001
        return None
    try:
        client = genai.Client(api_key=key)
        config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=BannerCritique)
        contents = [types.Part.from_bytes(data=png, mime_type="image/png"), _PROMPT.format(bp=breakpoint)]
        resp = client.models.generate_content(model=model, contents=contents, config=config)
    except Exception:  # noqa: BLE001
        return None
    parsed = getattr(resp, "parsed", None)
    if isinstance(parsed, BannerCritique):
        return parsed
    try:
        import json

        return BannerCritique.model_validate(json.loads(getattr(resp, "text", "") or "{}"))
    except Exception:  # noqa: BLE001
        return None


async def _critique(png: bytes, breakpoint: str, model: str) -> BannerCritique | None:
    return await asyncio.to_thread(_critique_sync, png, breakpoint, model)


def _apply_suggestions(layout: dict[str, Any], crit: BannerCritique) -> dict[str, Any]:
    from app.schemas.typography import ArtDirection, clamp_layout

    ad = ArtDirection(
        display="Space Grotesk", body="Inter",
        text_x=crit.text_x if crit.text_x is not None else layout.get("textX", 6),
        text_y=crit.text_y if crit.text_y is not None else layout.get("textY", 50),
        text_w=crit.text_w if crit.text_w is not None else layout.get("textW", 48),
        text_align=layout.get("textAlign", "left"),
        hero_x=crit.hero_x if crit.hero_x is not None else layout.get("heroX", 76),
        hero_y=crit.hero_y if crit.hero_y is not None else layout.get("heroY", 50),
        hero_w=crit.hero_w if crit.hero_w is not None else layout.get("heroW", 46),
    )
    merged = clamp_layout(ad)
    merged["textAlign"] = layout.get("textAlign", "left")
    return merged


async def review_and_correct(
    spec: dict[str, Any],
    *,
    max_iters: int = 2,
    model: str | None = None,
) -> dict[str, Any]:
    """Render → critique (3 breakpoints) → adjust desktop layout → repeat.

    Returns {"layout": <final layout>, "report": [...per-iteration verdicts...]}.
    Best-effort: returns the input layout on any failure.
    """
    from app.agents.tools import gemini_text

    review_model = model or gemini_text.FLASH_MODEL
    layout = dict(spec.get("layout") or {})
    report: list[dict[str, Any]] = []

    for iteration in range(max(1, max_iters)):
        trial = {**spec, "layout": layout}
        try:
            shots = await screenshot_breakpoints(trial)
        except Exception as exc:  # noqa: BLE001 — no Chromium / render error
            report.append({"iteration": iteration, "error": f"render failed: {type(exc).__name__}"})
            break
        crits = await asyncio.gather(*[_critique(png, bp, review_model) for bp, png in shots.items()])
        verdicts = {bp: c for bp, c in zip(shots.keys(), crits) if c is not None}
        if not verdicts:
            report.append({"iteration": iteration, "error": "no critique (vision unavailable)"})
            break
        report.append({
            "iteration": iteration,
            "verdicts": {bp: {"ok": c.ok, "issues": c.issues[:4]} for bp, c in verdicts.items()},
        })
        if all(c.ok for c in verdicts.values()):
            break
        changed = False
        # Desktop (wide, absolute %): apply the suggested composition.
        desktop = verdicts.get("desktop")
        if desktop and not desktop.ok and any(v is not None for v in (desktop.text_x, desktop.hero_x, desktop.text_w)):
            layout = _apply_suggestions(layout, desktop)
            changed = True
        # Stacked (tablet/mobile): when content overflows/clips, give a TALLER fold
        # (lower the aspect ratio) so the vertical stack fits.
        for bp, key, floor in (("tablet", "aspectRatioTablet", 0.7), ("mobile", "aspectRatioMobile", 0.6)):
            c = verdicts.get(bp)
            if c and not c.ok and (c.text_clipped or "overflow" in " ".join(c.issues).lower() or not c.legible):
                from app.services.banners.banner_render import aspect_for

                new_ar = round(max(floor, aspect_for(bp, layout) * 0.82), 3)
                if new_ar < aspect_for(bp, layout):
                    layout[key] = new_ar
                    changed = True
        if not changed:
            break  # nothing actionable → stop

    return {"layout": layout or (spec.get("layout") or {}), "report": report}


__all__ = ["review_and_correct", "BannerCritique"]
