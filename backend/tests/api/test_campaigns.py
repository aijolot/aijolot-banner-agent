"""Tests for campaign PATCH (GH-28)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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


def test_patch_unknown_campaign_404():
    assert client.patch("/campaigns/nope", json={"cta": "x"}).status_code == 404
