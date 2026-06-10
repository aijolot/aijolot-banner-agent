from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.brand import (
    BrandColorRole,
    BrandContext,
    FontCandidate,
    Typography,
)
from app.schemas.brand_discovery import (
    BrandColorRecommendation,
    BrandDiscoveryAsset,
    BrandDiscoverySnapshot,
    BrandRecommendationDraft,
    DiscoveredColor,
    DiscoveredFont,
)

INJECTION_VALUES = [
    "Inter; } body { background:url(javascript:alert(1)) }",
    "<script>alert(1)</script>",
    "Inter`touch /tmp/pwned`",
    "@import 'evil'",
    "Inter\\Arial",
    "Inter/Arial",
    "Inter&copy",
    "Inter\x00Bold",
    "expression(alert(1))",
]


def _seed_payload() -> dict:
    return {
        "id": "demo_brand",
        "name": "Demo Brand",
        "palette": [
            {"name": "Ink", "hex": "#0e0e10"},
            {"name": "Bone", "hex": "#ede8e0"},
            {"name": "Electric", "hex": "#3d5afe"},
        ],
        "typography": {"display": "Space Grotesk", "body": "Inter"},
        "voice": {"tone": ["Premium"], "prohibited_words": [], "required_phrases": []},
        "shopify": {"store_domain": "demo.myshopify.com"},
        "notes": "Legacy seed-style brand.",
    }


def _font_candidate_payload(**overrides) -> dict:
    payload = {
        "family": "Sora",
        "css_stack": '"Sora", sans-serif',
        "category": "sans",
        "source": "gemini_suggested",
        "recommended_roles": ["headline"],
        "rationale": "Geometric sans that matches the brand wordmark.",
        "evidence_refs": ["snapshot:fonts:0"],
    }
    payload.update(overrides)
    return payload


def _snapshot_payload(**overrides) -> dict:
    payload = {
        "id": "run_001",
        "brand_id": "demo_brand",
        "store_id": "store_1",
        "shop_domain": "demo.myshopify.com",
        "status": "succeeded",
        "discovered_at": "2026-06-09T12:00:00Z",
        "source_summary": "Theme settings + main CSS asset.",
        "assets": [
            {
                "kind": "logo",
                "url": "https://cdn.shopify.com/demo/logo.svg",
                "theme_asset_key": "config/settings_data.json",
                "content_type": "image/svg+xml",
                "source": "settings_data.sections.header.logo",
                "metadata": {"width": 240},
            }
        ],
        "colors": [
            {
                "hex": "#0e0e10",
                "name": "Ink",
                "source": "settings_data.colors.primary",
                "confidence": 0.9,
                "usage_hint": "Theme primary color",
            }
        ],
        "fonts": [
            {
                "family": "Space Grotesk",
                "source": "assets/theme.css:font-family",
                "css_stack": '"Space Grotesk", sans-serif',
                "confidence": 0.7,
                "sample_usage": "h1, .hero-title",
            }
        ],
        "theme_metadata": {"theme_name": "Dawn", "theme_id": "128934771"},
        "errors": [],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Backward compatibility: legacy Typography / BrandContext payloads
# ---------------------------------------------------------------------------


def test_typography_supports_legacy_display_body_only() -> None:
    typography = Typography(**{"display": "Space Grotesk", "body": "Inter"})

    assert typography.display == "Space Grotesk"
    assert typography.body == "Inter"
    assert typography.headline is None
    assert typography.accent is None
    assert typography.approved_fonts == []
    assert typography.discarded_fonts == []


def test_typography_defaults_remain_unchanged() -> None:
    typography = Typography()

    assert typography.display == "Space Grotesk"
    assert typography.body == "Inter"
    assert typography.approved_fonts == []


def test_existing_brand_context_payload_still_validates() -> None:
    brand = BrandContext(**_seed_payload())

    assert brand.color_system is not None
    assert brand.color_system.primary.hex == "#0E0E10"
    assert brand.typography.display == "Space Grotesk"
    assert brand.typography.body == "Inter"
    assert brand.typography.approved_fonts == []
    assert brand.typography.discarded_fonts == []


def test_typography_allows_empty_strings_for_legacy_fields() -> None:
    # Empty display/body strings were valid before the font system; keep them valid.
    typography = Typography(display="", body="")

    assert typography.display == ""
    assert typography.body == ""


# ---------------------------------------------------------------------------
# New typography fields and FontCandidate lifecycle
# ---------------------------------------------------------------------------


def test_typography_accepts_role_fields_and_font_lists() -> None:
    typography = Typography(
        display="Space Grotesk",
        body="Inter",
        headline="Archivo Black",
        accent="Fraunces",
        approved_fonts=[_font_candidate_payload(status="approved")],
        discarded_fonts=[
            _font_candidate_payload(
                family="Comic Neue",
                css_stack='"Comic Neue", cursive',
                status="discarded",
                recommended_roles=[],
                rationale="Off-brand playful tone.",
            )
        ],
    )

    assert typography.headline == "Archivo Black"
    assert typography.accent == "Fraunces"
    assert typography.approved_fonts[0].family == "Sora"
    assert typography.approved_fonts[0].status == "approved"
    assert typography.approved_fonts[0].recommended_roles == ["headline"]
    assert typography.discarded_fonts[0].status == "discarded"


def test_font_candidate_defaults_and_normalization() -> None:
    candidate = FontCandidate(
        family="  Space   Grotesk  ",
        css_stack='  "Space Grotesk",   \'Helvetica Neue\',  sans-serif ',
        source="shopify_theme",
    )

    assert candidate.family == "Space Grotesk"
    assert candidate.css_stack == "\"Space Grotesk\", 'Helvetica Neue', sans-serif"
    assert candidate.category == "unknown"
    assert candidate.status == "candidate"
    assert candidate.recommended_roles == []
    assert candidate.rationale == ""
    assert candidate.evidence_refs == []


def test_font_candidate_rejects_invalid_literals() -> None:
    with pytest.raises(ValidationError):
        FontCandidate(**_font_candidate_payload(status="active"))

    with pytest.raises(ValidationError):
        FontCandidate(**_font_candidate_payload(source="random_website"))

    with pytest.raises(ValidationError):
        FontCandidate(**_font_candidate_payload(category="gothic"))

    with pytest.raises(ValidationError):
        FontCandidate(**_font_candidate_payload(recommended_roles=["hero"]))


def test_font_candidate_requires_family_and_css_stack() -> None:
    with pytest.raises(ValidationError):
        FontCandidate(**_font_candidate_payload(family="   "))

    with pytest.raises(ValidationError):
        FontCandidate(**_font_candidate_payload(css_stack=""))


def test_font_family_keeps_stricter_rule_than_css_stack() -> None:
    # Commas/quotes are legal in a css stack but not in a single family name.
    with pytest.raises(ValidationError):
        FontCandidate(**_font_candidate_payload(family="Inter, sans-serif"))

    with pytest.raises(ValidationError):
        FontCandidate(**_font_candidate_payload(family='"Inter"'))


# ---------------------------------------------------------------------------
# Font safety: CSS/script injection rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", INJECTION_VALUES)
def test_font_candidate_family_rejects_injection(value: str) -> None:
    with pytest.raises(ValidationError):
        FontCandidate(**_font_candidate_payload(family=value))


@pytest.mark.parametrize("value", INJECTION_VALUES)
def test_font_candidate_css_stack_rejects_injection(value: str) -> None:
    with pytest.raises(ValidationError):
        FontCandidate(**_font_candidate_payload(css_stack=value))


@pytest.mark.parametrize("value", INJECTION_VALUES)
@pytest.mark.parametrize("field", ["display", "body", "headline", "accent"])
def test_typography_fields_reject_injection(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        Typography(**{field: value})


@pytest.mark.parametrize("value", INJECTION_VALUES)
def test_discovered_font_family_rejects_injection(value: str) -> None:
    with pytest.raises(ValidationError):
        DiscoveredFont(family=value, source="assets/theme.css")


def test_legitimate_font_values_pass() -> None:
    assert Typography(display="Space Grotesk").display == "Space Grotesk"
    assert Typography(body="Inter").body == "Inter"
    assert Typography(headline="Helvetica Neue, sans-serif").headline == "Helvetica Neue, sans-serif"

    candidate = FontCandidate(
        family="IBM Plex Sans",
        css_stack='"IBM Plex Sans", \'Helvetica Neue\', sans-serif',
        source="system_seed",
    )
    assert candidate.family == "IBM Plex Sans"
    assert candidate.css_stack == "\"IBM Plex Sans\", 'Helvetica Neue', sans-serif"


# ---------------------------------------------------------------------------
# Discovery snapshot
# ---------------------------------------------------------------------------


def test_discovery_snapshot_stores_assets_colors_fonts_with_source_and_confidence() -> None:
    snapshot = BrandDiscoverySnapshot(**_snapshot_payload())

    assert snapshot.status == "succeeded"
    assert snapshot.discovered_at.year == 2026
    assert snapshot.assets[0].kind == "logo"
    assert snapshot.assets[0].source == "settings_data.sections.header.logo"
    assert snapshot.assets[0].metadata == {"width": 240}
    assert snapshot.colors[0].hex == "#0E0E10"  # normalized to uppercase
    assert snapshot.colors[0].source == "settings_data.colors.primary"
    assert snapshot.colors[0].confidence == 0.9
    assert snapshot.fonts[0].family == "Space Grotesk"
    assert snapshot.fonts[0].confidence == 0.7
    assert snapshot.theme_metadata["theme_name"] == "Dawn"
    assert snapshot.errors == []


def test_discovery_snapshot_defaults_for_optional_collections() -> None:
    snapshot = BrandDiscoverySnapshot(
        id="run_002",
        brand_id="demo_brand",
        shop_domain="demo.myshopify.com",
        status="pending",
        discovered_at="2026-06-09T12:00:00Z",
    )

    assert snapshot.store_id is None
    assert snapshot.source_summary == ""
    assert snapshot.assets == []
    assert snapshot.colors == []
    assert snapshot.fonts == []
    assert snapshot.theme_metadata == {}
    assert snapshot.errors == []


def test_discovery_snapshot_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        BrandDiscoverySnapshot(**_snapshot_payload(status="done"))


def test_discovery_asset_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        BrandDiscoveryAsset(kind="video", source="theme")


def test_discovered_color_rejects_invalid_hex_and_confidence() -> None:
    with pytest.raises(ValidationError):
        DiscoveredColor(hex="not-a-color", source="theme")

    with pytest.raises(ValidationError):
        DiscoveredColor(hex="#0E0E10", source="theme", confidence=1.5)

    with pytest.raises(ValidationError):
        DiscoveredColor(hex="#0E0E10", source="theme", confidence=-0.1)


def test_discovered_font_rejects_out_of_range_confidence_and_allows_empty_stack() -> None:
    with pytest.raises(ValidationError):
        DiscoveredFont(family="Inter", source="theme.css", confidence=2.0)

    font = DiscoveredFont(family="Inter", source="theme.css")
    assert font.css_stack == ""
    assert font.confidence == 0.0


# ---------------------------------------------------------------------------
# Recommendation draft + schema-level apply/merge simulation
# ---------------------------------------------------------------------------


def _brand_with_explicit_color_system() -> BrandContext:
    payload = _seed_payload()
    payload["color_system"] = {
        "primary": {
            "key": "primary",
            "label": "Ink",
            "hex": "#0E0E10",
            "usage_hint": "Dominant identity color.",
            "agent_hint": "Anchor headlines and key surfaces.",
            "variants": [
                {"name": "Ink Soft", "hex": "#2A2A2E", "usage_hint": "Soft anchor", "source": "manual"}
            ],
        },
        "secondary": {
            "key": "secondary",
            "label": "Bone",
            "hex": "#EDE8E0",
            "usage_hint": "Support surfaces.",
            "agent_hint": "Use for backgrounds and balance.",
            "variants": [],
        },
        "tertiary": {
            "key": "tertiary",
            "label": "Electric",
            "hex": "#3D5AFE",
            "usage_hint": "CTA and highlights.",
            "agent_hint": "Use sparingly for attention.",
            "variants": [],
        },
    }
    return BrandContext(**payload)


def _recommendation_draft() -> BrandRecommendationDraft:
    return BrandRecommendationDraft(
        colors=[
            BrandColorRecommendation(
                role_key="tertiary",
                base_hex="#ff6b5c",
                label="Coral CTA",
                usage_hint="Use for CTA buttons and promo badges.",
                agent_hint="Reserve for high-attention promo moments.",
                variants=[
                    {"name": "Coral Hover", "hex": "#ff8478", "usage_hint": "CTA hover", "source": "gemini"}
                ],
                rationale="Warm contrast against the discovered ink/bone palette.",
                evidence_refs=["snapshot:colors:0"],
            ),
            BrandColorRecommendation(
                role_key="primary",
                base_hex="#101418",
                label="Deep Ink",
                usage_hint="Alternative dominant color.",
                agent_hint="Use as primary anchor.",
                rationale="Slightly bluer ink seen in the theme CSS.",
            ),
        ],
        fonts=[
            FontCandidate(**_font_candidate_payload()),
            FontCandidate(
                **_font_candidate_payload(
                    family="Papyrus",
                    css_stack="Papyrus, fantasy",
                    recommended_roles=["accent"],
                    rationale="Discovered in an old theme asset.",
                )
            ),
        ],
        summary="Draft generated from Shopify theme evidence.",
        source_notes=["colors: settings_data.json", "fonts: assets/theme.css"],
    )


def test_recommendation_draft_validates_role_key_and_hex() -> None:
    draft = _recommendation_draft()

    assert draft.colors[0].role_key == "tertiary"
    assert draft.colors[0].base_hex == "#FF6B5C"  # normalized
    assert draft.colors[0].variants[0].hex == "#FF8478"
    assert draft.fonts[0].status == "candidate"
    assert draft.summary.startswith("Draft generated")

    with pytest.raises(ValidationError):
        BrandColorRecommendation(
            role_key="accent",
            base_hex="#FF6B5C",
            label="Bad role",
            usage_hint="",
            agent_hint="",
            rationale="",
        )

    with pytest.raises(ValidationError):
        BrandColorRecommendation(
            role_key="primary",
            base_hex="ff6b5c",
            label="Missing hash",
            usage_hint="",
            agent_hint="",
            rationale="",
        )


def _apply_accepted_draft(
    brand: BrandContext,
    draft: BrandRecommendationDraft,
    *,
    accepted_roles: set[str],
    approved_families: set[str],
) -> BrandContext:
    """Schema-level simulation of the explicit apply step (Task 7 service behavior):
    only accepted recommendations are written; everything else is preserved."""

    assert brand.color_system is not None
    role_updates = {
        rec.role_key: BrandColorRole(
            key=rec.role_key,
            label=rec.label,
            hex=rec.base_hex,
            usage_hint=rec.usage_hint,
            agent_hint=rec.agent_hint,
            variants=rec.variants,
        )
        for rec in draft.colors
        if rec.role_key in accepted_roles
    }
    color_system = brand.color_system.model_copy(update=role_updates)

    approved = [
        font.model_copy(update={"status": "approved"})
        for font in draft.fonts
        if font.family in approved_families
    ]
    discarded = [
        font.model_copy(update={"status": "discarded"})
        for font in draft.fonts
        if font.family not in approved_families
    ]
    typography = brand.typography.model_copy(
        update={
            "approved_fonts": [*brand.typography.approved_fonts, *approved],
            "discarded_fonts": [*brand.typography.discarded_fonts, *discarded],
        }
    )
    return brand.model_copy(update={"color_system": color_system, "typography": typography})


def test_applying_accepted_draft_keeps_unaccepted_color_system_values() -> None:
    brand = _brand_with_explicit_color_system()
    draft = _recommendation_draft()

    merged = _apply_accepted_draft(
        brand,
        draft,
        accepted_roles={"tertiary"},  # the primary recommendation is NOT accepted
        approved_families={"Sora"},
    )

    assert merged.color_system is not None
    # Unaccepted roles keep their existing values (including variants).
    assert merged.color_system.primary.label == "Ink"
    assert merged.color_system.primary.hex == "#0E0E10"
    assert merged.color_system.primary.variants[0].name == "Ink Soft"
    assert merged.color_system.secondary.label == "Bone"
    assert merged.color_system.secondary.hex == "#EDE8E0"
    # Accepted role takes the recommended values.
    assert merged.color_system.tertiary.label == "Coral CTA"
    assert merged.color_system.tertiary.hex == "#FF6B5C"
    assert merged.color_system.tertiary.variants[0].name == "Coral Hover"
    # Legacy palette and typography display/body remain untouched.
    assert [c.hex for c in merged.palette] == [c.hex for c in brand.palette]
    assert merged.typography.display == "Space Grotesk"
    assert merged.typography.body == "Inter"
    # Fonts: accepted -> approved, the rest -> discarded; nothing auto-overwrites roles.
    assert [f.family for f in merged.typography.approved_fonts] == ["Sora"]
    assert merged.typography.approved_fonts[0].status == "approved"
    assert [f.family for f in merged.typography.discarded_fonts] == ["Papyrus"]
    assert merged.typography.discarded_fonts[0].status == "discarded"


def test_merged_brand_round_trips_through_validation() -> None:
    brand = _brand_with_explicit_color_system()
    merged = _apply_accepted_draft(
        brand,
        _recommendation_draft(),
        accepted_roles={"tertiary"},
        approved_families={"Sora"},
    )

    revalidated = BrandContext.model_validate(merged.model_dump())

    assert revalidated == merged
    assert revalidated.color_system is not None
    assert revalidated.color_system.tertiary.hex == "#FF6B5C"
    assert revalidated.typography.approved_fonts[0].family == "Sora"
