"""Seed knowledge graph (kg_documents) from docs/kg_seed/**/*.md.

Usage:
    python scripts/kg_seed.py [--dry-run]

Reads every Markdown file under docs/kg_seed/<kind_dir>/*.md, parses YAML
frontmatter for (title, brand_id?, metadata.*) + body, embeds the body via
`text-embedding-005` (768 dims), and upserts into public.kg_documents.

Idempotent: upsert by (kind, title, brand_id) — delete-then-insert, safe to
re-seed. With --dry-run it parses + reports counts but performs no embedding
or DB writes.

Lands per GH-NEW5.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/kg_seed.py` from repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import yaml  # noqa: E402

KIND_DIR_MAP = {
    "best_practice": "best_practices",
    "brand_example": "brand_examples",
    "liquid_pattern": "liquid_patterns",
    "audit_failure": "audit_failures",
    "seo_pattern": "seo_patterns",
}

SEED_ROOT = _REPO_ROOT / "docs" / "kg_seed"


class SeedDoc:
    __slots__ = ("kind", "title", "body", "metadata", "brand_id", "path")

    def __init__(self, *, kind: str, title: str, body: str, metadata: dict, brand_id: str | None, path: Path) -> None:
        self.kind = kind
        self.title = title
        self.body = body
        self.metadata = metadata
        self.brand_id = brand_id
        self.path = path


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a Markdown file into (frontmatter dict, body)."""

    stripped = text.lstrip("﻿")
    if not stripped.startswith("---"):
        return {}, text.strip()
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()
    front = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    if not isinstance(front, dict):
        front = {}
    return front, body


def _load_docs() -> list[SeedDoc]:
    docs: list[SeedDoc] = []
    for kind, dir_name in KIND_DIR_MAP.items():
        kind_dir = SEED_ROOT / dir_name
        if not kind_dir.is_dir():
            continue
        for md_path in sorted(kind_dir.glob("*.md")):
            front, body = _parse_frontmatter(md_path.read_text(encoding="utf-8"))
            title = str(front.get("title") or md_path.stem).strip()
            doc_kind = str(front.get("kind") or kind).strip()
            raw_brand = front.get("brand_id")
            brand_id = None if raw_brand in (None, "null", "") else str(raw_brand).strip()
            metadata = front.get("metadata") if isinstance(front.get("metadata"), dict) else {}
            if not body:
                print(f"  ! skip (empty body): {md_path}")
                continue
            docs.append(
                SeedDoc(kind=doc_kind, title=title, body=body, metadata=metadata, brand_id=brand_id, path=md_path)
            )
    return docs


def _upsert(client, doc: SeedDoc, embedding: list[float]) -> None:
    """Delete any existing row with the same identity, then insert."""

    query = client.table("kg_documents").delete().eq("kind", doc.kind).eq("title", doc.title)
    if doc.brand_id is None:
        query = query.is_("brand_id", "null")
    else:
        query = query.eq("brand_id", doc.brand_id)
    query.execute()

    payload = {
        "kind": doc.kind,
        "title": doc.title,
        "body": doc.body,
        "metadata": doc.metadata,
        "embedding": embedding,
        "brand_id": doc.brand_id,
    }
    client.table("kg_documents").insert(payload).execute()


def main(dry_run: bool = False) -> None:
    docs = _load_docs()
    by_kind: dict[str, int] = {}
    for doc in docs:
        by_kind[doc.kind] = by_kind.get(doc.kind, 0) + 1
    print(f"Parsed {len(docs)} KG docs from {SEED_ROOT}")
    for kind, count in sorted(by_kind.items()):
        print(f"  {kind}: {count}")

    if dry_run:
        print("\n--dry-run: no embeddings computed, no DB writes.")
        return

    from app.agents.tools.gemini_embed import embed_sync
    from app.core.settings import Settings
    from app.services.supabase.client import SupabaseClientFactory

    settings = Settings.from_env()
    settings.require_google_api_key()  # fail-closed: clear error if missing
    settings.require_supabase_service_role()
    client = SupabaseClientFactory(settings).service_role_client()

    written = 0
    for doc in docs:
        embedding = embed_sync([doc.body])[0]
        _upsert(client, doc, embedding)
        written += 1
        print(f"  upserted [{doc.kind}] {doc.title[:70]}")
    print(f"\nDone: upserted {written} KG documents.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
