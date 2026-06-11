"""F3 — catalog awareness: deterministic signals → proactive suggestions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.banners.catalog_signal_service import (
    CatalogSignalService,
    InMemoryCatalogSignals,
    handle_catalog_scan_job,
)
from app.services.banners.suggestion_service import InMemoryAgentSuggestions, SuggestionService

TEAM = "team-cat"


def _suggestions() -> SuggestionService:
    return SuggestionService(suggestions=InMemoryAgentSuggestions(), team_id=TEAM)


def _service(suggestions=None):
    return CatalogSignalService(
        signals=InMemoryCatalogSignals(), suggestions=suggestions or _suggestions(), team_id=TEAM, store_id="store-1"
    )


PRODUCTS = [
    {"shopify_gid": "gid://shopify/Product/1", "title": "Best Seller X", "image_url": "https://cdn/x.jpg",
     "raw": {"stock": 80, "sales_rank": 1}},
    {"shopify_gid": "gid://shopify/Product/2", "title": "Casi Agotado Y", "image_url": "https://cdn/y.jpg",
     "raw": {"stock": 7}},
    {"shopify_gid": "gid://shopify/Product/3", "title": "Normal Z", "image_url": None, "raw": {"stock": 200}},
]


def test_scan_emits_low_stock_and_best_seller_suggestions() -> None:
    sugg = _suggestions()
    svc = _service(sugg)
    summary = svc.scan(products=PRODUCTS)

    assert summary["products_scanned"] == 3
    pending = sugg.list()
    titles = {s.title for s in pending}
    assert any("Casi Agotado Y" in t for t in titles)  # low stock → urgency
    assert any("Best Seller X" in t for t in titles)  # explicit sales_rank
    low = next(s for s in pending if "Casi Agotado" in s.title)
    brief = low.payload["structured_brief"]
    assert brief["urgency"] == "high"
    assert brief["products"][0]["product_gid"] == "gid://shopify/Product/2"
    assert low.payload["product_image_url"] == "https://cdn/y.jpg"


def test_scan_is_idempotent_via_dedupe_keys() -> None:
    sugg = _suggestions()
    svc = _service(sugg)
    svc.scan(products=PRODUCTS)
    svc.scan(products=PRODUCTS)
    assert len(sugg.list()) == 2  # low_stock + best_seller, not duplicated


def test_new_product_signal_within_window() -> None:
    sugg = _suggestions()
    svc = _service(sugg)
    fresh = {
        "shopify_gid": "gid://shopify/Product/9", "title": "Nuevo W", "image_url": None,
        "raw": {"stock": 50, "published_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()},
    }
    svc.scan(products=[fresh])
    assert any("Estrena" in s.title for s in sugg.list())


def test_no_active_banner_signal_uses_active_set() -> None:
    svc = _service()
    svc.scan(products=PRODUCTS, active_product_gids={"gid://shopify/Product/1"})
    types = {(r["product_gid"], r["signal_type"]) for r in svc.list_signals()}
    assert ("gid://shopify/Product/2", "no_active_banner") in types
    assert ("gid://shopify/Product/1", "no_active_banner") not in types


def test_job_handler_runs_on_seed_data_without_supabase(monkeypatch) -> None:
    """Demo mode: the catalog_scan job produces suggestions from the seed catalog."""
    for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_TEAM_ID"):
        monkeypatch.delenv(var, raising=False)
    summary = handle_catalog_scan_job({"id": "j1", "team_id": "team-demo", "kind": "catalog_scan"})
    assert summary["stores"] >= 1
    # Seed has 'Set Lujo Boss Bottled' at stock 12 → at least the low_stock suggestion.
    assert "low_stock" in summary["suggestions"]
    assert "best_seller" in summary["suggestions"]
