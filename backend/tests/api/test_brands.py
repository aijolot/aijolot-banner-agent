"""Smoke tests for the brand endpoints (GH-26)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.brands.brand_service import BrandService

client = TestClient(app)
AUTH_HEADERS = {"X-Aijolot-User-Id": "test-user", "X-Aijolot-Team-Id": "team-1"}


def _clear_supabase_env(monkeypatch):
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "BRAND_CONTEXT_TEAM_ID", "SUPABASE_TEAM_ID"):
        monkeypatch.delenv(key, raising=False)


class FakeBrandRepository:
    def __init__(self):
        self.rows = {
            "supabase_brand": {
                "id": "00000000-0000-0000-0000-000000000001",
                "team_id": "team-1",
                "slug": "supabase_brand",
                "name": "Supabase Brand",
                "palette": [{"name": "Blue", "hex": "#0000FF"}],
                "typography": {"display": "Inter", "body": "Inter"},
                "voice": {"tone": ["Runtime"], "required_phrases": [], "prohibited_words": []},
                "required_phrases": [],
                "prohibited_words": [],
                "image_style_directives": "Runtime first",
                "logo_url": None,
                "description": "Runtime notes",
                "source_metadata": {
                    "shopify": {"store_domain": "runtime.myshopify.com", "default_placement": "hero"},
                    "notes": "Runtime notes",
                },
            }
        }

    def list(self, *, team_id: str):
        return list(self.rows.values())

    def get_by_slug(self, *, team_id: str, slug: str):
        return self.rows.get(slug)

    def upsert(self, *, team_id: str, slug: str, data: dict, store_id=None, created_by=None):
        self.rows[slug] = {**data, "id": f"uuid-{slug}", "team_id": team_id, "slug": slug}
        return self.rows[slug]


def test_list_brands_returns_seeds(monkeypatch):
    _clear_supabase_env(monkeypatch)
    r = client.get("/brands")
    assert r.status_code == 200
    ids = {b["id"] for b in r.json()}
    assert {"avocado_store", "demo_apparel", "maison"} <= ids


def test_get_brand_full_context(monkeypatch):
    _clear_supabase_env(monkeypatch)
    r = client.get("/brands/avocado_store")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Avocado Store"
    assert body["shopify"]["store_domain"] == "avocado-store.myshopify.com"
    assert all(c["hex"].startswith("#") for c in body["palette"])


def test_get_unknown_brand_404(monkeypatch):
    _clear_supabase_env(monkeypatch)
    assert client.get("/brands/nope").status_code == 404


def test_brand_routes_reject_invalid_brand_ids(monkeypatch):
    _clear_supabase_env(monkeypatch)
    brand = client.get("/brands/maison").json()

    assert client.get("/brands/BadBrand").status_code == 422
    assert client.put("/brands/BadBrand", json=brand).status_code == 422
    assert client.post("/brands/import", json={"brand_id": "BadBrand"}).status_code == 422


def test_put_brand_rejects_bad_hex(monkeypatch):
    _clear_supabase_env(monkeypatch)
    brand = client.get("/brands/demo_apparel").json()
    brand["palette"][0]["hex"] = "purple"
    r = client.put("/brands/demo_apparel", json=brand)
    assert r.status_code == 422


def test_put_brand_persists(tmp_path, monkeypatch):
    import app.services.brand_store as store

    _clear_supabase_env(monkeypatch)
    # round-trip against a temp copy so the test doesn't mutate the seeds
    src = store.get_brand("maison")
    monkeypatch.setattr(store, "BRANDS_DIR", tmp_path)
    store.save_brand("maison", src)

    brand = src.model_dump()
    brand["voice"]["tone"] = ["Premium", "Warm"]
    saved = store.save_brand("maison", store.BrandContext(**brand))
    assert saved.voice.tone == ["Premium", "Warm"]
    assert (tmp_path / "maison.md").exists()


def test_put_brand_rejects_unsafe_markdown_id(tmp_path, monkeypatch):
    import app.services.brand_store as store

    _clear_supabase_env(monkeypatch)
    src = store.get_brand("maison")
    monkeypatch.setattr(store, "BRANDS_DIR", tmp_path)

    with pytest.raises(Exception) as exc_info:  # noqa: BLE001
        store.save_brand("../maison", src)
    assert "String should match pattern" in str(exc_info.value)
    assert not (tmp_path.parent / "maison.md").exists()


def test_default_service_fails_when_supabase_credentials_lack_team_id(monkeypatch):
    import app.services.brand_store as store

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-placeholder")
    monkeypatch.delenv("BRAND_CONTEXT_TEAM_ID", raising=False)
    monkeypatch.delenv("SUPABASE_TEAM_ID", raising=False)

    with pytest.raises(store.MissingSettingsError) as exc_info:
        store._default_service()
    assert "BRAND_CONTEXT_TEAM_ID" in str(exc_info.value)
    assert "SUPABASE_TEAM_ID" in str(exc_info.value)


def test_list_and_get_can_use_supabase_backed_service(monkeypatch):
    import app.services.brand_store as store

    service = BrandService(repository=FakeBrandRepository(), team_id="team-1")
    monkeypatch.setattr(store, "_default_service", lambda: service)
    monkeypatch.setattr(store, "service_for_team", lambda team_id: service)

    listed = client.get("/brands")
    assert listed.status_code == 200
    assert listed.json() == [
        {"id": "supabase_brand", "name": "Supabase Brand", "palette": [{"name": "Blue", "hex": "#0000FF"}]}
    ]

    loaded = client.get("/api/v1/brands/supabase_brand", headers=AUTH_HEADERS)
    assert loaded.status_code == 200
    assert loaded.json()["shopify"]["store_domain"] == "runtime.myshopify.com"


def test_import_markdown_endpoint_upserts_into_supabase_service(tmp_path, monkeypatch):
    import app.services.brand_store as store
    from app.services.brands.markdown_importer import BrandMarkdownImporter

    (tmp_path / "seed_brand.md").write_text(
        """---
id: seed_brand
name: Seed Brand
palette:
- name: Green
  hex: '#00AA00'
shopify:
  store_domain: seed.myshopify.com
---

Imported notes.
""",
        encoding="utf-8",
    )
    service = BrandService(
        repository=FakeBrandRepository(),
        team_id="team-1",
        markdown_importer=BrandMarkdownImporter(base_dir=tmp_path),
    )
    monkeypatch.setattr(store, "_default_service", lambda: service)

    response = client.post("/brands/import", json={"brand_id": "seed_brand"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "seed_brand"
    assert service.get_brand("seed_brand").notes == "Imported notes.\n"
