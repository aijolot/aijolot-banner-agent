"""ADK Tool: Knowledge graph retrieval (pgvector). Lands in GH-NEW4/NEW8.

Hybrid retrieval: vector cosine similarity + metadata filter + kind filter.
"""

from __future__ import annotations


async def retrieve(
    query: str,
    *,
    kinds: list[str] | None = None,
    brand_id: str | None = None,
    metadata_filter: dict | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Return list of KGDocument dicts sorted by similarity desc."""
    raise NotImplementedError("Lands in services/supabase/kg.py + GH-NEW4/NEW8.")


async def index(doc: dict) -> str:
    """Embed + INSERT into kg_documents. Returns document id."""
    raise NotImplementedError("Lands in services/supabase/kg.py + GH-NEW4.")
