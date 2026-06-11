"""Deterministic font candidate extraction + curated seed pool (Task 6).

Two non-AI building blocks for the font workflow:

- :func:`font_candidates_from_snapshot` maps the raw ``DiscoveredFont`` evidence of a
  :class:`BrandDiscoverySnapshot` onto strict :class:`FontCandidate` drafts
  (``status="candidate"``) with provenance kept in ``evidence_refs``.
- :data:`SYSTEM_SEED_FONTS` is a curated pool of safe, widely available families,
  always labeled ``source="system_seed"``.

Nothing in this module is AI output and nothing here is ever presented as AI:
rationales are fixed deterministic strings ("Discovered in ..." / "Curated seed: ...").
Gemini-backed suggestions live in ``font_suggestions.py``.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.schemas.brand import FontCandidate, FontCategory
from app.schemas.brand_discovery import BrandDiscoverySnapshot, DiscoveredFont

__all__ = [
    "SYSTEM_SEED_FONTS",
    "build_css_stack",
    "font_candidates_from_snapshot",
    "guess_font_category",
]


# ---------------------------------------------------------------------------
# Category heuristic (simple keyword matching, see tests for the contract)
# ---------------------------------------------------------------------------

_MONO_KEYWORDS = ("mono", "code", "courier", "consol")
# Well-known serif families that do not carry "serif" in their name. Checked before
# the display keywords so "Playfair Display" classifies as serif.
_SERIF_NAME_KEYWORDS = ("playfair", "merriweather", "lora", "georgia", "garamond", "times", "baskerville")
_HANDWRITTEN_KEYWORDS = ("script", "hand", "caveat", "brush", "cursive")
_DISPLAY_KEYWORDS = ("display", "bebas", "oswald", "impact")
# Well-known sans families that do not carry "sans" in their name.
_SANS_NAME_KEYWORDS = ("grotesk", "grotesque", "helvetica", "arial", "inter", "roboto", "lato", "futura")

_GENERIC_BY_CATEGORY: dict[str, str] = {
    "mono": "monospace",
    "serif": "serif",
    "handwritten": "cursive",
    "display": "sans-serif",
    "sans": "sans-serif",
    "unknown": "sans-serif",
}


def _contains_any(name: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in name for keyword in keywords)


def guess_font_category(family: str) -> FontCategory:
    """Best-effort category from the family name alone; "unknown" when unsure."""

    name = " ".join(family.lower().split())
    if _contains_any(name, _MONO_KEYWORDS):
        return "mono"
    if _contains_any(name, _SERIF_NAME_KEYWORDS) or ("serif" in name and "sans" not in name):
        return "serif"
    if _contains_any(name, _HANDWRITTEN_KEYWORDS):
        return "handwritten"
    if _contains_any(name, _DISPLAY_KEYWORDS):
        return "display"
    if _contains_any(name, _SANS_NAME_KEYWORDS) or "sans" in name:
        return "sans"
    return "unknown"


def build_css_stack(family: str, category: FontCategory | str = "unknown") -> str:
    """``<family>, <generic>`` fallback stack; multi-word families get quoted."""

    family = " ".join(family.split())
    quoted = f'"{family}"' if " " in family else family
    return f"{quoted}, {_GENERIC_BY_CATEGORY.get(str(category), 'sans-serif')}"


# ---------------------------------------------------------------------------
# Snapshot -> FontCandidate mapping (deterministic)
# ---------------------------------------------------------------------------


def _candidate_source_for(discovered_source: str) -> str:
    """Map a snapshot evidence source onto the FontCandidate source literal."""

    bucket = str(discovered_source or "").strip().lower()
    if bucket.startswith("css"):
        return "storefront_css"
    # theme_settings*, section*, shop_metadata, ...: everything else came out of the
    # Shopify theme/admin surface.
    return "shopify_theme"


def _discovered_fonts(snapshot: BrandDiscoverySnapshot | dict[str, Any]) -> list[DiscoveredFont]:
    """Tolerant per-item extraction so one bad persisted entry never hides the rest."""

    if isinstance(snapshot, BrandDiscoverySnapshot):
        return list(snapshot.fonts)
    raw = snapshot.get("fonts") if isinstance(snapshot, dict) else None
    fonts: list[DiscoveredFont] = []
    for item in raw or []:
        if isinstance(item, DiscoveredFont):
            fonts.append(item)
            continue
        try:
            fonts.append(DiscoveredFont.model_validate(item))
        except ValidationError:
            continue
    return fonts


def font_candidates_from_snapshot(
    snapshot: BrandDiscoverySnapshot | dict[str, Any],
) -> list[FontCandidate]:
    """Map discovered font evidence onto deduped, sorted candidate drafts.

    Dedupe is by lowercased family: the highest-confidence entry wins the source
    mapping/rationale, a non-empty css_stack is kept from any duplicate, and every
    distinct evidence source is preserved in ``evidence_refs``.
    """

    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for font in _discovered_fonts(snapshot):
        key = font.family.lower()
        group = grouped.get(key)
        if group is None:
            grouped[key] = {"winner": font, "css_stack": font.css_stack, "sources": [font.source]}
            order.append(key)
            continue
        if font.source not in group["sources"]:
            group["sources"].append(font.source)
        if font.confidence > group["winner"].confidence:
            group["winner"] = font
        if not group["css_stack"] and font.css_stack:
            group["css_stack"] = font.css_stack

    ranked: list[tuple[float, FontCandidate]] = []
    for key in order:
        group = grouped[key]
        winner: DiscoveredFont = group["winner"]
        category = guess_font_category(winner.family)
        rationale = f"Discovered in {winner.source}"
        if winner.sample_usage:
            rationale += f" ({winner.sample_usage})"
        try:  # defense in depth: never let one bad mapping break the workflow
            candidate = FontCandidate(
                family=winner.family,
                css_stack=group["css_stack"] or build_css_stack(winner.family, category),
                category=category,
                source=_candidate_source_for(winner.source),
                status="candidate",
                recommended_roles=[],
                rationale=rationale,
                evidence_refs=list(group["sources"]),
            )
        except (ValidationError, ValueError):
            continue
        ranked.append((winner.confidence, candidate))

    ranked.sort(key=lambda item: (-item[0], item[1].family.lower()))
    return [candidate for _confidence, candidate in ranked]


# ---------------------------------------------------------------------------
# Curated seed pool (clearly non-AI fallback candidates)
# ---------------------------------------------------------------------------

_SEED_RATIONALE_PREFIX = "Curated seed (non-AI):"


def _seed(
    family: str,
    css_stack: str,
    category: FontCategory,
    roles: list[str],
    note: str,
) -> FontCandidate:
    return FontCandidate(
        family=family,
        css_stack=css_stack,
        category=category,
        source="system_seed",
        status="candidate",
        recommended_roles=roles,  # type: ignore[arg-type]
        rationale=f"{_SEED_RATIONALE_PREFIX} {note}",
        evidence_refs=[],
    )


SYSTEM_SEED_FONTS: tuple[FontCandidate, ...] = (
    # Modern sans
    _seed("Inter", 'Inter, "Helvetica Neue", Arial, sans-serif', "sans", ["body", "caption"], "highly readable modern sans for body copy and captions."),
    _seed("DM Sans", '"DM Sans", "Helvetica Neue", Arial, sans-serif', "sans", ["body", "caption"], "friendly low-contrast sans for body copy."),
    _seed("Work Sans", '"Work Sans", "Helvetica Neue", Arial, sans-serif', "sans", ["body", "headline"], "versatile workhorse sans for body and mid-size headlines."),
    _seed("Manrope", 'Manrope, "Helvetica Neue", Arial, sans-serif', "sans", ["headline", "body"], "rounded modern sans that pairs headlines with body copy."),
    # Grotesk display
    _seed("Space Grotesk", '"Space Grotesk", "Helvetica Neue", Arial, sans-serif', "sans", ["display", "headline"], "techy grotesk with strong character for hero and headline type."),
    _seed("Archivo", 'Archivo, Roboto, Arial, sans-serif', "sans", ["display", "headline"], "sturdy grotesque built for big banner headlines."),
    # Serif
    _seed("Playfair Display", '"Playfair Display", Georgia, "Times New Roman", serif', "serif", ["display"], "high-contrast editorial serif for premium hero moments."),
    _seed("Lora", 'Lora, Georgia, serif', "serif", ["body", "headline"], "balanced contemporary serif for editorial body copy."),
    _seed("Merriweather", 'Merriweather, Georgia, serif', "serif", ["body", "caption"], "screen-first serif that stays readable at small sizes."),
    _seed("Libre Baskerville", '"Libre Baskerville", Baskerville, Georgia, serif', "serif", ["body"], "classic book serif for trustworthy long-form copy."),
    # Geometric
    _seed("Poppins", 'Poppins, Futura, "Century Gothic", sans-serif', "sans", ["headline", "body"], "geometric sans with a friendly retail feel."),
    _seed("Montserrat", 'Montserrat, Futura, "Helvetica Neue", sans-serif', "sans", ["headline", "display"], "urban geometric sans for confident headlines."),
    # Condensed display
    _seed("Oswald", 'Oswald, "Arial Narrow", Impact, sans-serif', "display", ["display", "headline"], "condensed display face for loud promotional banners."),
    _seed("Bebas Neue", '"Bebas Neue", Impact, "Arial Narrow", sans-serif', "display", ["display"], "all-caps condensed poster face for maximum impact."),
    # Mono
    _seed("IBM Plex Mono", '"IBM Plex Mono", "Courier New", monospace', "mono", ["accent", "caption"], "clean monospace for prices, codes and technical accents."),
    _seed("JetBrains Mono", '"JetBrains Mono", "Courier New", monospace', "mono", ["accent", "caption"], "crisp monospace accent for discount codes and fine print."),
)
