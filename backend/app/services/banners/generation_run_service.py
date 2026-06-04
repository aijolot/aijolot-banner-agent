from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, cast
from uuid import uuid4

from app.agents.pipeline_runner import AgenticArtifactBundle, AgenticGenerationAdapter
from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.audit_reports import AuditReportRepository
from app.db.repositories.banner_layout_variants import BannerLayoutVariantRepository
from app.db.repositories.banner_variants import BannerVariantRepository
from app.db.repositories.campaign_revisions import CampaignRevisionRepository
from app.db.repositories.campaigns import CampaignRepository
from app.db.repositories.generation_events import GenerationEventRepository
from app.db.repositories.generation_runs import GenerationRunRepository
from app.schemas.generation import (
    FrontendProgressStep,
    FrontendStep,
    GenerationEventResponse,
    GenerationRunCreate,
    GenerationRunResponse,
    GenerationRunStatus,
)
from app.services.banners.audit_report_service import deterministic_mvp_audit_report
from app.services.banners.html_renderer import render_deterministic_mvp_preview
from app.services.supabase.client import SupabaseClientFactory
from app.workflows.banner_creation import DETERMINISTIC_LAYOUT_VARIANT_KEYS, FRONTEND_PROGRESS_STEPS, frontend_step_for_node, ordered_node_keys


class CampaignNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class GenerationRunNotFound(Exception):
    def __init__(self, run_id: str) -> None:
        super().__init__(f"generation run '{run_id}' not found")
        self.run_id = run_id


class GenerationRunPersistenceError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CampaignGenerationRunNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"generation run for campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class CampaignRepositoryProtocol(Protocol):
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...
    def update(self, *, campaign_id: str, data: dict[str, Any], team_id: str | None = None) -> dict[str, Any] | None: ...


class GenerationRunRepositoryProtocol(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...
    def update(self, *, run_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...
    def get(self, *, run_id: str) -> dict[str, Any] | None: ...
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...


class GenerationEventRepositoryProtocol(Protocol):
    def create_many(self, *, events: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    def list_by_run_id(self, *, run_id: str) -> list[dict[str, Any]]: ...


class RevisionRepositoryProtocol(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...
    def get(self, *, revision_id: str) -> dict[str, Any] | None: ...
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...
    def update(self, *, revision_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...


class ChildArtifactRepositoryProtocol(Protocol):
    def create_many(self, *, variants: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class AuditReportRepositoryProtocol(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...


class AgenticGenerationAdapterProtocol(Protocol):
    async def generate(self, **kwargs: Any) -> AgenticArtifactBundle: ...


class InMemoryGenerationRunRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self._sequence = 0

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        self._sequence += 1
        now = _utc_now_iso(self._sequence)
        row = {
            "id": str(uuid4()),
            "created_at": now,
            "started_at": data.get("started_at") or now,
            "_sequence": self._sequence,
            **data,
        }
        self.rows[str(row["id"])] = row
        return dict(row)

    def get(self, *, run_id: str) -> dict[str, Any] | None:
        row = self.rows.get(run_id)
        return dict(row) if row else None

    def update(self, *, run_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        row = self.rows.get(run_id)
        if row is None:
            return None
        row.update(data)
        return dict(row)

    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        rows = [row for row in self.rows.values() if str(row.get("campaign_id")) == campaign_id]
        if not rows:
            return None
        return dict(max(rows, key=lambda row: int(row.get("_sequence") or 0)))


class InMemoryGenerationEventRepository:
    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {}

    def create_many(self, *, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        for index, event in enumerate(events):
            row = {
                "id": str(uuid4()),
                "created_at": _utc_now_iso(index),
                **event,
            }
            self.rows.setdefault(str(row["generation_run_id"]), []).append(row)
            created.append(dict(row))
        return created

    def list_by_run_id(self, *, run_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows.get(run_id, [])]


_LOCAL_RUN_REPOSITORY = InMemoryGenerationRunRepository()
_LOCAL_EVENT_REPOSITORY = InMemoryGenerationEventRepository()
_LOCAL_CONTEXT_REPOSITORIES: dict[str, tuple[InMemoryGenerationRunRepository, InMemoryGenerationEventRepository]] = {}


def _local_repositories_for_team(team_id: str) -> tuple[InMemoryGenerationRunRepository, InMemoryGenerationEventRepository]:
    if team_id not in _LOCAL_CONTEXT_REPOSITORIES:
        _LOCAL_CONTEXT_REPOSITORIES[team_id] = (InMemoryGenerationRunRepository(), InMemoryGenerationEventRepository())
    return _LOCAL_CONTEXT_REPOSITORIES[team_id]


class GenerationRunService:
    """Tracks generation run progress without executing external graph work."""

    def __init__(
        self,
        *,
        run_repository: GenerationRunRepositoryProtocol | None = None,
        event_repository: GenerationEventRepositoryProtocol | None = None,
        campaign_repository: CampaignRepositoryProtocol | None = None,
        revision_repository: RevisionRepositoryProtocol | None = None,
        layout_variant_repository: ChildArtifactRepositoryProtocol | None = None,
        variant_repository: ChildArtifactRepositoryProtocol | None = None,
        audit_report_repository: AuditReportRepositoryProtocol | None = None,
        generation_adapter: AgenticGenerationAdapterProtocol | None = None,
        team_id: str | None = None,
    ) -> None:
        self.run_repository = run_repository or _LOCAL_RUN_REPOSITORY
        self.event_repository = event_repository or _LOCAL_EVENT_REPOSITORY
        self.campaign_repository = campaign_repository
        self.revision_repository = revision_repository
        self.layout_variant_repository = layout_variant_repository
        self.variant_repository = variant_repository
        self.audit_report_repository = audit_report_repository
        self.generation_adapter = generation_adapter or AgenticGenerationAdapter(mode="deterministic_demo")
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str | None = None) -> "GenerationRunService":
        return cls(
            run_repository=GenerationRunRepository(client),
            event_repository=GenerationEventRepository(client),
            campaign_repository=CampaignRepository(client),
            revision_repository=CampaignRevisionRepository(client),
            layout_variant_repository=BannerLayoutVariantRepository(client),
            variant_repository=BannerVariantRepository(client),
            audit_report_repository=AuditReportRepository(client),
            team_id=team_id,
        )

    def start_generation_run(self, campaign_id: str, request: GenerationRunCreate | None = None) -> GenerationRunResponse:
        request = request or GenerationRunCreate()
        campaign = self._get_campaign(campaign_id)
        if request.parent_run_id:
            self._verify_parent_run(campaign_id=campaign_id, parent_run_id=request.parent_run_id)
        now = _utc_now_iso()
        trace_id = str(uuid4())
        metadata = {
            **request.metadata,
            "facade_version": "task-10-deterministic",
            "artifact_version": "phase-2-agentic-deterministic",
            "agent_mode": "deterministic_demo",
            "image_provider": "fake",
            "kg_provider": "static",
            "audit_provider": "deterministic_local",
            "layout_variants": list(DETERMINISTIC_LAYOUT_VARIANT_KEYS),
        }
        row = self.run_repository.create(
            data={
                "campaign_id": campaign_id,
                "parent_run_id": request.parent_run_id,
                "run_type": request.run_type,
                "status": "running",
                "frontend_step": "intake_context",
                "adk_trace_id": trace_id,
                "started_by": request.started_by,
                "started_at": now,
                "metadata": metadata,
            }
        )
        run_id = str(row["id"])
        try:
            artifact_bundle = _run_agentic_adapter(
                self.generation_adapter,
                campaign=campaign or {"id": campaign_id},
                campaign_id=campaign_id,
                run_id=run_id,
                trace_id=trace_id,
                team_id=self.team_id,
                started_by=request.started_by,
            )
            metadata = {**metadata, **artifact_bundle.provenance}
            self.event_repository.create_many(events=self._events_from_bundle(run_id=run_id, bundle=artifact_bundle))
            self._persist_mvp_artifacts(campaign_id=campaign_id, campaign=campaign or {"id": campaign_id}, run_id=run_id, bundle=artifact_bundle)
            succeeded = self.run_repository.update(
                run_id=run_id,
                data={
                    "status": "succeeded",
                    "frontend_step": "review_publish",
                    "finished_at": _utc_now_iso(),
                    "error_message": None,
                    "metadata": metadata,
                },
            )
            if succeeded is None:
                raise RuntimeError("generation run update failed")
            row = succeeded
        except Exception as exc:
            self._mark_run_failed(run_id=run_id, error_message=str(exc))
            raise GenerationRunPersistenceError(str(exc)) from exc
        return self._run_response_from_record(row)

    def get_latest_for_campaign(self, campaign_id: str) -> GenerationRunResponse:
        self._get_campaign(campaign_id)
        row = self.run_repository.get_latest_by_campaign_id(campaign_id=campaign_id)
        if row is None:
            raise CampaignGenerationRunNotFound(campaign_id)
        return self._run_response_from_record(row)

    def get_run(self, run_id: str) -> GenerationRunResponse:
        row = self.run_repository.get(run_id=run_id)
        if row is None:
            raise GenerationRunNotFound(run_id)
        self._get_campaign(str(row["campaign_id"]))
        return self._run_response_from_record(row)

    def list_events(self, run_id: str) -> list[GenerationEventResponse]:
        run = self.run_repository.get(run_id=run_id)
        if run is None:
            raise GenerationRunNotFound(run_id)
        self._get_campaign(str(run["campaign_id"]))
        rows = self.event_repository.list_by_run_id(run_id=run_id)
        return [self._event_response_from_record(row) for row in rows]

    def _get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        if self.campaign_repository is None:
            return None
        campaign = self.campaign_repository.get(campaign_id=campaign_id, team_id=self.team_id)
        if campaign is None:
            raise CampaignNotFound(campaign_id)
        return campaign

    def _verify_parent_run(self, *, campaign_id: str, parent_run_id: str) -> None:
        parent = self.run_repository.get(run_id=parent_run_id)
        if parent is None or str(parent.get("campaign_id")) != campaign_id:
            raise GenerationRunNotFound(parent_run_id)
        self._get_campaign(str(parent["campaign_id"]))

    def _deterministic_events(self, *, run_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        base_created_at = datetime.now(timezone.utc)
        for index, node_key in enumerate(ordered_node_keys()):
            step = frontend_step_for_node(node_key)
            started_created_at = _utc_iso(base_created_at + timedelta(microseconds=index * 2))
            succeeded_created_at = _utc_iso(base_created_at + timedelta(microseconds=(index * 2) + 1))
            events.append(
                {
                    "generation_run_id": run_id,
                    "node_key": node_key,
                    "frontend_step": step,
                    "status": "started",
                    "input_summary": {"summary": f"Deterministic Task 10 input for {node_key}"},
                    "output_summary": {},
                    "duration_ms": 0,
                    "cost_usd": 0.0,
                    "created_at": started_created_at,
                }
            )
            events.append(
                {
                    "generation_run_id": run_id,
                    "node_key": node_key,
                    "frontend_step": step,
                    "status": "succeeded",
                    "input_summary": {},
                    "output_summary": {"summary": f"Deterministic Task 10 output for {node_key}"},
                    "duration_ms": 1 + index,
                    "cost_usd": 0.0,
                    "created_at": succeeded_created_at,
                }
            )
        return events

    def _events_from_bundle(self, *, run_id: str, bundle: AgenticArtifactBundle) -> list[dict[str, Any]]:
        if not bundle.events:
            return self._deterministic_events(run_id=run_id)
        events: list[dict[str, Any]] = []
        base_created_at = datetime.now(timezone.utc)
        for index, event in enumerate(bundle.events):
            node_key = str(event["node_key"])
            events.append(
                {
                    "generation_run_id": run_id,
                    "node_key": node_key,
                    "frontend_step": event.get("frontend_step") or frontend_step_for_node(node_key),
                    "status": event.get("status") or "succeeded",
                    "input_summary": _dict_or_wrapped_value(event.get("input_summary")) or {},
                    "output_summary": _dict_or_wrapped_value(event.get("output_summary")) or {},
                    "duration_ms": int(event.get("duration_ms") or 0),
                    "cost_usd": float(event.get("cost_usd") or 0.0),
                    "created_at": event.get("created_at") or _utc_iso(base_created_at + timedelta(microseconds=index)),
                }
            )
        return events

    def _persist_mvp_artifacts(self, *, campaign_id: str, campaign: dict[str, Any], run_id: str, bundle: AgenticArtifactBundle | None = None) -> None:
        if not all(
            (
                self.campaign_repository,
                self.revision_repository,
                self.layout_variant_repository,
                self.variant_repository,
                self.audit_report_repository,
            )
        ):
            return
        assert self.campaign_repository is not None
        assert self.revision_repository is not None
        assert self.layout_variant_repository is not None
        assert self.variant_repository is not None
        assert self.audit_report_repository is not None

        latest = self.revision_repository.get_latest_by_campaign_id(campaign_id=campaign_id)
        revision_number = int((latest or {}).get("revision_number") or 0) + 1
        previous_selected_revision_id = campaign.get("selected_revision_id")
        revision = self.revision_repository.create(
            data={
                "campaign_id": campaign_id,
                "generation_run_id": run_id,
                "revision_number": revision_number,
                "status": "draft",
                "concept": _concept_from_bundle(bundle=bundle, campaign=campaign, revision_number=revision_number),
                "liquid_config": _liquid_config_from_bundle(
                    bundle=bundle,
                    campaign_id=campaign_id,
                    run_id=run_id,
                    revision_number=revision_number,
                ),
                "html_preview": bundle.html_preview if bundle else render_deterministic_mvp_preview(campaign=campaign, revision_number=revision_number),
                "preview_storage_path": None,
            }
        )
        revision_id = str(revision["id"])
        self.layout_variant_repository.create_many(variants=_default_layout_variants(revision_id))
        self.variant_repository.create_many(variants=_default_segment_variants(revision_id))
        self.audit_report_repository.create(
            data=_audit_report_from_bundle(bundle=bundle, campaign_id=campaign_id, revision_id=revision_id, generation_run_id=run_id)
        )
        selected_revision = self.revision_repository.update(revision_id=revision_id, data={"status": "selected"})
        if selected_revision is None:
            raise RuntimeError("revision status update failed")

        updated_campaign = self.campaign_repository.update(
            campaign_id=campaign_id,
            team_id=self.team_id,
            data={"selected_revision_id": revision_id, "status": "needs_review"},
        )
        if updated_campaign is None:
            self._rollback_new_revision_selection(revision_id=revision_id)
            raise RuntimeError("campaign update failed")

        if previous_selected_revision_id and str(previous_selected_revision_id) != revision_id:
            previous = self.revision_repository.get(revision_id=str(previous_selected_revision_id))
            if previous and previous.get("status") == "selected":
                superseded = self.revision_repository.update(
                    revision_id=str(previous_selected_revision_id),
                    data={"status": "superseded"},
                )
                if superseded is None:
                    raise RuntimeError("previous revision supersede failed")

    def _rollback_new_revision_selection(self, *, revision_id: str) -> None:
        if self.revision_repository is None:
            return
        try:
            self.revision_repository.update(revision_id=revision_id, data={"status": "draft"})
        except Exception:
            return

    def _mark_run_failed(self, *, run_id: str, error_message: str) -> None:
        try:
            self.run_repository.update(
                run_id=run_id,
                data={
                    "status": "failed",
                    "frontend_step": "render_audit",
                    "finished_at": _utc_now_iso(),
                    "error_message": error_message,
                },
            )
        except Exception:
            return

    @staticmethod
    def _run_response_from_record(row: dict[str, Any]) -> GenerationRunResponse:
        return GenerationRunResponse(
            id=str(row["id"]),
            campaign_id=str(row["campaign_id"]),
            parent_run_id=str(row["parent_run_id"]) if row.get("parent_run_id") is not None else None,
            run_type=cast(Any, row.get("run_type") or "initial"),
            status=cast(Any, row.get("status") or "queued"),
            frontend_step=cast(Any, row.get("frontend_step") or "intake_context"),
            adk_trace_id=cast(str | None, row.get("adk_trace_id")),
            started_by=cast(str | None, row.get("started_by")),
            started_at=_string_or_none(row.get("started_at")),
            finished_at=_string_or_none(row.get("finished_at")),
            error_message=cast(str | None, row.get("error_message")),
            metadata=dict(row.get("metadata") or {}),
            created_at=_string_or_none(row.get("created_at")),
            progress=_progress_for_run(cast(Any, row.get("status") or "queued"), cast(Any, row.get("frontend_step") or "intake_context")),
        )

    @staticmethod
    def _event_response_from_record(row: dict[str, Any]) -> GenerationEventResponse:
        return GenerationEventResponse(
            id=str(row["id"]),
            generation_run_id=str(row["generation_run_id"]),
            node_key=str(row["node_key"]),
            frontend_step=cast(Any, row["frontend_step"]),
            status=cast(Any, row["status"]),
            input_summary=_dict_or_wrapped_value(row.get("input_summary")),
            output_summary=_dict_or_wrapped_value(row.get("output_summary")),
            duration_ms=int(row["duration_ms"]) if row.get("duration_ms") is not None else None,
            cost_usd=float(row["cost_usd"]) if row.get("cost_usd") is not None else None,
            created_at=_string_or_none(row.get("created_at")),
        )


def _configured_service_for_team(team_id_override: str | None = None) -> GenerationRunService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    has_supabase = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    team_id = team_id_override or settings.supabase_team_id or settings.brand_context_team_id
    if not has_supabase_signal:
        if team_id_override:
            run_repository, event_repository = _local_repositories_for_team(team_id_override)
            return GenerationRunService(run_repository=run_repository, event_repository=event_repository, team_id=team_id_override)
        return GenerationRunService(team_id=team_id)
    if not has_supabase:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID", "BRAND_CONTEXT_TEAM_ID"))
    client = SupabaseClientFactory(settings).service_role_client()
    return GenerationRunService.from_supabase_client(client, team_id=team_id)


def configured_service() -> GenerationRunService:
    return _configured_service_for_team()


def configured_service_for_team(team_id: str) -> GenerationRunService:
    return _configured_service_for_team(team_id)


def _run_agentic_adapter(adapter: AgenticGenerationAdapterProtocol, **kwargs: Any) -> AgenticArtifactBundle:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(adapter.generate(**kwargs))
    raise RuntimeError("GenerationRunService.start_generation_run cannot synchronously run the agentic adapter inside an active event loop")


def _concept_from_bundle(*, bundle: AgenticArtifactBundle | None, campaign: dict[str, Any], revision_number: int) -> dict[str, Any]:
    if bundle is None:
        return _deterministic_concept(campaign=campaign, revision_number=revision_number)
    return {
        **dict(bundle.concept),
        "refined_image_prompt": bundle.refined_image_prompt,
        "revision_number": revision_number,
        "mode": bundle.agent_mode,
        "image_asset": bundle.image_asset,
        "optimized_asset": bundle.optimized_asset,
    }


def _liquid_config_from_bundle(*, bundle: AgenticArtifactBundle | None, campaign_id: str, run_id: str, revision_number: int) -> dict[str, Any]:
    base = _deterministic_liquid_config(campaign_id=campaign_id, run_id=run_id, revision_number=revision_number)
    if bundle is None:
        return base
    return {
        **base,
        **dict(bundle.liquid_payload),
        "provider_provenance": dict(bundle.provenance),
        "agent_mode": bundle.agent_mode,
        "image_provider": bundle.provenance.get("image_provider", "fake"),
        "kg_provider": bundle.provenance.get("kg_provider", "static"),
        "audit_provider": bundle.provenance.get("audit_provider", "deterministic_local"),
        "safe_to_publish": False,
    }


def _audit_report_from_bundle(*, bundle: AgenticArtifactBundle | None, campaign_id: str, revision_id: str, generation_run_id: str) -> dict[str, Any]:
    base = deterministic_mvp_audit_report(campaign_id=campaign_id, revision_id=revision_id, generation_run_id=generation_run_id)
    if bundle is None:
        return base
    audit = {**base, **dict(bundle.audit_result)}
    audit.update(
        {
            "campaign_id": campaign_id,
            "revision_id": revision_id,
            "generation_run_id": generation_run_id,
            "provider": bundle.provenance.get("audit_provider", "deterministic_local"),
            "provider_provenance": dict(bundle.provenance),
            "human_review_required": bool(audit.get("human_review_required", True)),
            "avif_skipped": bool(audit.get("avif_skipped", False)),
            "schema_report": {"valid": bool((audit.get("schema_report") or {}).get("valid", audit.get("schema_valid", True)))},
        }
    )
    audit["seo_report"] = {
        **dict(base.get("seo_report") or {}),
        **dict(audit.get("seo_report") or {}),
        "audit_runtime": {
            "status": audit.get("status", "warn"),
            "findings": list(audit.get("findings") or []),
            "schema_report": dict(audit.get("schema_report") or {}),
            "human_review_required": bool(audit.get("human_review_required", True)),
            "avif_skipped": bool(audit.get("avif_skipped", False)),
        },
    }
    return audit


def _progress_for_run(status: GenerationRunStatus, frontend_step: FrontendStep) -> list[FrontendProgressStep]:
    step_keys = [cast(FrontendStep, step["key"]) for step in FRONTEND_PROGRESS_STEPS]
    current_index = step_keys.index(frontend_step) if frontend_step in step_keys else 0
    progress: list[FrontendProgressStep] = []
    for index, step in enumerate(FRONTEND_PROGRESS_STEPS):
        if status == "succeeded" or index < current_index:
            step_status: GenerationRunStatus = "succeeded"
        elif status in ("failed", "escalated") and index == current_index:
            step_status = status
        elif status == "running" and index == current_index:
            step_status = "running"
        else:
            step_status = "queued"
        progress.append(
            FrontendProgressStep(
                key=cast(Any, step["key"]),
                label=str(step["label"]),
                node_keys=[str(node) for node in tuple(cast(Any, step["node_keys"]))],
                status=step_status,
            )
        )
    return progress


def _utc_now_iso(offset_microseconds: int = 0) -> str:
    now = datetime.now(timezone.utc)
    if offset_microseconds:
        now = now + timedelta(microseconds=offset_microseconds)
    return _utc_iso(now)


def _deterministic_concept(*, campaign: dict[str, Any], revision_number: int) -> dict[str, Any]:
    brief_value = campaign.get("structured_brief")
    brief = brief_value if isinstance(brief_value, dict) else {}
    return {
        "title": campaign.get("title") or "Nueva campaña",
        "promo_label": campaign.get("promo_label") or "Oferta especial",
        "audience": brief.get("audience") or "Clientes destacados",
        "cta": brief.get("cta") or "Comprar ahora",
        "tone": brief.get("tone") or "Premium",
        "revision_number": revision_number,
        "mode": "deterministic_mvp",
    }


def _deterministic_liquid_config(*, campaign_id: str, run_id: str, revision_number: int) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "generation_run_id": run_id,
        "revision_number": revision_number,
        "section_type": "aijolot-mvp-banner",
        "safe_to_publish": False,
    }


def _default_layout_variants(revision_id: str) -> list[dict[str, Any]]:
    return [
        {
            "revision_id": revision_id,
            "key": key,
            "name": f"Hero layout {key}",
            "description": f"Deterministic MVP layout {key}",
            "layout_type": "split" if key == "A" else ("centered" if key == "B" else "media_first"),
            "is_recommended": key == "A",
            "config": {"variant_key": key, "offline_deterministic": True},
        }
        for key in DETERMINISTIC_LAYOUT_VARIANT_KEYS
    ]


def _default_segment_variants(revision_id: str) -> list[dict[str, Any]]:
    return [
        {
            "revision_id": revision_id,
            "segment_key": "default",
            "segment_label": "Default audience",
            "audience_rule": {},
            "eyebrow": "Limited offer",
            "headline": "Fresh picks for you",
            "subheadline": "Deterministic MVP banner copy",
            "cta_text": "Shop now",
            "cta_url": "/collections/all",
            "palette": {},
        }
    ]


def _utc_iso(value: datetime) -> str:
    return value.isoformat()


def _string_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _dict_or_wrapped_value(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return {"value": value}
