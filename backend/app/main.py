"""FastAPI bridge between the React UI and the ADK graph (GH-17, partial).

Currently exposes the brand endpoints needed by GH-26. Campaign / intake /
draft routes are added in their own tickets.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import brands, campaigns, intake

app = FastAPI(title="Aijolot Banner Agent — Bridge", version="0.1.0")

# Dev CORS: the static prototype and the eventual Vite build both run on
# localhost; allow the common dev ports.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(brands.router)
app.include_router(intake.router)
app.include_router(campaigns.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
