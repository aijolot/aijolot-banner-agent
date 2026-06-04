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


def _shape_doc(doc: dict[str, Any], *, score: float, source: str = "static") -> dict[str, Any]:
    title = str(doc.get("title", "Untitled KG document"))
    kind = str(doc.get("kind", "best_practice"))
    brand_id = doc.get("brand_id")
    raw_id = doc.get("id")
    doc_id = str(raw_id) if raw_id else str(uuid5(NAMESPACE_URL, f"aijolot-kg:{kind}:{brand_id}:{title}"))
    return {
        "id": doc_id,
        "kind": kind,
        "title": title,
        "body": str(doc.get("body", "")),
        "metadata": dict(doc.get("metadata") or {}),
        "brand_id": brand_id,
        "score": round(float(score), 4),
        "source": source,
    }


def _lexical_rank(
    docs: "list[dict[str, Any]] | tuple[dict[str, Any], ...]",
    *,
    query: str,
    allowed_kinds: set[str],
    brand_id: str | None,
    metadata_filter: dict,
    source: str,
) -> list[tuple[float, dict[str, Any]]]:
    query_tokens = _tokens(query)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for doc in docs:
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
        ranked.append((score, _shape_doc(doc, score=score, source=source)))
    return ranked


def _settings():
    from app.core.settings import Settings

    return Settings.from_env()


def _supabase_client(settings):
    """Return a Supabase client (service-role preferred, anon fallback) or None."""

    try:
        from app.services.supabase.client import SupabaseClientFactory

        factory = SupabaseClientFactory(settings)
        try:
            return factory.service_role_client()
        except Exception:
            return factory.anon_client()
    except Exception:
        return None


def _retrieve_db_rows(settings, *, kinds: list[str] | None, brand_id: str | None) -> list[dict[str, Any]]:
    client = _supabase_client(settings)
    if client is None:
        return []
    try:
        from app.db.repositories.kg_documents import KGDocumentRepository

        repo = KGDocumentRepository(client)
        return repo.list(kinds=kinds, brand_id=brand_id, limit=max(50, settings.kg_retrieval_top_k * 10))
    except Exception:
        return []


async def _retrieve_vector(
    settings,
    *,
    query: str,
    kinds: list[str] | None,
    brand_id: str | None,
    top_k: int,
) -> list[dict[str, Any]]:
    """Vector retrieval via the match_kg_documents RPC. Returns [] on any failure."""

    client = _supabase_client(settings)
    if client is None:
        return []
    try:
        from app.agents.tools.gemini_embed import embed

        vectors = await embed([query])
        if not vectors:
            return []
        embedding_literal = "[" + ",".join(repr(float(v)) for v in vectors[0]) + "]"
        params = {
            "query_embedding": embedding_literal,
            "match_kinds": kinds or None,
            "match_brand_id": brand_id,
            "match_count": max(1, top_k),
        }
        result = client.rpc("match_kg_documents", params).execute()
        rows = getattr(result, "data", None) or []
        return [
            _shape_doc(row, score=row.get("score", 0.0), source="db_vector")
            for row in rows
            if row.get("score", 0.0) >= settings.kg_similarity_threshold
        ]
    except Exception:
        return []


def _merge_floor(
    primary: list[dict[str, Any]],
    floor: list[tuple[float, dict[str, Any]]],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    """Combine primary results with the static lexical floor, de-duped, top_k."""

    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for doc in primary:
        key = (doc["kind"], doc["title"], str(doc.get("brand_id") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(doc)
    for _score, doc in floor:
        key = (doc["kind"], doc["title"], str(doc.get("brand_id") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(doc)
    return out[: max(0, top_k)]


async def retrieve(
    query: str,
    *,
    kinds: list[str] | None = None,
    brand_id: str | None = None,
    metadata_filter: dict | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return KGDocument-like dicts ranked by relevance.

    Tiered with graceful fallback: (1) Gemini-embedding vector search via the
    match_kg_documents RPC when ``KG_EMBEDDINGS_ENABLED`` + a key + Supabase are
    present; (2) Supabase rows ranked lexically; (3) the in-code static corpus.
    The static corpus is always merged in as a floor so retrieval never returns
    empty, preserving the deterministic test/dev behavior.
    """

    allowed_kinds = set(kinds or [])
    metadata_filter = metadata_filter or {}
    settings = _settings()

    static_ranked = _lexical_rank(
        _STATIC_DOCS,
        query=query,
        allowed_kinds=allowed_kinds,
        brand_id=brand_id,
        metadata_filter=metadata_filter,
        source="static",
    )
    static_ranked.sort(key=lambda item: (-item[0], str(item[1].get("title", ""))))

    primary: list[dict[str, Any]] = []

    if settings.kg_embeddings_enabled and settings.has_google_api_key():
        primary = await _retrieve_vector(
            settings, query=query, kinds=kinds, brand_id=brand_id, top_k=top_k
        )

    if not primary:
        db_rows = _retrieve_db_rows(settings, kinds=kinds, brand_id=brand_id)
        if db_rows:
            db_ranked = _lexical_rank(
                db_rows,
                query=query,
                allowed_kinds=allowed_kinds,
                brand_id=brand_id,
                metadata_filter=metadata_filter,
                source="db_lexical",
            )
            db_ranked.sort(key=lambda item: (-item[0], str(item[1].get("title", ""))))
            primary = [doc for _score, doc in db_ranked[: max(0, top_k)]]

    return _merge_floor(primary, static_ranked, top_k=top_k)


async def index(doc: dict[str, Any]) -> str:
    """Return deterministic id for a document without making network calls."""
    shaped = _shape_doc(doc, score=1.0)
    return shaped["id"]
