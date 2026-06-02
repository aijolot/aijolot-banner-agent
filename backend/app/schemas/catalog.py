from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
CatalogResourceType = Literal["product", "collection", "page"]


class CatalogSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    query_summary: str | None = None
    discount_rule: dict[str, Any] = Field(default_factory=dict)
    resource_types: list[CatalogResourceType] = Field(default_factory=lambda: ["product"])
    limit: int = Field(default=100, ge=1, le=250)

    @field_validator("query_summary")
    @classmethod
    def _blank_query_summary_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("resource_types")
    @classmethod
    def _dedupe_resource_types(cls, value: list[CatalogResourceType]) -> list[CatalogResourceType]:
        out: list[CatalogResourceType] = []
        for item in value:
            if item not in out:
                out.append(item)
        return out or ["product"]


class CatalogSnapshotItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    resource_type: CatalogResourceType = "product"
    shopify_product_gid: str | None = None
    shopify_variant_gid: str | None = None
    shopify_gid: str | None = None
    handle: str | None = None
    title: str
    vendor: str | None = None
    tags: list[str] = Field(default_factory=list)
    segment_key: str | None = None
    sku: str | None = None
    price: float | None = None
    sale_price: float | None = None
    stock: int | None = None
    image_url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class CatalogSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    campaign_id: str
    store_id: str | None = None
    source: str = "shopify_resource_cache"
    query_summary: str | None = None
    discount_rule: dict[str, Any] = Field(default_factory=dict)
    items: list[CatalogSnapshotItem] = Field(default_factory=list)
    item_count: int = 0
    created_at: str | None = None
