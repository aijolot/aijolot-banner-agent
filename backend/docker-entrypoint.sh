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

# Forward-migrate the persistent (self-hosted) Supabase DB to match
# supabase/migrations/ before serving. Idempotent + advisory-locked, so it's
# safe across concurrent cold starts. Set RUN_DB_MIGRATIONS=0 to skip, or
# DB_MIGRATIONS_BASELINE=<version> on the first run against an existing,
# untracked DB (see scripts/apply-migrations.sh). Non-fatal: a migration
# failure is logged but still lets the app boot so the service stays up.
if [ "${RUN_DB_MIGRATIONS:-1}" != "0" ]; then
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
