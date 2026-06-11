from __future__ import annotations

import pytest

from app.schemas.brand import BrandContext
from app.services.brands.font_roles import (
    font_aesthetic_hint,
    font_prompt_lines,
    quote_stack,
    resolve_font_category,
    resolve_font_family,
    resolve_font_stack,
    typography_config,
)


def _approved(family: str = "Space Grotesk", **overrides) -> dict:
    font = {
        "family": family,
        "css_stack": "Space Grotesk, Brand Fall, sans-serif",
        "category": "sans",
        "source": "gemini_suggested",
        "status": "approved",
        "recommended_roles": ["display", "headline"],
        "rationale": "techy grotesk",
        "evidence_refs": ["theme_settings:type_header_font"],
    }
    font.update(overrides)
    return font


def _brand(typography: dict | None) -> dict:
    brand: dict = {"name": "Demo Brand", "palette": [{"name": "Ink", "hex": "#111111"}]}
    if typography is not None:
        brand["typography"] = typography
    return brand


# ---------------------------------------------------------------------------
# quote_stack
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Space Grotesk, sans-serif", '"Space Grotesk", sans-serif'),
        ('"Space Grotesk", sans-serif', '"Space Grotesk", sans-serif'),
        ("'Helvetica Neue', Helvetica, sans-serif", "'Helvetica Neue', Helvetica, sans-serif"),
        ("Inter", "Inter"),
        ("sans-serif", "sans-serif"),
        ("  Space   Grotesk  ,   serif ", '"Space Grotesk", serif'),
        ("Inter,, sans-serif", "Inter, sans-serif"),
        ("", ""),
    ],
)
def test_quote_stack_quotes_multiword_families_and_keeps_generics(raw: str, expected: str) -> None:
    assert quote_stack(raw) == expected


# ---------------------------------------------------------------------------
# resolve_font_stack
# ---------------------------------------------------------------------------


def test_resolver_prefers_approved_css_stack_case_insensitively() -> None:
    brand = _brand({"display": "space grotesk", "body": "Inter", "approved_fonts": [_approved()]})

    assert resolve_font_stack(brand, "display") == '"Space Grotesk", "Brand Fall", sans-serif'


def test_resolver_ignores_non_approved_status_entries() -> None:
    brand = _brand({"display": "Space Grotesk", "body": "Inter", "approved_fonts": [_approved(status="candidate")]})

    # No approved match -> built stack, not the candidate's custom fallback chain.
    assert resolve_font_stack(brand, "display") == '"Space Grotesk", sans-serif'


def test_resolver_role_fallback_chains() -> None:
    brand = _brand({"display": "Space Grotesk", "body": "Inter"})

    assert resolve_font_stack(brand, "headline") == '"Space Grotesk", sans-serif'
    assert resolve_font_stack(brand, "accent") == '"Space Grotesk", sans-serif'
    assert resolve_font_stack(brand, "caption") == "Inter, sans-serif"

    explicit = _brand({"display": "Space Grotesk", "body": "Inter", "headline": "Oswald"})
    assert resolve_font_stack(explicit, "accent") == 'Oswald, sans-serif'


def test_resolver_treats_comma_value_as_existing_stack() -> None:
    brand = _brand({"display": "Helvetica Neue, Helvetica, sans-serif", "body": "Inter"})

    assert resolve_font_stack(brand, "display") == '"Helvetica Neue", Helvetica, sans-serif'


def test_resolver_builds_stack_from_single_family_with_category_generic() -> None:
    brand = _brand({"display": "Playfair Display", "body": "IBM Plex Mono"})

    assert resolve_font_stack(brand, "display") == '"Playfair Display", serif'
    assert resolve_font_stack(brand, "body") == '"IBM Plex Mono", monospace'


def test_resolver_returns_empty_for_missing_or_blank_typography() -> None:
    assert resolve_font_stack(_brand(None), "display") == ""
    assert resolve_font_stack(_brand({"display": "", "body": ""}), "body") == ""
    assert resolve_font_stack(None, "display") == ""
    assert resolve_font_stack(_brand({"display": "Inter", "body": "Inter"}), "not-a-role") == ""


def test_resolver_drops_unsafe_dict_values_instead_of_emitting_them() -> None:
    brand = _brand({"display": 'Evil;} body{background:url(x)', "body": "Inter</style>"})

    assert resolve_font_stack(brand, "display") == ""
    assert resolve_font_stack(brand, "body") == ""

    # Unsafe approved stack falls back to a rebuilt stack from family + category.
    rebuilt = _brand({
        "display": "Space Grotesk",
        "body": "Inter",
        "approved_fonts": [_approved(css_stack='Space Grotesk, url(evil)')],
    })
    assert resolve_font_stack(rebuilt, "display") == '"Space Grotesk", sans-serif'


def test_resolver_accepts_brand_context_model() -> None:
    brand = BrandContext(
        id="demo",
        name="Demo",
        palette=[{"name": "Ink", "hex": "#111111"}],
        typography={"display": "Space Grotesk", "body": "Inter", "approved_fonts": [_approved()]},
        shopify={"store_domain": "demo.myshopify.com"},
    )

    assert resolve_font_stack(brand, "display") == '"Space Grotesk", "Brand Fall", sans-serif'
    assert resolve_font_family(brand, "display") == "Space Grotesk"
    assert resolve_font_category(brand, "display") == "sans"


# ---------------------------------------------------------------------------
# font_prompt_lines / font_aesthetic_hint
# ---------------------------------------------------------------------------


def test_font_prompt_lines_mark_approved_with_category_and_legacy() -> None:
    brand = _brand({"display": "Space Grotesk", "body": "Inter", "approved_fonts": [_approved()]})

    assert font_prompt_lines(brand) == [
        "display: Space Grotesk (approved, sans)",
        "body: Inter (legacy)",
    ]


def test_font_prompt_lines_list_only_direct_roles_and_strip_stack_quotes() -> None:
    brand = _brand({"display": "'Helvetica Neue', sans-serif", "body": "Inter", "accent": "Oswald"})

    assert font_prompt_lines(brand) == [
        "display: Helvetica Neue (legacy)",
        "body: Inter (legacy)",
        "accent: Oswald (legacy)",
    ]
    assert font_prompt_lines(_brand(None)) == []
    assert font_prompt_lines(_brand({"display": "", "body": ""})) == []


def test_font_aesthetic_hint_maps_display_category_and_never_names_fonts() -> None:
    sans = _brand({"display": "Space Grotesk", "body": "Inter"})
    serif = _brand({"display": "Playfair Display", "body": "Inter"})
    unknown = _brand({"display": "Zorblat", "body": "Zorblat"})

    assert font_aesthetic_hint(sans) == "geometric sans-serif aesthetic"
    assert font_aesthetic_hint(serif) == "classic editorial serif aesthetic"
    assert "Space Grotesk" not in font_aesthetic_hint(sans)
    assert font_aesthetic_hint(unknown) == ""
    assert font_aesthetic_hint(_brand(None)) == ""

    approved_category = _brand({
        "display": "Zorblat",
        "body": "Inter",
        "approved_fonts": [_approved(family="Zorblat", category="handwritten", css_stack="Zorblat, cursive")],
    })
    assert font_aesthetic_hint(approved_category) == "organic handcrafted aesthetic"


# ---------------------------------------------------------------------------
# typography_config
# ---------------------------------------------------------------------------


def test_typography_config_builds_json_safe_block() -> None:
    brand = _brand({"display": "Space Grotesk", "body": "Inter", "approved_fonts": [_approved()]})

    config = typography_config(brand)

    assert config["stacks"] == {
        "display": '"Space Grotesk", "Brand Fall", sans-serif',
        "body": "Inter, sans-serif",
    }
    assert config["approved_fonts"] == [
        {"family": "Space Grotesk", "category": "sans", "recommended_roles": ["display", "headline"]}
    ]
    assert config["legacy"] == {"display": "Space Grotesk", "body": "Inter"}
    # No rationale/evidence noise in the Liquid config.
    assert "rationale" not in config["approved_fonts"][0]


def test_typography_config_omits_unassigned_roles_and_handles_missing_typography() -> None:
    legacy = typography_config(_brand({"display": "Archivo Black", "body": "Helvetica Neue, sans-serif"}))

    assert set(legacy["stacks"]) == {"display", "body"}
    assert legacy["stacks"]["body"] == '"Helvetica Neue", sans-serif'
    assert legacy["approved_fonts"] == []

    assert typography_config(_brand(None)) == {}
    assert typography_config({"name": "Demo"}) == {}
