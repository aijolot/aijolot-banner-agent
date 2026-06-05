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
