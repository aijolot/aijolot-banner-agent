from __future__ import annotations

from typing import Any, Protocol, cast

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.campaign_placements import CampaignPlacementRepository
from app.db.repositories.campaigns import CampaignRepository
from app.db.repositories.placement_types import PlacementTypeRepository
from app.schemas.placements import (
    CampaignPlacementResponse,
    CampaignPlacementUpsert,
    NormalizedPlacement,
    PlacementTargetMap,
    PlacementTargetType,
    PlacementTypeSummary,
    PlacementValidateRequest,
    PlacementValidationResponse,
)
from app.schemas.stores import ShopifyResourceSummary
from app.services.shopify.resource_service import ShopifyResourceService, StoreNotFound, configured_service as configured_resource_service
from app.services.supabase.client import SupabaseClientFactory

SEED_PLACEMENT_TYPES: list[dict[str, Any]] = [
    {
        "id": "seed-placement-announcement-bar",
        "key": "announcement_bar",
        "label": "Barra de anuncios",
        "description": "Short global promotional strip near the storefront header.",
        "supported_targets": ["home", "collection", "product", "page", "store"],
        "supported_slots": [{"key": "announce", "label": "Barra de anuncios"}, {"key": "after_header", "label": "Después del header"}],
        "default_dimensions": {"desktop": {"width": 1200, "height": 48}, "tablet": {"width": 768, "height": 48}, "mobile": {"width": 390, "height": 56}},
        "config_schema": {},
        "is_active": True,
    },
    {
        "id": "seed-placement-hero-main",
        "key": "hero_main",
        "label": "Hero principal",
        "description": "Primary above-the-fold marketing banner.",
        "supported_targets": ["home", "collection", "page"],
        "supported_slots": [{"key": "hero", "label": "Hero principal"}, {"key": "top", "label": "Parte superior"}],
        "default_dimensions": {"desktop": {"width": 1440, "height": 420}, "tablet": {"width": 768, "height": 360}, "mobile": {"width": 390, "height": 460}},
        "config_schema": {},
        "is_active": True,
    },
    {
        "id": "seed-placement-promo-card",
        "key": "promo_card",
        "label": "Promo card",
        "description": "Medium-sized promotional card inside homepage or grid sections.",
        "supported_targets": ["home", "collection"],
        "supported_slots": [{"key": "promo_l", "label": "Promo izquierda"}, {"key": "promo_r", "label": "Promo derecha"}, {"key": "coll_inline", "label": "Bloque intermedio"}],
        "default_dimensions": {"desktop": {"width": 600, "height": 300}, "tablet": {"width": 384, "height": 260}, "mobile": {"width": 390, "height": 260}},
        "config_schema": {},
        "is_active": True,
    },
    {
        "id": "seed-placement-collection-header",
        "key": "collection_header",
        "label": "Cabecera de colección",
        "description": "Collection page header banner.",
        "supported_targets": ["collection"],
        "supported_slots": [{"key": "coll_top", "label": "Cabecera de colección"}, {"key": "above_product_grid", "label": "Sobre grid de productos"}],
        "default_dimensions": {"desktop": {"width": 1440, "height": 320}, "tablet": {"width": 768, "height": 300}, "mobile": {"width": 390, "height": 360}},
        "config_schema": {},
        "is_active": True,
    },
    {
        "id": "seed-placement-pdp-strip",
        "key": "pdp_strip",
        "label": "Franja de oferta PDP",
        "description": "Product detail page offer strip.",
        "supported_targets": ["product"],
        "supported_slots": [{"key": "pdp_strip", "label": "Franja de oferta"}, {"key": "below_product_info", "label": "Debajo de información de producto"}],
        "default_dimensions": {"desktop": {"width": 520, "height": 90}, "tablet": {"width": 520, "height": 90}, "mobile": {"width": 390, "height": 110}},
        "config_schema": {},
        "is_active": True,
    },
    {
        "id": "seed-placement-pdp-cross-sell",
        "key": "pdp_cross_sell",
        "label": "Cross-sell PDP",
        "description": "Cross-sell banner inside product detail pages.",
        "supported_targets": ["product"],
        "supported_slots": [{"key": "pdp_cross", "label": "Cross-sell"}],
        "default_dimensions": {"desktop": {"width": 1200, "height": 220}, "tablet": {"width": 768, "height": 220}, "mobile": {"width": 390, "height": 280}},
        "config_schema": {},
        "is_active": True,
    },
    {
        "id": "seed-placement-footer-cta",
        "key": "footer_cta",
        "label": "CTA de footer",
        "description": "Footer call-to-action banner.",
        "supported_targets": ["home", "collection", "product", "page", "store"],
        "supported_slots": [{"key": "footer", "label": "CTA de footer"}, {"key": "bottom", "label": "Antes del footer"}],
        "default_dimensions": {"desktop": {"width": 1200, "height": 260}, "tablet": {"width": 768, "height": 260}, "mobile": {"width": 390, "height": 300}},
        "config_schema": {},
        "is_active": True,
    },
    {
        "id": "seed-placement-search-results-banner",
        "key": "search_results_banner",
        "label": "Banner de resultados de búsqueda",
        "description": "Banner rendered on search result pages for a query trigger.",
        "supported_targets": ["search"],
        "supported_slots": [{"key": "search_top", "label": "Banner de resultados"}],
        "default_dimensions": {"desktop": {"width": 1200, "height": 200}, "tablet": {"width": 768, "height": 200}, "mobile": {"width": 390, "height": 240}},
        "config_schema": {},
        "is_active": True,
    },
]


class PlacementTypeNotFound(Exception):
    def __init__(self, placement_type_key: str) -> None:
        super().__init__(f"placement type '{placement_type_key}' not found")
        self.placement_type_key = placement_type_key


class InvalidPlacement(Exception):
    pass


class CampaignNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class CampaignPlacementNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"placement for campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class PlacementTypeRepositoryProtocol(Protocol):
    def list_active(self) -> list[dict[str, Any]]: ...
    def get_by_key(self, *, key: str) -> dict[str, Any] | None: ...
    def get_by_id(self, *, placement_type_id: str) -> dict[str, Any] | None: ...


class CampaignRepositoryProtocol(Protocol):
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...


class CampaignPlacementRepositoryProtocol(Protocol):
    def get_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...
    def upsert_for_campaign(self, *, campaign_id: str, data: dict[str, Any]) -> dict[str, Any]: ...


class SeedPlacementTypeRepository:
    def list_active(self) -> list[dict[str, Any]]:
        return sorted(SEED_PLACEMENT_TYPES, key=lambda row: row["key"])

    def get_by_key(self, *, key: str) -> dict[str, Any] | None:
        return next((row for row in SEED_PLACEMENT_TYPES if row["key"] == key and row.get("is_active", True)), None)

    def get_by_id(self, *, placement_type_id: str) -> dict[str, Any] | None:
        return next((row for row in SEED_PLACEMENT_TYPES if row["id"] == placement_type_id), None)


class InMemoryCampaignPlacementRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def get_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        return self.rows.get(campaign_id)

    def upsert_for_campaign(self, *, campaign_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = {"id": f"local-placement-{campaign_id}", "campaign_id": campaign_id, **data}
        self.rows[campaign_id] = row
        return row


_LOCAL_PLACEMENT_REPOSITORY = InMemoryCampaignPlacementRepository()


class PlacementService:
    def __init__(
        self,
        *,
        placement_type_repository: PlacementTypeRepositoryProtocol | None = None,
        campaign_placement_repository: CampaignPlacementRepositoryProtocol | None = None,
        campaign_repository: CampaignRepositoryProtocol | None = None,
        resource_service: ShopifyResourceService | None = None,
        team_id: str | None = None,
    ) -> None:
        self.placement_type_repository = placement_type_repository or SeedPlacementTypeRepository()
        self.campaign_placement_repository = campaign_placement_repository or _LOCAL_PLACEMENT_REPOSITORY
        self.campaign_repository = campaign_repository
        self.resource_service = resource_service or configured_resource_service()
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str | None = None) -> "PlacementService":
        return cls(
            placement_type_repository=PlacementTypeRepository(client),
            campaign_placement_repository=CampaignPlacementRepository(client),
            campaign_repository=CampaignRepository(client),
            resource_service=ShopifyResourceService.from_supabase_client(client, team_id=team_id),
            team_id=team_id,
        )

    def list_placement_types(self, store_id: str) -> list[PlacementTypeSummary]:
        self.resource_service.get_store(store_id)
        return [self._placement_type_from_record(row) for row in self.placement_type_repository.list_active()]

    def list_targets(self, store_id: str, placement_type_key: str) -> PlacementTargetMap:
        self.resource_service.get_store(store_id)
        placement_type = self._get_placement_type(placement_type_key)
        targets = PlacementTargetMap()
        for target_type in placement_type.supported_targets:
            if target_type in ("collection", "product", "page", "search"):
                setattr(targets, target_type, self.resource_service.list_resources(store_id, resource_type=cast(Any, target_type)))
            else:
                setattr(targets, target_type, [])
        return targets

    def validate(self, request: PlacementValidateRequest) -> PlacementValidationResponse:
        placement_type = self._get_placement_type(request.placement_type_key)
        if request.target_type not in placement_type.supported_targets:
            raise InvalidPlacement(f"placement type '{request.placement_type_key}' does not support target '{request.target_type}'")
        self.resource_service.get_store(request.store_id)
        self._validate_slot(request, placement_type)
        target = self._resolve_target(request)
        if request.mode == "existing_section" and not request.existing_placement_key:
            raise InvalidPlacement("existing_placement_key is required for existing_section mode")
        normalized = request.to_normalized(placement_type_id=placement_type.id)
        if target is not None:
            normalized.target_resource_gid = target.shopify_gid
            normalized.target_handle = target.handle
            normalized.target_title = target.title
        elif request.target_type in ("home", "store"):
            normalized.target_title = request.target_title or ("Home" if request.target_type == "home" else "Store")
        elif request.target_type == "search":
            normalized.target_title = request.target_title or "Search results"
        return PlacementValidationResponse(valid=True, placement=normalized, errors=[])

    def save_campaign_placement(self, campaign_id: str, request: CampaignPlacementUpsert) -> CampaignPlacementResponse:
        campaign = self._get_campaign(campaign_id)
        if campaign and campaign.get("store_id") and str(campaign["store_id"]) != request.store_id:
            raise InvalidPlacement("campaign store_id does not match placement store_id")
        validated = self.validate(request).placement
        row = self.campaign_placement_repository.upsert_for_campaign(
            campaign_id=campaign_id,
            data=self._db_payload(validated),
        )
        if not row:
            raise InvalidPlacement("campaign placement could not be saved")
        row.setdefault("store_id", request.store_id)
        row.setdefault("placement_type_key", request.placement_type_key)
        return self._placement_response_from_record(row)

    def get_campaign_placement(self, campaign_id: str) -> CampaignPlacementResponse:
        campaign = self._get_campaign(campaign_id, allow_unconfigured=True)
        row = self.campaign_placement_repository.get_by_campaign_id(campaign_id=campaign_id)
        if row is None:
            raise CampaignPlacementNotFound(campaign_id)
        if campaign and campaign.get("store_id"):
            row.setdefault("store_id", str(campaign["store_id"]))
        return self._placement_response_from_record(row)

    def _get_campaign(self, campaign_id: str, *, allow_unconfigured: bool = False) -> dict[str, Any] | None:
        if self.campaign_repository is None:
            if allow_unconfigured:
                return None
            return None
        campaign = self.campaign_repository.get(campaign_id=campaign_id, team_id=self.team_id)
        if campaign is None:
            raise CampaignNotFound(campaign_id)
        return campaign

    def _get_placement_type(self, placement_type_key: str) -> PlacementTypeSummary:
        row = self.placement_type_repository.get_by_key(key=placement_type_key)
        if row is None:
            raise PlacementTypeNotFound(placement_type_key)
        return self._placement_type_from_record(row)

    def _placement_type_by_id(self, placement_type_id: str | None) -> PlacementTypeSummary | None:
        if not placement_type_id:
            return None
        row = self.placement_type_repository.get_by_id(placement_type_id=placement_type_id)
        return self._placement_type_from_record(row) if row else None

    @staticmethod
    def _placement_type_from_record(row: dict[str, Any]) -> PlacementTypeSummary:
        return PlacementTypeSummary(
            id=str(row["id"]),
            key=str(row["key"]),
            label=str(row["label"]),
            description=cast(str | None, row.get("description")),
            supported_targets=cast(list[PlacementTargetType], list(row.get("supported_targets") or [])),
            supported_slots=list(row.get("supported_slots") or []),
            default_dimensions=dict(row.get("default_dimensions") or {}),
            config_schema=dict(row.get("config_schema") or {}),
            is_active=bool(row.get("is_active", True)),
        )

    def _validate_slot(self, request: PlacementValidateRequest, placement_type: PlacementTypeSummary) -> None:
        if not request.slot:
            return
        slot_keys = {str(slot.get("key")) for slot in placement_type.supported_slots if isinstance(slot, dict) and slot.get("key")}
        if slot_keys and request.slot not in slot_keys:
            raise InvalidPlacement(f"slot '{request.slot}' is not supported by placement type '{placement_type.key}'")

    def _resolve_target(self, request: PlacementValidateRequest) -> ShopifyResourceSummary | None:
        if request.target_type in ("home", "store"):
            if request.target_resource_gid or request.target_handle:
                raise InvalidPlacement(f"resource identifiers are not valid for target '{request.target_type}'")
            return None
        if request.target_type == "search":
            if request.target_resource_gid:
                raise InvalidPlacement("target_resource_gid is not valid for target 'search'")
            return None
        resources = self.resource_service.list_resources(request.store_id, resource_type=cast(Any, request.target_type))
        for resource in resources:
            if request.target_resource_gid and resource.shopify_gid == request.target_resource_gid:
                return resource
            if request.target_handle and resource.handle == request.target_handle:
                return resource
        raise InvalidPlacement(f"target resource not found for '{request.target_type}'")

    @staticmethod
    def _db_payload(placement: NormalizedPlacement) -> dict[str, Any]:
        data = placement.model_dump(exclude={"store_id", "placement_type_key"})
        return data

    def _placement_response_from_record(self, row: dict[str, Any]) -> CampaignPlacementResponse:
        placement_type = self._placement_type_by_id(cast(str | None, row.get("placement_type_id")))
        placement_type_key = cast(str | None, row.get("placement_type_key")) or (placement_type.key if placement_type else "unknown")
        return CampaignPlacementResponse(
            id=str(row["id"]),
            campaign_id=str(row["campaign_id"]),
            store_id=str(row.get("store_id") or ""),
            placement_type_id=cast(str | None, row.get("placement_type_id")),
            placement_type_key=placement_type_key,
            mode=cast(Any, row["mode"]),
            target_type=cast(Any, row["target_type"]),
            target_resource_gid=cast(str | None, row.get("target_resource_gid")),
            target_handle=cast(str | None, row.get("target_handle")),
            target_title=cast(str | None, row.get("target_title")),
            existing_placement_key=cast(str | None, row.get("existing_placement_key")),
            existing_placement_label=cast(str | None, row.get("existing_placement_label")),
            existing_placement_size=cast(str | None, row.get("existing_placement_size")),
            slot=cast(str | None, row.get("slot")),
            slot_order=int(row.get("slot_order") or 0),
            scope_rule=dict(row.get("scope_rule") or {}),
            layout_json=dict(row.get("layout_json") or {}),
        )


def _configured_service_for_team(team_id_override: str | None = None) -> PlacementService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    has_supabase = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    team_id = team_id_override or settings.supabase_team_id or settings.brand_context_team_id
    if not has_supabase_signal:
        return PlacementService(team_id=team_id)
    if not has_supabase:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID", "BRAND_CONTEXT_TEAM_ID"))
    client = SupabaseClientFactory(settings).service_role_client()
    return PlacementService.from_supabase_client(client, team_id=team_id)


def configured_service() -> PlacementService:
    return _configured_service_for_team()


def configured_service_for_team(team_id: str) -> PlacementService:
    return _configured_service_for_team(team_id)
