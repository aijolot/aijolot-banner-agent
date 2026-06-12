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
#   the tracking table is empty but the schema already exists, so re-running the
#   early non-idempotent migrations (20260528…_initial_schema) would fail with
#   "relation already exists". This is auto-detected (empty tracking + a present
#   public.campaigns) and auto-baselined to 20260603210000 — the last migration
#   before the idempotent batch — so only 20260608+ get applied. No manual step:
#
#       SUPABASE_DB_URL=postgresql://... scripts/apply-migrations.sh
#
#   Override the auto-cutover with AUTO_BASELINE_VERSION, or force an explicit
#   baseline with DB_MIGRATIONS_BASELINE (disables auto-detection).
#
# Env:
#   SUPABASE_DB_URL         required — postgres connection string (DDL-capable)
#   DB_MIGRATIONS_BASELINE  optional — explicit baseline version (YYYYMMDDHHMMSS);
#                                      set to disable auto-baseline detection
#   AUTO_BASELINE_VERSION   optional — cutover used by auto-baseline (default
#                                      20260603210000)
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

# 2) Auto-baseline: a pre-existing DB whose tracking table is empty was migrated
#    out-of-band (psql -f without tracking — how the demo/local DBs were seeded).
#    Re-running the early, non-idempotent migrations (initial_schema…) would fail
#    with "relation already exists". So if the core schema is already present but
#    nothing is tracked, baseline to the last pre-idempotent migration; only the
#    idempotent batch (>= that version) gets (re-)applied. Override the cutover
#    with AUTO_BASELINE_VERSION, or skip auto-detection by passing an explicit
#    DB_MIGRATIONS_BASELINE.
if [[ -z "$BASELINE" ]]; then
  tracked_count="$(psql_q -c 'select count(*) from supabase_migrations.schema_migrations;')"
  has_core="$(psql_q -c "select (to_regclass('public.campaigns') is not null);")"
  if [[ "$tracked_count" == "0" && "$has_core" == "t" ]]; then
    BASELINE="${AUTO_BASELINE_VERSION:-20260603210000}"
    log "untracked existing schema detected — auto-baseline to $BASELINE"
  fi
fi

# 3) Baseline: record (without running) every migration <= baseline.
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

# 4) Apply each not-yet-recorded migration, in order.
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
