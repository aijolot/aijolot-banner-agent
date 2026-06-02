from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ShopifyResourceType = Literal["collection", "product", "page", "search"]
CachedShopifyResourceType = Literal["collection", "product", "page"]
StoreStatus = Literal["connected", "disconnected", "needs_attention"]


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
