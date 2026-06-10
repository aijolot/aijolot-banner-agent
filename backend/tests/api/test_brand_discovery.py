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

from app.main import app
from app.schemas.brand_discovery import BrandDiscoverySnapshot
from app.services.brands import brand_discovery_service as discovery_module
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
    assert body["recommendation"] == {}  # reserved for Task 5
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
# /api/v1 canonical routes (request-scoped team context)
# ---------------------------------------------------------------------------


def test_v1_discovery_routes_fail_closed_without_context(harness) -> None:
    assert client.post("/api/v1/brands/demo_brand/discovery-runs", json={}).status_code == 401
    assert client.get(f"/api/v1/brands/demo_brand/discovery-runs/{UNKNOWN_RUN_ID}").status_code == 401
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


def test_discovery_routes_are_present_in_openapi_contract() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/brands/{brand_id}/discovery-runs" in paths
    assert "/api/v1/brands/{brand_id}/discovery-runs/{run_id}" in paths
    assert "/brands/{brand_id}/discovery-runs" in paths
    assert "/brands/{brand_id}/discovery-runs/{run_id}" in paths
