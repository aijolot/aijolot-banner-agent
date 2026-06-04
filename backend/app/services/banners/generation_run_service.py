from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Protocol, cast
from uuid import uuid4

from app.core.settings import MissingSettingsError, Settings
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
from app.services.banners.async_run import run_coro as _run_coro
from app.services.supabase.client import SupabaseClientFactory
from app.workflows.banner_creation import FRONTEND_PROGRESS_STEPS, frontend_step_for_node, ordered_node_keys

if TYPE_CHECKING:
    from app.services.banners.run_orchestrator import RunOrchestrator


class CampaignNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class GenerationRunNotFound(Exception):
    def __init__(self, run_id: str) -> None:
        super().__init__(f"generation run '{run_id}' not found")
        self.run_id = run_id


class CampaignGenerationRunNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"generation run for campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class CampaignRepositoryProtocol(Protocol):
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...


class GenerationRunRepositoryProtocol(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...
    def get(self, *, run_id: str) -> dict[str, Any] | None: ...
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...
    def update(self, *, run_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...


class GenerationEventRepositoryProtocol(Protocol):
    def create_many(self, *, events: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    def list_by_run_id(self, *, run_id: str) -> list[dict[str, Any]]: ...


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

    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        rows = [row for row in self.rows.values() if str(row.get("campaign_id")) == campaign_id]
        if not rows:
            return None
        return dict(max(rows, key=lambda row: int(row.get("_sequence") or 0)))

    def update(self, *, run_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        row = self.rows.get(run_id)
        if row is None:
            return None
        row.update(data)
        return dict(row)


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
        orchestrator: "RunOrchestrator | None" = None,
        team_id: str | None = None,
    ) -> None:
        self.run_repository = run_repository or _LOCAL_RUN_REPOSITORY
        self.event_repository = event_repository or _LOCAL_EVENT_REPOSITORY
        self.campaign_repository = campaign_repository
        self.orchestrator = orchestrator
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str | None = None) -> "GenerationRunService":
        from app.db.repositories.audit_reports import AuditReportRepository
        from app.db.repositories.banner_layout_variants import BannerLayoutVariantRepository
        from app.db.repositories.banner_variants import BannerVariantRepository
        from app.db.repositories.campaign_revisions import CampaignRevisionRepository
        from app.services.banners.asset_service import BannerAssetService
        from app.services.banners.run_orchestrator import RunOrchestrator

        campaign_repository = CampaignRepository(client)
        try:
            asset_service: Any = BannerAssetService.from_supabase_client(client)
        except Exception:  # noqa: BLE001 — assets stay in-memory if storage unconfigured
            asset_service = None
        orchestrator = RunOrchestrator(
            revisions=CampaignRevisionRepository(client),
            variants=BannerVariantRepository(client),
            layout_variants=BannerLayoutVariantRepository(client),
            audit_reports=AuditReportRepository(client),
            campaigns=campaign_repository,
            asset_service=asset_service,
            team_id=team_id,
        )
        return cls(
            run_repository=GenerationRunRepository(client),
            event_repository=GenerationEventRepository(client),
            campaign_repository=campaign_repository,
            orchestrator=orchestrator,
            team_id=team_id,
        )

    def start_generation_run(self, campaign_id: str, request: GenerationRunCreate | None = None) -> GenerationRunResponse:
        request = request or GenerationRunCreate()
        campaign = self._get_campaign(campaign_id)
        if request.parent_run_id:
            self._verify_parent_run(campaign_id=campaign_id, parent_run_id=request.parent_run_id)
        # Real pipeline for initial runs when an orchestrator is wired (Supabase).
        # Refinement runs keep the deterministic shell here; RevisionService owns
        # their revision bookkeeping (rewired agentically in F9).
        if self.orchestrator is not None and campaign is not None and request.run_type != "refinement":
            return self._start_orchestrated_run(campaign_id, request, campaign)
        now = _utc_now_iso()
        trace_id = str(uuid4())
        metadata = {**request.metadata, "facade_version": "task-10-deterministic"}
        row = self.run_repository.create(
            data={
                "campaign_id": campaign_id,
                "parent_run_id": request.parent_run_id,
                "run_type": request.run_type,
                "status": "succeeded",
                "frontend_step": "review_publish",
                "adk_trace_id": trace_id,
                "started_by": request.started_by,
                "started_at": now,
                "finished_at": now,
                "metadata": metadata,
            }
        )
        run_id = str(row["id"])
        self.event_repository.create_many(events=self._deterministic_events(run_id=run_id))
        return self._run_response_from_record(row)

    def _start_orchestrated_run(
        self, campaign_id: str, request: GenerationRunCreate, campaign_row: dict[str, Any]
    ) -> GenerationRunResponse:
        assert self.orchestrator is not None
        now = _utc_now_iso()
        base_metadata = dict(request.metadata)
        run_row = self.run_repository.create(
            data={
                "campaign_id": campaign_id,
                "parent_run_id": request.parent_run_id,
                "run_type": request.run_type,
                "status": "running",
                "frontend_step": "intake_context",
                "adk_trace_id": str(uuid4()),
                "started_by": request.started_by,
                "started_at": now,
                "metadata": {**base_metadata, "facade_version": "f5-run-orchestrator"},
            }
        )
        run_id = str(run_row["id"])
        try:
            outcome = _run_coro(self.orchestrator.execute(run_id=run_id, campaign_row=campaign_row))
        except BaseException as exc:  # noqa: BLE001 — record honest failure on the run row
            outcome = _failed_outcome(f"{type(exc).__name__}: {exc}")
        if outcome.events:
            self.event_repository.create_many(events=outcome.events)
        updated = self.run_repository.update(
            run_id=run_id,
            data={
                "status": outcome.status,
                "frontend_step": outcome.frontend_step,
                "finished_at": _utc_now_iso(),
                "error_message": outcome.error_message,
                "metadata": {**base_metadata, **outcome.metadata},
            },
        ) or {**run_row, "status": outcome.status, "frontend_step": outcome.frontend_step}
        return self._run_response_from_record(updated)

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


def _failed_outcome(message: str) -> "Any":
    from app.services.banners.run_orchestrator import OrchestratorOutcome

    return OrchestratorOutcome(
        status="failed",
        frontend_step="intake_context",
        events=[],
        error_message=message[:500],
        metadata={"facade_version": "f5-run-orchestrator", "failed_node": "orchestrator"},
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
