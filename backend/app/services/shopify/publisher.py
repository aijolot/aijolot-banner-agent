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

SUPPORTED_LIQUID_PLACEMENTS = {"home", "collection", "product", "page", "store"}


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
        publish_mode: str = "live",
    ) -> None:
        self.client = client
        self.campaigns = campaigns
        self.revisions = revisions
        self.stores = stores
        self.schedules = schedules
        self.placements = placements
        self.publish_jobs = publish_jobs
        self.team_id = team_id
        self.publish_mode = publish_mode

    def install_theme_files(self, store_id: str) -> PublishJobResponse:
        """Install controlled theme files without creating invalid FK publish_jobs rows."""
        store = self._store(store_id)
        theme_id = str(store.get("theme_id") or "")
        if not theme_id:
            raise PublishUnsupported("store has no theme_id configured")
        idempotency_key = f"install-theme-files:{store_id}:{theme_id}:v1"
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
        self._validate_publish_payload(revision=revision, placement=placement)
        config = self._campaign_config(campaign=campaign, revision=revision, placement=placement, schedule=schedule)
        request_payload = {"campaign_id": campaign_id, "revision_id": revision["id"], "store_id": store["id"], "config": config, "publish_mode": self.publish_mode}
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
        if self.publish_mode == "dry_run_demo":
            return self._complete_dry_run_publish(job=job, campaign=campaign, revision=revision, schedule=schedule, store=store, placement=placement, config=config)
        if self.publish_mode != "live":
            raise PublisherUnavailable("publishing is disabled; set AIJOLOT_PUBLISH_MODE=dry_run_demo for the safe demo path")
        try:
            if store.get("theme_id"):
                theme_files.install_theme_files(self.client, theme_id=str(store["theme_id"]))
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

    def _complete_dry_run_publish(
        self,
        *,
        job: dict[str, Any],
        campaign: dict[str, Any],
        revision: dict[str, Any],
        schedule: dict[str, Any],
        store: dict[str, Any],
        placement: dict[str, Any] | None,
        config: dict[str, Any],
    ) -> PublishJobResponse:
        namespace = str(store.get("banner_metafield_namespace") or "aijolot")
        key = str(store.get("banner_metafield_key") or "banner_campaigns")
        shop_domain = str(store.get("shop_domain") or "demo-shopify-store.invalid")
        response = {
            "mode": "dry_run_demo",
            "dry_run": True,
            "live_shopify_mutation": False,
            "theme_files": [
                {"key": theme_files.SECTION_KEY, "operation": "upsert", "theme_id": str(store.get("theme_id") or "demo-theme")},
                {"key": theme_files.SNIPPET_KEY, "operation": "upsert", "theme_id": str(store.get("theme_id") or "demo-theme")},
            ],
            "metafield": {
                "owner": "shop",
                "namespace": namespace,
                "key": key,
                "type": "json",
                "config": [config],
            },
            "published_url": f"https://{shop_domain}/?aijolot_campaign={campaign['id']}&dry_run=1",
            "target": {
                "store_id": str(store["id"]),
                "shop_domain": shop_domain,
                "placement": dict(placement or {}),
                "schedule_id": str(schedule["id"]),
                "revision_id": str(revision["id"]),
            },
        }
        # Dry-run publish never marks the campaign live; the publish job response carries the demo result.
        row = self.publish_jobs.update(job_id=job["id"], data={"status": "succeeded", "response_payload": response, "finished_at": _now()}) or {**job, "status": "succeeded", "response_payload": response}
        return PublishJobResponse.model_validate(row)

    def unpublish_campaign(self, campaign_id: str) -> PublishJobResponse:
        if self.publish_mode == "dry_run_demo":
            raise PublisherUnavailable("dry-run demo publishing does not perform Shopify unpublish mutations")
        campaign = self._campaign(campaign_id)
        schedule = self.schedules.get_active_by_campaign_id(campaign_id=campaign_id) if self.schedules else None
        revision = self._revision_for_schedule(campaign, schedule) if schedule and schedule.get("status") in {"pending", "active"} else None
        store = self._store(str(campaign["store_id"])) if revision else None
        request_payload = {"campaign_id": campaign_id, "revision_id": revision["id"], "store_id": store["id"]} if revision and store else None
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
        base = dict(revision.get("liquid_config") or {})
        base.update(
            {
                "campaign_id": str(campaign["id"]),
                "revision_id": str(revision["id"]),
                "title": campaign.get("title"),
                "placement": dict(placement or {}),
                "active_from": schedule.get("starts_at"),
                "active_until": schedule.get("ends_at"),
            }
        )
        return base

    def _validate_publish_payload(self, *, revision: dict[str, Any], placement: dict[str, Any] | None) -> None:
        liquid_config = revision.get("liquid_config")
        if not isinstance(liquid_config, dict) or not liquid_config:
            raise PublishUnsupported("selected revision has no generated Liquid/metafield payload")
        target_type = placement.get("target_type") if placement else "home"
        if target_type == "search":
            raise PublishUnsupported("search result placement publishing is not supported in the Shopify Liquid MVP")
        if target_type not in SUPPORTED_LIQUID_PLACEMENTS:
            raise PublishUnsupported(f"placement target '{target_type}' is not supported by the Shopify Liquid MVP")

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
        selected_revision_id = campaign.get("selected_revision_id")
        schedule_revision_id = schedule.get("revision_id")
        if not selected_revision_id or str(schedule_revision_id) != str(selected_revision_id):
            raise CampaignRevisionNotFound(str(campaign["id"]))
        revision = self.revisions.get(revision_id=str(selected_revision_id))
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
    settings = Settings.from_env()
    if settings.aijolot_publish_mode != "dry_run_demo":
        raise PublisherUnavailable("publishing is disabled; set AIJOLOT_PUBLISH_MODE=dry_run_demo to enable safe demo dry-run publishing")
    if not team_id:
        raise PublisherUnavailable("dry-run demo publishing requires request team context")
    if not (settings.supabase_url and settings.supabase_service_role_key):
        raise PublisherUnavailable("dry-run demo publishing requires Supabase persistence configuration")
    client = SupabaseClientFactory(settings).service_role_client()
    return ShopifyPublisher(
        client=None,
        campaigns=CampaignRepository(client),
        revisions=CampaignRevisionRepository(client),
        stores=StoreRepository(client),
        schedules=ScheduleRepository(client),
        placements=CampaignPlacementRepository(client),
        publish_jobs=PublishJobRepository(client),
        team_id=team_id,
        publish_mode="dry_run_demo",
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
