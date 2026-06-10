"""Brand discovery run workflow (Task 4 of the brand discovery plan).

Synchronous first implementation: starting a run verifies the brand, resolves a
Shopify Admin client, inserts a ``brand_discovery_runs`` row (status
``running``), executes the evidence collector inline, then updates the row with
the final status + snapshot and mirrors the latest snapshot onto the brand row
(``brand_contexts.discovery_snapshot``).

Failure semantics:

- Unknown brand -> :class:`BrandNotFound` (routes map to 404).
- Unknown/foreign ``store_id`` -> :class:`StoreNotFound` (routes map to 404).
- No Shopify Admin credentials -> :class:`DiscoveryUnavailable` (503): discovery
  is never faked when Shopify cannot be reached.
- No Supabase runtime persistence -> :class:`DiscoveryPersistenceUnavailable`
  (503): discovery runs are never tracked in-memory/offline.
- An unexpected collector crash marks the run ``failed`` (with the error message
  recorded in the snapshot) instead of leaving an orphaned ``running`` row.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.brand_discovery_runs import BrandDiscoveryRunRepository
from app.db.repositories.stores import StoreRepository
from app.schemas.brand_discovery import (
    BrandDiscoverySnapshot,
    BrandDiscoveryStatus,
    BrandRecommendationDraft,
)
from app.services.brands.brand_recommendations import BrandRecommendationService
from app.services.brands.brand_service import (
    BrandNotFound,
    BrandService,
    DiscoveryPersistenceUnavailable,
)
from app.services.brands.shopify_discovery import ShopifyDiscoveryClient, collect_brand_evidence
from app.services.shopify.admin_factory import admin_client_or_none
from app.services.shopify.resource_service import StoreNotFound
from app.services.supabase.client import SupabaseClientFactory

__all__ = [
    "BrandDiscoveryRunPayload",
    "BrandDiscoveryService",
    "BrandNotFound",
    "DiscoveryPersistenceUnavailable",
    "DiscoveryRunCreateRequest",
    "DiscoveryRunMissingSnapshot",
    "DiscoveryUnavailable",
    "StoreNotFound",
    "configured_discovery_service",
]


class DiscoveryUnavailable(RuntimeError):
    """Raised when discovery cannot run because no Shopify Admin client is configured."""


class DiscoveryRunMissingSnapshot(RuntimeError):
    """Raised when a recommendation is requested for a run without usable snapshot evidence."""


class DiscoveryRunCreateRequest(BaseModel):
    """Body for ``POST /brands/{brand_id}/discovery-runs``."""

    store_id: str | None = Field(
        default=None,
        description="Optional store UUID to scope the run; validated against the request team's stores.",
    )

    @field_validator("store_id", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class BrandDiscoveryRunPayload(BaseModel):
    """One discovery run as returned by the discovery routes.

    ``snapshot`` carries the full :class:`BrandDiscoverySnapshot` shape (raw
    evidence with provenance). ``recommendation`` stays an empty dict until the
    Gemini recommendation step (``POST .../recommendations``) attaches a
    :class:`BrandRecommendationDraft` dump.
    """

    id: str
    brand_id: str
    store_id: str | None = None
    status: BrandDiscoveryStatus
    snapshot: BrandDiscoverySnapshot | None = None
    recommendation: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DiscoveryRunsRepositoryProtocol(Protocol):
    """Subset of :class:`BrandDiscoveryRunRepository` the service relies on."""

    def insert(
        self,
        *,
        team_id: str,
        brand_id: str,
        status: str = "pending",
        snapshot: dict[str, Any] | None = None,
        recommendation: dict[str, Any] | None = None,
        store_id: str | None = None,
    ) -> dict[str, Any]: ...

    def get(self, *, run_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...

    def update_status(
        self,
        *,
        run_id: str,
        status: str,
        team_id: str | None = None,
        snapshot: dict[str, Any] | None = None,
        recommendation: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None: ...


class StoreRepositoryProtocol(Protocol):
    def get(self, *, store_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...


class ColorRecommenderProtocol(Protocol):
    """Subset of :class:`BrandRecommendationService` the run workflow relies on."""

    async def recommend_colors(
        self, *, brand: Any, snapshot: BrandDiscoverySnapshot
    ) -> BrandRecommendationDraft: ...


ClientProvider = Callable[[], ShopifyDiscoveryClient | None]


class BrandDiscoveryService:
    """Run Shopify brand discovery and persist run history + latest snapshot."""

    def __init__(
        self,
        brand_service: BrandService,
        runs_repository: DiscoveryRunsRepositoryProtocol | None = None,
        client_provider: ClientProvider | None = None,
        *,
        store_repository: StoreRepositoryProtocol | None = None,
        team_id: str | None = None,
    ) -> None:
        self.brand_service = brand_service
        self.runs_repository = runs_repository
        self.client_provider = client_provider
        self.store_repository = store_repository
        self.team_id = team_id or getattr(brand_service, "team_id", None)

    # -- public API ----------------------------------------------------------

    def start_run(self, brand_id: str, *, store_id: str | None = None) -> dict[str, Any]:
        """Run discovery synchronously and return the completed run payload."""

        brand = self.brand_service.get_brand(brand_id)  # BrandNotFound propagates -> 404
        team_id = self._require_persistence()
        assert self.runs_repository is not None
        if store_id is not None and self.store_repository is not None:
            if self.store_repository.get(store_id=store_id, team_id=team_id) is None:
                raise StoreNotFound(store_id)
        client = self._client()
        shop_domain = str(getattr(client, "shop_domain", "") or "") or brand.shopify.store_domain

        row = self.runs_repository.insert(
            team_id=team_id, brand_id=brand_id, status="running", store_id=store_id
        )
        run_id = str(row.get("id") or "").strip()
        if not run_id:
            raise DiscoveryPersistenceUnavailable("discovery run row could not be created")

        try:
            snapshot = collect_brand_evidence(
                client, brand_id=brand_id, shop_domain=shop_domain, store_id=store_id
            )
        except Exception as exc:  # noqa: BLE001 - collector never raises by contract; defense in depth
            snapshot = self._crash_snapshot(
                brand_id=brand_id, store_id=store_id, shop_domain=shop_domain, exc=exc
            )

        snapshot_payload = snapshot.model_dump(mode="json")
        updated = self.runs_repository.update_status(
            run_id=run_id, team_id=team_id, status=snapshot.status, snapshot=snapshot_payload
        )
        # Latest evidence also lives on the brand row so the editor can show the
        # most recent discovery state without a run id.
        self.brand_service.save_discovery_snapshot(brand_id, snapshot)
        final_row = updated or {**row, "status": snapshot.status, "snapshot": snapshot_payload}
        return self._payload_from_row(final_row)

    def get_run(self, run_id: str, *, brand_id: str | None = None) -> dict[str, Any] | None:
        """Return a run payload scoped to the service team, or ``None``.

        ``brand_id`` (when given) must match the run's brand: runs reached
        through another brand's URL behave as not found.
        """

        team_id = self._require_persistence()
        assert self.runs_repository is not None
        row = self.runs_repository.get(run_id=run_id, team_id=team_id)
        if row is None:
            return None
        if brand_id is not None and str(row.get("brand_id")) != brand_id:
            return None
        return self._payload_from_row(row)

    async def recommend_colors_for_run(
        self,
        brand_id: str,
        run_id: str,
        *,
        recommender: ColorRecommenderProtocol | None = None,
    ) -> dict[str, Any] | None:
        """Generate + persist a Gemini-backed color recommendation draft for one run.

        Returns the updated run payload, or ``None`` when the run is not visible
        for this team/brand (routes map to 404). Raises
        :class:`DiscoveryRunMissingSnapshot` when the run carries no usable
        snapshot evidence (routes map to 409) and lets
        ``BrandRecommendationUnavailable`` propagate (routes map to 503) -- the
        draft is never faked without Gemini.
        """

        run = self.get_run(run_id, brand_id=brand_id)
        if run is None:
            return None
        snapshot_payload = run.get("snapshot")
        if not isinstance(snapshot_payload, dict) or not snapshot_payload:
            raise DiscoveryRunMissingSnapshot(f"discovery run '{run_id}' has no snapshot")
        brand = self.brand_service.get_brand(brand_id)  # BrandNotFound propagates -> 404
        try:
            snapshot = BrandDiscoverySnapshot.model_validate(snapshot_payload)
        except ValidationError as exc:
            raise DiscoveryRunMissingSnapshot(
                f"discovery run '{run_id}' snapshot is not usable"
            ) from exc
        service = recommender if recommender is not None else BrandRecommendationService()
        draft = await service.recommend_colors(brand=brand, snapshot=snapshot)
        return self.attach_recommendation(run_id, draft, brand_id=brand_id)

    def attach_recommendation(
        self,
        run_id: str,
        recommendation: BrandRecommendationDraft | dict[str, Any],
        *,
        brand_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Persist a recommendation draft onto an existing run row (status unchanged)."""

        team_id = self._require_persistence()
        assert self.runs_repository is not None
        row = self.runs_repository.get(run_id=run_id, team_id=team_id)
        if row is None:
            return None
        if brand_id is not None and str(row.get("brand_id")) != brand_id:
            return None
        payload = (
            recommendation.model_dump(mode="json")
            if isinstance(recommendation, BrandRecommendationDraft)
            else dict(recommendation)
        )
        updated = self.runs_repository.update_status(
            run_id=run_id, team_id=team_id, status=str(row.get("status")), recommendation=payload
        )
        if updated is None:
            return None
        return self._payload_from_row(updated)

    # -- internals -------------------------------------------------------------

    def _require_persistence(self) -> str:
        if self.runs_repository is None or not self.team_id:
            raise DiscoveryPersistenceUnavailable(
                "brand discovery requires Supabase runtime storage (SUPABASE_URL, "
                "SUPABASE_SERVICE_ROLE_KEY, BRAND_CONTEXT_TEAM_ID); discovery runs are never faked offline"
            )
        return self.team_id

    def _client(self) -> ShopifyDiscoveryClient:
        client: ShopifyDiscoveryClient | None = None
        if self.client_provider is not None:
            try:
                client = self.client_provider()
            except (MissingSettingsError, ValueError):
                client = None
        if client is None:
            raise DiscoveryUnavailable(
                "brand discovery requires Shopify Admin credentials "
                "(SHOPIFY_SHOP_DOMAIN, SHOPIFY_ADMIN_ACCESS_TOKEN)"
            )
        return client

    @staticmethod
    def _crash_snapshot(
        *, brand_id: str, store_id: str | None, shop_domain: str, exc: Exception
    ) -> BrandDiscoverySnapshot:
        return BrandDiscoverySnapshot(
            id=f"disc_{uuid4().hex[:12]}",
            brand_id=brand_id,
            store_id=store_id,
            shop_domain=shop_domain,
            status="failed",
            discovered_at=datetime.now(timezone.utc),
            source_summary="discovery crashed before evidence collection completed",
            errors=[f"discovery: unexpected error ({exc.__class__.__name__}: {exc})"],
        )

    @staticmethod
    def _payload_from_row(row: dict[str, Any]) -> dict[str, Any]:
        snapshot = row.get("snapshot")
        recommendation = row.get("recommendation")
        payload = BrandDiscoveryRunPayload(
            id=str(row.get("id")),
            brand_id=str(row.get("brand_id")),
            store_id=row.get("store_id"),
            status=row.get("status"),
            snapshot=snapshot if isinstance(snapshot, dict) and snapshot else None,
            recommendation=recommendation if isinstance(recommendation, dict) else {},
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
        return payload.model_dump(mode="json")


def configured_discovery_service(*, team_id: str | None = None) -> BrandDiscoveryService:
    """Build a discovery service from the environment.

    With ``team_id`` (canonical /api/v1 path) the brand service is scoped to the
    request team; without it (root prototype routes) the configured/default demo
    service is used. Repositories stay ``None`` without Supabase so the service
    raises :class:`DiscoveryPersistenceUnavailable` instead of faking runs.
    """

    from app.services import brand_store

    settings = Settings.from_env()
    brand_service = brand_store.service_for_team(team_id) if team_id else brand_store._default_service()
    runs_repository: BrandDiscoveryRunRepository | None = None
    store_repository: StoreRepository | None = None
    try:
        supabase = SupabaseClientFactory(settings).service_role_client()
        runs_repository = BrandDiscoveryRunRepository(supabase)
        store_repository = StoreRepository(supabase)
    except MissingSettingsError:
        pass
    return BrandDiscoveryService(
        brand_service,
        runs_repository,
        lambda: admin_client_or_none(settings),
        store_repository=store_repository,
        team_id=team_id,
    )
