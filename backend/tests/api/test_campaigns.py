"""Tests for campaign PATCH (GH-28)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH_HEADERS = {"X-Aijolot-User-Id": "test-user", "X-Aijolot-Team-Id": "test-team", "X-Aijolot-Store-Id": "test-store"}


def _new_campaign() -> str:
    with client.stream("POST", "/campaigns/intake", json={"message": "Promo en la home"}) as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                evt = json.loads(line[len("data: "):])
                if evt["type"] == "done":
                    return evt["campaign"]["id"]
    raise AssertionError("no campaign created")


def test_patch_updates_brief():
    cid = _new_campaign()
    r = client.patch(f"/campaigns/{cid}", json={"cta": "Comprar ahora", "audience": "VIP"})
    assert r.status_code == 200
    body = r.json()
    assert body["structured_brief"]["cta"] == "Comprar ahora"
    assert body["structured_brief"]["audience"] == "VIP"
    # unset fields are preserved
    assert body["id"] == cid


def test_get_campaign_roundtrip():
    cid = _new_campaign()
    client.patch(f"/campaigns/{cid}", json={"tone": "Premium"})
    r = client.get(f"/campaigns/{cid}")
    assert r.status_code == 200
    assert r.json()["structured_brief"]["tone"] == "Premium"


def test_v1_create_list_get_campaigns():
    created = client.post("/api/v1/campaigns", headers=AUTH_HEADERS, json={"title": "Dashboard Draft", "raw_brief": "Home sale"})
    assert created.status_code == 200
    cid = created.json()["id"]
    assert created.json()["title"] == "Dashboard Draft"

    listed = client.get("/api/v1/campaigns", headers=AUTH_HEADERS)
    assert listed.status_code == 200
    assert any(row["id"] == cid for row in listed.json())

    loaded = client.get(f"/api/v1/campaigns/{cid}", headers=AUTH_HEADERS)
    assert loaded.status_code == 200
    assert loaded.json()["raw_brief"] == "Home sale"


def test_patch_unknown_campaign_404():
    assert client.patch("/campaigns/nope", json={"cta": "x"}).status_code == 404


def test_configured_campaign_service_rejects_partial_supabase_env(monkeypatch):
    from app.core.settings import MissingSettingsError
    from app.services import campaign_store

    campaign_store.set_service(None)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_TEAM_ID", raising=False)
    monkeypatch.delenv("SUPABASE_STORE_ID", raising=False)

    try:
        with pytest.raises(MissingSettingsError):
            campaign_store._configured_service()
    finally:
        campaign_store.set_service(None)
