from __future__ import annotations

from typing import Any, Protocol, cast

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.shopify_resource_cache import ShopifyResourceCacheRepository
from app.db.repositories.stores import StoreRepository
from app.schemas.stores import ShopifyResourceSummary, ShopifyResourceType, StoreSummary
from app.services.supabase.client import SupabaseClientFactory

DEMO_TEAM_ID = "00000000-0000-0000-0000-000000000001"
DEMO_STORE_ID = "00000000-0000-0000-0000-000000000101"

SEED_STORES: list[dict[str, Any]] = [
    {
        "id": DEMO_STORE_ID,
        "team_id": DEMO_TEAM_ID,
        "shop_domain": "maison-store.myshopify.com",
        "display_name": "Maison Store",
        "shopify_api_version": "2026-01",
        "theme_id": "demo-theme",
        "banner_metafield_namespace": "aijolot",
        "banner_metafield_key": "banner_campaigns",
        "status": "connected",
    }
]

SEED_RESOURCES: list[dict[str, Any]] = [
    {
        "id": "seed-collection-1",
        "store_id": DEMO_STORE_ID,
        "resource_type": "collection",
        "shopify_gid": "gid://shopify/Collection/1",
        "handle": "fragancias",
        "title": "Fragancias",
        "vendor": None,
        "tags": ["perfume", "hugo-boss"],
        "image_url": None,
        "status": "active",
        "raw": {},
    },
    {
        "id": "seed-collection-2",
        "store_id": DEMO_STORE_ID,
        "resource_type": "collection",
        "shopify_gid": "gid://shopify/Collection/2",
        "handle": "hombre",
        "title": "Hombre",
        "vendor": None,
        "tags": ["masculino"],
        "image_url": None,
        "status": "active",
        "raw": {},
    },
    {
        "id": "seed-collection-3",
        "store_id": DEMO_STORE_ID,
        "resource_type": "collection",
        "shopify_gid": "gid://shopify/Collection/3",
        "handle": "mujer",
        "title": "Mujer",
        "vendor": None,
        "tags": ["femenino"],
        "image_url": None,
        "status": "active",
        "raw": {},
    },
    {
        "id": "seed-product-1001",
        "store_id": DEMO_STORE_ID,
        "resource_type": "product",
        "shopify_gid": "gid://shopify/Product/1001",
        "handle": "boss-bottled-edp-100ml",
        "title": "Boss Bottled EDP 100ml",
        "vendor": "Hugo Boss",
        "tags": ["fragancia", "gender:male"],
        "image_url": None,
        "status": "active",
        "raw": {"sku": "HB-BOTTLED-100", "stock": 64, "price": 138, "sale": 124.2},
    },
    {
        "id": "seed-product-1002",
        "store_id": DEMO_STORE_ID,
        "resource_type": "product",
        "shopify_gid": "gid://shopify/Product/1002",
        "handle": "boss-alive-edp-80ml",
        "title": "Boss Alive EDP 80ml",
        "vendor": "Hugo Boss",
        "tags": ["fragancia", "gender:female"],
        "image_url": None,
        "status": "active",
        "raw": {"sku": "HB-ALIVE-80", "stock": 51, "price": 124, "sale": 111.6},
    },
    {
        "id": "seed-product-1003",
        "store_id": DEMO_STORE_ID,
        "resource_type": "product",
        "shopify_gid": "gid://shopify/Product/1003",
        "handle": "set-lujo-boss-bottled",
        "title": "Set Lujo Boss Bottled",
        "vendor": "Hugo Boss",
        "tags": ["fragancia", "vip:true"],
        "image_url": None,
        "status": "active",
        "raw": {"sku": "HB-SET-LUX", "stock": 12, "price": 210, "sale": 189},
    },
    {
        "id": "seed-page-2001",
        "store_id": DEMO_STORE_ID,
        "resource_type": "page",
        "shopify_gid": "gid://shopify/Page/2001",
        "handle": "promociones",
        "title": "Promociones",
        "vendor": None,
        "tags": ["landing"],
        "image_url": None,
        "status": "published",
        "raw": {},
    },
    {
        "id": "seed-vendor-1",
        "store_id": DEMO_STORE_ID,
        "resource_type": "vendor",
        "shopify_gid": "vendor:hugo-boss",
        "handle": "hugo-boss",
        "title": "Hugo Boss",
        "vendor": "Hugo Boss",
        "tags": [],
        "image_url": None,
        "status": "active",
        "raw": {"derived": "products.vendor"},
    },
    {
        "id": "seed-segment-1",
        "store_id": DEMO_STORE_ID,
        "resource_type": "customer_segment",
        "shopify_gid": "gid://shopify/Segment/9001",
        "handle": "clientes-vip",
        "title": "Clientes VIP",
        "vendor": None,
        "tags": [],
        "image_url": None,
        "status": "active",
        "raw": {"query": "amount_spent > 500"},
    },
]


class StoreNotFound(Exception):
    def __init__(self, store_id: str) -> None:
        super().__init__(f"store '{store_id}' not found")
        self.store_id = store_id


class StoreRepositoryProtocol(Protocol):
    def list(self, *, team_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]: ...
    def get(self, *, store_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...


class ResourceRepositoryProtocol(Protocol):
    def list_for_store(self, *, store_id: str, resource_type: str, limit: int = 100) -> list[dict[str, Any]]: ...


class SeedStoreRepository:
    def list(self, *, team_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        rows = [row for row in SEED_STORES if team_id is None or row["team_id"] == team_id]
        return rows[:limit]

    def get(self, *, store_id: str, team_id: str | None = None) -> dict[str, Any] | None:
        return next((row for row in SEED_STORES if row["id"] == store_id and (team_id is None or row["team_id"] == team_id)), None)


class SeedShopifyResourceCacheRepository:
    def list_for_store(self, *, store_id: str, resource_type: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = [
            row
            for row in SEED_RESOURCES
            if row["store_id"] == store_id and row["resource_type"] == resource_type
        ]
        return sorted(rows, key=lambda row: str(row.get("title") or ""))[:limit]


class ShopifyResourceService:
    """Store/catalog read service backed by Supabase cache or deterministic seeds.

    This service never calls Shopify live APIs. It only reads stores and
    shopify_resource_cache rows (or their local seed fallback).
    """

    def __init__(
        self,
        *,
        store_repository: StoreRepositoryProtocol | None = None,
        resource_repository: ResourceRepositoryProtocol | None = None,
        team_id: str | None = None,
    ) -> None:
        self.store_repository = store_repository or SeedStoreRepository()
        self.resource_repository = resource_repository or SeedShopifyResourceCacheRepository()
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str | None = None) -> "ShopifyResourceService":
        return cls(
            store_repository=StoreRepository(client),
            resource_repository=ShopifyResourceCacheRepository(client),
            team_id=team_id,
        )

    def list_stores(self, *, limit: int = 100) -> list[StoreSummary]:
        rows = self.store_repository.list(team_id=self.team_id, limit=limit)
        stores = [self._store_from_record(row) for row in rows]
        return sorted(stores, key=lambda store: store.name.lower())

    def get_store(self, store_id: str) -> StoreSummary:
        row = self.store_repository.get(store_id=store_id, team_id=self.team_id)
        if row is None:
            raise StoreNotFound(store_id)
        return self._store_from_record(row)

    def list_resources(
        self,
        store_id: str,
        *,
        resource_type: ShopifyResourceType,
        limit: int = 100,
        query: str | None = None,
    ) -> list[ShopifyResourceSummary]:
        # Ensure the store belongs to the configured team/scope before returning resources.
        self.get_store(store_id)
        if resource_type == "search":
            return [
                ShopifyResourceSummary(
                    id=f"{store_id}:search",
                    store_id=store_id,
                    resource_type="search",
                    shopify_gid=None,
                    handle="search",
                    title="Search results",
                    status="available",
                    metadata={"virtual": True},
                )
            ]
        # Fetch a wider window when filtering so the text query can narrow it down.
        fetch_limit = max(limit, 250) if query else limit
        rows = self.resource_repository.list_for_store(store_id=store_id, resource_type=resource_type, limit=fetch_limit)
        resources = [self._resource_from_record(row) for row in rows]
        needle = (query or "").strip().lower()
        if needle:
            resources = [r for r in resources if needle in self._haystack(r)]
        resources = sorted(resources, key=lambda resource: resource.title.lower())
        return resources[:limit]

    @staticmethod
    def _haystack(resource: ShopifyResourceSummary) -> str:
        parts = [resource.title, resource.handle or "", resource.vendor or "", " ".join(resource.tags)]
        return " ".join(parts).lower()

    @staticmethod
    def _store_from_record(row: dict[str, Any]) -> StoreSummary:
        display_name = row.get("display_name") or row.get("name") or row.get("shop_domain") or "Store"
        return StoreSummary(
            id=str(row["id"]),
            team_id=str(row["team_id"]),
            shop_domain=str(row["shop_domain"]),
            name=str(display_name),
            shopify_api_version=str(row.get("shopify_api_version") or "2026-01"),
            theme_id=cast(str | None, row.get("theme_id")),
            status=str(row.get("status") or "connected"),
            banner_metafield_namespace=str(row.get("banner_metafield_namespace") or "aijolot"),
            banner_metafield_key=str(row.get("banner_metafield_key") or "banner_campaigns"),
        )

    @staticmethod
    def _resource_from_record(row: dict[str, Any]) -> ShopifyResourceSummary:
        metadata = _safe_metadata(row.get("raw") or row.get("metadata") or {})
        tags = row.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        return ShopifyResourceSummary(
            id=str(row["id"]),
            store_id=str(row["store_id"]),
            resource_type=cast(ShopifyResourceType, row["resource_type"]),
            shopify_gid=cast(str | None, row.get("shopify_gid")),
            handle=cast(str | None, row.get("handle")),
            title=str(row.get("title") or row.get("handle") or "Untitled"),
            vendor=cast(str | None, row.get("vendor")),
            tags=[str(tag) for tag in tags],
            image_url=cast(str | None, row.get("image_url")),
            status=cast(str | None, row.get("status")),
            metadata=metadata,
        )


def _configured_service_for_team(team_id_override: str | None = None) -> ShopifyResourceService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    has_supabase = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    team_id = team_id_override or settings.supabase_team_id or settings.brand_context_team_id
    if not has_supabase_signal:
        return ShopifyResourceService(team_id=team_id)
    if not has_supabase:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID", "BRAND_CONTEXT_TEAM_ID"))
    client = SupabaseClientFactory(settings).service_role_client()
    return ShopifyResourceService.from_supabase_client(client, team_id=team_id)


def configured_service() -> ShopifyResourceService:
    return _configured_service_for_team()


def configured_service_for_team(team_id: str) -> ShopifyResourceService:
    return _configured_service_for_team(team_id)


_SENSITIVE_METADATA_KEYS = ("token", "secret", "password", "authorization", "auth")


def _safe_metadata(value: Any) -> dict[str, Any]:
    redacted = _redact_sensitive_metadata(value)
    return redacted if isinstance(redacted, dict) else {}


def _redact_sensitive_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact_sensitive_metadata(item)
            for key, item in value.items()
            if not any(part in key.lower() for part in _SENSITIVE_METADATA_KEYS)
        }
    if isinstance(value, list):
        return [_redact_sensitive_metadata(item) for item in value]
    return value
