from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ShopifyResourceType = Literal["collection", "product", "page", "search", "vendor", "customer_segment"]
CachedShopifyResourceType = Literal["collection", "product", "page", "vendor", "customer_segment"]
StoreStatus = Literal["connected", "disconnected", "needs_attention"]


class SyncResult(BaseModel):
    """Per-resource-type outcome of a live Shopify catalog sync."""

    model_config = ConfigDict(extra="forbid")

    resource_type: CachedShopifyResourceType
    fetched: int = 0
    written: int = 0
    skipped: int = 0


class SyncReport(BaseModel):
    """Summary of a live Shopify catalog sync (or dry-run preview)."""

    model_config = ConfigDict(extra="forbid")

    store_id: str
    source: str = "shopify_admin_graphql"
    dry_run: bool = False
    results: list[SyncResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StoreSummary(BaseModel):
    """Frontend-safe store shape. Deliberately excludes token/secret columns."""

    model_config = ConfigDict(extra="forbid")

    id: str
    team_id: str
    shop_domain: str
    name: str
    shopify_api_version: str = "2026-01"
    theme_id: str | None = None
    status: StoreStatus = "connected"
    banner_metafield_namespace: str = "aijolot"
    banner_metafield_key: str = "banner_campaigns"


class ShopifyResourceSummary(BaseModel):
    """Selectable Shopify target resource from the local cache."""

    model_config = ConfigDict(extra="forbid")

    id: str
    store_id: str
    resource_type: ShopifyResourceType
    shopify_gid: str | None = None
    handle: str | None = None
    title: str
    vendor: str | None = None
    tags: list[str] = Field(default_factory=list)
    image_url: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
