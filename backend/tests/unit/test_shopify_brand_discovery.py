"""Shopify brand evidence collector (Task 3) — stub client, no network."""

from __future__ import annotations

import json
from typing import Any

from app.services.brands.shopify_discovery import (
    DEFAULT_MAX_ASSET_BYTES,
    collect_brand_evidence,
)
from app.services.shopify.client import ShopifyAdminClient, ShopifyApiError

SECRET_TOKEN = "shpat_super_secret_token_value"  # noqa: S105 - fake, proves no leak

SHOP_WITH_BRAND: dict[str, Any] = {
    "name": "Demo Apparel",
    "primaryDomain": {"url": "https://demo-apparel.com", "host": "demo-apparel.com"},
    "brand": {
        "slogan": "Wear the noise.",
        "shortDescription": "Streetwear for loud people.",
        "colors": {
            "primary": [{"background": "#0E0E10", "foreground": "#ffffff"}],
            "secondary": [{"background": "#ede8e0"}],
        },
        "logo": {"image": {"url": "https://cdn.shopify.com/s/files/logo.png"}},
        "squareLogo": {"image": {"url": "https://cdn.shopify.com/s/files/logo-square.png"}},
        "coverImage": {"image": {"url": "https://cdn.shopify.com/s/files/cover.jpg"}},
    },
}

THEMES = [
    {"id": 111, "name": "Old Theme", "role": "unpublished"},
    {"id": 123456789, "name": "Dawn", "role": "main"},
]

ASSET_INDEX = [
    {"key": "config/settings_data.json", "size": 2000},
    {"key": "config/settings_schema.json", "size": 1500},
    {"key": "assets/base.css", "size": 4000},
    {"key": "assets/vendor.css.liquid", "size": 500},
    {"key": "assets/huge.css", "size": 999_999},  # over the byte cap -> never fetched
    {"key": "assets/app.js", "size": 100},
    {"key": "sections/header.liquid", "size": 900},
    {"key": "sections/image-banner.liquid", "size": 700},
    {"key": "sections/hero-slide.liquid", "size": 600},
    {"key": "layout/theme.liquid", "size": 800},
]

SETTINGS_DATA = {
    "current": {
        "colors_accent_1": "#3d5afe",
        "color_card": "#abc",  # short hex -> must expand to #AABBCC
        "type_header_font": "helvetica_n4",
        "type_body_font": "assistant_n4",
        "font_size_base": "16",  # must NOT become a font family
        "logo": "shopify://shop_images/logo-main.png",
        "sections": {
            "hero-1": {
                "type": "image-banner",
                "settings": {"image": "shopify://shop_images/hero.jpg"},
            }
        },
    }
}

SETTINGS_SCHEMA = [
    {
        "name": "Colors",
        "settings": [
            {"type": "color", "id": "colors_accent_1", "default": "#3D5AFE"},
            {"type": "color", "id": "colors_button", "default": "#ff6b5c"},
        ],
    },
    {
        "name": "Typography",
        "settings": [{"type": "font_picker", "id": "type_body_font", "default": "assistant_n4"}],
    },
]

BASE_CSS = """
:root {
  --color-primary: #0e0e10;
  --color-accent: #f4f;
  --font-heading-family: "Space Grotesk", Helvetica, sans-serif;
}
h1 { color: #3d5afe; font-family: var(--font-heading-family); }
.hero { background: #ff6b5c; }
.legacy { font-family: Helvetica, Arial !important; }
.generic { font-family: sans-serif; }
"""

VENDOR_CSS = ".btn { color: #00ff00; }"

HEADER_LIQUID = """
<img class="logo" src="{{ 'logo-dark.png' | asset_url }}" alt="logo">
<img src="https://cdn.shopify.com/s/files/1/header-promo.png">
"""

IMAGE_BANNER_LIQUID = (
    '<div style="background-image:url(https://cdn.shopify.com/s/files/1/banner-summer.jpg)"></div>'
)

THEME_LIQUID = '<link rel="icon" href="https://cdn.shopify.com/s/files/1/favicon.png">'

HERO_SLIDE_LIQUID = "{{ 'hero-bg.webp' | asset_url }}"

ASSET_BODIES = {
    "config/settings_data.json": json.dumps(SETTINGS_DATA),
    "config/settings_schema.json": json.dumps(SETTINGS_SCHEMA),
    "assets/base.css": BASE_CSS,
    "assets/vendor.css.liquid": VENDOR_CSS,
    "sections/header.liquid": HEADER_LIQUID,
    "sections/image-banner.liquid": IMAGE_BANNER_LIQUID,
    "layout/theme.liquid": THEME_LIQUID,
    "sections/hero-slide.liquid": HERO_SLIDE_LIQUID,
}


class FakeShopifyClient:
    """Stub of the Admin client surface the collector uses (no network)."""

    shop_domain = "demo-apparel.myshopify.com"

    def __init__(
        self,
        *,
        shop: dict[str, Any] | None = None,
        themes: list[dict[str, Any]] | None = None,
        asset_index: list[dict[str, Any]] | None = None,
        asset_bodies: dict[str, str] | None = None,
        fail_shop: bool = False,
        fail_brand: bool = False,
        fail_themes: bool = False,
        fail_asset_list: bool = False,
        fail_assets: bool = False,
    ) -> None:
        self.access_token = SECRET_TOKEN  # present only to prove it never leaks
        self.shop = SHOP_WITH_BRAND if shop is None else shop
        self.themes = THEMES if themes is None else themes
        self.asset_index = ASSET_INDEX if asset_index is None else asset_index
        self.asset_bodies = dict(ASSET_BODIES) if asset_bodies is None else asset_bodies
        self.fail_shop = fail_shop
        self.fail_brand = fail_brand
        self.fail_themes = fail_themes
        self.fail_asset_list = fail_asset_list
        self.fail_assets = fail_assets
        self.fetched_keys: list[str] = []

    def get_shop_metadata(self, *, include_brand: bool = True) -> dict[str, Any]:
        if self.fail_shop:
            raise ShopifyApiError("Shopify GraphQL request failed with status 401")
        if include_brand and self.fail_brand:
            raise ShopifyApiError("Shopify GraphQL error: 1 error(s)")
        shop = dict(self.shop)
        if not include_brand:
            shop.pop("brand", None)
        return shop

    def get_main_theme(self) -> dict[str, Any] | None:
        if self.fail_themes:
            raise ShopifyApiError("Shopify API request failed with status 403")
        for theme in self.themes:
            if str(theme.get("role") or "").lower() == "main":
                return dict(theme)
        return None

    def list_theme_assets(self, *, theme_id: str) -> list[dict[str, Any]]:
        if self.fail_asset_list:
            raise ShopifyApiError("Shopify API request failed with status 403")
        return [dict(entry) for entry in self.asset_index]

    def get_theme_asset(self, *, theme_id: str, key: str) -> dict[str, Any] | None:
        self.fetched_keys.append(key)
        if self.fail_assets:
            raise ShopifyApiError("Shopify API request failed with status 403")
        body = self.asset_bodies.get(key)
        if body is None:
            raise ShopifyApiError("Shopify API request failed with status 404")
        return {"key": key, "value": body, "content_type": "text/plain"}


def _collect(client: FakeShopifyClient, **kwargs: Any):
    return collect_brand_evidence(
        client,
        brand_id="demo_brand",
        shop_domain="demo-apparel.myshopify.com",
        store_id="store_1",
        **kwargs,
    )


def _colors_by_hex(snapshot) -> dict[str, Any]:
    return {color.hex: color for color in snapshot.colors}


def _fonts_by_family(snapshot) -> dict[str, Any]:
    return {font.family: font for font in snapshot.fonts}


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_success_snapshot_identity_and_status() -> None:
    snapshot = _collect(FakeShopifyClient())

    assert snapshot.status == "succeeded"
    assert snapshot.errors == []
    assert snapshot.id.startswith("disc_") and len(snapshot.id) == len("disc_") + 12
    assert snapshot.brand_id == "demo_brand"
    assert snapshot.store_id == "store_1"
    assert snapshot.shop_domain == "demo-apparel.myshopify.com"
    assert snapshot.discovered_at.tzinfo is not None
    assert snapshot.theme_metadata["shop_name"] == "Demo Apparel"
    assert snapshot.theme_metadata["shop_primary_domain_host"] == "demo-apparel.com"
    assert snapshot.theme_metadata["brand_slogan"] == "Wear the noise."
    assert snapshot.theme_metadata["theme_name"] == "Dawn"
    assert snapshot.theme_metadata["theme_id"] == "123456789"
    assert snapshot.theme_metadata["theme_role"] == "main"


def test_success_extracts_shop_brand_colors_and_logo_assets() -> None:
    snapshot = _collect(FakeShopifyClient())
    colors = _colors_by_hex(snapshot)

    assert colors["#FFFFFF"].source == "shop_metadata"
    assert colors["#FFFFFF"].confidence == 0.95
    assert colors["#EDE8E0"].name == "brand secondary background"

    shop_assets = [asset for asset in snapshot.assets if asset.source == "shop_metadata"]
    logo_urls = {asset.url for asset in shop_assets if asset.kind == "logo"}
    assert logo_urls == {
        "https://cdn.shopify.com/s/files/logo.png",
        "https://cdn.shopify.com/s/files/logo-square.png",
    }
    assert any(
        asset.kind == "hero" and asset.url == "https://cdn.shopify.com/s/files/cover.jpg"
        for asset in shop_assets
    )


def test_settings_data_parsing_covers_nested_dicts_fonts_and_assets() -> None:
    snapshot = _collect(FakeShopifyClient())
    colors = _colors_by_hex(snapshot)
    fonts = _fonts_by_family(snapshot)

    # Colors from settings_data, including #RGB -> #RRGGBB expansion.
    assert colors["#3D5AFE"].source == "theme_settings:config/settings_data.json"
    assert colors["#3D5AFE"].name == "colors_accent_1"
    assert colors["#3D5AFE"].confidence == 0.9
    assert colors["#AABBCC"].name == "color_card"

    # settings_schema defaults at lower confidence, named via the sibling "id".
    assert colors["#FF6B5C"].source == "theme_settings:config/settings_schema.json"
    assert colors["#FF6B5C"].name == "colors_button"
    assert colors["#FF6B5C"].confidence == 0.5

    # Shopify font_picker values parse into families; numeric settings do not.
    assert fonts["Assistant"].confidence == 0.9
    assert "16" not in fonts

    # Logo + nested hero/banner section references become assets (https only -> raw_ref).
    settings_assets = [a for a in snapshot.assets if a.source == "theme_settings:config/settings_data.json"]
    logo = next(a for a in settings_assets if a.kind == "logo" and "raw_ref" in a.metadata)
    assert logo.url is None
    assert logo.metadata["raw_ref"] == "shopify://shop_images/logo-main.png"
    assert any(a.kind == "banner" and a.metadata.get("section_type") == "image-banner" for a in settings_assets)
    hero = next(a for a in settings_assets if a.kind == "hero")
    assert hero.metadata["raw_ref"] == "shopify://shop_images/hero.jpg"

    # Both settings files are recorded as provenance assets.
    assert sum(1 for a in snapshot.assets if a.kind == "settings") == 2


def test_css_parsing_custom_properties_short_hex_and_font_stacks() -> None:
    snapshot = _collect(FakeShopifyClient())
    colors = _colors_by_hex(snapshot)
    fonts = _fonts_by_family(snapshot)

    # Custom property colors keep the property name; #RGB expands.
    assert colors["#FF44FF"].name == "color-accent"
    assert colors["#FF44FF"].confidence == 0.6
    # Raw hex colors get the low confidence tier.
    assert colors["#00FF00"].confidence == 0.4
    assert colors["#00FF00"].source == "css:assets/vendor.css.liquid"

    # Font custom property: quotes stripped, full stack kept.
    grotesk = fonts["Space Grotesk"]
    assert grotesk.css_stack == "Space Grotesk, Helvetica, sans-serif"
    assert grotesk.confidence == 0.6
    assert grotesk.source == "css:assets/base.css"

    # var() references and generic-only stacks never become fonts.
    families_lower = {family.lower() for family in fonts}
    assert "sans-serif" not in families_lower
    assert not any("var" in family.lower() for family in fonts)

    # Both stylesheets are recorded as provenance assets.
    assert sum(1 for a in snapshot.assets if a.kind == "css") == 2


def test_dedupe_keeps_highest_confidence_and_merges_font_stacks() -> None:
    snapshot = _collect(FakeShopifyClient())
    colors = _colors_by_hex(snapshot)
    fonts = _fonts_by_family(snapshot)

    # #0E0E10 appears in shop brand (0.95), css var (0.6) and raw css (0.4).
    assert len([c for c in snapshot.colors if c.hex == "#0E0E10"]) == 1
    assert colors["#0E0E10"].confidence == 0.95
    assert colors["#0E0E10"].source == "shop_metadata"
    # #3D5AFE appears in settings_data (0.9), schema default (0.5), raw css (0.4).
    assert colors["#3D5AFE"].confidence == 0.9

    # Helvetica: theme settings picker (0.9, no stack) merged with css stack (0.6).
    helvetica = fonts["Helvetica"]
    assert helvetica.confidence == 0.9
    assert helvetica.source == "theme_settings:config/settings_data.json"
    assert helvetica.css_stack == "Helvetica, Arial"
    assert len([f for f in snapshot.fonts if f.family.lower() == "helvetica"]) == 1


def test_section_and_layout_files_yield_image_assets() -> None:
    snapshot = _collect(FakeShopifyClient())
    section_assets = [a for a in snapshot.assets if a.source.startswith("section:")]

    logo_ref = next(a for a in section_assets if a.theme_asset_key == "assets/logo-dark.png")
    assert logo_ref.kind == "logo"
    assert logo_ref.source == "section:sections/header.liquid"

    assert any(
        a.kind == "banner" and a.url == "https://cdn.shopify.com/s/files/1/banner-summer.jpg"
        for a in section_assets
    )
    assert any(
        a.kind == "hero" and a.theme_asset_key == "assets/hero-bg.webp" for a in section_assets
    )
    assert any(
        a.kind == "theme_asset" and a.url == "https://cdn.shopify.com/s/files/1/favicon.png"
        for a in section_assets
    )
    # header promo image (https) is attributed to the header context.
    assert any(
        a.kind == "logo" and a.url == "https://cdn.shopify.com/s/files/1/header-promo.png"
        for a in section_assets
    )


def test_source_summary_reports_counts_per_source() -> None:
    snapshot = _collect(FakeShopifyClient())

    assert "theme: Dawn (id 123456789)" in snapshot.source_summary
    assert "shop_metadata:" in snapshot.source_summary
    assert "theme_settings:" in snapshot.source_summary
    assert "css:" in snapshot.source_summary
    assert "section:" in snapshot.source_summary
    assert "errors" not in snapshot.source_summary


# ---------------------------------------------------------------------------
# Degraded paths: partial / failed
# ---------------------------------------------------------------------------


def test_brand_field_unavailable_degrades_to_basic_shop_query() -> None:
    snapshot = _collect(FakeShopifyClient(fail_brand=True))

    assert snapshot.status == "partial"
    assert len(snapshot.errors) == 1
    assert snapshot.errors[0].startswith("shop_metadata: brand metadata unavailable")
    assert snapshot.theme_metadata["shop_name"] == "Demo Apparel"
    # No brand colors/logo, but theme settings evidence still flows.
    assert not any(color.source == "shop_metadata" for color in snapshot.colors)
    assert _colors_by_hex(snapshot)["#3D5AFE"].confidence == 0.9


def test_partial_when_theme_assets_forbidden_keeps_shop_metadata() -> None:
    client = FakeShopifyClient(fail_asset_list=True, fail_assets=True)
    snapshot = _collect(client)

    assert snapshot.status == "partial"
    assert any("403" in error for error in snapshot.errors)
    assert any(error.startswith("theme_assets: asset listing failed") for error in snapshot.errors)
    # Shop metadata evidence survives.
    assert _colors_by_hex(snapshot)["#0E0E10"].source == "shop_metadata"
    assert snapshot.theme_metadata["theme_name"] == "Dawn"
    # No css/settings evidence got through.
    assert not any(color.source.startswith(("css:", "theme_settings:")) for color in snapshot.colors)


def test_failed_when_nothing_can_be_fetched() -> None:
    snapshot = _collect(FakeShopifyClient(fail_shop=True, fail_themes=True))

    assert snapshot.status == "failed"
    assert len(snapshot.errors) >= 2
    assert snapshot.colors == []
    assert snapshot.fonts == []
    assert snapshot.assets == []
    assert snapshot.theme_metadata == {}
    assert "errors:" in snapshot.source_summary


def test_collector_never_raises_and_records_malformed_settings_json() -> None:
    bodies = dict(ASSET_BODIES)
    bodies["config/settings_data.json"] = "{not valid json"
    snapshot = _collect(FakeShopifyClient(asset_bodies=bodies))

    assert snapshot.status == "partial"
    assert any(
        error.startswith("theme_settings:config/settings_data.json: parse failed")
        for error in snapshot.errors
    )
    # Other sources keep contributing evidence.
    assert _colors_by_hex(snapshot)["#FF44FF"].name == "color-accent"


# ---------------------------------------------------------------------------
# Byte caps
# ---------------------------------------------------------------------------


def test_byte_cap_skips_oversized_assets_with_error() -> None:
    bodies = dict(ASSET_BODIES)
    bodies["config/settings_data.json"] = "x" * (DEFAULT_MAX_ASSET_BYTES + 1)
    client = FakeShopifyClient(asset_bodies=bodies)
    snapshot = _collect(client)

    assert snapshot.status == "partial"
    assert any("byte cap" in error for error in snapshot.errors)
    # No settings_data evidence, but the schema defaults still landed.
    assert not any(c.source == "theme_settings:config/settings_data.json" for c in snapshot.colors)
    assert _colors_by_hex(snapshot)["#FF6B5C"].name == "colors_button"
    # Oversized stylesheets are filtered out via the asset index and never fetched.
    assert "assets/huge.css" not in client.fetched_keys


# ---------------------------------------------------------------------------
# Injection safety and secret hygiene
# ---------------------------------------------------------------------------


def test_malicious_css_font_families_are_dropped_not_crashing() -> None:
    bodies = dict(ASSET_BODIES)
    bodies["assets/base.css"] = """
.evil { font-family: "Evil; } body { background:url(javascript:alert(1)) }", serif; }
.evil2 { font-family: Evil<script>alert(1)</script>, serif; }
.evil3 { font-family: var(--inject), expression(alert(1)); }
.ok { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
"""
    snapshot = _collect(FakeShopifyClient(asset_bodies=bodies))
    fonts = _fonts_by_family(snapshot)

    blob = " ".join(fonts).lower()
    assert "evil" not in blob
    assert "script" not in blob
    assert "expression" not in blob
    assert fonts["Helvetica Neue"].css_stack == "Helvetica Neue, Helvetica, Arial, sans-serif"


def test_snapshot_never_contains_access_token() -> None:
    success_dump = _collect(FakeShopifyClient()).model_dump_json()
    failed_dump = _collect(FakeShopifyClient(fail_shop=True, fail_themes=True)).model_dump_json()

    assert SECRET_TOKEN not in success_dump
    assert SECRET_TOKEN not in failed_dump


# ---------------------------------------------------------------------------
# New ShopifyAdminClient read methods (scripted transport, no network)
# ---------------------------------------------------------------------------


class _ScriptedAdminClient(ShopifyAdminClient):
    def __init__(
        self,
        *,
        responses: dict[str, dict[str, Any]] | None = None,
        graphql_data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(shop_domain="demo-apparel.myshopify.com", access_token="test-token")
        self._responses = responses or {}
        self._graphql_data = graphql_data or {}
        self.rest_calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.graphql_queries: list[str] = []

    def _request(self, method, path, *, json=None, params=None):  # type: ignore[override]
        self.rest_calls.append((method, path, params))
        return self._responses.get(path, {})

    def graphql(self, query, variables=None):  # type: ignore[override]
        self.graphql_queries.append(query)
        return self._graphql_data


def test_admin_client_get_main_theme_picks_role_main() -> None:
    client = _ScriptedAdminClient(
        responses={
            "/themes.json": {
                "themes": [
                    {"id": 1, "name": "Draft", "role": "unpublished"},
                    {"id": 2, "name": "Dawn", "role": "MAIN"},
                ]
            }
        }
    )

    assert client.list_themes()[0]["id"] == 1
    main = client.get_main_theme()
    assert main is not None and main["id"] == 2
    assert ("GET", "/themes.json", None) in client.rest_calls


def test_admin_client_get_theme_asset_requests_specific_key() -> None:
    client = _ScriptedAdminClient(
        responses={"/themes/77/assets.json": {"asset": {"key": "config/settings_data.json", "value": "{}"}}}
    )

    asset = client.get_theme_asset(theme_id="77", key="config/settings_data.json")

    assert asset is not None and asset["value"] == "{}"
    assert client.rest_calls[-1] == (
        "GET",
        "/themes/77/assets.json",
        {"asset[key]": "config/settings_data.json"},
    )


def test_admin_client_get_shop_metadata_toggles_brand_fields() -> None:
    client = _ScriptedAdminClient(graphql_data={"shop": {"name": "Demo"}})

    with_brand = client.get_shop_metadata(include_brand=True)
    without_brand = client.get_shop_metadata(include_brand=False)

    assert with_brand == {"name": "Demo"}
    assert without_brand == {"name": "Demo"}
    assert "brand" in client.graphql_queries[0]
    assert "brand" not in client.graphql_queries[1]
