from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.core.settings import Settings
from app.db.repositories.campaign_placements import CampaignPlacementRepository
from app.db.repositories.campaign_revisions import CampaignRevisionRepository
from app.db.repositories.campaigns import CampaignRepository
from app.db.repositories.publish_jobs import PublishJobRepository
from app.db.repositories.schedules import ScheduleRepository
from app.db.repositories.stores import StoreRepository
from app.schemas.schedules import PublishJobResponse
from app.services.shopify import metafields, theme_files
from app.services.supabase.client import SupabaseClientFactory


class PublishError(Exception):
    pass


class PublisherUnavailable(PublishError):
    pass


class CampaignNotFound(PublishError):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign {campaign_id} not found")


class CampaignNotScheduled(PublishError):
    def __init__(self, campaign_id: str, status: str | None) -> None:
        super().__init__(f"campaign {campaign_id} must be scheduled before publishing (current status: {status})")


class CampaignRevisionNotFound(PublishError):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign {campaign_id} has no selected schedule revision")


class StoreNotFound(PublishError):
    def __init__(self, store_id: str) -> None:
        super().__init__(f"store {store_id} not found")


class PublishUnsupported(PublishError):
    pass


class ShopifyPublisher:
    def __init__(
        self,
        *,
        client: Any,
        campaigns: Any,
        revisions: Any,
        stores: Any,
        schedules: Any,
        placements: Any,
        publish_jobs: Any,
        team_id: str | None = None,
        dry_run: bool = False,
    ) -> None:
        self.client = client
        self.campaigns = campaigns
        self.revisions = revisions
        self.stores = stores
        self.schedules = schedules
        self.placements = placements
        self.publish_jobs = publish_jobs
        self.team_id = team_id
        self.dry_run = dry_run

    def install_theme_files(self, store_id: str) -> PublishJobResponse:
        """Install controlled theme files without creating invalid FK publish_jobs rows."""
        store = self._store(store_id)
        theme_id = str(store.get("theme_id") or "")
        if not theme_id:
            raise PublishUnsupported("store has no theme_id configured")
        suffix = ":dry" if self.dry_run else ":v1"
        idempotency_key = f"install-theme-files:{store_id}:{theme_id}{suffix}"
        if self.dry_run:
            response = {"dry_run": True, "would_install": theme_files.installed_asset_keys()}
            row = self._standalone_theme_job(store_id=store_id, theme_id=theme_id, status="succeeded", response_payload=response, idempotency_key=idempotency_key)
            return PublishJobResponse.model_validate(row)
        try:
            response = {"assets": theme_files.install_theme_files(self.client, theme_id=theme_id)}
            row = self._standalone_theme_job(store_id=store_id, theme_id=theme_id, status="succeeded", response_payload=response, idempotency_key=idempotency_key)
            return PublishJobResponse.model_validate(row)
        except Exception as exc:
            row = self._standalone_theme_job(store_id=store_id, theme_id=theme_id, status="failed", error_message=str(exc), idempotency_key=idempotency_key)
            return PublishJobResponse.model_validate(row)

    def publish_campaign(self, campaign_id: str) -> PublishJobResponse:
        campaign = self._campaign(campaign_id)
        if campaign.get("status") not in {"scheduled", "published"}:
            raise CampaignNotScheduled(campaign_id, campaign.get("status"))
        schedule = self._active_schedule(campaign_id, campaign.get("status"))
        revision = self._revision_for_schedule(campaign, schedule)
        store = self._store(str(campaign["store_id"]))
        placement = self.placements.get_by_campaign_id(campaign_id=campaign_id) if self.placements else None
        if placement and placement.get("target_type") == "search":
            raise PublishUnsupported("search result placement publishing is not supported in the Shopify Liquid MVP")
        config = self._campaign_config(campaign=campaign, revision=revision, placement=placement, schedule=schedule)
        request_payload = {"campaign_id": campaign_id, "revision_id": revision["id"], "store_id": store["id"], "config": config, "dry_run": self.dry_run}
        job = self._create_job(
            campaign_id=campaign_id,
            revision_id=str(revision["id"]),
            schedule_id=str(schedule["id"]),
            action="publish",
            request_payload=request_payload,
            idempotency_key="publish:" + _hash(request_payload),
        )
        if job.get("status") == "succeeded":
            return PublishJobResponse.model_validate(job)
        if self.dry_run:
            response = {
                "dry_run": True,
                "would_install": theme_files.installed_asset_keys() if store.get("theme_id") else [],
                "would_write_metafield": {
                    "namespace": str(store.get("banner_metafield_namespace") or "aijolot"),
                    "key": str(store.get("banner_metafield_key") or "banner_campaigns"),
                    "campaign_id": config["campaign_id"],
                    "anchor": (config.get("placement") or {}).get("anchor"),
                },
            }
            row = self.publish_jobs.update(job_id=job["id"], data={"status": "succeeded", "response_payload": response, "finished_at": _now()}) or {**job, "status": "succeeded", "response_payload": response}
            return PublishJobResponse.model_validate(row)
        try:
            if store.get("theme_id"):
                theme_files.install_theme_files(self.client, theme_id=str(store["theme_id"]))
            # Re-host any locally-served banner image on Shopify Files so a live
            # storefront can actually load it (a localhost/private Supabase URL would
            # 404 for visitors). Best-effort: keeps the original URL on failure.
            config = self._rehost_assets(config)
            response = metafields.publish_campaign_config(
                self.client,
                namespace=str(store.get("banner_metafield_namespace") or "aijolot"),
                key=str(store.get("banner_metafield_key") or "banner_campaigns"),
                config=config,
            )
            self.campaigns.update(campaign_id=campaign_id, data={"status": "published"}, team_id=self.team_id)
            row = self.publish_jobs.update(job_id=job["id"], data={"status": "succeeded", "response_payload": response, "finished_at": _now()}) or {**job, "status": "succeeded", "response_payload": response}
            return PublishJobResponse.model_validate(row)
        except Exception as exc:
            self.publish_jobs.update(job_id=job["id"], data={"status": "failed", "error_message": str(exc), "finished_at": _now()})
            self.campaigns.update(campaign_id=campaign_id, data={"status": "failed"}, team_id=self.team_id)
            raise

    def unpublish_campaign(self, campaign_id: str) -> PublishJobResponse:
        campaign = self._campaign(campaign_id)
        schedule = self.schedules.get_active_by_campaign_id(campaign_id=campaign_id) if self.schedules else None
        revision = self._revision_for_schedule(campaign, schedule) if schedule and schedule.get("status") in {"pending", "active"} else None
        store = self._store(str(campaign["store_id"])) if revision else None
        request_payload = {"campaign_id": campaign_id, "revision_id": revision["id"], "store_id": store["id"], "dry_run": self.dry_run} if revision and store else None
        existing_job = self._existing_job("unpublish:" + _hash(request_payload)) if request_payload else None
        if existing_job and existing_job.get("status") == "succeeded":
            return PublishJobResponse.model_validate(existing_job)
        if campaign.get("status") not in {"scheduled", "published"}:
            raise CampaignNotScheduled(campaign_id, campaign.get("status"))
        if not schedule or schedule.get("status") not in {"pending", "active"} or not revision or not store or not request_payload:
            raise CampaignNotScheduled(campaign_id, campaign.get("status"))
        job = self._create_job(
            campaign_id=campaign_id,
            revision_id=str(revision["id"]),
            schedule_id=str(schedule["id"]),
            action="unpublish",
            request_payload=request_payload,
            idempotency_key="unpublish:" + _hash(request_payload),
        )
        if job.get("status") == "succeeded":
            return PublishJobResponse.model_validate(job)
        if self.dry_run:
            response = {
                "dry_run": True,
                "would_clear_metafield": {
                    "namespace": str(store.get("banner_metafield_namespace") or "aijolot"),
                    "key": str(store.get("banner_metafield_key") or "banner_campaigns"),
                    "campaign_id": campaign_id,
                },
            }
            row = self.publish_jobs.update(job_id=job["id"], data={"status": "succeeded", "response_payload": response, "finished_at": _now()}) or {**job, "status": "succeeded", "response_payload": response}
            return PublishJobResponse.model_validate(row)
        try:
            response = metafields.clear_campaign_config(
                self.client,
                namespace=str(store.get("banner_metafield_namespace") or "aijolot"),
                key=str(store.get("banner_metafield_key") or "banner_campaigns"),
                campaign_id=campaign_id,
            )
            self.campaigns.update(campaign_id=campaign_id, data={"status": "approved"}, team_id=self.team_id)
            row = self.publish_jobs.update(job_id=job["id"], data={"status": "succeeded", "response_payload": response, "finished_at": _now()}) or {**job, "status": "succeeded", "response_payload": response}
            return PublishJobResponse.model_validate(row)
        except Exception as exc:
            self.publish_jobs.update(job_id=job["id"], data={"status": "failed", "error_message": str(exc), "finished_at": _now()})
            raise

    def _campaign_config(self, *, campaign: dict[str, Any], revision: dict[str, Any], placement: dict[str, Any] | None, schedule: dict[str, Any]) -> dict[str, Any]:
        from app.services.shopify.theme_files import ANCHOR_BY_PLACEMENT_KEY

        base = dict(revision.get("liquid_config") or {})
        placement_config = dict(placement or {})
        # Resolve the theme anchor key so the placement-aware snippets filter this
        # campaign to the right spot. Controlled enum string (safe in Liquid).
        if placement_config and not placement_config.get("anchor"):
            key = placement_config.get("placement_type_key")
            anchor = ANCHOR_BY_PLACEMENT_KEY.get(str(key)) if key else None
            if anchor:
                placement_config["anchor"] = anchor
        base.update(
            {
                "campaign_id": str(campaign["id"]),
                "revision_id": str(revision["id"]),
                "title": campaign.get("title"),
                "placement": placement_config,
                "active_from": schedule.get("starts_at"),
                "active_until": schedule.get("ends_at"),
            }
        )
        return base

    def _rehost_assets(self, config: dict[str, Any]) -> dict[str, Any]:
        """Swap locally-hosted banner image URLs for Shopify Files CDN URLs.

        Best-effort and isolated: any error returns the config unchanged so the
        publish still proceeds. Only touches truly-local URLs — a hosted Supabase
        URL is already storefront-reachable and is left as-is.
        """
        try:
            from app.services.shopify import shopify_files

            return shopify_files.rehost_config_assets(
                self.client, config, fetch_bytes=self._fetch_asset_bytes
            )
        except Exception:  # noqa: BLE001 — never fail a publish over asset hosting
            return config

    @staticmethod
    def _fetch_asset_bytes(url: str) -> bytes | None:
        import httpx

        try:
            with httpx.Client(timeout=20.0) as http:
                response = http.get(url)
            if response.status_code >= 400:
                return None
            return response.content or None
        except Exception:  # noqa: BLE001 — best-effort fetch
            return None

    def _campaign(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.campaigns.get(campaign_id=campaign_id, team_id=self.team_id)
        if not campaign:
            raise CampaignNotFound(campaign_id)
        return campaign

    def _active_schedule(self, campaign_id: str, status: str | None) -> dict[str, Any]:
        schedule = self.schedules.get_active_by_campaign_id(campaign_id=campaign_id) if self.schedules else None
        if not schedule or schedule.get("status") not in {"pending", "active"}:
            raise CampaignNotScheduled(campaign_id, status)
        return schedule

    def _revision_for_schedule(self, campaign: dict[str, Any], schedule: dict[str, Any]) -> dict[str, Any]:
        revision_id = schedule.get("revision_id") or campaign.get("selected_revision_id")
        revision = self.revisions.get(revision_id=revision_id) if revision_id else None
        if not revision or str(revision.get("campaign_id")) != str(campaign["id"]):
            raise CampaignRevisionNotFound(str(campaign["id"]))
        return revision

    def _store(self, store_id: str) -> dict[str, Any]:
        store = self.stores.get(store_id=store_id, team_id=self.team_id)
        if not store:
            raise StoreNotFound(store_id)
        return store

    def _create_job(self, **data: Any) -> dict[str, Any]:
        payload = {"status": "running", "started_at": _now(), "request_payload": {}, "response_payload": {}, **data}
        if hasattr(self.publish_jobs, "create_or_get"):
            return self.publish_jobs.create_or_get(data=payload)
        return self.publish_jobs.create(data=payload)

    def _existing_job(self, idempotency_key: str) -> dict[str, Any] | None:
        if hasattr(self.publish_jobs, "get_by_idempotency_key"):
            return self.publish_jobs.get_by_idempotency_key(idempotency_key=idempotency_key)
        return None

    @staticmethod
    def _standalone_theme_job(*, store_id: str, theme_id: str, status: str, idempotency_key: str, response_payload: dict[str, Any] | None = None, error_message: str | None = None) -> dict[str, Any]:
        return {
            "id": idempotency_key,
            "campaign_id": "00000000-0000-0000-0000-000000000000",
            "revision_id": "00000000-0000-0000-0000-000000000000",
            "action": "install_theme_files",
            "status": status,
            "request_payload": {"store_id": store_id, "theme_id": theme_id},
            "response_payload": response_payload or {},
            "error_message": error_message,
            "idempotency_key": idempotency_key,
            "finished_at": _now(),
        }


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]


def configured_publisher(*, team_id: str | None = None) -> ShopifyPublisher:
    """Build a request-scoped publisher. Fails closed (503-style) without creds.

    The Shopify client is constructed only via admin_factory; the token is never
    logged or placed into any job payload/response. ``SHOPIFY_PUBLISH_DRY_RUN``
    (default true) makes publish/unpublish record the job without mutating the
    store.
    """

    from app.core.settings import MissingSettingsError
    from app.services.shopify.admin_factory import configured_admin_client

    settings = Settings.from_env()
    if not (settings.supabase_url and settings.supabase_service_role_key):
        raise PublisherUnavailable("publishing endpoints require Supabase configuration")
    try:
        client = configured_admin_client(settings)
    except (MissingSettingsError, ValueError) as exc:
        raise PublisherUnavailable(
            "publishing requires Shopify Admin credentials (SHOPIFY_SHOP_DOMAIN, SHOPIFY_ADMIN_ACCESS_TOKEN)"
        ) from exc
    supabase = SupabaseClientFactory(settings).service_role_client()
    return ShopifyPublisher(
        client=client,
        campaigns=CampaignRepository(supabase),
        revisions=CampaignRevisionRepository(supabase),
        stores=StoreRepository(supabase),
        schedules=ScheduleRepository(supabase),
        placements=CampaignPlacementRepository(supabase),
        publish_jobs=PublishJobRepository(supabase),
        team_id=team_id or settings.supabase_team_id,
        dry_run=settings.shopify_publish_dry_run,
    )


__all__ = [
    "ShopifyPublisher",
    "PublisherUnavailable",
    "CampaignNotFound",
    "CampaignNotScheduled",
    "CampaignRevisionNotFound",
    "StoreNotFound",
    "PublishUnsupported",
    "configured_publisher",
]
