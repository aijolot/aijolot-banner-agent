"""Seed knowledge graph (kg_documents) from docs/kg_seed/**/*.md.

Usage:
    python scripts/kg_seed.py [--dry-run]

Reads every Markdown file under docs/kg_seed/<kind>/*.md, parses frontmatter
for metadata (title, brand_id?, metadata.*), embeds the body via Vertex
`text-embedding-005`, and INSERTs into public.kg_documents.

Idempotent: re-runs upsert by (kind, title, brand_id) — safe to re-seed.

Lands per GH-NEW5.
"""

from __future__ import annotations

import argparse


KIND_DIR_MAP = {
    "best_practice": "best_practices",
    "brand_example": "brand_examples",
    "liquid_pattern": "liquid_patterns",
    "audit_failure": "audit_failures",
    "seo_pattern": "seo_patterns",
}


def main(dry_run: bool = False) -> None:
    raise NotImplementedError("Lands in GH-NEW5 — embed + upsert pipeline.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
