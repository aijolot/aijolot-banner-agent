"""Service-level tests for applying accepted discovery recommendations (Task 7).

Runs against a markdown-mode BrandService rooted at tmp_path (same fallback mode
the other brand service tests use), so every apply round-trips through
``save_brand`` -> markdown -> ``get_brand``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.brand import BrandContext, FontCandidate
from app.schemas.brand_discovery import BrandColorRecommendation
from app.schemas.brand_recommendations import ApplyDiscoveryRecommendationsRequest
from app.services.brands.apply_recommendations import RecommendationApplyError
from app.services.brands.brand_service import BrandNotFound, BrandService
from app.services.brands.markdown_importer import BrandMarkdownImporter

BRAND_ID = "demo_brand"


@pytest.fixture()
def service(tmp_path: Path) -> BrandService:
    return BrandService(markdown_importer=BrandMarkdownImporter(base_dir=tmp_path))


def _font_payload(**overrides) -> dict:
    payload = {
        "family": "Sora",
        "css_stack": '"Sora", sans-serif',
        "category": "sans",
        "source": "gemini_suggested",
        "status": "candidate",
        "recommended_roles": ["headline"],
        "rationale": "Geometric sans that matches the wordmark.",
        "evidence_refs": ["snapshot:fonts:0"],
    }
    payload.update(overrides)
    return payload


def _seed_brand() -> BrandContext:
    # Role labels intentionally differ from the palette names so tests can prove
    # whether the legacy palette sync ran (it must run only when colors are accepted).
    return BrandContext(
        **{
            "id": BRAND_ID,
            "name": "Demo Brand",
            "palette": [
                {"name": "Ink", "hex": "#0E0E10"},
                {"name": "Bone", "hex": "#EDE8E0"},
                {"name": "Electric", "hex": "#3D5AFE"},
                {"name": "Linen Extra", "hex": "#FAF3E3"},  # extra beyond the 3 roles
            ],
            "color_system": {
                "primary": {
                    "key": "primary",
                    "label": "Ink Anchor",
                    "hex": "#0E0E10",
                    "usage_hint": "Dominant identity color.",
                    "agent_hint": "Anchor headlines and key surfaces.",
                    "variants": [
                        {"name": "Ink Soft", "hex": "#2A2A2E", "usage_hint": "Soft anchor", "source": "manual"}
                    ],
                },
                "secondary": {
                    "key": "secondary",
                    "label": "Bone Field",
                    "hex": "#EDE8E0",
                    "usage_hint": "Support surfaces.",
                    "agent_hint": "Use for backgrounds and balance.",
                    "variants": [],
                },
                "tertiary": {
                    "key": "tertiary",
                    "label": "Electric Pop",
                    "hex": "#3D5AFE",
                    "usage_hint": "CTA and highlights.",
                    "agent_hint": "Use sparingly for attention.",
                    "variants": [],
                },
            },
            "typography": {
                "display": "Space Grotesk",
                "body": "Inter",
                "approved_fonts": [_font_payload(status="approved", rationale="Approved earlier.")],
                "discarded_fonts": [
                    _font_payload(
                        family="Papyrus",
                        css_stack="Papyrus, fantasy",
                        category="handwritten",
                        source="shopify_theme",
                        status="discarded",
                        recommended_roles=[],
                        rationale="Off-brand.",
                    )
                ],
            },
            "voice": {"tone": ["Premium"], "prohibited_words": [], "required_phrases": []},
            "logo_url": None,
            "image_style_directives": ["Soft daylight"],
            "shopify": {"store_domain": "demo.myshopify.com"},
            "notes": "Seed notes.",
        }
    )


@pytest.fixture()
def seeded(service: BrandService) -> BrandContext:
    service.save_brand(BRAND_ID, _seed_brand())
    # Reload so comparisons run against the persisted form (markdown round-trip
    # normalizes the notes body with a trailing newline).
    return service.get_brand(BRAND_ID)


def _tertiary_recommendation(**overrides) -> BrandColorRecommendation:
    payload = {
        "role_key": "tertiary",
        "base_hex": "#FF6B5C",
        "label": "Coral CTA",
        "usage_hint": "CTA buttons and promo badges.",
        "agent_hint": "Reserve for high-attention promo moments.",
        "variants": [
            {"name": "Coral Hover", "hex": "#FF8478", "usage_hint": "CTA hover", "source": "ai_suggested"}
        ],
        "rationale": "Warm contrast against the ink/bone palette.",
        "evidence_refs": ["snapshot:colors:0"],
    }
    payload.update(overrides)
    return BrandColorRecommendation(**payload)


# ---------------------------------------------------------------------------
# Colors: accepted roles replace, unaccepted roles stay byte-identical
# ---------------------------------------------------------------------------


def test_unknown_brand_raises_brand_not_found(service: BrandService) -> None:
    with pytest.raises(BrandNotFound):
        service.apply_discovery_recommendations("nope", ApplyDiscoveryRecommendationsRequest())


def test_accepted_color_replaces_only_that_role(service: BrandService, seeded: BrandContext) -> None:
    request = ApplyDiscoveryRecommendationsRequest(colors=[_tertiary_recommendation()])

    merged = service.apply_discovery_recommendations(BRAND_ID, request)

    assert merged.color_system is not None and seeded.color_system is not None
    # Accepted role takes the full recommended payload, variant source preserved.
    assert merged.color_system.tertiary.label == "Coral CTA"
    assert merged.color_system.tertiary.hex == "#FF6B5C"
    assert merged.color_system.tertiary.usage_hint == "CTA buttons and promo badges."
    assert merged.color_system.tertiary.agent_hint == "Reserve for high-attention promo moments."
    assert [v.name for v in merged.color_system.tertiary.variants] == ["Coral Hover"]
    assert merged.color_system.tertiary.variants[0].source == "ai_suggested"
    # Unaccepted roles are byte-identical, variants included.
    assert merged.color_system.primary.model_dump() == seeded.color_system.primary.model_dump()
    assert merged.color_system.secondary.model_dump() == seeded.color_system.secondary.model_dump()
    assert merged.color_system.primary.variants[0].name == "Ink Soft"


def test_palette_syncs_all_three_roles_and_preserves_extras(service: BrandService, seeded: BrandContext) -> None:
    request = ApplyDiscoveryRecommendationsRequest(colors=[_tertiary_recommendation()])

    merged = service.apply_discovery_recommendations(BRAND_ID, request)

    # palette[0..2] = post-merge role colors (name = role label, hex = role base hex).
    assert [(c.name, c.hex) for c in merged.palette[:3]] == [
        ("Ink Anchor", "#0E0E10"),
        ("Bone Field", "#EDE8E0"),
        ("Coral CTA", "#FF6B5C"),
    ]
    # Entries beyond index 2 are preserved as extras.
    assert len(merged.palette) == 4
    assert merged.palette[3].model_dump() == {"name": "Linen Extra", "hex": "#FAF3E3"}


def test_no_accepted_colors_keeps_color_system_and_palette_untouched(
    service: BrandService, seeded: BrandContext
) -> None:
    request = ApplyDiscoveryRecommendationsRequest(approved_fonts=[FontCandidate(**_font_payload(family="Archivo Black", css_stack='"Archivo Black", sans-serif'))])

    merged = service.apply_discovery_recommendations(BRAND_ID, request)

    assert merged.color_system == seeded.color_system
    # No palette sync without accepted colors: names still differ from role labels.
    assert [c.name for c in merged.palette] == ["Ink", "Bone", "Electric", "Linen Extra"]


# ---------------------------------------------------------------------------
# Fonts: approve / discard / dedupe / move
# ---------------------------------------------------------------------------


def test_approved_fonts_merge_with_case_insensitive_dedupe(service: BrandService, seeded: BrandContext) -> None:
    request = ApplyDiscoveryRecommendationsRequest(
        approved_fonts=[
            FontCandidate(**_font_payload(family="sora", rationale="Re-approved with refreshed rationale.")),
            FontCandidate(**_font_payload(family="Archivo Black", css_stack='"Archivo Black", sans-serif', recommended_roles=["display"])),
        ]
    )

    merged = service.apply_discovery_recommendations(BRAND_ID, request)

    # "sora" replaced the existing "Sora" entry in place (no duplicate row).
    assert [f.family for f in merged.typography.approved_fonts] == ["sora", "Archivo Black"]
    assert all(f.status == "approved" for f in merged.typography.approved_fonts)
    assert merged.typography.approved_fonts[0].rationale == "Re-approved with refreshed rationale."
    # Existing discards not mentioned in the request stay.
    assert [f.family for f in merged.typography.discarded_fonts] == ["Papyrus"]


def test_discarded_fonts_move_out_of_approved_and_persist(service: BrandService, seeded: BrandContext) -> None:
    request = ApplyDiscoveryRecommendationsRequest(
        discarded_fonts=[FontCandidate(**_font_payload(rationale="Too soft for the brand."))]  # Sora
    )

    merged = service.apply_discovery_recommendations(BRAND_ID, request)

    assert merged.typography.approved_fonts == []  # removed from approved
    assert [f.family for f in merged.typography.discarded_fonts] == ["Papyrus", "Sora"]
    assert all(f.status == "discarded" for f in merged.typography.discarded_fonts)

    # Task 6 dependency: the discard persists across save/reload so suggestion
    # services never re-offer the family.
    reloaded = service.get_brand(BRAND_ID)
    assert [f.family for f in reloaded.typography.discarded_fonts] == ["Papyrus", "Sora"]


def test_approving_previously_discarded_family_reverses_the_discard(
    service: BrandService, seeded: BrandContext
) -> None:
    request = ApplyDiscoveryRecommendationsRequest(
        approved_fonts=[
            FontCandidate(
                **_font_payload(
                    family="Papyrus", css_stack="Papyrus, fantasy", category="handwritten", source="shopify_theme"
                )
            )
        ]
    )

    merged = service.apply_discovery_recommendations(BRAND_ID, request)

    assert [f.family for f in merged.typography.approved_fonts] == ["Sora", "Papyrus"]
    assert merged.typography.approved_fonts[1].status == "approved"
    assert merged.typography.discarded_fonts == []


def test_same_family_approved_and_discarded_raises(service: BrandService, seeded: BrandContext) -> None:
    request = ApplyDiscoveryRecommendationsRequest(
        approved_fonts=[FontCandidate(**_font_payload(family="Inter Tight", css_stack='"Inter Tight", sans-serif'))],
        discarded_fonts=[FontCandidate(**_font_payload(family="inter tight", css_stack='"Inter Tight", sans-serif'))],
    )

    with pytest.raises(RecommendationApplyError) as exc_info:
        service.apply_discovery_recommendations(BRAND_ID, request)

    assert "approved and discarded in the same request" in str(exc_info.value)
    assert "inter tight" in str(exc_info.value)
    assert isinstance(exc_info.value, ValueError)  # routes map ValueError -> 422
    # Nothing persisted on failure.
    assert service.get_brand(BRAND_ID) == seeded


# ---------------------------------------------------------------------------
# Typography role assignment
# ---------------------------------------------------------------------------


def test_typography_role_assignment_uses_canonical_approved_family(
    service: BrandService, seeded: BrandContext
) -> None:
    request = ApplyDiscoveryRecommendationsRequest(
        approved_fonts=[
            FontCandidate(**_font_payload(family="Archivo Black", css_stack='"Archivo Black", sans-serif'))
        ],
        typography_roles={"headline": "archivo   black", "display": "Sora"},  # Sora already approved on the brand
    )

    merged = service.apply_discovery_recommendations(BRAND_ID, request)

    assert merged.typography.headline == "Archivo Black"  # canonical casing from approved_fonts
    assert merged.typography.display == "Sora"
    # Unassigned roles keep their existing values (body never becomes None/empty).
    assert merged.typography.body == "Inter"
    assert merged.typography.accent is None


def test_typography_role_with_unapproved_family_raises(service: BrandService, seeded: BrandContext) -> None:
    request = ApplyDiscoveryRecommendationsRequest(typography_roles={"display": "Comic Neue"})

    with pytest.raises(RecommendationApplyError) as exc_info:
        service.apply_discovery_recommendations(BRAND_ID, request)

    assert "'display'" in str(exc_info.value)
    assert "'Comic Neue' is not in approved_fonts" in str(exc_info.value)


def test_typography_role_with_discarded_family_in_same_request_raises(
    service: BrandService, seeded: BrandContext
) -> None:
    # Discarding removes the family from approved, so assigning it must fail.
    request = ApplyDiscoveryRecommendationsRequest(
        discarded_fonts=[FontCandidate(**_font_payload())],  # Sora
        typography_roles={"display": "Sora"},
    )

    with pytest.raises(RecommendationApplyError):
        service.apply_discovery_recommendations(BRAND_ID, request)


@pytest.mark.parametrize("role_key", ["caption", "hero", "DISPLAY"])
def test_typography_role_with_unknown_key_raises(service: BrandService, seeded: BrandContext, role_key: str) -> None:
    request = ApplyDiscoveryRecommendationsRequest(typography_roles={role_key: "Sora"})

    with pytest.raises(RecommendationApplyError) as exc_info:
        service.apply_discovery_recommendations(BRAND_ID, request)

    assert "unknown typography role" in str(exc_info.value)
    assert "display, headline, body, accent" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Logo / image directives accept-or-keep semantics
# ---------------------------------------------------------------------------


def test_logo_url_set_only_when_provided(service: BrandService, seeded: BrandContext) -> None:
    accepted = service.apply_discovery_recommendations(
        BRAND_ID, ApplyDiscoveryRecommendationsRequest(logo_url="https://cdn.shopify.com/demo/logo.svg")
    )
    assert accepted.logo_url == "https://cdn.shopify.com/demo/logo.svg"

    # None and empty string both mean "not accepted": the existing logo stays.
    kept_none = service.apply_discovery_recommendations(BRAND_ID, ApplyDiscoveryRecommendationsRequest())
    assert kept_none.logo_url == "https://cdn.shopify.com/demo/logo.svg"
    kept_empty = service.apply_discovery_recommendations(BRAND_ID, ApplyDiscoveryRecommendationsRequest(logo_url="  "))
    assert kept_empty.logo_url == "https://cdn.shopify.com/demo/logo.svg"


def test_image_style_directives_none_keeps_and_list_replaces(service: BrandService, seeded: BrandContext) -> None:
    kept = service.apply_discovery_recommendations(BRAND_ID, ApplyDiscoveryRecommendationsRequest())
    assert kept.image_style_directives == ["Soft daylight"]

    replaced = service.apply_discovery_recommendations(
        BRAND_ID, ApplyDiscoveryRecommendationsRequest(image_style_directives=["Linen texture", "Golden hour"])
    )
    assert replaced.image_style_directives == ["Linen texture", "Golden hour"]

    cleared = service.apply_discovery_recommendations(
        BRAND_ID, ApplyDiscoveryRecommendationsRequest(image_style_directives=[])
    )
    assert cleared.image_style_directives == []


# ---------------------------------------------------------------------------
# Empty request no-op + full round trip
# ---------------------------------------------------------------------------


def test_empty_request_is_a_noop_without_a_write(service: BrandService, tmp_path: Path, seeded: BrandContext) -> None:
    brand_file = tmp_path / f"{BRAND_ID}.md"
    before_bytes = brand_file.read_bytes()
    before_mtime = brand_file.stat().st_mtime_ns

    result = service.apply_discovery_recommendations(BRAND_ID, ApplyDiscoveryRecommendationsRequest())

    assert result == seeded
    assert brand_file.read_bytes() == before_bytes
    assert brand_file.stat().st_mtime_ns == before_mtime  # not rewritten


def test_full_apply_round_trips_through_save_and_reload(service: BrandService, seeded: BrandContext) -> None:
    request = ApplyDiscoveryRecommendationsRequest(
        run_id="00000000-0000-0000-0000-000000000001",  # provenance only
        colors=[
            _tertiary_recommendation(),
            _tertiary_recommendation(
                role_key="primary",
                base_hex="#101418",
                label="Deep Ink",
                usage_hint="Alternative dominant color.",
                agent_hint="Use as primary anchor.",
                variants=[],
                rationale="Slightly bluer ink from theme CSS.",
            ),
        ],
        logo_url="https://cdn.shopify.com/demo/logo.svg",
        image_style_directives=["Linen texture"],
        approved_fonts=[
            FontCandidate(**_font_payload(family="Archivo Black", css_stack='"Archivo Black", sans-serif'))
        ],
        discarded_fonts=[
            FontCandidate(**_font_payload(family="Comic Neue", css_stack='"Comic Neue", cursive'))
        ],
        typography_roles={"headline": "Archivo Black"},
    )

    merged = service.apply_discovery_recommendations(BRAND_ID, request)
    reloaded = service.get_brand(BRAND_ID)

    assert reloaded == merged
    assert reloaded.color_system is not None
    assert reloaded.color_system.primary.label == "Deep Ink"
    assert reloaded.color_system.primary.hex == "#101418"
    assert reloaded.color_system.secondary.label == "Bone Field"  # untouched role
    assert reloaded.color_system.tertiary.hex == "#FF6B5C"
    assert [(c.name, c.hex) for c in reloaded.palette] == [
        ("Deep Ink", "#101418"),
        ("Bone Field", "#EDE8E0"),
        ("Coral CTA", "#FF6B5C"),
        ("Linen Extra", "#FAF3E3"),
    ]
    assert [f.family for f in reloaded.typography.approved_fonts] == ["Sora", "Archivo Black"]
    assert [f.family for f in reloaded.typography.discarded_fonts] == ["Papyrus", "Comic Neue"]
    assert reloaded.typography.headline == "Archivo Black"
    assert reloaded.typography.display == "Space Grotesk"  # untouched legacy fields
    assert reloaded.typography.body == "Inter"
    assert reloaded.logo_url == "https://cdn.shopify.com/demo/logo.svg"
    assert reloaded.image_style_directives == ["Linen texture"]
    assert reloaded.notes == seeded.notes
    # The merged brand revalidates cleanly (spec: model_validate(model_dump())).
    assert BrandContext.model_validate(merged.model_dump()) == merged
