"""API tests for the brand discovery run workflow (Task 4).

No network, no live Supabase: the route-level factory
(``brand_discovery_service.configured_discovery_service``) is monkeypatched with
fake repositories/clients and the evidence collector is stubbed, mirroring how
``test_brands.py`` stubs the brand store and Gemini.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agents.tools import gemini_text
from app.main import app
from app.schemas.brand_discovery import BrandDiscoverySnapshot
from app.services.brands import brand_discovery_service as discovery_module
from app.services.brands import brand_recommendations as recommendations_module
from app.services.brands.brand_discovery_service import BrandDiscoveryService
from app.services.brands.brand_service import BrandService

client = TestClient(app)
AUTH_TEAM_1 = {"X-Aijolot-User-Id": "user-1", "X-Aijolot-Team-Id": "team-1"}
AUTH_TEAM_2 = {"X-Aijolot-User-Id": "user-2", "X-Aijolot-Team-Id": "team-2"}
KNOWN_STORE_ID = "00000000-0000-0000-0000-000000000301"
UNKNOWN_RUN_ID = "00000000-0000-0000-0000-0000000009ff"


def _clear_supabase_env(monkeypatch) -> None:
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "BRAND_CONTEXT_TEAM_ID", "SUPABASE_TEAM_ID"):
        monkeypatch.delenv(key, raising=False)


def _brand_row(slug: str, team_id: str = "team-1") -> dict[str, Any]:
    return {
        "id": f"uuid-{slug}",
        "team_id": team_id,
        "slug": slug,
        "name": slug.replace("_", " ").title(),
        "palette": [{"name": "Ink", "hex": "#111111"}],
        "typography": {"display": "Inter", "body": "Inter"},
        "voice": {"tone": ["Clear"], "required_phrases": [], "prohibited_words": []},
        "source_metadata": {"shopify": {"store_domain": "runtime.myshopify.com"}},
    }


class FakeBrandRepository:
    """brand_contexts stand-in (get_by_slug for reads, update_fields for snapshots)."""

    def __init__(self, slugs: tuple[str, ...] = ("demo_brand", "other_brand")) -> None:
        self.rows = {slug: _brand_row(slug) for slug in slugs}

    def list(self, *, team_id: str):
        return list(self.rows.values())

    def get_by_slug(self, *, team_id: str, slug: str):
        return self.rows.get(slug)

    def upsert(self, *, team_id: str, slug: str, data: dict, store_id=None, created_by=None):
        self.rows[slug] = {**data, "id": f"uuid-{slug}", "team_id": team_id, "slug": slug}
        return self.rows[slug]

    def update_fields(self, *, team_id: str, slug: str, data: dict):
        row = self.rows.get(slug)
        if row is None:
            return None
        row.update(data)
        return row


class FakeRunsRepository:
    """brand_discovery_runs stand-in with team scoping like the Supabase repo."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def insert(self, *, team_id, brand_id, status="pending", snapshot=None, recommendation=None, store_id=None):
        self._counter += 1
        run_id = f"00000000-0000-0000-0000-{self._counter:012d}"
        row = {
            "id": run_id,
            "team_id": team_id,
            "brand_id": brand_id,
            "store_id": store_id,
            "status": status,
            "snapshot": snapshot or {},
            "recommendation": recommendation or {},
            "created_at": "2026-06-10T00:00:00+00:00",
            "updated_at": "2026-06-10T00:00:00+00:00",
        }
        self.rows[run_id] = row
        return dict(row)

    def get(self, *, run_id, team_id=None):
        row = self.rows.get(run_id)
        if row is None or (team_id and row["team_id"] != team_id):
            return None
        return dict(row)

    def update_status(self, *, run_id, status, team_id=None, snapshot=None, recommendation=None):
        row = self.rows.get(run_id)
        if row is None or (team_id and row["team_id"] != team_id):
            return None
        row["status"] = status
        if snapshot is not None:
            row["snapshot"] = snapshot
        if recommendation is not None:
            row["recommendation"] = recommendation
        row["updated_at"] = "2026-06-10T00:00:01+00:00"
        return dict(row)


class FakeStoreRepository:
    def __init__(self) -> None:
        self.rows = {KNOWN_STORE_ID: {"id": KNOWN_STORE_ID, "team_id": "team-1", "shop_domain": "demo-apparel.myshopify.com"}}

    def get(self, *, store_id, team_id=None):
        row = self.rows.get(store_id)
        if row is None or (team_id and row["team_id"] != team_id):
            return None
        return dict(row)


class FakeAdminClient:
    """Only the attribute the service reads; the collector itself is stubbed."""

    shop_domain = "demo-apparel.myshopify.com"
    access_token = "shpat_secret_never_leaks"  # noqa: S105 - proves the token never reaches payloads


class DiscoveryHarness:
    """Shared fake wiring; ``factory`` replaces configured_discovery_service."""

    def __init__(self) -> None:
        self.runs = FakeRunsRepository()
        self.brand_repository = FakeBrandRepository()
        self.stores = FakeStoreRepository()
        self.admin_client: Any = FakeAdminClient()
        self.runs_available = True
        self.requested_team_ids: list[str | None] = []

    def factory(self, *, team_id: str | None = None) -> BrandDiscoveryService:
        self.requested_team_ids.append(team_id)
        resolved = team_id or "team-1"
        return BrandDiscoveryService(
            BrandService(repository=self.brand_repository, team_id=resolved),
            self.runs if self.runs_available else None,
            lambda: self.admin_client,
            store_repository=self.stores,
            team_id=resolved,
        )


@pytest.fixture()
def harness(monkeypatch) -> DiscoveryHarness:
    fake = DiscoveryHarness()
    monkeypatch.setattr(discovery_module, "configured_discovery_service", fake.factory)
    return fake


def _snapshot(brand_id: str = "demo_brand", status: str = "succeeded", errors: tuple[str, ...] = ()) -> BrandDiscoverySnapshot:
    return BrandDiscoverySnapshot(
        id="disc_abc123def456",
        brand_id=brand_id,
        shop_domain="demo-apparel.myshopify.com",
        status=status,
        discovered_at=datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc),
        source_summary="theme: Dawn (id 99)",
        colors=[{"hex": "#112233", "name": "ink", "source": "theme_settings:config/settings_data.json", "confidence": 0.9}],
        fonts=[{"family": "Archivo Black", "source": "css:assets/base.css", "confidence": 0.6}],
        theme_metadata={"theme_name": "Dawn", "theme_id": "99"},
        errors=list(errors),
    )


def _stub_collector(monkeypatch, result: BrandDiscoverySnapshot | Exception) -> dict[str, Any]:
    calls: dict[str, Any] = {}

    def fake_collect(client, *, brand_id, shop_domain, store_id=None, **kwargs):
        calls.update({"client": client, "brand_id": brand_id, "shop_domain": shop_domain, "store_id": store_id})
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(discovery_module, "collect_brand_evidence", fake_collect)
    return calls


def _gemini_recommendation_payload() -> dict[str, Any]:
    base = {
        "usage_hint": "Use it in banners.",
        "agent_hint": "Guidance for the agent.",
        "variants": [],
        "rationale": "Backed by theme evidence.",
        "evidence_refs": ["theme_settings:config/settings_data.json"],
    }
    return {
        "colors": [
            {**base, "role_key": "primary", "base_hex": "#112233", "label": "Theme Ink"},
            {**base, "role_key": "secondary", "base_hex": "#F4EDE2", "label": "Sand"},
            {**base, "role_key": "tertiary", "base_hex": "#FF6B5C", "label": "Coral Pop"},
        ],
        "summary": "Navy-led palette from theme settings.",
    }


def _stub_gemini(monkeypatch, result: Any) -> dict[str, Any]:
    """Fake the Gemini call inside BrandRecommendationService (no real AI in tests)."""

    captured: dict[str, Any] = {}

    async def fake_generate(prompt, *, model, structured=None):
        captured["prompt"] = prompt
        captured["model"] = model
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(recommendations_module.gemini_text, "generate", fake_generate)
    return captured


# ---------------------------------------------------------------------------
# POST /brands/{brand_id}/discovery-runs (root prototype)
# ---------------------------------------------------------------------------


def test_root_post_creates_succeeded_run_and_persists_snapshot(harness, monkeypatch) -> None:
    calls = _stub_collector(monkeypatch, _snapshot())

    response = client.post("/brands/demo_brand/discovery-runs", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["brand_id"] == "demo_brand"
    assert body["status"] == "succeeded"
    assert body["store_id"] is None
    assert body["recommendation"] == {}  # stays empty until POST .../recommendations runs
    assert body["created_at"] and body["updated_at"]
    assert body["snapshot"]["colors"][0]["hex"] == "#112233"
    assert body["snapshot"]["fonts"][0]["family"] == "Archivo Black"
    assert "shpat_secret_never_leaks" not in response.text

    # Collector got the request-scoped client and the client's shop domain.
    assert calls["client"] is harness.admin_client
    assert calls["brand_id"] == "demo_brand"
    assert calls["shop_domain"] == "demo-apparel.myshopify.com"

    # Run row finalized (no orphaned "running" rows on the happy path).
    stored_run = harness.runs.rows[body["id"]]
    assert stored_run["status"] == "succeeded"
    assert stored_run["snapshot"]["status"] == "succeeded"

    # Latest snapshot mirrored onto the brand row via save_discovery_snapshot.
    assert harness.brand_repository.rows["demo_brand"]["discovery_snapshot"]["status"] == "succeeded"


def test_root_post_validates_store_id_against_team_stores(harness, monkeypatch) -> None:
    calls = _stub_collector(monkeypatch, _snapshot())

    accepted = client.post("/brands/demo_brand/discovery-runs", json={"store_id": KNOWN_STORE_ID})
    assert accepted.status_code == 200
    assert accepted.json()["store_id"] == KNOWN_STORE_ID
    assert calls["store_id"] == KNOWN_STORE_ID

    unknown = client.post(
        "/brands/demo_brand/discovery-runs",
        json={"store_id": "00000000-0000-0000-0000-0000000003ff"},
    )
    assert unknown.status_code == 404
    assert "not found" in unknown.json()["detail"]


def test_post_unknown_brand_returns_404(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())

    response = client.post("/brands/nope/discovery-runs", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "brand 'nope' not found"
    assert harness.runs.rows == {}


def test_post_missing_shopify_client_returns_503(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())
    harness.admin_client = None

    response = client.post("/brands/demo_brand/discovery-runs", json={})

    assert response.status_code == 503
    assert "Shopify Admin credentials" in response.json()["detail"]
    assert harness.runs.rows == {}  # no run row when discovery cannot start


def test_post_without_runs_persistence_returns_503(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())
    harness.runs_available = False

    response = client.post("/brands/demo_brand/discovery-runs", json={})

    assert response.status_code == 503
    assert "Supabase" in response.json()["detail"]


def test_root_routes_in_markdown_fallback_mode_return_503_not_fake_runs(monkeypatch) -> None:
    _clear_supabase_env(monkeypatch)  # real factory, markdown/demo mode

    started = client.post("/brands/avocado_store/discovery-runs", json={})
    assert started.status_code == 503
    assert "Supabase" in started.json()["detail"]

    fetched = client.get(f"/brands/avocado_store/discovery-runs/{UNKNOWN_RUN_ID}")
    assert fetched.status_code == 503


def test_post_partial_discovery_returns_200_with_errors(harness, monkeypatch) -> None:
    partial = _snapshot(status="partial", errors=("theme_assets: asset listing failed (403)",))
    _stub_collector(monkeypatch, partial)

    response = client.post("/brands/demo_brand/discovery-runs", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["snapshot"]["errors"] == ["theme_assets: asset listing failed (403)"]
    assert harness.runs.rows[body["id"]]["status"] == "partial"


def test_post_collector_crash_marks_run_failed(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, RuntimeError("kaboom"))

    response = client.post("/brands/demo_brand/discovery-runs", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert any("kaboom" in error for error in body["snapshot"]["errors"])

    stored_run = harness.runs.rows[body["id"]]
    assert stored_run["status"] == "failed"  # not left "running"
    assert any("kaboom" in error for error in stored_run["snapshot"]["errors"])


# ---------------------------------------------------------------------------
# GET /brands/{brand_id}/discovery-runs/{run_id} (root prototype)
# ---------------------------------------------------------------------------


def test_get_returns_run_and_unknown_run_404(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())
    run_id = client.post("/brands/demo_brand/discovery-runs", json={}).json()["id"]

    found = client.get(f"/brands/demo_brand/discovery-runs/{run_id}")
    assert found.status_code == 200
    assert found.json()["id"] == run_id
    assert found.json()["status"] == "succeeded"
    assert found.json()["snapshot"]["shop_domain"] == "demo-apparel.myshopify.com"

    assert client.get(f"/brands/demo_brand/discovery-runs/{UNKNOWN_RUN_ID}").status_code == 404
    assert client.get("/brands/demo_brand/discovery-runs/not-a-uuid").status_code == 422


def test_get_run_through_other_brand_path_is_404(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())
    run_id = client.post("/brands/demo_brand/discovery-runs", json={}).json()["id"]

    response = client.get(f"/brands/other_brand/discovery-runs/{run_id}")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /brands/{brand_id}/discovery-runs/{run_id}/recommendations (Task 5)
# ---------------------------------------------------------------------------


def test_root_recommendations_persist_gemini_draft_and_return_updated_run(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())
    captured = _stub_gemini(monkeypatch, _gemini_recommendation_payload())
    run_id = client.post("/brands/demo_brand/discovery-runs", json={}).json()["id"]

    response = client.post(f"/brands/demo_brand/discovery-runs/{run_id}/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == run_id
    assert body["status"] == "succeeded"  # run status unchanged by the recommendation step
    recommendation = body["recommendation"]
    assert [color["role_key"] for color in recommendation["colors"]] == ["primary", "secondary", "tertiary"]
    assert recommendation["colors"][0]["base_hex"] == "#112233"
    assert recommendation["colors"][0]["evidence_refs"] == ["theme_settings:config/settings_data.json"]
    assert recommendation["summary"] == "Navy-led palette from theme settings."
    assert recommendation["fonts"] == []  # reserved for Task 6
    assert "shpat_secret_never_leaks" not in response.text

    # Draft persisted onto the run row, snapshot left untouched.
    stored_run = harness.runs.rows[run_id]
    assert stored_run["status"] == "succeeded"
    assert stored_run["recommendation"]["summary"] == "Navy-led palette from theme settings."
    assert stored_run["snapshot"]["colors"][0]["hex"] == "#112233"

    # The Gemini prompt carried the snapshot evidence and the existing brand roles.
    prompt = str(captured["prompt"])
    assert "#112233" in prompt
    assert "theme_settings:config/settings_data.json" in prompt
    assert "#111111" in prompt  # existing approved color system (derived from the brand palette)


def test_root_recommendations_unknown_run_returns_404(harness, monkeypatch) -> None:
    _stub_gemini(monkeypatch, _gemini_recommendation_payload())

    response = client.post(f"/brands/demo_brand/discovery-runs/{UNKNOWN_RUN_ID}/recommendations")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_root_recommendations_cross_brand_run_returns_404(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())
    _stub_gemini(monkeypatch, _gemini_recommendation_payload())
    run_id = client.post("/brands/demo_brand/discovery-runs", json={}).json()["id"]

    response = client.post(f"/brands/other_brand/discovery-runs/{run_id}/recommendations")

    assert response.status_code == 404
    assert harness.runs.rows[run_id]["recommendation"] == {}


def test_root_recommendations_run_without_snapshot_returns_409(harness, monkeypatch) -> None:
    _stub_gemini(monkeypatch, _gemini_recommendation_payload())
    row = harness.runs.insert(team_id="team-1", brand_id="demo_brand", status="running")

    response = client.post(f"/brands/demo_brand/discovery-runs/{row['id']}/recommendations")

    assert response.status_code == 409
    assert "has no snapshot" in response.json()["detail"]
    assert harness.runs.rows[row["id"]]["recommendation"] == {}


def test_root_recommendations_gemini_unavailable_returns_503_and_persists_nothing(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())
    _stub_gemini(monkeypatch, gemini_text.GeminiUnavailable("Gemini is unavailable: set GOOGLE_API_KEY"))
    run_id = client.post("/brands/demo_brand/discovery-runs", json={}).json()["id"]

    response = client.post(f"/brands/demo_brand/discovery-runs/{run_id}/recommendations")

    assert response.status_code == 503
    assert "Gemini is unavailable" in response.json()["detail"]
    assert harness.runs.rows[run_id]["recommendation"] == {}  # no fake/deterministic fallback draft


# ---------------------------------------------------------------------------
# /api/v1 canonical routes (request-scoped team context)
# ---------------------------------------------------------------------------


def test_v1_discovery_routes_fail_closed_without_context(harness) -> None:
    assert client.post("/api/v1/brands/demo_brand/discovery-runs", json={}).status_code == 401
    assert client.get(f"/api/v1/brands/demo_brand/discovery-runs/{UNKNOWN_RUN_ID}").status_code == 401
    assert client.post(f"/api/v1/brands/demo_brand/discovery-runs/{UNKNOWN_RUN_ID}/recommendations").status_code == 401
    assert harness.requested_team_ids == []  # no service is even built without auth


def test_v1_post_and_get_use_request_team_scope(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())

    created = client.post("/api/v1/brands/demo_brand/discovery-runs", headers=AUTH_TEAM_1, json={})
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "succeeded"
    assert harness.requested_team_ids == ["team-1"]
    assert harness.runs.rows[body["id"]]["team_id"] == "team-1"

    same_team = client.get(f"/api/v1/brands/demo_brand/discovery-runs/{body['id']}", headers=AUTH_TEAM_1)
    assert same_team.status_code == 200
    assert same_team.json()["id"] == body["id"]


def test_v1_get_run_from_other_team_is_404(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())
    run_id = client.post("/api/v1/brands/demo_brand/discovery-runs", headers=AUTH_TEAM_1, json={}).json()["id"]

    cross_team = client.get(f"/api/v1/brands/demo_brand/discovery-runs/{run_id}", headers=AUTH_TEAM_2)

    assert cross_team.status_code == 404
    assert "team-1" not in cross_team.text


def test_v1_unknown_brand_returns_404(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())

    response = client.post("/api/v1/brands/nope/discovery-runs", headers=AUTH_TEAM_1, json={})

    assert response.status_code == 404


def test_v1_recommendations_use_request_team_scope(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())
    _stub_gemini(monkeypatch, _gemini_recommendation_payload())
    run_id = client.post("/api/v1/brands/demo_brand/discovery-runs", headers=AUTH_TEAM_1, json={}).json()["id"]

    recommended = client.post(
        f"/api/v1/brands/demo_brand/discovery-runs/{run_id}/recommendations", headers=AUTH_TEAM_1
    )

    assert recommended.status_code == 200
    body = recommended.json()
    assert [color["role_key"] for color in body["recommendation"]["colors"]] == ["primary", "secondary", "tertiary"]
    assert harness.requested_team_ids == ["team-1", "team-1"]
    assert harness.runs.rows[run_id]["recommendation"]["summary"] == "Navy-led palette from theme settings."

    # The persisted draft is also visible on subsequent reads of the run.
    fetched = client.get(f"/api/v1/brands/demo_brand/discovery-runs/{run_id}", headers=AUTH_TEAM_1)
    assert fetched.status_code == 200
    assert fetched.json()["recommendation"]["colors"][0]["base_hex"] == "#112233"


def test_v1_recommendations_from_other_team_is_404(harness, monkeypatch) -> None:
    _stub_collector(monkeypatch, _snapshot())
    _stub_gemini(monkeypatch, _gemini_recommendation_payload())
    run_id = client.post("/api/v1/brands/demo_brand/discovery-runs", headers=AUTH_TEAM_1, json={}).json()["id"]

    cross_team = client.post(
        f"/api/v1/brands/demo_brand/discovery-runs/{run_id}/recommendations", headers=AUTH_TEAM_2
    )

    assert cross_team.status_code == 404
    assert "team-1" not in cross_team.text
    assert harness.runs.rows[run_id]["recommendation"] == {}


def test_discovery_routes_are_present_in_openapi_contract() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/brands/{brand_id}/discovery-runs" in paths
    assert "/api/v1/brands/{brand_id}/discovery-runs/{run_id}" in paths
    assert "/api/v1/brands/{brand_id}/discovery-runs/{run_id}/recommendations" in paths
    assert "/api/v1/brands/{brand_id}/apply-discovery-recommendations" in paths
    assert "/brands/{brand_id}/discovery-runs" in paths
    assert "/brands/{brand_id}/discovery-runs/{run_id}" in paths
    assert "/brands/{brand_id}/discovery-runs/{run_id}/recommendations" in paths
    assert "/brands/{brand_id}/apply-discovery-recommendations" in paths


# ---------------------------------------------------------------------------
# POST /brands/{brand_id}/apply-discovery-recommendations (Task 7)
# ---------------------------------------------------------------------------


@pytest.fixture()
def apply_store(monkeypatch) -> FakeBrandRepository:
    """Route brand storage (root ``_default_service`` + v1 ``service_for_team``)
    onto one fake repository, mirroring how test_brands.py stubs the brand store."""

    from app.services import brand_store

    repository = FakeBrandRepository()
    seen_teams: list[str] = []

    def for_team(team_id: str) -> BrandService:
        seen_teams.append(team_id)
        return BrandService(repository=repository, team_id=team_id)

    monkeypatch.setattr(brand_store, "_default_service", lambda: BrandService(repository=repository, team_id="team-1"))
    monkeypatch.setattr(brand_store, "service_for_team", for_team)
    repository.seen_teams = seen_teams  # type: ignore[attr-defined]
    return repository


def _apply_payload(**overrides) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": "00000000-0000-0000-0000-000000000001",
        "colors": [
            {
                "role_key": "tertiary",
                "base_hex": "#FF6B5C",
                "label": "Coral CTA",
                "usage_hint": "CTA buttons and promo badges.",
                "agent_hint": "Reserve for promo moments.",
                "variants": [{"name": "Coral Hover", "hex": "#FF8478", "usage_hint": "Hover", "source": "ai_suggested"}],
                "rationale": "Warm contrast against the discovered ink.",
                "evidence_refs": ["snapshot:colors:0"],
            }
        ],
        "logo_url": "https://cdn.shopify.com/demo/logo.svg",
        "image_style_directives": ["Soft daylight", "Linen texture"],
        "approved_fonts": [
            {
                "family": "Sora",
                "css_stack": '"Sora", sans-serif',
                "category": "sans",
                "source": "gemini_suggested",
                "status": "candidate",
                "recommended_roles": ["headline"],
                "rationale": "Matches the wordmark.",
            }
        ],
        "discarded_fonts": [
            {
                "family": "Papyrus",
                "css_stack": "Papyrus, fantasy",
                "category": "handwritten",
                "source": "shopify_theme",
                "status": "candidate",
            }
        ],
        "typography_roles": {"headline": "Sora"},
    }
    payload.update(overrides)
    return payload


def test_root_apply_merges_accepted_recommendations_and_persists(apply_store) -> None:
    response = client.post("/brands/demo_brand/apply-discovery-recommendations", json=_apply_payload())

    assert response.status_code == 200
    body = response.json()
    # Accepted role replaced wholesale; the other roles keep the palette-derived values.
    assert body["color_system"]["tertiary"]["label"] == "Coral CTA"
    assert body["color_system"]["tertiary"]["hex"] == "#FF6B5C"
    assert body["color_system"]["tertiary"]["variants"][0]["source"] == "ai_suggested"
    assert body["color_system"]["primary"]["hex"] == "#111111"
    assert body["color_system"]["secondary"]["hex"] == "#111111"
    # Legacy palette synced to the three post-merge role colors.
    assert [color["hex"] for color in body["palette"]] == ["#111111", "#111111", "#FF6B5C"]
    assert body["palette"][2]["name"] == "Coral CTA"
    # Fonts: approved with status flipped, discarded persisted; role assigned.
    assert [font["family"] for font in body["typography"]["approved_fonts"]] == ["Sora"]
    assert body["typography"]["approved_fonts"][0]["status"] == "approved"
    assert [font["family"] for font in body["typography"]["discarded_fonts"]] == ["Papyrus"]
    assert body["typography"]["discarded_fonts"][0]["status"] == "discarded"
    assert body["typography"]["headline"] == "Sora"
    assert body["typography"]["display"] == "Inter"  # legacy fields untouched
    assert body["typography"]["body"] == "Inter"
    assert body["logo_url"] == "https://cdn.shopify.com/demo/logo.svg"
    assert body["image_style_directives"] == ["Soft daylight", "Linen texture"]

    # Persisted through save_brand: the merged brand survives a reload.
    row = apply_store.rows["demo_brand"]
    assert row["color_system"]["tertiary"]["hex"] == "#FF6B5C"
    assert row["typography_system"]["headline"] == "Sora"
    assert [font["family"] for font in row["typography_system"]["discarded_fonts"]] == ["Papyrus"]
    reloaded = client.get("/brands/demo_brand")
    assert reloaded.status_code == 200
    assert reloaded.json() == body


def test_root_apply_empty_request_is_noop(apply_store) -> None:
    before = client.get("/brands/demo_brand").json()

    response = client.post("/brands/demo_brand/apply-discovery-recommendations", json={})

    assert response.status_code == 200
    assert response.json() == before
    # No write happened: upsert would have added the color_system column payload.
    assert "color_system" not in apply_store.rows["demo_brand"]


def test_root_apply_unknown_brand_returns_404(apply_store) -> None:
    response = client.post("/brands/nope/apply-discovery-recommendations", json=_apply_payload())

    assert response.status_code == 404
    assert response.json()["detail"] == "brand 'nope' not found"


def test_root_apply_unapproved_role_family_returns_422(apply_store) -> None:
    payload = _apply_payload(typography_roles={"headline": "Comic Neue"})

    response = client.post("/brands/demo_brand/apply-discovery-recommendations", json=payload)

    assert response.status_code == 422
    assert "'Comic Neue' is not in approved_fonts" in response.json()["detail"]
    assert "color_system" not in apply_store.rows["demo_brand"]  # nothing persisted


def test_root_apply_unknown_role_key_returns_422(apply_store) -> None:
    payload = _apply_payload(typography_roles={"hero": "Sora"})

    response = client.post("/brands/demo_brand/apply-discovery-recommendations", json=payload)

    assert response.status_code == 422
    assert "unknown typography role" in response.json()["detail"]


def test_root_apply_same_family_approved_and_discarded_returns_422(apply_store) -> None:
    payload = _apply_payload()
    payload["discarded_fonts"].append(
        {"family": "sora", "css_stack": '"Sora", sans-serif', "category": "sans", "source": "gemini_suggested"}
    )

    response = client.post("/brands/demo_brand/apply-discovery-recommendations", json=payload)

    assert response.status_code == 422
    assert "approved and discarded in the same request" in response.json()["detail"]
    assert "color_system" not in apply_store.rows["demo_brand"]


def test_root_apply_invalid_color_payload_returns_422(apply_store) -> None:
    payload = _apply_payload()
    payload["colors"][0]["base_hex"] = "not-a-color"

    response = client.post("/brands/demo_brand/apply-discovery-recommendations", json=payload)

    assert response.status_code == 422


def test_v1_apply_fails_closed_without_context(apply_store) -> None:
    response = client.post("/api/v1/brands/demo_brand/apply-discovery-recommendations", json=_apply_payload())

    assert response.status_code == 401
    assert apply_store.seen_teams == []  # no team service is even built without auth
    assert "color_system" not in apply_store.rows["demo_brand"]


def test_v1_apply_uses_request_team_scope_and_persists(apply_store) -> None:
    response = client.post(
        "/api/v1/brands/demo_brand/apply-discovery-recommendations", headers=AUTH_TEAM_1, json=_apply_payload()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["color_system"]["tertiary"]["hex"] == "#FF6B5C"
    assert body["typography"]["headline"] == "Sora"
    assert apply_store.seen_teams == ["team-1"]
    assert apply_store.rows["demo_brand"]["team_id"] == "team-1"

    fetched = client.get("/api/v1/brands/demo_brand", headers=AUTH_TEAM_1)
    assert fetched.status_code == 200
    assert fetched.json() == body


def test_v1_apply_unknown_brand_returns_404(apply_store) -> None:
    response = client.post(
        "/api/v1/brands/nope/apply-discovery-recommendations", headers=AUTH_TEAM_1, json=_apply_payload()
    )

    assert response.status_code == 404


def test_v1_apply_invalid_request_returns_422(apply_store) -> None:
    payload = _apply_payload(typography_roles={"headline": "Comic Neue"})

    response = client.post(
        "/api/v1/brands/demo_brand/apply-discovery-recommendations", headers=AUTH_TEAM_1, json=payload
    )

    assert response.status_code == 422
    assert "'Comic Neue' is not in approved_fonts" in response.json()["detail"]
