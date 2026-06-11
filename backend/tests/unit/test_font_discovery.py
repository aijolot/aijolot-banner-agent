"""Unit tests for deterministic font candidate extraction + curated seeds (Task 6)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.brand import FontCandidate
from app.schemas.brand_discovery import BrandDiscoverySnapshot, DiscoveredFont
from app.services.brands.font_discovery import (
    SYSTEM_SEED_FONTS,
    build_css_stack,
    font_candidates_from_snapshot,
    guess_font_category,
)

THEME_SOURCE = "theme_settings:config/settings_data.json"
CSS_SOURCE = "css:assets/base.css"
SECTION_SOURCE = "section:sections/hero.liquid"


def _snapshot(fonts: list[dict]) -> BrandDiscoverySnapshot:
    return BrandDiscoverySnapshot(
        id="disc_abc123def456",
        brand_id="demo_brand",
        shop_domain="demo-apparel.myshopify.com",
        status="succeeded",
        discovered_at=datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc),
        fonts=fonts,
    )


# ---------------------------------------------------------------------------
# Snapshot -> FontCandidate mapping
# ---------------------------------------------------------------------------


def test_maps_discovered_fonts_to_candidates_with_source_evidence_and_rationale() -> None:
    snapshot = _snapshot(
        [
            {"family": "Assistant", "source": THEME_SOURCE, "confidence": 0.9, "sample_usage": "theme setting current.type_header_font"},
            {"family": "Archivo Black", "source": CSS_SOURCE, "css_stack": "'Archivo Black', sans-serif", "confidence": 0.55},
            {"family": "Mystery Sans", "source": "shop_metadata", "confidence": 0.2},
        ]
    )

    candidates = font_candidates_from_snapshot(snapshot)

    assert [candidate.family for candidate in candidates] == ["Assistant", "Archivo Black", "Mystery Sans"]
    assert all(isinstance(candidate, FontCandidate) for candidate in candidates)
    assert all(candidate.status == "candidate" for candidate in candidates)
    assert all(candidate.recommended_roles == [] for candidate in candidates)

    theme_font = candidates[0]
    assert theme_font.source == "shopify_theme"  # theme_settings* prefix
    assert theme_font.evidence_refs == [THEME_SOURCE]
    assert theme_font.rationale == f"Discovered in {THEME_SOURCE} (theme setting current.type_header_font)"

    css_font = candidates[1]
    assert css_font.source == "storefront_css"  # css* prefix
    assert css_font.evidence_refs == [CSS_SOURCE]
    assert css_font.rationale == f"Discovered in {CSS_SOURCE}"

    other_font = candidates[2]
    assert other_font.source == "shopify_theme"  # anything else maps to shopify_theme
    assert other_font.evidence_refs == ["shop_metadata"]


def test_css_stack_kept_when_present_and_built_with_quoting_and_generic_when_missing() -> None:
    snapshot = _snapshot(
        [
            {"family": "Archivo Black", "source": CSS_SOURCE, "css_stack": "'Archivo Black', sans-serif", "confidence": 0.6},
            {"family": "Playfair Display", "source": THEME_SOURCE, "confidence": 0.9},  # no stack -> built
            {"family": "Lora", "source": THEME_SOURCE, "confidence": 0.8},  # single word -> unquoted
            {"family": "IBM Plex Mono", "source": CSS_SOURCE, "confidence": 0.7},
        ]
    )

    by_family = {candidate.family: candidate for candidate in font_candidates_from_snapshot(snapshot)}

    assert by_family["Archivo Black"].css_stack == "'Archivo Black', sans-serif"  # discovered stack kept
    assert by_family["Playfair Display"].css_stack == '"Playfair Display", serif'  # quoted + category generic
    assert by_family["Lora"].css_stack == "Lora, serif"
    assert by_family["IBM Plex Mono"].css_stack == '"IBM Plex Mono", monospace'


def test_build_css_stack_helper_quotes_multiword_and_picks_generic() -> None:
    assert build_css_stack("Inter", "sans") == "Inter, sans-serif"
    assert build_css_stack("Space  Grotesk", "sans") == '"Space Grotesk", sans-serif'  # whitespace collapsed
    assert build_css_stack("Caveat", "handwritten") == "Caveat, cursive"
    assert build_css_stack("Whatever", "unknown") == "Whatever, sans-serif"
    assert build_css_stack("Whatever", "display") == "Whatever, sans-serif"


@pytest.mark.parametrize(
    ("family", "category"),
    [
        ("IBM Plex Mono", "mono"),
        ("Source Code Pro", "mono"),
        ("Courier New", "mono"),
        ("Playfair Display", "serif"),  # known serif name wins over the Display keyword
        ("Merriweather", "serif"),
        ("Lora", "serif"),
        ("Georgia", "serif"),
        ("Garamond", "serif"),
        ("Times New Roman", "serif"),
        ("PT Serif", "serif"),  # "Serif" in name without "Sans"
        ("Source Sans Serif", "sans"),  # "Sans" beats the bare "Serif" token
        ("Dancing Script", "handwritten"),
        ("Caveat", "handwritten"),
        ("Bebas Neue", "display"),
        ("Oswald", "display"),
        ("Big Display Face", "display"),
        ("Comic Sans MS", "sans"),
        ("Helvetica Neue", "sans"),
        ("Space Grotesk", "sans"),
        ("Inter", "sans"),
        ("Totally Novel Face", "unknown"),
    ],
)
def test_guess_font_category_keyword_heuristics(family: str, category: str) -> None:
    assert guess_font_category(family) == category


def test_dedupes_by_lowercased_family_keeping_best_confidence_stack_and_all_sources() -> None:
    snapshot = _snapshot(
        [
            {"family": "archivo black", "source": CSS_SOURCE, "css_stack": "'Archivo Black', sans-serif", "confidence": 0.55},
            {"family": "Archivo Black", "source": THEME_SOURCE, "confidence": 0.9},  # higher confidence, no stack
            {"family": "Archivo Black", "source": THEME_SOURCE, "confidence": 0.1},  # duplicate source, ignored
        ]
    )

    candidates = font_candidates_from_snapshot(snapshot)

    assert len(candidates) == 1
    winner = candidates[0]
    assert winner.family == "Archivo Black"  # highest-confidence entry wins the spelling
    assert winner.source == "shopify_theme"  # ...and the source mapping
    assert winner.css_stack == "'Archivo Black', sans-serif"  # non-empty stack merged from the duplicate
    assert winner.evidence_refs == [CSS_SOURCE, THEME_SOURCE]  # every distinct source kept
    assert winner.rationale == f"Discovered in {THEME_SOURCE}"


def test_sorts_by_confidence_desc_then_family_name() -> None:
    snapshot = _snapshot(
        [
            {"family": "Zilla Slab", "source": CSS_SOURCE, "confidence": 0.5},
            {"family": "Assistant", "source": CSS_SOURCE, "confidence": 0.5},
            {"family": "Lora", "source": THEME_SOURCE, "confidence": 0.9},
        ]
    )

    families = [candidate.family for candidate in font_candidates_from_snapshot(snapshot)]

    assert families == ["Lora", "Assistant", "Zilla Slab"]


def test_accepts_snapshot_as_dict_and_skips_invalid_font_entries() -> None:
    payload = _snapshot([{"family": "Lora", "source": THEME_SOURCE, "confidence": 0.9}]).model_dump(mode="json")
    payload["fonts"].append({"family": "Bad<script>", "source": CSS_SOURCE, "confidence": 0.7})  # invalid family
    payload["fonts"].append({"source": CSS_SOURCE})  # missing family
    payload["fonts"].append("not-a-font")  # garbage entry

    candidates = font_candidates_from_snapshot(payload)

    assert [candidate.family for candidate in candidates] == ["Lora"]
    assert candidates[0].source == "shopify_theme"


def test_empty_or_fontless_snapshots_return_no_candidates() -> None:
    assert font_candidates_from_snapshot(_snapshot([])) == []
    assert font_candidates_from_snapshot({}) == []
    assert font_candidates_from_snapshot({"fonts": None}) == []


def test_unsafe_constructed_font_is_dropped_not_raised() -> None:
    # Defense in depth: bypass DiscoveredFont validation to prove the converter
    # drops (not raises) anything FontCandidate would reject.
    bad = DiscoveredFont.model_construct(
        family="Eval<script>", source=CSS_SOURCE, css_stack="", confidence=0.9, sample_usage=""
    )
    good = DiscoveredFont(family="Lora", source=THEME_SOURCE, confidence=0.5)
    snapshot = BrandDiscoverySnapshot.model_construct(
        id="disc_abc123def456",
        brand_id="demo_brand",
        shop_domain="demo-apparel.myshopify.com",
        status="succeeded",
        discovered_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        fonts=[bad, good],
    )

    candidates = font_candidates_from_snapshot(snapshot)

    assert [candidate.family for candidate in candidates] == ["Lora"]


# ---------------------------------------------------------------------------
# Curated seed pool
# ---------------------------------------------------------------------------


def test_system_seed_fonts_are_complete_valid_and_clearly_labeled() -> None:
    families = [seed.family for seed in SYSTEM_SEED_FONTS]

    assert families == [
        "Inter",
        "DM Sans",
        "Work Sans",
        "Manrope",
        "Space Grotesk",
        "Archivo",
        "Playfair Display",
        "Lora",
        "Merriweather",
        "Libre Baskerville",
        "Poppins",
        "Montserrat",
        "Oswald",
        "Bebas Neue",
        "IBM Plex Mono",
        "JetBrains Mono",
    ]
    assert len({family.lower() for family in families}) == len(families)  # unique

    for seed in SYSTEM_SEED_FONTS:
        assert isinstance(seed, FontCandidate)
        assert seed.source == "system_seed"
        assert seed.status == "candidate"
        assert seed.css_stack.strip()
        assert "(" not in seed.css_stack and "<" not in seed.css_stack
        assert seed.css_stack.split(",")[-1].strip() in {"sans-serif", "serif", "monospace", "cursive"}
        assert seed.category in {"sans", "serif", "display", "mono", "handwritten"}  # never unknown
        assert seed.recommended_roles, f"{seed.family} must recommend at least one role"
        assert seed.rationale.startswith("Curated seed (non-AI):")
        assert seed.evidence_refs == []

    # FontCandidate round-trips through strict validation (proves stacks/families are safe).
    for seed in SYSTEM_SEED_FONTS:
        FontCandidate.model_validate(seed.model_dump())


def test_seed_pool_covers_the_expected_role_and_category_mix() -> None:
    by_family = {seed.family: seed for seed in SYSTEM_SEED_FONTS}

    assert by_family["Space Grotesk"].recommended_roles == ["display", "headline"]
    assert by_family["Inter"].recommended_roles == ["body", "caption"]
    assert by_family["Playfair Display"].recommended_roles == ["display"]
    assert by_family["IBM Plex Mono"].category == "mono"
    assert by_family["IBM Plex Mono"].recommended_roles == ["accent", "caption"]

    categories = {seed.category for seed in SYSTEM_SEED_FONTS}
    assert {"sans", "serif", "display", "mono"} <= categories
    roles_covered = {role for seed in SYSTEM_SEED_FONTS for role in seed.recommended_roles}
    assert roles_covered == {"display", "headline", "body", "accent", "caption"}
