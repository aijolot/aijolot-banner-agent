"""Smoke tests for the brand endpoints (GH-26)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.brand import BrandContext
from app.services.brands.brand_service import BrandService

client = TestClient(app)
AUTH_HEADERS = {"X-Aijolot-User-Id": "test-user", "X-Aijolot-Team-Id": "team-1"}


def _color_system(primary_hex: str = "#111111", primary_label: str = "Hero Ink") -> dict:
    return {
        "primary": {
            "key": "primary",
            "label": primary_label,
            "hex": primary_hex,
            "usage_hint": "Use for hero headlines.",
            "agent_hint": "Dominant brand anchor.",
        },
        "secondary": {
            "key": "secondary",
            "label": "Warm Paper",
            "hex": "#F5E8D0",
            "usage_hint": "Use for backgrounds.",
            "agent_hint": "Support primary.",
        },
        "tertiary": {
            "key": "tertiary",
            "label": "Coral CTA",
            "hex": "#FF6655",
            "usage_hint": "Use for CTAs.",
            "agent_hint": "Apply sparingly.",
        },
    }


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


def _brand_payload_without_color_system() -> dict:
    return {
        "id": "roles_brand",
        "name": "Roles Brand",
        "palette": [
            {"name": "Ink", "hex": "#111111"},
            {"name": "Paper", "hex": "#F5E8D0"},
            {"name": "Coral", "hex": "#FF6655"},
        ],
        "typography": {"display": "Inter", "body": "Inter"},
        "voice": {"tone": ["Clear"], "required_phrases": [], "prohibited_words": []},
        "shopify": {"store_domain": "roles.myshopify.com"},
        "notes": "Role notes.",
    }


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


def test_brand_service_record_payload_writes_top_level_color_system() -> None:
    payload = _brand_payload_without_color_system()
    payload["color_system"] = _color_system(primary_label="Canonical Hero Ink")
    brand = BrandContext(**payload)

    record = BrandService._record_payload_from_brand(brand)

    assert record["color_system"]["primary"]["label"] == "Canonical Hero Ink"
    assert "color_system" not in record["source_metadata"]


def test_brand_service_restores_top_level_color_system_before_legacy_metadata() -> None:
    row = {
        "id": "uuid-roles",
        "slug": "roles_brand",
        "name": "Roles Brand",
        "palette": [{"name": "Ink", "hex": "#111111"}],
        "color_system": _color_system(primary_hex="#222222", primary_label="Top Level Hero"),
        "source_metadata": {
            "shopify": {"store_domain": "roles.myshopify.com"},
            "color_system": _color_system(primary_hex="#333333", primary_label="Legacy Hero"),
        },
    }

    brand = BrandService._brand_from_record(row)

    assert brand.color_system is not None
    assert brand.color_system.primary.label == "Top Level Hero"
    assert brand.color_system.primary.hex == "#222222"


def test_brand_service_restores_legacy_metadata_color_system_when_top_level_missing() -> None:
    row = {
        "id": "uuid-roles",
        "slug": "roles_brand",
        "name": "Roles Brand",
        "palette": [{"name": "Ink", "hex": "#111111"}],
        "source_metadata": {
            "shopify": {"store_domain": "roles.myshopify.com"},
            "color_system": _color_system(primary_hex="#333333", primary_label="Legacy Hero"),
        },
    }

    brand = BrandService._brand_from_record(row)

    assert brand.color_system is not None
    assert brand.color_system.primary.label == "Legacy Hero"
    assert brand.color_system.primary.hex == "#333333"


def test_brand_service_normalizes_old_records_without_color_system_from_palette() -> None:
    row = {
        "id": "uuid-legacy",
        "slug": "legacy_brand",
        "name": "Legacy Brand",
        "palette": [
            {"name": "Ink", "hex": "#111111"},
            {"name": "Paper", "hex": "#F5E8D0"},
            {"name": "Coral", "hex": "#FF6655"},
        ],
        "source_metadata": {"shopify": {"store_domain": "legacy.myshopify.com"}},
    }

    brand = BrandService._brand_from_record(row)

    assert brand.color_system is not None
    assert brand.color_system.primary.hex == "#111111"
    assert brand.color_system.secondary.hex == "#F5E8D0"
    assert brand.color_system.tertiary.hex == "#FF6655"


def test_brand_service_record_payload_keeps_legacy_typography_and_full_typography_system() -> None:
    payload = _brand_payload_without_color_system()
    payload["typography"] = _extended_typography()
    brand = BrandContext(**payload)

    record = BrandService._record_payload_from_brand(brand)

    # Old readers of the typography column keep seeing the two-key shape only.
    assert record["typography"] == {"display": "Archivo Black", "body": "Inter"}
    # The full extended dump goes to the dedicated typography_system column.
    assert record["typography_system"]["headline"] == "Archivo Black"
    assert record["typography_system"]["accent"] == "Caveat"
    assert record["typography_system"]["approved_fonts"][0]["family"] == "Archivo Black"
    assert record["typography_system"]["discarded_fonts"][0]["status"] == "discarded"
    # Discovery evidence never rides along with brand saves.
    assert "discovery_snapshot" not in record


def test_brand_service_restores_typography_system_before_legacy_typography() -> None:
    row = {
        "id": "uuid-fonts",
        "slug": "fonts_brand",
        "name": "Fonts Brand",
        "palette": [{"name": "Ink", "hex": "#111111"}],
        "typography": {"display": "Legacy Display", "body": "Legacy Body"},
        "typography_system": _extended_typography(),
        "source_metadata": {"shopify": {"store_domain": "fonts.myshopify.com"}},
    }

    brand = BrandService._brand_from_record(row)

    assert brand.typography.display == "Archivo Black"
    assert brand.typography.headline == "Archivo Black"
    assert [font.family for font in brand.typography.approved_fonts] == ["Archivo Black"]
    assert [font.family for font in brand.typography.discarded_fonts] == ["Papyrus"]


def test_brand_service_legacy_rows_without_typography_system_load_with_defaults() -> None:
    row = {
        "id": "uuid-legacy-fonts",
        "slug": "legacy_fonts_brand",
        "name": "Legacy Fonts Brand",
        "palette": [{"name": "Ink", "hex": "#111111"}],
        "typography": {"display": "Space Grotesk", "body": "Inter"},
        "typography_system": None,
        "discovery_snapshot": None,
        "source_metadata": {"shopify": {"store_domain": "legacy.myshopify.com"}},
    }

    brand = BrandService._brand_from_record(row)

    assert brand.typography.display == "Space Grotesk"
    assert brand.typography.body == "Inter"
    assert brand.typography.headline is None
    assert brand.typography.accent is None
    assert brand.typography.approved_fonts == []
    assert brand.typography.discarded_fonts == []


def test_put_and_get_brand_round_trips_extended_typography_root_and_v1(monkeypatch):
    import app.services.brand_store as store

    repository = FakeBrandRepository()
    service = BrandService(repository=repository, team_id="team-1")
    monkeypatch.setattr(store, "_default_service", lambda: service)
    monkeypatch.setattr(store, "service_for_team", lambda team_id: service)

    payload = _brand_payload_without_color_system()
    payload["id"] = "fonts_brand"
    payload["typography"] = _extended_typography()

    saved = client.put("/brands/fonts_brand", json=payload)
    assert saved.status_code == 200
    assert saved.json()["typography"]["approved_fonts"][0]["family"] == "Archivo Black"

    # Stored row keeps the legacy column stable and the full dump separate.
    stored = repository.rows["fonts_brand"]
    assert stored["typography"] == {"display": "Archivo Black", "body": "Inter"}
    assert stored["typography_system"]["discarded_fonts"][0]["family"] == "Papyrus"

    for response in (
        client.get("/brands/fonts_brand"),
        client.get("/api/v1/brands/fonts_brand", headers=AUTH_HEADERS),
    ):
        assert response.status_code == 200
        typography = response.json()["typography"]
        assert typography["display"] == "Archivo Black"
        assert typography["headline"] == "Archivo Black"
        assert typography["accent"] == "Caveat"
        assert [font["family"] for font in typography["approved_fonts"]] == ["Archivo Black"]
        assert [font["status"] for font in typography["discarded_fonts"]] == ["discarded"]

    v1_saved = client.put("/api/v1/brands/fonts_brand", headers=AUTH_HEADERS, json=payload)
    assert v1_saved.status_code == 200
    assert v1_saved.json()["typography"]["discarded_fonts"][0]["family"] == "Papyrus"


def test_put_brand_with_extended_typography_round_trips_markdown_fallback(tmp_path, monkeypatch):
    import app.services.brand_store as store

    _clear_supabase_env(monkeypatch)
    seed = store.get_brand("maison").model_dump()
    monkeypatch.setattr(store, "BRANDS_DIR", tmp_path)
    seed["typography"] = _extended_typography()

    saved = client.put("/brands/maison", json=seed)
    assert saved.status_code == 200
    assert (tmp_path / "maison.md").exists()

    loaded = client.get("/brands/maison")
    assert loaded.status_code == 200
    typography = loaded.json()["typography"]
    assert typography["headline"] == "Archivo Black"
    assert [font["family"] for font in typography["approved_fonts"]] == ["Archivo Black"]
    assert [font["family"] for font in typography["discarded_fonts"]] == ["Papyrus"]


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


def test_root_palette_suggestions_returns_gemini_suggestions(monkeypatch):
    import app.services.brand_store as store
    from app.services.brands import palette_suggestions as palette_module

    _clear_supabase_env(monkeypatch)

    async def fake_generate(prompt, *, model, structured=None):
        return {
            "suggestions": [
                {"name": "Avocado Glow", "hex": "#7AC943", "usage_hint": "Use behind hero product cards", "rationale": "Fresh and branded."}
            ]
        }

    monkeypatch.setattr(palette_module.gemini_text, "generate", fake_generate)
    response = client.post("/brands/avocado_store/palette-suggestions", json={"role_key": "primary", "count": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "gemini"
    assert body["role_key"] == "primary"
    assert body["suggestions"] == [
        {"name": "Avocado Glow", "hex": "#7AC943", "usage_hint": "Use behind hero product cards", "rationale": "Fresh and branded."}
    ]


def test_palette_suggestions_missing_brand_returns_404(monkeypatch):
    _clear_supabase_env(monkeypatch)
    response = client.post("/brands/nope/palette-suggestions", json={"role_key": "primary", "count": 3})
    assert response.status_code == 404


def test_palette_suggestions_gemini_unavailable_maps_to_503(monkeypatch):
    from app.agents.tools import gemini_text
    from app.services.brands import palette_suggestions as palette_module

    _clear_supabase_env(monkeypatch)

    async def fake_generate(prompt, *, model, structured=None):
        raise gemini_text.GeminiUnavailable("Gemini is unavailable: set GOOGLE_API_KEY")

    monkeypatch.setattr(palette_module.gemini_text, "generate", fake_generate)
    response = client.post("/brands/avocado_store/palette-suggestions", json={"role_key": "primary", "count": 3})

    assert response.status_code == 503
    assert "Gemini is unavailable" in response.json()["detail"]
    assert "suggestions" not in response.json()


def test_palette_suggestions_invalid_role_key_returns_validation_error(monkeypatch):
    _clear_supabase_env(monkeypatch)
    response = client.post("/brands/avocado_store/palette-suggestions", json={"role_key": "accent", "count": 3})
    assert response.status_code == 422


def test_palette_suggestions_draft_context_overrides_persisted_brand(monkeypatch):
    from app.services.brands import palette_suggestions as palette_module

    _clear_supabase_env(monkeypatch)
    captured: dict[str, str] = {}
    persisted = client.get("/brands/avocado_store").json()
    draft = {**persisted, "name": "Unsaved Palette Draft"}
    draft["color_system"]["primary"]["hex"] = "#123ABC"
    draft["palette"][0]["hex"] = "#123ABC"

    async def fake_generate(prompt, *, model, structured=None):
        captured["prompt"] = prompt
        return {"suggestions": [{"name": "Draft Violet", "hex": "#7654D8", "usage_hint": "Draft accent", "rationale": "Matches unsaved colors."}]}

    monkeypatch.setattr(palette_module.gemini_text, "generate", fake_generate)
    response = client.post(
        "/brands/avocado_store/palette-suggestions",
        json={"role_key": "primary", "count": 3, "draft_brand_context": draft},
    )

    assert response.status_code == 200
    assert response.json()["base_hex"] == "#123ABC"
    assert "Unsaved Palette Draft" in captured["prompt"]
    assert "#123ABC" in captured["prompt"]


def test_api_v1_palette_suggestions_uses_auth_scoped_service(monkeypatch):
    import app.services.brand_store as store
    from app.services.brands import palette_suggestions as palette_module

    service = BrandService(repository=FakeBrandRepository(), team_id="team-1")
    called: dict[str, str] = {}

    def fake_service_for_team(team_id: str):
        called["team_id"] = team_id
        return service

    async def fake_generate(prompt, *, model, structured=None):
        return {"suggestions": [{"name": "Runtime Blue", "hex": "#3366FF", "usage_hint": "Use on banners", "rationale": "Runtime fit."}]}

    monkeypatch.setattr(store, "service_for_team", fake_service_for_team)
    monkeypatch.setattr(palette_module.gemini_text, "generate", fake_generate)

    unauthenticated = client.post("/api/v1/brands/supabase_brand/palette-suggestions", json={"role_key": "primary", "count": 3})
    assert unauthenticated.status_code in {401, 403}

    response = client.post(
        "/api/v1/brands/supabase_brand/palette-suggestions",
        headers=AUTH_HEADERS,
        json={"role_key": "primary", "count": 3},
    )

    assert response.status_code == 200
    assert called["team_id"] == "team-1"
    assert response.json()["suggestions"][0]["hex"] == "#3366FF"
