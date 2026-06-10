"""Export kg_documents → supabase/seeds/kg_documents.sql (precomputed seed).

Usage:
    python scripts/kg_export_sql.py

Reads every row from public.kg_documents (via the service-role Supabase client)
and writes a deterministic, idempotent SQL seed file with the embeddings baked
in. That file is applied automatically by `supabase db reset` (see
supabase/config.toml [db.seed]), so a fresh environment/DB gets the full KG
corpus WITHOUT needing GOOGLE_API_KEY or any Gemini calls at deploy time.

Source of truth is still docs/kg_seed/**/*.md. The pipeline is:

    docs/kg_seed/**/*.md  --(scripts/kg_seed.py, needs Gemini)-->  kg_documents
    kg_documents          --(this script, DB read only)----------->  seeds/*.sql

Regenerate the seed whenever the corpus changes:
    python scripts/kg_seed.py          # markdown -> embeddings -> DB
    python scripts/kg_export_sql.py    # DB -> supabase/seeds/kg_documents.sql

This script makes NO Gemini calls — it only reads the DB and writes a file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as `python scripts/kg_export_sql.py` from repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

OUT_PATH = _REPO_ROOT / "supabase" / "seeds" / "kg_documents.sql"

# Columns we persist. id/created_at/updated_at are intentionally omitted so the
# table defaults (gen_random_uuid(), now()) apply — the seed is keyed by the
# (kind, title, brand_id) identity, not by a frozen UUID.
COLUMNS = ("kind", "title", "body", "metadata", "embedding", "brand_id")


def _sql_str(value: str) -> str:
    """Single-quoted SQL string literal with quotes doubled."""

    return "'" + value.replace("'", "''") + "'"


def _sql_metadata(value: object) -> str:
    """jsonb literal: compact JSON, stable key order, cast to jsonb."""

    text = json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sql_str(text) + "::jsonb"


def _sql_embedding(value: object) -> str:
    """pgvector literal: '[f,f,...]'::vector.

    PostgREST may return the vector as a JSON string ("[...]") or as a list.
    """

    if isinstance(value, str):
        literal = value.strip()
    elif isinstance(value, (list, tuple)):
        literal = "[" + ",".join(repr(float(v)) for v in value) + "]"
    else:
        raise TypeError(f"unexpected embedding type: {type(value)!r}")
    if not (literal.startswith("[") and literal.endswith("]")):
        raise ValueError(f"malformed embedding literal: {literal[:40]}…")
    return _sql_str(literal) + "::vector"


def _sql_brand(value: object) -> str:
    return "null" if value in (None, "", "null") else _sql_str(str(value))


def _row_tuple(row: dict) -> str:
    return (
        "  ("
        + _sql_str(str(row["kind"]))
        + ", "
        + _sql_str(str(row["title"]))
        + ", "
        + _sql_str(str(row["body"]))
        + ", "
        + _sql_metadata(row.get("metadata"))
        + ", "
        + _sql_embedding(row["embedding"])
        + ", "
        + _sql_brand(row.get("brand_id"))
        + ")"
    )


def main() -> None:
    from app.core.settings import Settings
    from app.services.supabase.client import SupabaseClientFactory

    settings = Settings.from_env()
    settings.require_supabase_service_role()
    client = SupabaseClientFactory(settings).service_role_client()

    rows = (
        client.table("kg_documents")
        .select(",".join(COLUMNS))
        .execute()
        .data
    )
    # Deterministic order so the generated file diffs cleanly.
    rows.sort(key=lambda r: (str(r["kind"]), str(r["title"]), str(r.get("brand_id") or "")))

    header = (
        "-- Aijolot Banner Agent — KG corpus seed (public.kg_documents)\n"
        "--\n"
        "-- GENERATED FILE — do not edit by hand.\n"
        "-- Regenerate after changing docs/kg_seed/**/*.md:\n"
        "--   python scripts/kg_seed.py        # markdown -> embeddings -> DB (needs GOOGLE_API_KEY)\n"
        "--   python scripts/kg_export_sql.py  # DB -> this file (no Gemini calls)\n"
        "--\n"
        "-- Applied automatically by `supabase db reset` after migrations\n"
        "-- (supabase/config.toml [db.seed].sql_paths). Embeddings are baked in,\n"
        "-- so a fresh environment needs NO Gemini/GOOGLE_API_KEY to populate the KG.\n"
        "-- Embedding model: gemini-embedding-001 (768 dims).\n\n"
        "-- Authoritative resync: clear then insert the full corpus. Safe to re-run.\n"
        "delete from public.kg_documents;\n\n"
    )

    body = (
        "insert into public.kg_documents\n"
        "  (" + ", ".join(COLUMNS) + ")\n"
        "values\n"
        + ",\n".join(_row_tuple(r) for r in rows)
        + ";\n"
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(header + body, encoding="utf-8")
    print(f"Wrote {len(rows)} kg_documents rows -> {OUT_PATH.relative_to(_REPO_ROOT)}")


if __name__ == "__main__":
    main()
