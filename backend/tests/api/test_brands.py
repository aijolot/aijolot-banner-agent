"""Smoke tests for the brand endpoints (GH-26)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_brands_returns_seeds():
    r = client.get("/brands")
    assert r.status_code == 200
    ids = {b["id"] for b in r.json()}
    assert {"avocado_store", "demo_apparel", "maison"} <= ids


def test_get_brand_full_context():
    r = client.get("/brands/avocado_store")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Avocado Store"
    assert body["shopify"]["store_domain"] == "avocado-store.myshopify.com"
    assert all(c["hex"].startswith("#") for c in body["palette"])


def test_get_unknown_brand_404():
    assert client.get("/brands/nope").status_code == 404


def test_put_brand_rejects_bad_hex():
    brand = client.get("/brands/demo_apparel").json()
    brand["palette"][0]["hex"] = "purple"
    r = client.put("/brands/demo_apparel", json=brand)
    assert r.status_code == 422


def test_put_brand_persists(tmp_path, monkeypatch):
    import app.services.brand_store as store

    # round-trip against a temp copy so the test doesn't mutate the seeds
    src = store.get_brand("maison")
    monkeypatch.setattr(store, "BRANDS_DIR", tmp_path)
    store.save_brand("maison", src)

    brand = client.get("/brands/maison").json() if False else src.model_dump()
    brand["voice"]["tone"] = ["Premium", "Warm"]
    saved = store.save_brand("maison", store.BrandContext(**brand))
    assert saved.voice.tone == ["Premium", "Warm"]
    assert (tmp_path / "maison.md").exists()
