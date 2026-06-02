#!/usr/bin/env python3
"""Offline-safe smoke test for the constrained hackathon demo path.

Runs FastAPI in-process with TestClient and deterministic fallbacks. It does not
call Gemini, Shopify, Supabase, Lighthouse, or external networks. Use this after
scripts/reset-demo-data.py; it is safe to run repeatedly.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
VENV_PYTHON = BACKEND / ".venv" / "bin" / "python"
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve() and not os.getenv("AIJOLOT_SMOKE_NO_VENV"):
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])
sys.path.insert(0, str(BACKEND))

# Force deterministic offline mode before importing the backend. Do not read or
# print secrets; simply remove provider signals from this process environment.
for key in list(os.environ):
    if key.startswith(("SUPABASE_", "SHOPIFY_", "GEMINI_", "GOOGLE_")) or key in {
        "AIJOLOT_INTAKE_PROVIDER",
        "CAMPAIGN_STORE_ID",
    }:
        os.environ.pop(key, None)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.schemas.generation import GenerationEventResponse, GenerationRunCreate, GenerationRunResponse  # noqa: E402
from app.services import campaign_store  # noqa: E402
from app.services.banners.campaign_service import CampaignService  # noqa: E402

TEAM_ID = "00000000-0000-0000-0000-000000000001"
USER_ID = "00000000-0000-0000-0000-000000000601"
STORE_ID = "00000000-0000-0000-0000-000000000101"
AUTH = {
    "Authorization": f"Bearer demo:{USER_ID}:{TEAM_ID}:{STORE_ID}",
    "X-Aijolot-User-Id": USER_ID,
    "X-Aijolot-Team-Id": TEAM_ID,
    "X-Aijolot-Store-Id": STORE_ID,
}
DEMO_CAMPAIGN_UUID = "00000000-0000-0000-0000-000000000401"
RUN_ID = "00000000-0000-0000-0000-000000000501"


def _parse_sse_done(text: str) -> dict[str, Any]:
    for chunk in text.split("\n\n"):
        if not chunk.startswith("data: "):
            continue
        payload = json.loads(chunk.removeprefix("data: "))
        if payload.get("type") == "done":
            return payload
    raise AssertionError(f"SSE stream did not include done event: {text[:400]}")


class DeterministicGenerationRunService:
    def __init__(self) -> None:
        self.run: GenerationRunResponse | None = None
        self.events: list[GenerationEventResponse] = []

    def start_generation_run(self, campaign_id: str, request: GenerationRunCreate | None = None) -> GenerationRunResponse:
        request = request or GenerationRunCreate()
        self.run = GenerationRunResponse(
            id=RUN_ID,
            campaign_id=campaign_id,
            run_type=request.run_type,
            status="succeeded",
            frontend_step="review_publish",
            adk_trace_id="demo-trace-deterministic",
            started_by=request.started_by,
            metadata={
                "mode": "DETERMINISTIC FALLBACK",
                "provider": "offline-testclient",
                "kg_retrieval": "static deterministic retrieval",
                "layout_variants": ["A", "B", "C"],
                **(request.metadata or {}),
            },
        )
        self.events = [
            GenerationEventResponse(
                id="demo-event-1",
                generation_run_id=RUN_ID,
                node_key="static_kg_retrieval",
                frontend_step="intake_context",
                status="succeeded",
                metadata={"retrieval": "static deterministic retrieval"},
            ),
            GenerationEventResponse(
                id="demo-event-2",
                generation_run_id=RUN_ID,
                node_key="deterministic_abc_variants",
                frontend_step="image",
                status="succeeded",
                metadata={"variants": ["A", "B", "C"], "live_model": False},
            ),
        ]
        return self.run

    def get_latest_for_campaign(self, campaign_id: str) -> GenerationRunResponse:
        assert self.run is not None and self.run.campaign_id == campaign_id
        return self.run

    def get_run(self, run_id: str) -> GenerationRunResponse:
        assert self.run is not None and self.run.id == run_id
        return self.run

    def list_events(self, run_id: str) -> list[GenerationEventResponse]:
        assert self.run is not None and self.run.id == run_id
        return self.events


def _install_deterministic_generation() -> None:
    from app.api.v1 import generation

    service = DeterministicGenerationRunService()
    generation.configured_service_for_team = lambda team_id: service  # type: ignore[assignment]


def assert_ok(response, label: str) -> dict[str, Any] | list[Any]:
    assert response.status_code == 200, f"{label} failed: {response.status_code} {response.text}"
    return response.json()


def main() -> int:
    print("Aijolot demo smoke: DETERMINISTIC FALLBACK (no external providers)")
    campaign_store.set_service(CampaignService())
    _install_deterministic_generation()
    client = TestClient(app)

    brands = assert_ok(client.get("/api/v1/brands", headers=AUTH), "list brands")
    assert {brand["id"] for brand in brands} >= {"avocado_store", "demo_apparel", "maison"}

    stores = assert_ok(client.get("/api/v1/stores", headers=AUTH), "list stores")
    assert stores and stores[0]["id"] == STORE_ID
    resources = assert_ok(
        client.get(f"/api/v1/stores/{STORE_ID}/shopify/resources", params={"resource_type": "product"}, headers=AUTH),
        "list seeded product resources",
    )
    assert any(resource["handle"] == "boss-bottled-edp-100ml" for resource in resources)

    unauth_generation = client.post(f"/api/v1/campaigns/{DEMO_CAMPAIGN_UUID}/generation-runs", json={})
    assert unauth_generation.status_code == 401, unauth_generation.text

    intake_message = (
        "Black Friday 30% off para clientes VIP en home hero. "
        "CTA: Comprar ahora. Tono premium, urgencia alta, fecha 2026-11-27."
    )
    intake = client.post("/api/v1/campaigns/intake", json={"message": intake_message}, headers=AUTH)
    assert intake.status_code == 200, intake.text
    done = _parse_sse_done(intake.text)
    assert done["complete"] is True, done
    campaign = done["campaign"]
    assert campaign["status"] in {"needs_review", "draft"}
    assert campaign["structured_brief"]["cta"].lower().startswith("comprar")

    patched = assert_ok(
        client.patch(
            f"/api/v1/campaigns/{campaign['id']}",
            json={"title": "Smoke Black Friday VIP", "tone": "Premium"},
            headers=AUTH,
        ),
        "patch campaign",
    )
    assert patched["title"] == "Smoke Black Friday VIP"

    run = assert_ok(
        client.post(
            f"/api/v1/campaigns/{DEMO_CAMPAIGN_UUID}/generation-runs",
            json={"started_by": USER_ID, "metadata": {"scenario": "avocado-black-friday"}},
            headers=AUTH,
        ),
        "deterministic generation run",
    )
    assert run["status"] == "succeeded"
    assert run["metadata"]["mode"] == "DETERMINISTIC FALLBACK"
    assert run["metadata"]["layout_variants"] == ["A", "B", "C"]

    events = assert_ok(client.get(f"/api/v1/generation-runs/{RUN_ID}/events", headers=AUTH), "generation events")
    assert [event["node_key"] for event in events] == ["static_kg_retrieval", "deterministic_abc_variants"]

    print("smoke demo flow passed: auth, seeded resources, intake, patch, static KG, deterministic A/B/C generation")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        campaign_store.set_service(None)
