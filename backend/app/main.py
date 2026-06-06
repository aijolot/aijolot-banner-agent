"""FastAPI bridge between the React UI and the ADK graph.

The app preserves root-level prototype routes for the current static frontend
and also exposes canonical `/api/v1` routes for new backend/frontend work.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import brands, campaigns, intake
from app.api.v1.router import router as api_v1_router

app = FastAPI(title="Aijolot Banner Agent — Bridge", version="0.1.0")

# CORS. In dev the static prototype and the eventual Vite build run on
# localhost; in prod the frontend is served same-origin from this container
# (see the StaticFiles mount below), so CORS is mostly a safety net. Any extra
# allowed origins can be supplied via CORS_ALLOW_ORIGINS (comma-separated),
# e.g. the public Cloud Run URL or a custom domain.
_extra_origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
        *_extra_origins,
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(brands.router)
app.include_router(intake.router)
app.include_router(campaigns.router)
app.include_router(api_v1_router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve the static React/Babel frontend same-origin. Mounted LAST so every API
# router (/api/v1, /brands, /campaigns, /health, /docs, ...) takes precedence;
# StaticFiles only handles paths that no route matched. html=True makes "/"
# return index.html. The mount is skipped if the frontend dir is absent (e.g.
# a backend-only test environment) so it never breaks the test suite.
_frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if _frontend_dir.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(_frontend_dir), html=True),
        name="frontend",
    )
