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

# Cloud Run injects $PORT (defaults to 8080).
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
