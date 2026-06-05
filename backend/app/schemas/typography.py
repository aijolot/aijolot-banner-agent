"""Typography pairing proposed per campaign concept (creative direction)."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Curated, reliably-loadable Google Fonts the agent may choose from. An allow-list
# keeps typography on-concept without loading arbitrary/invalid families (and avoids
# injecting unbounded names into a stylesheet URL).
DISPLAY_FONTS = [
    "Space Grotesk", "Archivo Black", "Fraunces", "Playfair Display", "Bebas Neue",
    "Anton", "Syne", "Unbounded", "DM Serif Display", "Sora", "Familjen Grotesk",
    "Big Shoulders Display", "Montserrat", "Poppins", "Cormorant Garamond", "Oswald",
]
BODY_FONTS = [
    "Inter", "DM Sans", "Work Sans", "Manrope", "IBM Plex Sans", "Public Sans",
    "Nunito Sans", "Mulish", "Karla", "Figtree", "Hanken Grotesk", "Albert Sans",
]


class FontPairing(BaseModel):
    """A display+body type pairing chosen to fit the campaign concept."""

    display: str = Field(description="Headline/display font family (from the allowed display set)")
    body: str = Field(description="Body/subhead font family (from the allowed body set)")
    rationale: str = Field(default="", description="One line: why this pairing fits the campaign mood")


class ArtDirection(BaseModel):
    """Type pairing + banner composition (all positions in PERCENT, never px)."""

    display: str = Field(description="Headline font family (from the allowed display set)")
    body: str = Field(description="Body font family (from the allowed body set)")
    rationale: str = Field(default="", description="One line: why these choices fit the campaign")
    # Composition over a 1440-wide fixed-aspect banner; values are 0-100 percentages.
    # Not range-constrained at the model layer (the LLM may stray) — clamp_layout()
    # projects them onto safe ranges so an out-of-range value never breaks the call.
    text_x: float = Field(default=6, description="Copy block left edge %")
    text_y: float = Field(default=50, description="Copy block vertical center %")
    text_w: float = Field(default=48, description="Copy block width %")
    text_align: str = Field(default="left", description="left | center | right")
    hero_x: float = Field(default=76, description="Hero center X %")
    hero_y: float = Field(default=50, description="Hero center Y %")
    hero_w: float = Field(default=46, description="Hero width %")
    hero_h: float = Field(default=92, description="Hero height % (may exceed 100 to crop-grow)")
    hero_behind: bool = Field(default=False, description="Place the hero BEHIND the copy so text can sit over it")


class HeadlineRun(BaseModel):
    """One styled segment of the headline (per-word emphasis)."""

    text: str = Field(description="Segment text")
    b: bool = Field(default=False, description="Bold/heavy")
    i: bool = Field(default=False, description="Italic")
    u: bool = Field(default=False, description="Underline")
    color: str | None = Field(default=None, description="Hex/rgb color for this word, or null")
    scale: float = Field(default=1.0, description="Relative size 0.6-2.0 to enlarge a key word")


class HeadlineStyle(BaseModel):
    runs: list[HeadlineRun] = Field(default_factory=list, description="Headline split into styled runs")


def clamp_layout(ad: "ArtDirection") -> dict:
    """Project an ArtDirection onto a safe layout dict the banner consumes."""

    def c(v: float, lo: float, hi: float, d: float) -> float:
        try:
            return max(lo, min(hi, float(v)))
        except (TypeError, ValueError):
            return d

    align = (ad.text_align or "left").strip().lower()
    if align not in {"left", "center", "right"}:
        align = "left"
    return {
        "textX": c(ad.text_x, 2, 60, 6),
        "textY": c(ad.text_y, 10, 90, 50),
        "textW": c(ad.text_w, 24, 70, 48),
        "textAlign": align,
        "heroX": c(ad.hero_x, 20, 98, 76),
        "heroY": c(ad.hero_y, 10, 90, 50),
        # Hero may grow large (up to 85% wide / 130% tall to crop-grow).
        "heroW": c(ad.hero_w, 24, 85, 46),
        "heroH": c(ad.hero_h, 60, 130, 92),
        "heroBehind": bool(ad.hero_behind),
        "aspectRatio": 2.4,
    }


def _luminance(hex_color: str) -> float | None:
    """Perceived luminance 0-1 of a #rgb/#rrggbb color, or None if unparsable."""
    c = (hex_color or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) < 6:
        return None
    try:
        r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def coerce_runs(runs: list, full_headline: str, *, ink: str | None = None) -> list[dict]:
    """Sanitize proposed headline runs; fall back to a single plain run when the
    concatenated text drifts too far from the real headline (anti-fabrication).

    Emphasis colors are gated by luminance against the copy `ink` (which the
    background was designed for): on a light/bright background (dark ink) only dark
    emphasis colors pass; on a dark background only light ones. This keeps the agent
    free to 'play' with color while preventing low-contrast (e.g. orange-on-orange).
    """

    ink_lum = _luminance(ink or "#111111")
    light_bg = (ink_lum if ink_lum is not None else 0.1) < 0.5  # dark ink ⇒ light bg

    def _color(c: str | None) -> str | None:
        c = (c or "").strip()
        import re

        if not (re.fullmatch(r"#[0-9a-fA-F]{3,8}", c) or re.fullmatch(r"rgba?\([\d.,\s]+\)", c)):
            return None
        lum = _luminance(c) if c.startswith("#") else None
        if lum is not None:
            # Drop low-contrast emphasis. On a bright/light background only genuinely
            # DARK emphasis colors reliably contrast (a mid/bright tint risks hue-clash
            # like orange-on-orange); the vision review strips any that still slip through.
            if light_bg and lum > 0.5:
                return None
            if not light_bg and lum < 0.5:
                return None
        return c

    out: list[dict] = []
    for r in runs or []:
        get = (lambda k, d=None: r.get(k, d)) if isinstance(r, dict) else (lambda k, d=None: getattr(r, k, d))
        text = str(get("text", "") or "")
        if not text:
            continue
        try:
            scale = max(0.6, min(2.0, float(get("scale", 1.0) or 1.0)))
        except (TypeError, ValueError):
            scale = 1.0
        out.append({
            "text": text, "b": bool(get("b")), "i": bool(get("i")), "u": bool(get("u")),
            "color": _color(get("color")), "scale": scale,
        })
    joined = " ".join(p["text"] for p in out).split()
    if not out or " ".join(joined).lower().replace(" ", "") != (full_headline or "").lower().replace(" ", ""):
        # Runs don't reconstruct the headline → don't risk altered copy.
        return []
    return out


def coerce_pairing(display: str, body: str) -> tuple[str, str]:
    """Snap a proposed pairing onto the allow-list (case-insensitive), else defaults."""

    def _match(value: str, allowed: list[str], default: str) -> str:
        v = (value or "").strip().lower()
        for name in allowed:
            if name.lower() == v:
                return name
        return default

    return (
        _match(display, DISPLAY_FONTS, "Space Grotesk"),
        _match(body, BODY_FONTS, "Inter"),
    )


__all__ = ["FontPairing", "DISPLAY_FONTS", "BODY_FONTS", "coerce_pairing"]
