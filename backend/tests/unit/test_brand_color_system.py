from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.brand import (
    BrandColorRole,
    BrandColorSystem,
    BrandColorVariant,
    BrandContext,
    PaletteColor,
    color_system_from_palette,
    ensure_color_system,
)


def _seed_payload() -> dict:
    return {
        "id": "demo_brand",
        "name": "Demo Brand",
        "palette": [
            {"name": "Ink", "hex": "#0e0e10"},
            {"name": "Bone", "hex": "#ede8e0"},
            {"name": "Electric", "hex": "#3d5afe"},
        ],
        "typography": {"display": "Inter", "body": "Arial"},
        "voice": {"tone": ["Premium"], "prohibited_words": [], "required_phrases": []},
        "shopify": {"store_domain": "demo.myshopify.com"},
        "notes": "Legacy seed-style brand without color_system.",
    }


def test_brand_context_accepts_seed_style_payload_without_color_system() -> None:
    brand = BrandContext(**_seed_payload())

    assert brand.id == "demo_brand"
    assert brand.palette[0].hex == "#0E0E10"
    assert brand.color_system is not None
    assert brand.color_system.primary.hex == "#0E0E10"
    assert brand.color_system.secondary.hex == "#EDE8E0"
    assert brand.color_system.tertiary.hex == "#3D5AFE"


def test_color_system_builds_from_legacy_palette_order() -> None:
    palette = [
        PaletteColor(name="Primary legacy", hex="#111111"),
        PaletteColor(name="Secondary legacy", hex="#222222"),
        PaletteColor(name="Tertiary legacy", hex="#333333"),
    ]

    color_system = color_system_from_palette(palette)

    assert color_system.primary.key == "primary"
    assert color_system.primary.label == "Primary"
    assert color_system.primary.hex == "#111111"
    assert color_system.primary.usage_hint == (
        "Main brand color for dominant identity moments, headline emphasis, and major visual anchors."
    )
    assert color_system.primary.agent_hint == (
        "Prefer for main brand identity, key text/visual anchors, and high-recognition surfaces."
    )
    assert color_system.secondary.key == "secondary"
    assert color_system.secondary.label == "Secondary"
    assert color_system.secondary.hex == "#222222"
    assert color_system.tertiary.key == "tertiary"
    assert color_system.tertiary.label == "Tertiary / Accent"
    assert color_system.tertiary.hex == "#333333"


def test_color_system_palette_fallback_reuses_available_colors() -> None:
    one_color_system = color_system_from_palette([PaletteColor(name="Only", hex="#abcdef")])
    assert one_color_system.primary.hex == "#ABCDEF"
    assert one_color_system.secondary.hex == "#ABCDEF"
    assert one_color_system.tertiary.hex == "#ABCDEF"

    two_color_system = color_system_from_palette(
        [PaletteColor(name="First", hex="#111111"), PaletteColor(name="Second", hex="#222222")]
    )
    assert two_color_system.primary.hex == "#111111"
    assert two_color_system.secondary.hex == "#222222"
    assert two_color_system.tertiary.hex == "#222222"


def test_ensure_color_system_returns_brand_with_generated_roles() -> None:
    brand = BrandContext(**_seed_payload())

    normalized = ensure_color_system(brand)

    assert normalized.color_system is not None
    assert normalized.color_system.primary.hex == "#0E0E10"
    assert normalized.color_system.secondary.hex == "#EDE8E0"
    assert normalized.color_system.tertiary.hex == "#3D5AFE"


def test_hex_values_normalize_to_uppercase_for_role_colors_and_variants() -> None:
    role = BrandColorRole(
        key="primary",
        label="Primary",
        hex="  #abcdef  ",
        variants=[BrandColorVariant(name="Light", hex="#a1b2c3", usage_hint="Soft background")],
    )

    assert role.hex == "#ABCDEF"
    assert role.variants[0].hex == "#A1B2C3"


def test_invalid_role_keys_fail_validation() -> None:
    with pytest.raises(ValidationError):
        BrandColorRole(key="accent", label="Accent", hex="#123456")

    with pytest.raises(ValidationError):
        BrandColorSystem(
            primary=BrandColorRole(key="secondary", label="Secondary", hex="#111111"),
            secondary=BrandColorRole(key="secondary", label="Secondary", hex="#222222"),
            tertiary=BrandColorRole(key="tertiary", label="Tertiary", hex="#333333"),
        )


def test_explicit_color_system_preserves_role_metadata_and_variants() -> None:
    payload = _seed_payload()
    payload["color_system"] = {
        "primary": {
            "key": "primary",
            "label": "Hero Green",
            "hex": "#1f4d2e",
            "usage_hint": "Use for hero headlines.",
            "agent_hint": "Prioritize for dominant brand identity.",
            "variants": [
                {
                    "name": "Hero Green Dark",
                    "hex": "#0f2d1a",
                    "usage_hint": "Use for dark anchors.",
                    "source": "seed_migration",
                }
            ],
        },
        "secondary": {
            "key": "secondary",
            "label": "Soft Leaf",
            "hex": "#7cb342",
            "usage_hint": "Use for support surfaces.",
            "agent_hint": "Use for balance around the hero color.",
            "variants": [],
        },
        "tertiary": {
            "key": "tertiary",
            "label": "Coral CTA",
            "hex": "#ff6b5c",
            "usage_hint": "Use for CTA and badges.",
            "agent_hint": "Use sparingly for attention moments.",
            "variants": [
                {"name": "Coral Hover", "hex": "#ff8478", "usage_hint": "CTA hover", "source": "manual"}
            ],
        },
    }

    brand = BrandContext(**payload)

    assert brand.color_system is not None
    assert brand.color_system.primary.label == "Hero Green"
    assert brand.color_system.primary.hex == "#1F4D2E"
    assert brand.color_system.primary.usage_hint == "Use for hero headlines."
    assert brand.color_system.primary.agent_hint == "Prioritize for dominant brand identity."
    assert brand.color_system.primary.variants[0].name == "Hero Green Dark"
    assert brand.color_system.primary.variants[0].hex == "#0F2D1A"
    assert brand.color_system.primary.variants[0].usage_hint == "Use for dark anchors."
    assert brand.color_system.primary.variants[0].source == "seed_migration"
    assert brand.color_system.tertiary.label == "Coral CTA"
    assert brand.color_system.tertiary.variants[0].hex == "#FF8478"
