from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Protocol, cast
from uuid import uuid4

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.banner_layout_variants import BannerLayoutVariantRepository
from app.db.repositories.banner_variants import BannerVariantRepository
from app.db.repositories.campaign_revisions import CampaignRevisionRepository
from app.db.repositories.campaigns import CampaignRepository
from app.db.repositories.generation_runs import GenerationRunRepository
from app.db.repositories.refinement_requests import RefinementRequestRepository
from app.schemas.generation import (
    CampaignRevisionResponse,
    GenerationRunResponse,
    RegenerateRequest,
    RegenerateResponse,
    VariantSelectionResponse,
)
from app.services.banners.generation_run_service import GenerationRunService
from app.services.supabase.client import SupabaseClientFactory


class RevisionServiceError(Exception):
    pass


class CampaignNotFound(RevisionServiceError):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class RevisionNotFound(RevisionServiceError):
    def __init__(self, revision_id: str) -> None:
        super().__init__(f"revision '{revision_id}' not found")
        self.revision_id = revision_id


class VariantNotFound(RevisionServiceError):
    def __init__(self, variant_id: str) -> None:
        super().__init__(f"variant '{variant_id}' not found")
        self.variant_id = variant_id


class RefinementRequestNotFound(RevisionServiceError):
    def __init__(self, refinement_request_id: str) -> None:
        super().__init__(f"refinement request '{refinement_request_id}' not found")
        self.refinement_request_id = refinement_request_id


class CampaignRepositoryProtocol(Protocol):
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...
    def update(self, *, campaign_id: str, data: dict[str, Any], team_id: str | None = None) -> dict[str, Any] | None: ...


class RevisionRepositoryProtocol(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...
    def get(self, *, revision_id: str) -> dict[str, Any] | None: ...
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...
    def list_by_campaign_id(self, *, campaign_id: str) -> list[dict[str, Any]]: ...
    def update(self, *, revision_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...


class VariantRepositoryProtocol(Protocol):
    def create_many(self, *, variants: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    def get(self, *, variant_id: str) -> dict[str, Any] | None: ...
    def list_by_revision_id(self, *, revision_id: str) -> list[dict[str, Any]]: ...


class LayoutVariantRepositoryProtocol(Protocol):
    def create_many(self, *, variants: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    def list_by_revision_id(self, *, revision_id: str) -> list[dict[str, Any]]: ...


class RefinementRequestRepositoryProtocol(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...
    def get(self, *, refinement_request_id: str) -> dict[str, Any] | None: ...
    def update(self, *, refinement_request_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...


class RevisionService:
    def __init__(
        self,
        *,
        campaigns: CampaignRepositoryProtocol,
        revisions: RevisionRepositoryProtocol,
        variants: VariantRepositoryProtocol,
        layout_variants: LayoutVariantRepositoryProtocol,
        refinement_requests: RefinementRequestRepositoryProtocol,
        generation_runs: GenerationRunService,
        team_id: str | None = None,
    ) -> None:
        self.campaigns = campaigns
        self.revisions = revisions
        self.variants = variants
        self.layout_variants = layout_variants
        self.refinement_requests = refinement_requests
        self.generation_runs = generation_runs
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str | None = None) -> "RevisionService":
        return cls(
            campaigns=CampaignRepository(client),
            revisions=CampaignRevisionRepository(client),
            variants=BannerVariantRepository(client),
            layout_variants=BannerLayoutVariantRepository(client),
            refinement_requests=RefinementRequestRepository(client),
            generation_runs=GenerationRunService.from_supabase_client(client, team_id=team_id),
            team_id=team_id,
        )

    def list_revisions(self, campaign_id: str) -> list[CampaignRevisionResponse]:
        self._get_campaign(campaign_id)
        return [self._revision_response(row) for row in self.revisions.list_by_campaign_id(campaign_id=campaign_id)]

    def select_variant(self, campaign_id: str, variant_id: str) -> VariantSelectionResponse:
        campaign = self._get_campaign(campaign_id)
        variant = self.variants.get(variant_id=variant_id)
        if variant is None:
            raise VariantNotFound(variant_id)
        revision = self.revisions.get(revision_id=str(variant["revision_id"]))
        if revision is None or str(revision.get("campaign_id")) != campaign_id:
            raise VariantNotFound(variant_id)

        previous_revision_id = campaign.get("selected_revision_id")
        if previous_revision_id and str(previous_revision_id) != str(revision["id"]):
            previous = self.revisions.get(revision_id=str(previous_revision_id))
            if previous and previous.get("status") == "selected":
                self.revisions.update(revision_id=str(previous_revision_id), data={"status": "superseded"})

        updated_revision = self.revisions.update(revision_id=str(revision["id"]), data={"status": "selected"}) or revision
        updated_campaign = self.campaigns.update(
            campaign_id=campaign_id,
            team_id=self.team_id,
            data={"selected_revision_id": str(revision["id"]), "status": "draft"},
        ) or {**campaign, "selected_revision_id": str(revision["id"]), "status": "draft"}
        return VariantSelectionResponse(
            campaign_id=campaign_id,
            selected_revision_id=str(updated_revision["id"]),
            selected_variant_id=variant_id,
            campaign_status=str(updated_campaign.get("status") or "draft"),
            revision=self._revision_response(updated_revision),
        )

    def regenerate(self, campaign_id: str, request: RegenerateRequest) -> RegenerateResponse:
        campaign = self._get_campaign(campaign_id)
        refinement = None
        if request.refinement_request_id:
            refinement = self.refinement_requests.get(refinement_request_id=request.refinement_request_id)
            if refinement is None or str(refinement.get("campaign_id")) != campaign_id:
                raise RefinementRequestNotFound(request.refinement_request_id)

        prompt = _normalize_prompt(request.prompt or (refinement or {}).get("prompt") or "Refine banner")
        source_revision_id = request.source_revision_id or (refinement or {}).get("source_revision_id") or campaign.get("selected_revision_id")
        source_revision = self._source_revision(campaign_id=campaign_id, source_revision_id=source_revision_id)

        # F9 — agentic refine: when an orchestrator is wired, re-run the relevant
        # pipeline nodes to produce a genuinely new revision with real artifacts.
        # Otherwise (tests / in-memory) keep the deterministic copy bookkeeping.
        if getattr(self.generation_runs, "orchestrator", None) is not None:
            return self._agentic_regenerate(
                campaign_id=campaign_id, request=request, prompt=prompt, source_revision=source_revision, refinement=refinement
            )

        parent_run_id = source_revision.get("generation_run_id")
        run = self.generation_runs.start_generation_run(
            campaign_id,
            request=_run_request(parent_run_id=parent_run_id, started_by=request.requested_by, prompt=prompt),
        )
        revision = self._create_revised_revision(campaign_id=campaign_id, source_revision=source_revision, run=run, prompt=prompt)
        previous_revision_id = campaign.get("selected_revision_id")
        if previous_revision_id and str(previous_revision_id) != str(revision["id"]):
            previous = self.revisions.get(revision_id=str(previous_revision_id))
            if previous and previous.get("status") == "selected":
                self.revisions.update(revision_id=str(previous_revision_id), data={"status": "superseded"})
        self.campaigns.update(
            campaign_id=campaign_id,
            team_id=self.team_id,
            data={"selected_revision_id": str(revision["id"]), "status": "draft"},
        )
        if refinement is not None:
            self.refinement_requests.update(
                refinement_request_id=str(refinement["id"]),
                data={
                    "status": "succeeded",
                    "result_revision_id": str(revision["id"]),
                    "result_summary": f"Created revision {revision['revision_number']} from requested changes.",
                    "finished_at": _utc_now_iso(),
                },
            )
        return RegenerateResponse(
            generation_run=run,
            revision=self._revision_response(revision),
            refinement_request_id=str(refinement["id"]) if refinement else None,
        )

    def edit(self, campaign_id: str, request: RegenerateRequest) -> RegenerateResponse:
        """Banner-edit: scoped, non-destructive edit of an assembled revision (F-edit)."""
        campaign = self._get_campaign(campaign_id)
        refinement = None
        if request.refinement_request_id:
            refinement = self.refinement_requests.get(refinement_request_id=request.refinement_request_id)
            if refinement is None or str(refinement.get("campaign_id")) != campaign_id:
                raise RefinementRequestNotFound(request.refinement_request_id)
        prompt = _normalize_prompt(request.prompt or (refinement or {}).get("prompt") or "Edit banner")
        source_revision_id = request.source_revision_id or (refinement or {}).get("source_revision_id") or campaign.get("selected_revision_id")
        source_revision = self._source_revision(campaign_id=campaign_id, source_revision_id=source_revision_id)
        if getattr(self.generation_runs, "orchestrator", None) is None:
            # No orchestrator (in-memory/tests) → fall back to the deterministic copy path.
            return self.regenerate(campaign_id, request)

        from app.workflows.banner_creation import _load_runtime_skill

        normalize_targets = _load_runtime_skill("refinement-route").normalize_targets
        targets = normalize_targets(request.target_nodes, prompt)
        run, revision_id = self.generation_runs.start_banner_edit_run(
            campaign_id, source_revision=source_revision, prompt=prompt, targets=targets,
            started_by=request.requested_by, parent_run_id=source_revision.get("generation_run_id"),
        )
        revision = self.revisions.get(revision_id=str(revision_id)) if revision_id else None
        if revision is None:
            revision = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id) or source_revision
        if refinement is not None:
            self.refinement_requests.update(
                refinement_request_id=str(refinement["id"]),
                data={
                    "status": "succeeded" if run.status == "succeeded" else "failed",
                    "result_revision_id": str(revision["id"]) if revision else None,
                    "result_summary": f"Banner edit ({', '.join(targets)}) → revision {revision.get('revision_number') if revision else '?'}.",
                    "finished_at": _utc_now_iso(),
                },
            )
        return RegenerateResponse(
            generation_run=run,
            revision=self._revision_response(revision),
            refinement_request_id=str(refinement["id"]) if refinement else None,
        )

    def _agentic_regenerate(
        self,
        *,
        campaign_id: str,
        request: RegenerateRequest,
        prompt: str,
        source_revision: dict[str, Any],
        refinement: dict[str, Any] | None,
    ) -> RegenerateResponse:
        from app.workflows.banner_creation import _load_runtime_skill

        normalize_targets = _load_runtime_skill("refinement-route").normalize_targets
        targets = normalize_targets(request.target_nodes, prompt)
        run, revision_id = self.generation_runs.start_refinement_run(
            campaign_id,
            prompt=prompt,
            targets=targets,
            started_by=request.requested_by,
            parent_run_id=source_revision.get("generation_run_id"),
        )
        # The orchestrator already created/promoted the new revision + pointed the
        # campaign at it. Read it back for the response.
        revision = None
        if revision_id:
            revision = self.revisions.get(revision_id=str(revision_id))
        if revision is None:
            revision = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id) or source_revision
        if refinement is not None:
            self.refinement_requests.update(
                refinement_request_id=str(refinement["id"]),
                data={
                    "status": "succeeded" if run.status == "succeeded" else "failed",
                    "result_revision_id": str(revision["id"]) if revision else None,
                    "result_summary": f"Agentic refine ({', '.join(targets)}) → revision {revision.get('revision_number') if revision else '?'}.",
                    "finished_at": _utc_now_iso(),
                },
            )
        return RegenerateResponse(
            generation_run=run,
            revision=self._revision_response(revision),
            refinement_request_id=str(refinement["id"]) if refinement else None,
        )

    def _create_revised_revision(
        self, *, campaign_id: str, source_revision: dict[str, Any], run: GenerationRunResponse, prompt: str
    ) -> dict[str, Any]:
        latest = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id) or source_revision
        revision_number = int(latest.get("revision_number") or 0) + 1
        concept = dict(source_revision.get("concept") or {})
        concept["revision_note"] = prompt
        concept["revision_source_id"] = str(source_revision["id"])
        liquid_config = dict(source_revision.get("liquid_config") or {})
        liquid_config["revision_note"] = prompt
        html_preview = _append_revision_marker(source_revision.get("html_preview"), revision_number, prompt)
        revision = self.revisions.create(
            data={
                "campaign_id": campaign_id,
                "generation_run_id": run.id,
                "revision_number": revision_number,
                "status": "selected",
                "concept": concept,
                "liquid_config": liquid_config,
                "html_preview": html_preview,
                "preview_storage_path": None,
            }
        )
        if source_revision.get("status") == "selected":
            self.revisions.update(revision_id=str(source_revision["id"]), data={"status": "superseded"})
        self._copy_layout_variants(str(source_revision["id"]), str(revision["id"]), prompt)
        self._copy_banner_variants(str(source_revision["id"]), str(revision["id"]), prompt)
        return revision

    def _copy_layout_variants(self, source_revision_id: str, new_revision_id: str, prompt: str) -> None:
        rows = self.layout_variants.list_by_revision_id(revision_id=source_revision_id)
        if not rows:
            rows = _default_layout_variants(source_revision_id)
        copies = []
        for row in rows:
            config = dict(row.get("config") or {})
            config["revision_note"] = prompt
            copies.append({**_without_identity(row), "revision_id": new_revision_id, "config": config})
        self.layout_variants.create_many(variants=copies)

    def _copy_banner_variants(self, source_revision_id: str, new_revision_id: str, prompt: str) -> None:
        rows = self.variants.list_by_revision_id(revision_id=source_revision_id)
        if not rows:
            rows = _default_banner_variants(source_revision_id)
        copies = []
        for row in rows:
            headline = str(row.get("headline") or row.get("segment_label") or "Banner")
            copies.append({**_without_identity(row), "revision_id": new_revision_id, "headline": f"{headline} — revised"})
        self.variants.create_many(variants=copies)

    def _source_revision(self, *, campaign_id: str, source_revision_id: Any) -> dict[str, Any]:
        if source_revision_id:
            revision = self.revisions.get(revision_id=str(source_revision_id))
            if revision is None or str(revision.get("campaign_id")) != campaign_id:
                raise RevisionNotFound(str(source_revision_id))
            return revision
        latest = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id)
        if latest is None:
            raise RevisionNotFound("latest")
        return latest

    def _get_campaign(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.campaigns.get(campaign_id=campaign_id, team_id=self.team_id)
        if campaign is None:
            raise CampaignNotFound(campaign_id)
        return campaign

    def _revision_response(self, row: dict[str, Any]) -> CampaignRevisionResponse:
        revision_id = str(row["id"])
        return CampaignRevisionResponse(
            id=revision_id,
            campaign_id=str(row["campaign_id"]),
            generation_run_id=str(row["generation_run_id"]) if row.get("generation_run_id") else None,
            revision_number=int(row.get("revision_number") or 0),
            status=str(row.get("status") or "draft"),
            concept=dict(row.get("concept") or {}),
            liquid_config=dict(row.get("liquid_config") or {}),
            html_preview=cast(str | None, row.get("html_preview")),
            preview_storage_path=cast(str | None, row.get("preview_storage_path")),
            created_at=str(row["created_at"]) if row.get("created_at") is not None else None,
            layout_variants=[cast(Any, item) for item in self.layout_variants.list_by_revision_id(revision_id=revision_id)],
            variants=[cast(Any, item) for item in self.variants.list_by_revision_id(revision_id=revision_id)],
        )


def _configured_service_for_team(team_id_override: str | None = None) -> RevisionService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    has_supabase = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    team_id = team_id_override or settings.supabase_team_id or settings.brand_context_team_id
    if not has_supabase_signal:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_TEAM_ID"))
    if not has_supabase:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID", "BRAND_CONTEXT_TEAM_ID"))
    client = SupabaseClientFactory(settings).service_role_client()
    return RevisionService.from_supabase_client(client, team_id=team_id)


def configured_service() -> RevisionService:
    return _configured_service_for_team()


def configured_service_for_team(team_id: str) -> RevisionService:
    return _configured_service_for_team(team_id)


def _run_request(*, parent_run_id: Any, started_by: str | None, prompt: str) -> Any:
    from app.schemas.generation import GenerationRunCreate

    return GenerationRunCreate(
        run_type="refinement",
        parent_run_id=str(parent_run_id) if parent_run_id else None,
        started_by=started_by,
        metadata={"facade_version": "task-16-deterministic-revision", "prompt": prompt},
    )


def _without_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in {"id", "created_at"}}


def _normalize_prompt(value: Any) -> str:
    prompt = " ".join(str(value or "Refine banner").split())
    return (prompt or "Refine banner")[:8000]


def _append_revision_marker(html_value: Any, revision_number: int, prompt: str) -> str:
    base = str(html_value or "<section class='aijolot-banner'></section>")
    safe_prompt = html.escape(_normalize_prompt(prompt), quote=True).replace("--", "&#45;&#45;")
    return f"{base}\n<!-- revision {revision_number}: {safe_prompt} -->"


def _default_layout_variants(revision_id: str) -> list[dict[str, Any]]:
    from app.workflows.banner_creation import DETERMINISTIC_LAYOUT_VARIANT_KEYS

    return [
        {
            "revision_id": revision_id,
            "key": key,
            "name": f"Hero layout {key}",
            "description": f"Deterministic MVP layout {key}",
            "layout_type": "split" if key == "A" else ("centered" if key == "B" else "media_first"),
            "is_recommended": key == "A",
            "config": {"variant_key": key},
        }
        for key in DETERMINISTIC_LAYOUT_VARIANT_KEYS
    ]


def _default_banner_variants(revision_id: str) -> list[dict[str, Any]]:
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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
