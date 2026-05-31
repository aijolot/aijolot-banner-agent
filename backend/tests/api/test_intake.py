"""Tests for campaign intake (GH-27)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.campaign import StructuredBrief
from app.services import campaign_store
from app.services.campaign_store import extract_into

client = TestClient(app)

TEST_PROMPT = ("Quiero un banner de Black Friday para Avocado Store con 50% off "
               "audífonos a mujeres 25-40, urgencia alta, en la home hero")


def test_extractor_pulls_fields():
    b = extract_into(StructuredBrief(), TEST_PROMPT)
    assert b.urgency == "high"
    assert "mujeres" in b.audience.lower()
    assert "Home" in b.placement
    assert b.goal  # goal seeded from the brief
    # no CTA mentioned -> still missing, so the agent must ask for it
    assert "cta" in b.missing()


def test_extractor_is_multiturn():
    b = extract_into(StructuredBrief(), TEST_PROMPT)
    b = extract_into(b, 'El CTA: "Comprar ahora"')
    assert b.cta == "Comprar ahora"
    assert b.is_complete()


def _read_sse(resp):
    events = []
    for line in resp.iter_lines():
        if line and line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


def test_intake_streams_tokens_and_done():
    with client.stream("POST", "/campaigns/intake", json={"message": TEST_PROMPT}) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = _read_sse(resp)
    assert any(e["type"] == "token" for e in events)
    done = [e for e in events if e["type"] == "done"]
    assert len(done) == 1
    d = done[0]
    assert d["complete"] is False  # CTA still missing
    assert "cta" in d["missing"]
    assert d["campaign"]["structured_brief"]["urgency"] == "high"
    assert d["campaign"]["id"].startswith("cmp_")


def test_intake_continues_same_campaign():
    with client.stream("POST", "/campaigns/intake", json={"message": TEST_PROMPT}) as r1:
        cid = [e for e in _read_sse(r1) if e["type"] == "done"][0]["campaign"]["id"]
    with client.stream("POST", "/campaigns/intake", json={"message": 'CTA: "Comprar ya"', "campaign_id": cid}) as r2:
        done = [e for e in _read_sse(r2) if e["type"] == "done"][0]
    assert done["campaign"]["id"] == cid
    assert done["complete"] is True
    assert done["campaign"]["structured_brief"]["cta"] == "Comprar ya"


def test_intake_rejects_non_editable_campaign():
    campaign = campaign_store.create_campaign(title="Approved", raw_brief="Locked")
    campaign.status = "approved"

    response = client.post("/campaigns/intake", json={"message": "CTA: Comprar", "campaign_id": campaign.id})

    assert response.status_code == 409
    assert "not editable" in response.json()["detail"]
