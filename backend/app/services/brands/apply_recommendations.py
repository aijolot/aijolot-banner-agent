"""Merge user-accepted discovery recommendations into a BrandContext (Task 7).

Pure merge logic, kept out of ``brand_service.py`` for cohesion. The user is the
approval gate: ONLY items listed in the request change; everything else on the
brand stays exactly as loaded (unaccepted roles keep their variants, untouched
fonts keep their status, legacy fields keep working).

Merge rules:

- Colors: each accepted ``BrandColorRecommendation`` replaces its role wholesale
  (label/hex/hints/variants, variant ``source`` preserved as provided). Roles not
  in the request are untouched. When at least one color is accepted, the legacy
  ``palette[0..2]`` is re-synced to the three role colors post-merge (the same
  rule as the frontend ``syncPaletteFromColorSystem``) and entries beyond index 2
  are preserved as extras, so old generation paths keep working.
- Fonts: approved fonts upsert into ``typography.approved_fonts`` (dedupe by
  lowercased family, replacing the existing entry in place) with
  ``status="approved"``. Discarded fonts move to ``typography.discarded_fonts``
  with ``status="discarded"`` and are removed from ``approved_fonts`` if present;
  discards persist so suggestion services never re-offer those families (Task 6).
  An explicit approval symmetrically reverses an earlier discard of the same
  family. Approving AND discarding one family in the same request is a user
  error -> ``RecommendationApplyError`` (422 at the route layer).
- ``typography_roles``: assigns ``Typography.<display|headline|body|accent>`` to
  an approved family (validated against the post-merge approved list, canonical
  casing taken from the approved entry). Unknown role keys or unapproved
  families -> ``RecommendationApplyError``. ``display``/``body`` keep their
  current values when not assigned — they never become None/empty implicitly.
- ``logo_url``: set only when provided and non-empty (empty string = ignore).
- ``image_style_directives``: ``None`` keeps, a list (possibly empty) replaces.

The merged brand is re-validated through ``BrandContext.model_validate`` before
being returned, so ``model_copy`` shortcuts can never leak an invalid brand.
"""

from __future__ import annotations

from typing import Any

from app.schemas.brand import (
    BrandColorRole,
    BrandColorSystem,
    BrandContext,
    FontCandidate,
    PaletteColor,
    Typography,
    color_system_from_palette,
)
from app.schemas.brand_discovery import BrandColorRecommendation
from app.schemas.brand_recommendations import ApplyDiscoveryRecommendationsRequest

__all__ = [
    "ASSIGNABLE_FONT_ROLES",
    "RecommendationApplyError",
    "merge_discovery_recommendations",
]

# Typography role fields that exist on the Typography model ("caption" has no field).
ASSIGNABLE_FONT_ROLES: tuple[str, ...] = ("display", "headline", "body", "accent")


class RecommendationApplyError(ValueError):
    """User-correctable apply request problem (-> 422 via the ValueError route mapping)."""


# -- colors ---------------------------------------------------------------------------


def _role_from_recommendation(recommendation: BrandColorRecommendation) -> BrandColorRole:
    return BrandColorRole(
        key=recommendation.role_key,
        label=recommendation.label,
        hex=recommendation.base_hex,
        usage_hint=recommendation.usage_hint,
        agent_hint=recommendation.agent_hint,
        variants=[variant.model_copy(deep=True) for variant in recommendation.variants],
    )


def _merged_color_system(
    brand: BrandContext, accepted: list[BrandColorRecommendation]
) -> BrandColorSystem:
    current = brand.color_system or color_system_from_palette(brand.palette)
    role_updates = {rec.role_key: _role_from_recommendation(rec) for rec in accepted}
    merged = current.model_copy(update=role_updates)
    # model_copy(update=...) skips validators; rebuild so the key-per-field invariant holds.
    return BrandColorSystem.model_validate(merged.model_dump())


def _synced_palette(palette: list[PaletteColor], color_system: BrandColorSystem) -> list[PaletteColor]:
    """palette[0..2] = the three role colors; entries beyond index 2 are kept as extras."""

    roles = (color_system.primary, color_system.secondary, color_system.tertiary)
    synced = [PaletteColor(name=role.label, hex=role.hex) for role in roles]
    extras = [color.model_copy(deep=True) for color in palette[3:]]
    return [*synced, *extras]


# -- fonts ----------------------------------------------------------------------------


def _upsert_by_family(fonts: list[FontCandidate], entry: FontCandidate) -> list[FontCandidate]:
    """Replace the existing entry for the same family (case-insensitive) in place, or append."""

    key = entry.family.lower()
    result: list[FontCandidate] = []
    replaced = False
    for font in fonts:
        if font.family.lower() == key:
            if not replaced:
                result.append(entry)
                replaced = True
            continue  # drop accidental duplicate rows for the same family
        result.append(font)
    if not replaced:
        result.append(entry)
    return result


def _without_family(fonts: list[FontCandidate], family: str) -> list[FontCandidate]:
    key = family.lower()
    return [font for font in fonts if font.family.lower() != key]


def _merged_typography(
    typography: Typography, request: ApplyDiscoveryRecommendationsRequest
) -> Typography:
    approved_keys = {font.family.lower() for font in request.approved_fonts}
    discarded_keys = {font.family.lower() for font in request.discarded_fonts}
    conflict = sorted(approved_keys & discarded_keys)
    if conflict:
        raise RecommendationApplyError(
            "font families cannot be approved and discarded in the same request: "
            + ", ".join(conflict)
        )

    approved = list(typography.approved_fonts)
    discarded = list(typography.discarded_fonts)
    for font in request.approved_fonts:
        approved = _upsert_by_family(approved, font.model_copy(update={"status": "approved"}))
        # An explicit approval reverses an earlier discard of the same family.
        discarded = _without_family(discarded, font.family)
    for font in request.discarded_fonts:
        approved = _without_family(approved, font.family)
        # Discards persist: suggestion services rely on this list to never re-offer them.
        discarded = _upsert_by_family(discarded, font.model_copy(update={"status": "discarded"}))

    updates: dict[str, Any] = {"approved_fonts": approved, "discarded_fonts": discarded}
    canonical_families = {font.family.lower(): font.family for font in approved}
    for role_key, family in (request.typography_roles or {}).items():
        if role_key not in ASSIGNABLE_FONT_ROLES:
            raise RecommendationApplyError(
                f"unknown typography role {role_key!r}; allowed roles: "
                + ", ".join(ASSIGNABLE_FONT_ROLES)
            )
        wanted = " ".join(str(family).split())
        match = canonical_families.get(wanted.lower())
        if match is None:
            raise RecommendationApplyError(
                f"typography role {role_key!r} must reference an approved font family; "
                f"{family!r} is not in approved_fonts after this request"
            )
        updates[role_key] = match
    return Typography.model_validate(typography.model_copy(update=updates).model_dump())


# -- merge ----------------------------------------------------------------------------


def merge_discovery_recommendations(
    brand: BrandContext, request: ApplyDiscoveryRecommendationsRequest
) -> BrandContext:
    """Return a new BrandContext with ONLY the accepted recommendations applied."""

    updates: dict[str, Any] = {"typography": _merged_typography(brand.typography, request)}

    if request.colors:
        color_system = _merged_color_system(brand, request.colors)
        updates["color_system"] = color_system
        updates["palette"] = _synced_palette(brand.palette, color_system)

    logo_url = (request.logo_url or "").strip()
    if logo_url:
        updates["logo_url"] = logo_url
    if request.image_style_directives is not None:
        updates["image_style_directives"] = list(request.image_style_directives)

    # Full re-validation: partial model_copy updates must never leak an invalid brand.
    return BrandContext.model_validate(brand.model_copy(update=updates).model_dump())
