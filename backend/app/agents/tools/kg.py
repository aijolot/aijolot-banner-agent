"""ADK Tool: deterministic knowledge graph retrieval.

Embeddings/pgvector are intentionally optional for Task 11: no live external
calls are made. Retrieval ranks an in-code seed corpus with simple lexical
matching, and can be replaced/augmented by the KGDocumentRepository later.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid5, NAMESPACE_URL

_TOKEN_RE = re.compile(r"[a-z0-9%]+", re.IGNORECASE)

_STATIC_DOCS: tuple[dict[str, Any], ...] = (
    {
        "kind": "best_practice",
        "title": "Keep hero banner hierarchy to one message, one proof point, one CTA",
        "body": "Use a short benefit-led headline, one supporting line, and a single action CTA. Avoid competing promos in the hero area.",
        "metadata": {"category": "hierarchy", "applicable_when": "all ecommerce banners"},
        "brand_id": None,
    },
    {
        "kind": "best_practice",
        "title": "CTA copy should be action-first and under five words",
        "body": "Short CTAs such as Shop now, Claim offer, or Explore collection scan quickly and improve click intent on mobile.",
        "metadata": {"category": "cta", "applicable_when": "conversion and urgency medium/high"},
        "brand_id": None,
    },
    {
        "kind": "best_practice",
        "title": "Reserve safe text zones for responsive crops",
        "body": "Place text away from product focal points and edges. Keep the subject on one side and copy on the other for desktop-to-mobile cropping.",
        "metadata": {"category": "layout", "applicable_when": "hero, collection, product, search"},
        "brand_id": None,
    },
    {
        "kind": "best_practice",
        "title": "Use brand palette tokens with contrast-aware roles",
        "body": "Assign primary palette color to the CTA, neutral or light color to the background, and reserve accent colors for urgency badges.",
        "metadata": {"category": "brand", "applicable_when": "branded creative"},
        "brand_id": None,
    },
    {
        "kind": "best_practice",
        "title": "Product banners should communicate offer and product context immediately",
        "body": "Mention the product or collection category, surface price or discount when available, and keep imagery uncluttered.",
        "metadata": {"category": "catalog", "applicable_when": "product and collection campaigns"},
        "brand_id": None,
    },
    {
        "kind": "best_practice",
        "title": "Avoid generating text, logos, UI chrome, or faces inside source imagery",
        "body": "Image generation prompts should describe photographic/background assets only. Render all marketing text in HTML for accessibility and brand control.",
        "metadata": {"category": "image_safety", "applicable_when": "AI image generation"},
        "brand_id": None,
    },
)


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(value or "") if len(token) > 2}


def _shape_doc(doc: dict[str, Any], *, score: float) -> dict[str, Any]:
    title = str(doc.get("title", "Untitled KG document"))
    kind = str(doc.get("kind", "best_practice"))
    brand_id = doc.get("brand_id")
    return {
        "id": str(uuid5(NAMESPACE_URL, f"aijolot-kg:{kind}:{brand_id}:{title}")),
        "kind": kind,
        "title": title,
        "body": str(doc.get("body", "")),
        "metadata": dict(doc.get("metadata") or {}),
        "brand_id": brand_id,
        "score": round(score, 4),
        "source": "static",
    }


async def retrieve(
    query: str,
    *,
    kinds: list[str] | None = None,
    brand_id: str | None = None,
    metadata_filter: dict | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return deterministic KGDocument-like dicts sorted by lexical relevance."""
    allowed_kinds = set(kinds or [])
    query_tokens = _tokens(query)
    metadata_filter = metadata_filter or {}

    ranked: list[tuple[float, dict[str, Any]]] = []
    for doc in _STATIC_DOCS:
        if allowed_kinds and doc.get("kind") not in allowed_kinds:
            continue
        doc_brand_id = doc.get("brand_id")
        if doc_brand_id and brand_id and doc_brand_id != brand_id:
            continue
        metadata = dict(doc.get("metadata") or {})
        if any(metadata.get(key) != value for key, value in metadata_filter.items()):
            continue

        haystack = " ".join([str(doc.get("title", "")), str(doc.get("body", "")), " ".join(map(str, metadata.values()))])
        overlap = len(query_tokens & _tokens(haystack))
        if overlap <= 0:
            continue
        score = overlap + (0.15 if doc.get("kind") == "best_practice" else 0.0)
        if brand_id and doc_brand_id == brand_id:
            score += 0.5
        ranked.append((score, doc))

    ranked.sort(key=lambda item: (-item[0], str(item[1].get("title", ""))))
    return [_shape_doc(doc, score=score) for score, doc in ranked[: max(0, top_k)]]


async def index(doc: dict[str, Any]) -> str:
    """Return deterministic id for a document without making network calls."""
    shaped = _shape_doc(doc, score=1.0)
    return shaped["id"]
