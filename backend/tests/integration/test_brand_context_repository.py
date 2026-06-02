from __future__ import annotations

import os
from uuid import uuid4

import pytest

from app.core.settings import Settings
from app.db.repositories.brand_contexts import BrandContextRepository
from app.services.supabase.client import SupabaseClientFactory


pytestmark = pytest.mark.integration


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
            "shopify": {"store_domain": "invalid-column.myshopify.com"},
            "notes": "invalid column",
            "source_metadata": {"notes": "valid metadata"},
        },
    )

    assert row["slug"] == "maison-hugo-boss-demo"
    assert row["name"] == "Maison Hugo Boss Demo"
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
