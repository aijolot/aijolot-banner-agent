#!/bin/sh
# Container entrypoint for Cloud Run.
#
# Loads runtime configuration from a Secret Manager secret that Cloud Run mounts
# as a dotenv-style file (see deploy: --set-secrets=/secrets/app.env=...), then
# launches uvicorn. The app reads pure environment variables (os.getenv), so we
# export every line of the mounted file into the process environment first.
set -e

ENV_FILE="${RUNTIME_ENV_FILE:-/secrets/app.env}"
if [ -f "$ENV_FILE" ]; then
    echo "entrypoint: loading runtime env from $ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
else
    echo "entrypoint: no runtime env file at $ENV_FILE (using process env only)"
fi

# Optional: forward-migrate the DB on boot to match supabase/migrations/.
# OPT-IN (default off). This only works when SUPABASE_DB_URL is a reachable
# raw-Postgres DDL endpoint. In the current self-hosted topology it is NOT:
# SUPABASE_DB_URL points at the Supavisor pooler (needs a tenant-id user) and
# the raw Postgres (supabase-db) lives only on the VM's docker network, which
# Cloud Run cannot reach — so migrations are applied on the VM instead (see
# scripts/migrate-supabase-vm.sh). Enable here only if you repoint
# SUPABASE_DB_URL at a reachable raw Postgres. Idempotent + advisory-locked;
# non-fatal so a failure never loops the service.
if [ "${RUN_DB_MIGRATIONS:-0}" != "0" ]; then
    if [ -n "${SUPABASE_DB_URL:-}" ]; then
        echo "entrypoint: applying DB migrations"
        bash /app/scripts/apply-migrations.sh || \
            echo "entrypoint: WARNING — migrations did not complete cleanly"
    else
        echo "entrypoint: SUPABASE_DB_URL unset — skipping DB migrations"
    fi
fi

# Cloud Run injects $PORT (defaults to 8080).
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
