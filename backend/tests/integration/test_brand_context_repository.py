from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.settings import Settings
from app.db.repositories.brand_contexts import BrandContextRepository
from app.db.repositories.brand_discovery_runs import BrandDiscoveryRunRepository
from app.services.supabase.client import SupabaseClientFactory


pytestmark = pytest.mark.integration


def _extended_typography() -> dict:
    return {
        "display": "Archivo Black",
        "body": "Inter",
        "headline": "Archivo Black",
        "accent": "Caveat",
        "approved_fonts": [
            {
                "family": "Archivo Black",
                "css_stack": "'Archivo Black', 'Arial Black', sans-serif",
                "category": "display",
                "source": "shopify_theme",
                "status": "approved",
                "recommended_roles": ["display", "headline"],
                "rationale": "Storefront hero already uses it.",
                "evidence_refs": ["theme:config/settings_data.json"],
            }
        ],
        "discarded_fonts": [
            {
                "family": "Papyrus",
                "css_stack": "Papyrus, fantasy",
                "category": "handwritten",
                "source": "gemini_suggested",
                "status": "discarded",
                "recommended_roles": [],
                "rationale": "Off-brand.",
                "evidence_refs": [],
            }
        ],
    }


def _discovery_snapshot_dict(brand_id: str) -> dict:
    return {
        "id": f"run-{uuid4().hex[:8]}",
        "brand_id": brand_id,
        "store_id": None,
        "shop_domain": "pytest.myshopify.com",
        "status": "succeeded",
        "discovered_at": datetime.now(UTC).isoformat(),
        "source_summary": "Theme settings + storefront css.",
        "assets": [
            {"kind": "logo", "url": "https://cdn.example.com/logo.png", "source": "theme:config/settings_data.json"}
        ],
        "colors": [{"hex": "#112233", "name": "Ink", "source": "theme:config/settings_data.json", "confidence": 0.9}],
        "fonts": [{"family": "Archivo Black", "source": "css:assets/theme.css", "confidence": 0.8}],
        "theme_metadata": {"theme_name": "Dawn"},
        "errors": [],
    }


class _FakeTable:
    def __init__(self) -> None:
        self.payload: dict | None = None

    def upsert(self, payload: dict, *, on_conflict: str):
        self.payload = payload
        return self


class _FakeClient:
    def __init__(self) -> None:
        self.table_obj = _FakeTable()

    def table(self, name: str) -> _FakeTable:
        assert name == "brand_contexts"
        return self.table_obj


def test_repository_upsert_filters_payload_to_brand_context_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.db.repositories.brand_contexts as module

    fake_client = _FakeClient()

    def fake_execute_data(query):
        assert query is fake_client.table_obj
        assert fake_client.table_obj.payload is not None
        return fake_client.table_obj.payload

    monkeypatch.setattr(module, "execute_data", fake_execute_data)

    repo = BrandContextRepository(fake_client)  # type: ignore[arg-type]
    row = repo.upsert(
        team_id="00000000-0000-0000-0000-000000000001",
        slug="maison-hugo-boss-demo",
        data={
            "id": "api-id-must-not-reach-db",
            "name": "Maison Hugo Boss Demo",
            "palette": [],
            "color_system": {"primary": {"key": "primary", "hex": "#111111"}},
            "typography": {"display": "Inter", "body": "Inter"},
            "typography_system": {"display": "Inter", "body": "Inter", "approved_fonts": []},
            "discovery_snapshot": {"id": "run-1", "status": "succeeded"},
            "shopify": {"store_domain": "invalid-column.myshopify.com"},
            "notes": "invalid column",
            "source_metadata": {"notes": "valid metadata"},
        },
    )

    assert row["slug"] == "maison-hugo-boss-demo"
    assert row["name"] == "Maison Hugo Boss Demo"
    assert row["color_system"] == {"primary": {"key": "primary", "hex": "#111111"}}
    assert row["typography"] == {"display": "Inter", "body": "Inter"}
    assert row["typography_system"] == {"display": "Inter", "body": "Inter", "approved_fonts": []}
    assert row["discovery_snapshot"] == {"id": "run-1", "status": "succeeded"}
    assert row["source_metadata"] == {"notes": "valid metadata"}
    assert "id" not in row
    assert "shopify" not in row
    assert "notes" not in row


def _client_and_team_id():
    settings = Settings.from_env()
    team_id = os.getenv("BRAND_CONTEXT_TEAM_ID") or os.getenv("SUPABASE_TEAM_ID")
    if settings.supabase_url is None or settings.supabase_service_role_key is None or not team_id:
        pytest.skip("Supabase service-role settings and BRAND_CONTEXT_TEAM_ID are required")
    try:
        client = SupabaseClientFactory(settings).service_role_client()
        client.table("teams").select("id").eq("id", team_id).limit(1).execute()
    except Exception as exc:  # noqa: BLE001 - live integration availability check
        pytest.skip(f"Supabase is not available: {exc}")
    return client, team_id


def test_brand_context_repository_upserts_gets_lists_and_archives() -> None:
    client, team_id = _client_and_team_id()
    repo = BrandContextRepository(client)
    slug = f"pytest_brand_{uuid4().hex[:8]}"

    created = repo.upsert(
        team_id=team_id,
        slug=slug,
        data={
            "name": "Pytest Brand",
            "palette": [{"name": "Ink", "hex": "#111111"}],
            "typography": {"display": "Inter", "body": "Inter"},
            "voice": {"tone": ["Clear"], "prohibited_words": [], "required_phrases": []},
            "description": "Repository integration note.",
            "source_metadata": {
                "shopify": {"store_domain": "pytest.myshopify.com", "default_placement": "hero"},
                "notes": "Repository integration note.",
            },
        },
    )
    try:
        assert created["slug"] == slug
        assert created["source_metadata"]["shopify"]["store_domain"] == "pytest.myshopify.com"

        loaded = repo.get_by_slug(team_id=team_id, slug=slug)
        assert loaded is not None
        assert loaded["name"] == "Pytest Brand"

        slugs = {row["slug"] for row in repo.list(team_id=team_id)}
        assert slug in slugs
    finally:
        repo.archive(team_id=team_id, slug=slug)


def test_brand_context_repository_round_trips_typography_system_and_discovery_snapshot() -> None:
    client, team_id = _client_and_team_id()
    repo = BrandContextRepository(client)
    slug = f"pytest_fonts_{uuid4().hex[:8]}"
    typography_system = _extended_typography()
    snapshot = _discovery_snapshot_dict(slug)

    repo.upsert(
        team_id=team_id,
        slug=slug,
        data={
            "name": "Pytest Fonts Brand",
            "palette": [{"name": "Ink", "hex": "#111111"}],
            "typography": {"display": "Archivo Black", "body": "Inter"},
            "typography_system": typography_system,
            "discovery_snapshot": snapshot,
            "source_metadata": {"shopify": {"store_domain": "pytest.myshopify.com"}},
        },
    )
    try:
        loaded = repo.get_by_slug(team_id=team_id, slug=slug)
        assert loaded is not None
        # Legacy column stays the two-key shape; full system round-trips intact.
        assert loaded["typography"] == {"display": "Archivo Black", "body": "Inter"}
        assert loaded["typography_system"] == typography_system
        assert loaded["discovery_snapshot"] == snapshot
    finally:
        repo.archive(team_id=team_id, slug=slug)


def test_legacy_brand_rows_without_typography_system_keep_loading_with_defaults() -> None:
    from app.services.brands.brand_service import BrandService

    client, team_id = _client_and_team_id()
    repo = BrandContextRepository(client)
    slug = f"pytest_legacy_{uuid4().hex[:8]}"

    repo.upsert(
        team_id=team_id,
        slug=slug,
        data={
            "name": "Pytest Legacy Brand",
            "palette": [{"name": "Ink", "hex": "#111111"}],
            "typography": {"display": "Space Grotesk", "body": "Inter"},
            "source_metadata": {"shopify": {"store_domain": "pytest.myshopify.com"}},
        },
    )
    try:
        loaded = repo.get_by_slug(team_id=team_id, slug=slug)
        assert loaded is not None
        assert loaded["typography_system"] is None
        assert loaded["discovery_snapshot"] is None

        brand = BrandService._brand_from_record(loaded)
        assert brand.typography.display == "Space Grotesk"
        assert brand.typography.body == "Inter"
        assert brand.typography.headline is None
        assert brand.typography.accent is None
        assert brand.typography.approved_fonts == []
        assert brand.typography.discarded_fonts == []
    finally:
        repo.archive(team_id=team_id, slug=slug)


def test_brand_service_save_and_reload_round_trips_extended_typography_live() -> None:
    from app.schemas.brand import BrandContext
    from app.services.brands.brand_service import BrandService

    client, team_id = _client_and_team_id()
    repo = BrandContextRepository(client)
    service = BrandService(repository=repo, team_id=team_id)
    slug = f"pytest_service_{uuid4().hex[:8]}"
    brand = BrandContext(
        id=slug,
        name="Pytest Service Brand",
        palette=[{"name": "Ink", "hex": "#111111"}],
        typography=_extended_typography(),
        shopify={"store_domain": "pytest.myshopify.com"},
    )

    try:
        saved = service.save_brand(slug, brand)
        assert saved.typography.approved_fonts[0].family == "Archivo Black"

        reloaded = service.get_brand(slug)
        assert reloaded.typography.headline == "Archivo Black"
        assert reloaded.typography.accent == "Caveat"
        assert [font.family for font in reloaded.typography.approved_fonts] == ["Archivo Black"]
        assert [font.status for font in reloaded.typography.discarded_fonts] == ["discarded"]

        raw = repo.get_by_slug(team_id=team_id, slug=slug)
        assert raw is not None
        assert raw["typography"] == {"display": "Archivo Black", "body": "Inter"}
        assert raw["typography_system"]["approved_fonts"][0]["css_stack"] == "'Archivo Black', 'Arial Black', sans-serif"
    finally:
        repo.archive(team_id=team_id, slug=slug)


def test_brand_service_discovery_snapshot_helpers_round_trip_live() -> None:
    from app.schemas.brand import BrandContext
    from app.services.brands.brand_service import BrandNotFound, BrandService

    client, team_id = _client_and_team_id()
    repo = BrandContextRepository(client)
    service = BrandService(repository=repo, team_id=team_id)
    slug = f"pytest_disc_{uuid4().hex[:8]}"
    service.save_brand(
        slug,
        BrandContext(
            id=slug,
            name="Pytest Discovery Brand",
            palette=[{"name": "Ink", "hex": "#111111"}],
            shopify={"store_domain": "pytest.myshopify.com"},
        ),
    )

    try:
        assert service.get_discovery_snapshot(slug) is None

        snapshot = _discovery_snapshot_dict(slug)
        persisted = service.save_discovery_snapshot(slug, snapshot)
        assert isinstance(persisted["discovered_at"], str)  # model_dump(mode="json")

        loaded = service.get_discovery_snapshot(slug)
        assert loaded is not None
        assert loaded["shop_domain"] == "pytest.myshopify.com"
        assert loaded["colors"][0]["hex"] == "#112233"
        assert loaded["fonts"][0]["family"] == "Archivo Black"

        # Saving the brand again must not wipe the stored snapshot.
        service.save_brand(slug, service.get_brand(slug))
        assert service.get_discovery_snapshot(slug) == loaded

        with pytest.raises(BrandNotFound):
            service.save_discovery_snapshot(f"missing_{uuid4().hex[:8]}", snapshot)
    finally:
        repo.archive(team_id=team_id, slug=slug)


def test_brand_discovery_run_repository_crud_live() -> None:
    client, team_id = _client_and_team_id()
    runs = BrandDiscoveryRunRepository(client)
    brand_id = f"pytest_brand_{uuid4().hex[:8]}"

    created = runs.insert(team_id=team_id, brand_id=brand_id, status="pending")
    run_id = created["id"]
    try:
        assert created["status"] == "pending"
        assert created["snapshot"] == {}
        assert created["recommendation"] == {}

        loaded = runs.get(run_id=run_id, team_id=team_id)
        assert loaded is not None
        assert loaded["brand_id"] == brand_id

        second = runs.insert(team_id=team_id, brand_id=brand_id, status="running", store_id="store-1")
        try:
            listed = runs.list_for_brand(team_id=team_id, brand_id=brand_id)
            assert {row["id"] for row in listed} >= {run_id, second["id"]}
            created_ats = [row["created_at"] for row in listed]
            assert created_ats == sorted(created_ats, reverse=True)

            updated = runs.update_status(
                run_id=run_id,
                team_id=team_id,
                status="succeeded",
                snapshot=_discovery_snapshot_dict(brand_id),
                recommendation={"summary": "Use Archivo Black for display."},
            )
            assert updated is not None
            assert updated["status"] == "succeeded"
            assert updated["snapshot"]["status"] == "succeeded"
            assert updated["recommendation"]["summary"] == "Use Archivo Black for display."

            # Other-team scoping: no row visible/updated for a different team id.
            assert runs.get(run_id=run_id, team_id="not-the-team") is None
            assert runs.update_status(run_id=run_id, team_id="not-the-team", status="failed") is None
        finally:
            client.table("brand_discovery_runs").delete().eq("id", second["id"]).execute()
    finally:
        client.table("brand_discovery_runs").delete().eq("id", run_id).execute()
