"""brand-context-load skill."""

from __future__ import annotations

from typing import Any

from app.agents.tools import brand_fs
from app.schemas.brand import BrandContext, PaletteColor, Shopify, Typography, Voice

_DEFAULT_PALETTE = [PaletteColor(name="Ink", hex="#111111"), PaletteColor(name="Canvas", hex="#FFFFFF")]


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_brand_context(value: BrandContext | dict[str, Any]) -> BrandContext:
    """Coerce brand input into the persisted BrandContext contract.

    Accepts API/DB-shaped dictionaries and fills conservative defaults for
    optional creative fields so downstream skills can use one stable model.
    """
    if isinstance(value, BrandContext):
        return value

    data = dict(value or {})
    brand_id = str(data.get("id") or data.get("slug") or data.get("brand_id") or "default").strip().lower()
    name = str(data.get("name") or brand_id or "Default Brand").strip()

    palette_in = data.get("palette") or _DEFAULT_PALETTE
    palette: list[dict[str, str]] = []
    for idx, item in enumerate(palette_in):
        if isinstance(item, PaletteColor):
            palette.append(item.model_dump())
        elif isinstance(item, dict):
            palette.append({"name": str(item.get("name") or f"Color {idx + 1}"), "hex": str(item.get("hex") or "#111111")})
        elif isinstance(item, str):
            palette.append({"name": f"Color {idx + 1}", "hex": item})
    if not palette:
        palette = [color.model_dump() for color in _DEFAULT_PALETTE]

    voice_in = data.get("voice") or {}
    if isinstance(voice_in, Voice):
        voice = voice_in.model_dump()
    else:
        if not isinstance(voice_in, dict):
            voice_in = {"tone": voice_in}
        voice = {
            "tone": _as_string_list(voice_in.get("tone") or data.get("tone")),
            "prohibited_words": _as_string_list(voice_in.get("prohibited_words") or data.get("prohibited_words")),
            "required_phrases": _as_string_list(voice_in.get("required_phrases") or data.get("required_phrases")),
        }

    typography_in = data.get("typography") or {}
    typography = typography_in.model_dump() if isinstance(typography_in, Typography) else typography_in
    shopify_in = data.get("shopify") or {}
    shopify = shopify_in.model_dump() if isinstance(shopify_in, Shopify) else {
        "store_domain": shopify_in.get("store_domain") or data.get("store_domain") or "example.myshopify.com",
        "theme_id": shopify_in.get("theme_id") or data.get("theme_id"),
        "default_placement": shopify_in.get("default_placement") or data.get("default_placement") or "hero",
    }

    return BrandContext.model_validate({
        "id": brand_id,
        "name": name,
        "palette": palette,
        "typography": typography or {},
        "voice": voice,
        "logo_url": data.get("logo_url"),
        "image_style_directives": _as_string_list(data.get("image_style_directives")),
        "shopify": shopify,
        "notes": str(data.get("notes") or data.get("description") or ""),
    })


async def run(brand_id: str | None = None, *, brand_context: BrandContext | dict[str, Any] | None = None) -> BrandContext:
    if brand_context is not None:
        return normalize_brand_context(brand_context)
    if not brand_id:
        raise ValueError("brand_id is required when brand_context is not provided")
    return normalize_brand_context(brand_fs.read(brand_id))
