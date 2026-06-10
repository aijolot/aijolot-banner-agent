"""Contract tests for the canonical /api/v1 namespace."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH_HEADERS = {"X-Aijolot-User-Id": "test-user", "X-Aijolot-Team-Id": "00000000-0000-0000-0000-000000000001", "X-Aijolot-Store-Id": "00000000-0000-0000-0000-000000000101"}


def _read_sse(resp):
    events = []
    for line in resp.iter_lines():
        if line and line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def _new_v1_campaign() -> str:
    response = client.post("/api/v1/campaigns", headers=AUTH_HEADERS, json={"title": "Promo", "raw_brief": "Promo en la home"})
    assert response.status_code == 200
    return response.json()["id"]


def _done_campaign(events):
    done = [e for e in events if e["type"] == "done"]
    assert len(done) == 1
    return done[0]["campaign"]


def test_health_root_route_remains_available():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root_intake_route_remains_available():
    with client.stream("POST", "/campaigns/intake", json={"message": "Promo en la home"}) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        events = _read_sse(r)
    assert any(e["type"] == "token" for e in events)
    assert any(e["type"] == "done" for e in events)


def test_v1_intake_route_matches_root_contract():
    with client.stream("POST", "/api/v1/campaigns/intake", headers=AUTH_HEADERS, json={"message": "Promo en la home"}) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        events = _read_sse(r)
    assert any(e["type"] == "token" for e in events)
    campaign = _done_campaign(events)
    UUID(campaign["id"])
    assert any("missing" in e for e in events if e["type"] == "done")


def test_v1_campaign_create_uses_uuid_but_root_intake_preserves_prototype_ids():
    cid = _new_v1_campaign()
    UUID(cid)

    with client.stream("POST", "/campaigns/intake", json={"message": "Promo en la home"}) as r:
        assert r.status_code == 200
        events = _read_sse(r)
    assert _done_campaign(events)["id"].startswith("cmp_")


def test_v1_intake_continues_with_returned_uuid_campaign_id():
    with client.stream("POST", "/api/v1/campaigns/intake", headers=AUTH_HEADERS, json={"message": "Promo en home con CTA Comprar"}) as r:
        assert r.status_code == 200
        first = _done_campaign(_read_sse(r))
    UUID(first["id"])

    with client.stream("POST", "/api/v1/campaigns/intake", headers=AUTH_HEADERS, json={"message": "audiencia VIP y urgencia alta", "campaign_id": first["id"]}) as r:
        assert r.status_code == 200
        second = _done_campaign(_read_sse(r))
    assert second["id"] == first["id"]


def test_v1_brand_routes_match_root_contract(tmp_path, monkeypatch):
    import app.services.brand_store as store

    brands = client.get("/api/v1/brands", headers=AUTH_HEADERS)
    assert brands.status_code == 200
    assert {b["id"] for b in brands.json()} >= {"avocado_store", "demo_apparel", "maison"}

    brand = client.get("/api/v1/brands/avocado_store", headers=AUTH_HEADERS)
    assert brand.status_code == 200
    assert brand.json()["name"] == "Avocado Store"

    assert client.get("/api/v1/brands/nope", headers=AUTH_HEADERS).status_code == 404

    # Exercise v1 PUT without mutating checked-in seed files.
    source = store.get_brand("maison")
    monkeypatch.setattr(store, "BRANDS_DIR", tmp_path)
    store.save_brand("maison", source)
    payload = source.model_dump()
    payload["voice"]["tone"] = ["Premium", "Editorial"]

    saved = client.put("/api/v1/brands/maison", headers=AUTH_HEADERS, json=payload)
    assert saved.status_code == 200
    assert saved.json()["voice"]["tone"] == ["Premium", "Editorial"]


def test_v1_campaign_get_and_patch_match_root_contract():
    cid = _new_v1_campaign()

    patch = client.patch(f"/api/v1/campaigns/{cid}", headers=AUTH_HEADERS, json={"cta": "Comprar ahora", "audience": "VIP"})
    assert patch.status_code == 200
    assert patch.json()["structured_brief"]["cta"] == "Comprar ahora"
    assert patch.json()["structured_brief"]["audience"] == "VIP"

    get = client.get(f"/api/v1/campaigns/{cid}", headers=AUTH_HEADERS)
    assert get.status_code == 200
    assert get.json()["id"] == cid
    assert get.json()["structured_brief"]["cta"] == "Comprar ahora"


def test_v1_routes_are_present_in_openapi_contract():
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/brands" in paths
    assert "/api/v1/brands/{brand_id}" in paths
    assert "/api/v1/campaigns/intake" in paths
    assert "/api/v1/campaigns/{campaign_id}" in paths
    assert "/campaigns/intake" in paths
    assert "/health" in paths


def test_preview_read_retries_transient_failures(monkeypatch) -> None:
    """503 race after build: one transient repo failure must NOT surface as 503."""
    from app.api.v1 import previews

    monkeypatch.setattr(previews, "_RETRY_DELAY_S", 0.0)
    attempts: list[int] = []

    def flaky_reader():
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError("transient")
        return {"html_preview": "<html></html>"}

    result = previews._read_with_retry(flaky_reader)
    assert result["html_preview"]
    assert len(attempts) == 2

    # Persistent failures still bubble up (mapped to 503 by the endpoint).
    def always_broken():
        raise ConnectionError("down")

    import pytest as _pytest

    with _pytest.raises(ConnectionError):
        previews._read_with_retry(always_broken)
