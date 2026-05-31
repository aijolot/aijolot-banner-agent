from __future__ import annotations

from typing import Any, Protocol, cast
from uuid import uuid4

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.campaign_catalog import CampaignCatalogRepository
from app.db.repositories.campaigns import CampaignRepository
from app.schemas.catalog import CatalogResourceType, CatalogSnapshotItem, CatalogSnapshotResponse
from app.schemas.stores import ShopifyResourceSummary
from app.services.shopify.resource_service import DEMO_STORE_ID, ShopifyResourceService, configured_service as configured_resource_service
from app.services.supabase.client import SupabaseClientFactory

SOURCE_SHOPIFY_CACHE = "shopify_resource_cache"
SENSITIVE_METADATA_KEYS = ("token", "secret", "password", "authorization", "auth")


class CampaignNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class CampaignCatalogSnapshotNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"catalog snapshot for campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class InvalidCatalogSnapshot(Exception):
    pass


class CampaignRepositoryProtocol(Protocol):
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...


class CatalogRepositoryProtocol(Protocol):
    def create_snapshot(self, *, campaign_id: str, source: str, query_summary: str | None, discount_rule: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]: ...
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...


class InMemoryCampaignCatalogRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def create_snapshot(self, *, campaign_id: str, source: str, query_summary: str | None, discount_rule: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        snapshot = {
            "id": f"local-catalog-snapshot-{uuid4()}",
            "campaign_id": campaign_id,
            "source": source,
            "query_summary": query_summary,
            "discount_rule": discount_rule or {},
            "items": [{"id": f"local-catalog-item-{index + 1}", **item} for index, item in enumerate(items)],
            "created_at": None,
        }
        self.rows[campaign_id] = snapshot
        return snapshot

    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        return self.rows.get(campaign_id)


_LOCAL_CATALOG_REPOSITORY = InMemoryCampaignCatalogRepository()


class CatalogSnapshotService:
    """Creates reproducible campaign catalog snapshots from cached Shopify resources.

    This service intentionally never calls live Shopify APIs. The resource service
    is backed by shopify_resource_cache in configured Supabase mode or deterministic
    seed data in local/demo mode.
    """

    def __init__(
        self,
        *,
        campaign_repository: CampaignRepositoryProtocol | None = None,
        catalog_repository: CatalogRepositoryProtocol | None = None,
        resource_service: ShopifyResourceService | Any | None = None,
        team_id: str | None = None,
    ) -> None:
        self.campaign_repository = campaign_repository
        self.catalog_repository = catalog_repository or _LOCAL_CATALOG_REPOSITORY
        self.resource_service = resource_service or configured_resource_service()
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str | None = None) -> "CatalogSnapshotService":
        return cls(
            campaign_repository=CampaignRepository(client),
            catalog_repository=CampaignCatalogRepository(client),
            resource_service=ShopifyResourceService.from_supabase_client(client, team_id=team_id),
            team_id=team_id,
        )

    def create_snapshot(
        self,
        campaign_id: str,
        *,
        store_id: str | None = None,
        query_summary: str | None = None,
        discount_rule: dict[str, Any] | None = None,
        resource_types: list[CatalogResourceType] | None = None,
        limit: int = 100,
    ) -> CatalogSnapshotResponse:
        campaign = self._get_campaign(campaign_id)
        resolved_store_id = self._resolve_store_id(campaign=campaign, explicit_store_id=store_id)
        if campaign and campaign.get("store_id") and str(campaign["store_id"]) != resolved_store_id:
            raise InvalidCatalogSnapshot("request store_id does not match campaign store_id")
        items = self._snapshot_items(store_id=resolved_store_id, resource_types=resource_types or ["product"], limit=limit)
        row = self.catalog_repository.create_snapshot(
            campaign_id=campaign_id,
            source=SOURCE_SHOPIFY_CACHE,
            query_summary=query_summary,
            discount_rule=discount_rule or {},
            items=[item.model_dump() for item in items],
        )
        return self._response_from_record(row, store_id=resolved_store_id)

    def get_snapshot(self, campaign_id: str) -> CatalogSnapshotResponse:
        self._get_campaign(campaign_id, allow_unconfigured=True)
        row = self.catalog_repository.get_latest_by_campaign_id(campaign_id=campaign_id)
        if row is None:
            raise CampaignCatalogSnapshotNotFound(campaign_id)
        return self._response_from_record(row, store_id=cast(str | None, row.get("store_id")))

    def _get_campaign(self, campaign_id: str, *, allow_unconfigured: bool = False) -> dict[str, Any] | None:
        if self.campaign_repository is None:
            return None
        campaign = self.campaign_repository.get(campaign_id=campaign_id, team_id=self.team_id)
        if campaign is None:
            raise CampaignNotFound(campaign_id)
        return campaign

    @staticmethod
    def _resolve_store_id(*, campaign: dict[str, Any] | None, explicit_store_id: str | None) -> str:
        if campaign and campaign.get("store_id"):
            return str(campaign["store_id"])
        if explicit_store_id:
            return explicit_store_id
        return DEMO_STORE_ID

    def _snapshot_items(self, *, store_id: str, resource_types: list[CatalogResourceType], limit: int) -> list[CatalogSnapshotItem]:
        items: list[CatalogSnapshotItem] = []
        per_type_limit = max(1, min(limit, 250))
        for resource_type in resource_types:
            resources = self.resource_service.list_resources(store_id, resource_type=resource_type, limit=per_type_limit)
            items.extend(self._item_from_resource(resource) for resource in resources)
        return sorted(items, key=lambda item: (item.resource_type, item.title.lower()))[:limit]

    @staticmethod
    def _item_from_resource(resource: ShopifyResourceSummary) -> CatalogSnapshotItem:
        metadata = _safe_metadata(resource.metadata)
        sku = _string_or_none(metadata.get("sku"))
        price = _float_or_none(metadata.get("price"))
        sale_price = _float_or_none(metadata.get("sale") if "sale" in metadata else metadata.get("sale_price"))
        stock = _int_or_none(metadata.get("stock") if "stock" in metadata else metadata.get("inventory_quantity"))
        raw = {
            "resource_id": resource.id,
            "store_id": resource.store_id,
            "resource_type": resource.resource_type,
            "shopify_gid": resource.shopify_gid,
            "handle": resource.handle,
            "vendor": resource.vendor,
            "tags": resource.tags,
            "status": resource.status,
            "metadata": metadata,
        }
        return CatalogSnapshotItem(
            resource_type=cast(CatalogResourceType, resource.resource_type),
            shopify_product_gid=resource.shopify_gid if resource.resource_type == "product" else None,
            shopify_gid=resource.shopify_gid,
            handle=resource.handle,
            title=resource.title,
            vendor=resource.vendor,
            tags=resource.tags,
            sku=sku,
            price=price,
            sale_price=sale_price,
            stock=stock,
            image_url=resource.image_url,
            raw=raw,
        )

    @staticmethod
    def _response_from_record(row: dict[str, Any], *, store_id: str | None = None) -> CatalogSnapshotResponse:
        items = sorted(
            [_item_from_record(item) for item in list(row.get("items") or [])],
            key=lambda item: (item.resource_type, item.title.lower()),
        )
        resolved_store_id = store_id or _store_id_from_items(items)
        return CatalogSnapshotResponse(
            id=str(row["id"]),
            campaign_id=str(row["campaign_id"]),
            store_id=resolved_store_id,
            source=str(row.get("source") or SOURCE_SHOPIFY_CACHE),
            query_summary=cast(str | None, row.get("query_summary")),
            discount_rule=dict(row.get("discount_rule") or {}),
            items=items,
            item_count=len(items),
            created_at=str(row["created_at"]) if row.get("created_at") is not None else None,
        )


def _store_id_from_items(items: list[CatalogSnapshotItem]) -> str | None:
    for item in items:
        store_id = item.raw.get("store_id")
        if store_id:
            return str(store_id)
    return None


def _item_from_record(row: dict[str, Any]) -> CatalogSnapshotItem:
    raw = _safe_metadata(row.get("raw") or {})
    resource_type = cast(CatalogResourceType, raw.get("resource_type") or row.get("resource_type") or "product")
    metadata_value = raw.get("metadata")
    metadata: dict[str, Any] = metadata_value if isinstance(metadata_value, dict) else {}
    return CatalogSnapshotItem(
        id=str(row["id"]) if row.get("id") is not None else None,
        resource_type=resource_type,
        shopify_product_gid=cast(str | None, row.get("shopify_product_gid")),
        shopify_variant_gid=cast(str | None, row.get("shopify_variant_gid")),
        shopify_gid=cast(str | None, row.get("shopify_gid") or raw.get("shopify_gid") or row.get("shopify_product_gid")),
        handle=cast(str | None, row.get("handle") or raw.get("handle")),
        title=str(row.get("title") or "Untitled"),
        vendor=cast(str | None, row.get("vendor") or raw.get("vendor")),
        tags=[str(tag) for tag in (row.get("tags") or raw.get("tags") or [])],
        segment_key=cast(str | None, row.get("segment_key")),
        sku=_string_or_none(row.get("sku") or metadata.get("sku")),
        price=_float_or_none(row.get("price") if row.get("price") is not None else metadata.get("price")),
        sale_price=_float_or_none(row.get("sale_price") if row.get("sale_price") is not None else metadata.get("sale_price") or metadata.get("sale")),
        stock=_int_or_none(row.get("stock") if row.get("stock") is not None else metadata.get("stock")),
        image_url=cast(str | None, row.get("image_url")),
        raw=raw,
    )


def configured_service() -> CatalogSnapshotService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    has_supabase = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    team_id = settings.supabase_team_id or settings.brand_context_team_id
    if not has_supabase_signal:
        return CatalogSnapshotService(team_id=team_id)
    if not has_supabase:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID", "BRAND_CONTEXT_TEAM_ID"))
    client = SupabaseClientFactory(settings).service_role_client()
    return CatalogSnapshotService.from_supabase_client(client, team_id=team_id)


def _safe_metadata(value: Any) -> dict[str, Any]:
    redacted = _redact_sensitive_metadata(value)
    return redacted if isinstance(redacted, dict) else {}


def _redact_sensitive_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _redact_sensitive_metadata(item)
            for key, item in value.items()
            if not any(part in str(key).lower() for part in SENSITIVE_METADATA_KEYS)
        }
    if isinstance(value, list):
        return [_redact_sensitive_metadata(item) for item in value]
    return value


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
