"""Per-variant featured product → per-variant catalog grounding."""

from __future__ import annotations

from app.services.banners.run_orchestrator import (
    _brief_product_items,
    _coerce_price,
    _variant_catalog_context,
    _variant_product_ref,
)


_SNAPSHOT = {
    "items": [
        {"title": "212 Heroes", "shopify_product_gid": "gid://shopify/Product/1"},
        {"title": "Odyssey Mandarin Sky EDP 100ml Hombre", "shopify_product_gid": "gid://shopify/Product/14988752617842"},
        {"title": "My Way Intense by Giorgio Armani EDP 90ml Dama", "shopify_product_gid": "gid://shopify/Product/14988758385010"},
    ],
    "discount_rule": {"percent": 15},
}


def test_no_product_returns_shared_context() -> None:
    spec = {"key": "male", "audience": "hombres"}
    assert _variant_catalog_context(_SNAPSHOT, spec) is _SNAPSHOT


def test_matches_product_by_gid_and_scopes_to_it() -> None:
    spec = {"key": "male", "product_gid": "gid://shopify/Product/14988752617842"}
    ctx = _variant_catalog_context(_SNAPSHOT, spec)
    assert [i["title"] for i in ctx["items"]] == ["Odyssey Mandarin Sky EDP 100ml Hombre"]
    # Discount rule carried forward so the per-variant copy still knows the offer.
    assert ctx["discount_rule"] == {"percent": 15}


def test_matches_product_by_title_case_insensitive() -> None:
    spec = {"key": "female", "product_title": "my way intense by giorgio armani edp 90ml dama"}
    ctx = _variant_catalog_context(_SNAPSHOT, spec)
    assert ctx["items"][0]["shopify_product_gid"] == "gid://shopify/Product/14988758385010"


def test_synthesizes_when_product_not_in_snapshot() -> None:
    spec = {"key": "male", "product_title": "Brand New Drop", "product_image_url": "https://cdn/x.jpg"}
    ctx = _variant_catalog_context(_SNAPSHOT, spec)
    assert ctx["items"][0]["title"] == "Brand New Drop"
    assert ctx["items"][0]["image_url"] == "https://cdn/x.jpg"


def test_product_ref_only_keeps_present_fields() -> None:
    assert _variant_product_ref({"product_gid": "gid://x", "key": "male"}) == {"product_gid": "gid://x"}
    assert _variant_product_ref({"key": "male"}) == {}


# --- Phase 2: campaign-level products → catalog grounding ---

def test_coerce_price_parses_strings_and_numbers() -> None:
    assert _coerce_price("1,299.00") == 1299.0
    assert _coerce_price("$12.99") == 12.99
    assert _coerce_price(999) == 999.0
    assert _coerce_price("") is None
    assert _coerce_price("agotado") is None


def test_brief_product_items_shapes_catalog_items() -> None:
    row = {
        "structured_brief": {
            "products": [
                {"product_title": "Boss Bottled", "product_gid": "gid://shopify/Product/9", "product_image_url": "https://cdn/b.jpg", "price": "1,299.00"},
                {"product_title": "", "product_gid": None},  # skipped (no title/gid)
            ]
        }
    }
    items = _brief_product_items(row)
    assert len(items) == 1
    assert items[0]["title"] == "Boss Bottled"
    assert items[0]["shopify_product_gid"] == "gid://shopify/Product/9"
    assert items[0]["image_url"] == "https://cdn/b.jpg"
    assert items[0]["price"] == 1299.0


def test_brief_product_items_empty_when_no_products() -> None:
    assert _brief_product_items({"structured_brief": {}}) == []
    assert _brief_product_items(None) == []
