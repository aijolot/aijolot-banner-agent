# syntax=docker/dockerfile:1
#
# Aijolot Banner Agent — single-container image for Cloud Run.
# Serves the FastAPI backend AND the static React/Babel frontend from one
# process. The repo layout (/app/backend + /app/frontend) is preserved because
# banner_render._frontend_dir() resolves the frontend via parents[4]/frontend.

FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    APP_ENV=production

WORKDIR /app

# Build/runtime system deps. Pillow + pillow-avif need libs; build-essential
# covers any wheels without prebuilt manylinux artifacts. curl is handy for
# container debugging. Playwright's own OS deps are installed by
# `playwright install --with-deps` below.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libjpeg62-turbo \
        zlib1g \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 1) Install Python deps first for better layer caching. We copy the whole
#    backend (the package metadata + sources) and install it; deps come from
#    backend/pyproject.toml.
COPY backend/ /app/backend/
RUN pip install /app/backend

# 2) Install the Chromium browser that Playwright drives for the screenshot
#    self-review loop, plus its OS dependencies. Pinned to the playwright
#    version resolved above so the binary matches the Python client.
RUN playwright install --with-deps chromium

# 3) Frontend static assets (no build step — CDN React + Babel-standalone).
COPY frontend/ /app/frontend/

# 4) DB migrations + the applier the entrypoint runs on boot. The self-hosted
#    Supabase DB persists across deploys, so the entrypoint forward-migrates it
#    (psql, installed above) to match supabase/migrations/ before serving.
COPY supabase/ /app/supabase/
COPY scripts/apply-migrations.sh /app/scripts/apply-migrations.sh
RUN chmod +x /app/scripts/apply-migrations.sh

# Cloud Run injects $PORT (defaults to 8080). The entrypoint loads runtime
# config from the mounted Secret Manager env file, then binds 0.0.0.0:$PORT.
ENV PORT=8080
WORKDIR /app/backend
EXPOSE 8080

RUN chmod +x /app/backend/docker-entrypoint.sh
CMD ["/app/backend/docker-entrypoint.sh"]
