"""Fase 0 — /api/v1/suggestions: auth boundaries + lifecycle through the API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.banners.suggestion_service import InMemoryAgentSuggestions, SuggestionService

client = TestClient(app)
TEAM_A = "11111111-1111-1111-1111-111111111111"
AUTH_TEAM_A = {"X-Aijolot-User-Id": "user-a", "X-Aijolot-Team-Id": TEAM_A, "X-Aijolot-Store-Id": "store-a"}
AUTH_TEAM_B = {"X-Aijolot-User-Id": "user-b", "X-Aijolot-Team-Id": "22222222-2222-2222-2222-222222222222", "X-Aijolot-Store-Id": "store-b"}


def _install(monkeypatch):
    from app.api.v1 import suggestions as module

    stores: dict[str, InMemoryAgentSuggestions] = {}
    created: list[dict] = []

    def factory(team_id: str, **callbacks):
        repo = stores.setdefault(team_id, InMemoryAgentSuggestions())

        def create_campaign(payload):
            created.append(payload)
            return "33333333-3333-3333-3333-333333333333"

        return SuggestionService(suggestions=repo, team_id=team_id, create_campaign=create_campaign)

    monkeypatch.setattr(module, "configured_service_for_team", factory)
    return stores, created


def test_suggestions_fail_closed_without_context() -> None:
    assert client.get("/api/v1/suggestions").status_code == 401


def test_list_accept_dismiss_flow(monkeypatch) -> None:
    stores, created = _install(monkeypatch)
    # Seed two suggestions for team A directly through the repo.
    repo = stores.setdefault(TEAM_A, InMemoryAgentSuggestions())
    s1 = repo.create(data={"team_id": TEAM_A, "kind": "calendar_event", "title": "Buen Fin", "payload": {"structured_brief": {"goal": "BF"}}})
    s2 = repo.create(data={"team_id": TEAM_A, "kind": "catalog_signal", "title": "Liquida X"})

    listed = client.get("/api/v1/suggestions", headers=AUTH_TEAM_A)
    assert listed.status_code == 200
    assert {s["title"] for s in listed.json()["suggestions"]} == {"Buen Fin", "Liquida X"}

    accepted = client.post(f"/api/v1/suggestions/{s1['id']}/accept", headers=AUTH_TEAM_A)
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["campaign_id"] == "33333333-3333-3333-3333-333333333333"
    assert body["suggestion"]["status"] == "accepted"
    assert created[0]["structured_brief"]["goal"] == "BF"

    dismissed = client.post(f"/api/v1/suggestions/{s2['id']}/dismiss", headers=AUTH_TEAM_A)
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"

    # Acting twice → 409; acting on someone else's suggestion → 404.
    assert client.post(f"/api/v1/suggestions/{s1['id']}/accept", headers=AUTH_TEAM_A).status_code == 409
    assert client.post(f"/api/v1/suggestions/{s1['id']}/accept", headers=AUTH_TEAM_B).status_code == 404

    remaining = client.get("/api/v1/suggestions", headers=AUTH_TEAM_A)
    assert remaining.json()["suggestions"] == []
