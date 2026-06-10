from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.core.auth import UserContext
from app.main import app
from app.schemas.campaign import Campaign, StructuredBrief
from app.schemas.generation import GenerationRunResponse

client = TestClient(app)
AUTH_TEAM_A = {"X-Aijolot-User-Id": "user-a", "X-Aijolot-Team-Id": "team-a", "X-Aijolot-Store-Id": "store-a"}
AUTH_TEAM_B = {"X-Aijolot-User-Id": "user-b", "X-Aijolot-Team-Id": "team-b", "X-Aijolot-Store-Id": "store-b"}


class ScopedCampaignService:
    def __init__(self, context: UserContext) -> None:
        self.context = context
        self.rows = {
            "cmp-a": Campaign(id="cmp-a", title="Team A", raw_brief="A", structured_brief=StructuredBrief(goal="A"), status="draft"),
            "cmp-b": Campaign(id="cmp-b", title="Team B", raw_brief="B", structured_brief=StructuredBrief(goal="B"), status="draft"),
        }
        self.owners = {"cmp-a": "team-a", "cmp-b": "team-b"}

    def list_campaigns(self, *, limit: int = 100) -> list[Campaign]:
        return [row for campaign_id, row in self.rows.items() if self.owners[campaign_id] == self.context.team_id][:limit]

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        if self.owners.get(campaign_id) != self.context.team_id:
            return None
        return self.rows.get(campaign_id)

    def create_campaign(self, *, title: str = "", raw_brief: str = "") -> Campaign:
        return Campaign(id=f"{self.context.team_id}-new", title=title, raw_brief=raw_brief, structured_brief=StructuredBrief(), status="draft")

    def apply_patch(self, campaign_id: str, fields: dict[str, Any]) -> Campaign | None:
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            return None
        if "title" in fields:
            campaign.title = fields["title"]
        return campaign

    def intake(self, message: str, campaign_id: str | None, **kwargs: Any) -> tuple[Campaign, str]:
        campaign = Campaign(
            id=f"{self.context.team_id}-intake",
            title="Intake",
            raw_brief=message,
            structured_brief=StructuredBrief(goal=message),
            status="draft",
        )
        return campaign, f"reply for {self.context.team_id}"


def test_v1_campaign_routes_fail_closed_without_context(monkeypatch) -> None:
    from app.api import campaigns

    monkeypatch.setattr(campaigns, "_service_for_context", lambda context: ScopedCampaignService(context))

    assert client.get("/api/v1/campaigns").status_code == 401
    assert client.post("/api/v1/campaigns", json={"title": "x"}).status_code == 401
    assert client.get("/api/v1/campaigns/cmp-a").status_code == 401
    assert client.patch("/api/v1/campaigns/cmp-a", json={"title": "x"}).status_code == 401


def test_v1_campaign_routes_fail_closed_without_context_on_default_service() -> None:
    assert client.get("/api/v1/campaigns").status_code == 401
    assert client.post("/api/v1/campaigns", json={"title": "x"}).status_code == 401
    assert client.get("/api/v1/campaigns/cmp-a").status_code == 401
    assert client.patch("/api/v1/campaigns/cmp-a", json={"title": "x"}).status_code == 401


def test_v1_campaign_routes_do_not_leak_cross_team_data(monkeypatch) -> None:
    from app.api import campaigns

    monkeypatch.setattr(campaigns, "_service_for_context", lambda context: ScopedCampaignService(context))

    listed = client.get("/api/v1/campaigns", headers=AUTH_TEAM_A)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == ["cmp-a"]

    same_team = client.get("/api/v1/campaigns/cmp-a", headers=AUTH_TEAM_A)
    assert same_team.status_code == 200
    assert same_team.json()["title"] == "Team A"

    cross_team = client.get("/api/v1/campaigns/cmp-b", headers=AUTH_TEAM_A)
    assert cross_team.status_code == 404
    assert "Team B" not in cross_team.text


def test_v1_campaign_mutations_are_scoped_to_request_team(monkeypatch) -> None:
    from app.api import campaigns

    monkeypatch.setattr(campaigns, "_service_for_context", lambda context: ScopedCampaignService(context))

    created = client.post("/api/v1/campaigns", headers=AUTH_TEAM_B, json={"title": "New B", "raw_brief": "Brief B"})
    assert created.status_code == 200
    assert created.json()["id"] == "team-b-new"

    patched = client.patch("/api/v1/campaigns/cmp-a", headers=AUTH_TEAM_B, json={"title": "stolen"})
    assert patched.status_code == 404


def test_v1_campaign_default_in_memory_service_does_not_leak_between_request_teams() -> None:
    created = client.post("/api/v1/campaigns", headers=AUTH_TEAM_A, json={"title": "Secret A", "raw_brief": "A"})
    assert created.status_code == 200
    campaign_id = created.json()["id"]

    team_b_list = client.get("/api/v1/campaigns", headers=AUTH_TEAM_B)
    assert team_b_list.status_code == 200
    assert campaign_id not in {row["id"] for row in team_b_list.json()}

    team_b_get = client.get(f"/api/v1/campaigns/{campaign_id}", headers=AUTH_TEAM_B)
    assert team_b_get.status_code == 404
    assert "Secret A" not in team_b_get.text


def test_v1_intake_fails_closed_without_context() -> None:
    response = client.post("/api/v1/campaigns/intake", json={"message": "Promo en la home"})

    assert response.status_code == 401


def test_v1_intake_uses_request_scoped_campaign_service(monkeypatch) -> None:
    from app.services import campaign_store

    seen: dict[str, str | None] = {}

    def scoped_service(context: UserContext) -> ScopedCampaignService:
        seen["team_id"] = context.team_id
        seen["store_id"] = context.store_id
        return ScopedCampaignService(context)

    monkeypatch.setattr(campaign_store, "get_service_for_context", scoped_service)

    with client.stream("POST", "/api/v1/campaigns/intake", headers=AUTH_TEAM_B, json={"message": "Promo en la home"}) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert seen == {"team_id": "team-b", "store_id": "store-b"}
    assert "team-b-intake" in body


def test_art_catalog_and_placement_routes_fail_closed_without_context() -> None:
    campaign_id = "00000000-0000-0000-0000-000000000401"
    store_id = "00000000-0000-0000-0000-000000000301"

    assert client.get("/api/v1/brands").status_code == 401
    assert client.post("/api/v1/brands/avocado_store/discovery-runs", json={}).status_code == 401
    assert client.get("/api/v1/brands/avocado_store/discovery-runs/00000000-0000-0000-0000-000000000601").status_code == 401
    assert (
        client.post("/api/v1/brands/avocado_store/discovery-runs/00000000-0000-0000-0000-000000000601/recommendations").status_code
        == 401
    )
    assert client.get("/api/v1/stores").status_code == 401
    team_b_brands = client.get("/api/v1/brands", headers=AUTH_TEAM_B)
    assert team_b_brands.status_code == 200
    assert team_b_brands.json() == []
    assert client.get(f"/api/v1/campaigns/{campaign_id}/art-direction").status_code == 401
    assert client.put(f"/api/v1/campaigns/{campaign_id}/art-direction", json={"background_mode": "hero"}).status_code == 401
    assert client.get(f"/api/v1/campaigns/{campaign_id}/catalog-snapshot").status_code == 401
    assert client.post(f"/api/v1/campaigns/{campaign_id}/catalog-snapshot", json={}).status_code == 401
    assert client.get(f"/api/v1/stores/{store_id}/placement-types").status_code == 401
    assert client.get(f"/api/v1/stores/{store_id}/placement-types/hero_main/targets").status_code == 401
    placement_payload = {
        "store_id": store_id,
        "placement_type_key": "hero_main",
        "mode": "new_section",
        "target_type": "home",
    }
    assert client.post("/api/v1/placements/validate", json=placement_payload).status_code == 401
    assert client.get(f"/api/v1/campaigns/{campaign_id}/placement").status_code == 401
    assert client.post(f"/api/v1/campaigns/{campaign_id}/placement", json=placement_payload).status_code == 401


def test_art_catalog_and_placement_default_services_are_team_scoped(monkeypatch) -> None:
    from app.api.v1 import art_direction, catalog, placements

    seen: dict[str, str] = {}

    class ArtService:
        def __init__(self, team_id: str) -> None:
            self.team_id = team_id

        def get_art_direction(self, campaign_id: str):
            seen["art"] = self.team_id
            from app.services.banners.art_direction_service import ArtDirectionNotFound

            raise ArtDirectionNotFound(campaign_id)

    class CatalogService:
        def __init__(self, team_id: str) -> None:
            self.team_id = team_id

        def get_snapshot(self, campaign_id: str):
            seen["catalog"] = self.team_id
            from app.services.banners.catalog_snapshot_service import CampaignCatalogSnapshotNotFound

            raise CampaignCatalogSnapshotNotFound(campaign_id)

    class PlacementSvc:
        def __init__(self, team_id: str) -> None:
            self.team_id = team_id

        def list_placement_types(self, store_id: str):
            seen["placement"] = self.team_id
            return []

    monkeypatch.setattr(art_direction, "configured_service_for_team", lambda team_id: ArtService(team_id))
    monkeypatch.setattr(catalog, "configured_service_for_team", lambda team_id: CatalogService(team_id))
    monkeypatch.setattr(placements, "configured_service_for_team", lambda team_id: PlacementSvc(team_id))

    campaign_id = "00000000-0000-0000-0000-000000000401"
    store_id = "00000000-0000-0000-0000-000000000301"
    assert client.get(f"/api/v1/campaigns/{campaign_id}/art-direction", headers=AUTH_TEAM_B).status_code == 404
    assert client.get(f"/api/v1/campaigns/{campaign_id}/catalog-snapshot", headers=AUTH_TEAM_B).status_code == 404
    assert client.get(f"/api/v1/stores/{store_id}/placement-types", headers=AUTH_TEAM_B).status_code == 200
    assert seen == {"art": "team-b", "catalog": "team-b", "placement": "team-b"}


def test_generation_mutation_fails_closed_without_context() -> None:
    campaign_id = "00000000-0000-0000-0000-000000000401"

    response = client.post(f"/api/v1/campaigns/{campaign_id}/generation-runs", json={})

    assert response.status_code == 401


def test_generation_default_service_is_scoped_to_request_team(monkeypatch) -> None:
    from app.api.v1 import generation

    seen: dict[str, str] = {}

    class TeamScopedGenerationService:
        def __init__(self, team_id: str) -> None:
            self.team_id = team_id

        def start_generation_run(self, campaign_id: str, request) -> GenerationRunResponse:
            seen["team_id"] = self.team_id
            return GenerationRunResponse(
                id="00000000-0000-0000-0000-000000000501",
                campaign_id=campaign_id,
                status="queued",
                frontend_step="intake_context",
                run_type="initial",
                progress=[],
                metadata={},
                error_message=None,
                started_by=None,
                parent_run_id=None,
                started_at="2026-06-01T00:00:00Z",
                finished_at=None,
            )

    monkeypatch.setattr(generation, "configured_service_for_team", lambda team_id: TeamScopedGenerationService(team_id))

    campaign_id = "00000000-0000-0000-0000-000000000401"
    response = client.post(f"/api/v1/campaigns/{campaign_id}/generation-runs", headers=AUTH_TEAM_B, json={})

    assert response.status_code == 200
    assert seen["team_id"] == "team-b"


def test_generation_run_lookup_hides_cross_team_campaign_id(monkeypatch) -> None:
    from app.api.v1 import generation
    from app.services.banners.generation_run_service import CampaignNotFound

    class CrossTeamGenerationService:
        def get_run(self, run_id: str) -> GenerationRunResponse:
            raise CampaignNotFound("00000000-0000-0000-0000-secretteamid")

    monkeypatch.setattr(generation, "configured_service_for_team", lambda team_id: CrossTeamGenerationService())

    response = client.get("/api/v1/generation-runs/00000000-0000-0000-0000-000000000501", headers=AUTH_TEAM_A)

    assert response.status_code == 404
    assert "secretteamid" not in response.text


def test_generation_default_in_memory_runs_do_not_leak_between_request_teams() -> None:
    campaign_id = "00000000-0000-0000-0000-00000000aaa1"
    created = client.post(f"/api/v1/campaigns/{campaign_id}/generation-runs", headers=AUTH_TEAM_A, json={})
    assert created.status_code == 200
    run_id = created.json()["id"]

    team_b_get = client.get(f"/api/v1/generation-runs/{run_id}", headers=AUTH_TEAM_B)
    assert team_b_get.status_code == 404
    assert campaign_id not in team_b_get.text

    team_b_events = client.get(f"/api/v1/generation-runs/{run_id}/events", headers=AUTH_TEAM_B)
    assert team_b_events.status_code == 404
    assert campaign_id not in team_b_events.text
