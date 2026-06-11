#!/usr/bin/env bash
#
# Apply pending Supabase migrations to a (self-hosted) Postgres without
# `supabase db reset` — so demo/prod data is preserved.
#
# Why this exists: the Cloud Run image ships new code but the deploy never
# migrated the persistent self-hosted DB, so the schema drifted behind `main`
# (e.g. campaign_revisions.status gained 'plan' in 20260608… but the demo DB
# still rejected it via campaign_revisions_status_check). This brings any DB
# forward to match supabase/migrations/.
#
# How it works (same contract as the Supabase CLI):
#   - tracks applied migrations in supabase_migrations.schema_migrations
#   - applies every *.sql under supabase/migrations/ whose 14-digit version is
#     not yet recorded, in filename order, each in ONE transaction
#   - takes a transaction-level advisory lock so concurrent Cloud Run cold
#     starts can't double-apply
#
# First run against an EXISTING, untracked DB (e.g. the current demo):
#   the tracking table is empty, so without a baseline this would try to
#   re-run 20260528…_initial_schema and fail ("relation already exists").
#   Pass DB_MIGRATIONS_BASELINE=<version> to mark everything up to and
#   including that version as already-applied. For the demo, the last
#   migration known to be applied before the breakage is 20260603210000:
#
#       DB_MIGRATIONS_BASELINE=20260603210000 \
#       SUPABASE_DB_URL=postgresql://... \
#       scripts/apply-migrations.sh
#
#   Subsequent runs need no baseline — tracking is now populated.
#
# Env:
#   SUPABASE_DB_URL         required — postgres connection string (DDL-capable)
#   DB_MIGRATIONS_BASELINE  optional — version (YYYYMMDDHHMMSS) to baseline
#   MIGRATIONS_DIR          optional — defaults to ../supabase/migrations
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-$SCRIPT_DIR/../supabase/migrations}"
DB_URL="${SUPABASE_DB_URL:-}"
BASELINE="${DB_MIGRATIONS_BASELINE:-}"
# Arbitrary fixed key so all runners serialize on the same advisory lock.
LOCK_KEY=823641

log() { echo "apply-migrations: $*" >&2; }

if [[ -z "$DB_URL" ]]; then
  log "SUPABASE_DB_URL not set — skipping (nothing to migrate)"
  exit 0
fi
if ! command -v psql >/dev/null 2>&1; then
  log "ERROR: psql not found on PATH"
  exit 1
fi
if [[ ! -d "$MIGRATIONS_DIR" ]]; then
  log "ERROR: migrations dir not found: $MIGRATIONS_DIR"
  exit 1
fi

psql_q() { psql "$DB_URL" -v ON_ERROR_STOP=1 -qtA "$@"; }

# 1) Tracking table (mirrors the Supabase CLI's schema).
psql_q >/dev/null <<'SQL'
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (
  version     text primary key,
  name        text,
  inserted_at timestamptz not null default now()
);
SQL

# 2) Optional baseline: record (without running) every migration <= baseline.
if [[ -n "$BASELINE" ]]; then
  for f in "$MIGRATIONS_DIR"/*.sql; do
    [[ -e "$f" ]] || continue
    base="$(basename "$f")"
    version="${base%%_*}"
    name="${base#*_}"; name="${name%.sql}"
    if (( 10#$version <= 10#$BASELINE )); then
      psql_q >/dev/null -c \
        "insert into supabase_migrations.schema_migrations (version, name) \
         values ('$version', '$name') on conflict (version) do nothing;"
    fi
  done
  log "baseline applied up to $BASELINE"
fi

# 3) Apply each not-yet-recorded migration, in order.
applied="$(psql_q -c 'select version from supabase_migrations.schema_migrations;')"
pending=0
for f in "$MIGRATIONS_DIR"/*.sql; do
  [[ -e "$f" ]] || continue
  base="$(basename "$f")"
  version="${base%%_*}"
  name="${base#*_}"; name="${name%.sql}"
  if grep -qxF "$version" <<<"$applied"; then
    continue
  fi
  pending=$((pending + 1))
  log "applying $version ($name)"
  # One transaction: advisory lock -> migration body -> record. The lock makes
  # this safe under concurrent runners; idempotent migrations make a re-applied
  # body (if a racer already ran it) harmless.
  psql "$DB_URL" -v ON_ERROR_STOP=1 -q --single-transaction \
    -c "select pg_advisory_xact_lock($LOCK_KEY);" \
    -f "$f" \
    -c "insert into supabase_migrations.schema_migrations (version, name) \
        values ('$version', '$name') on conflict (version) do nothing;"
done

if (( pending == 0 )); then
  log "database already up to date"
else
  log "done — applied $pending migration(s)"
fi
