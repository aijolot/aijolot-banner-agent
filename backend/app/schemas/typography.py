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
        "textW": c(ad.text_w, 24, 66, 48),
        "textAlign": align,
        "heroX": c(ad.hero_x, 30, 98, 76),
        "heroY": c(ad.hero_y, 10, 90, 50),
        "heroW": c(ad.hero_w, 24, 66, 46),
        "heroH": 92,
        "aspectRatio": 2.4,
    }


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
