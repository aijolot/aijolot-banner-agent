"""Campaign generation run and revision endpoints.

MVP auth alignment: default service-role backed routes fail closed unless a
request-scoped user/team context is present. Tests may monkeypatch the service
factory with fakes; those remain prototype-compatible and do not require auth.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request

from app.core.auth import UserContext, require_user_context
from app.core.settings import MissingSettingsError
from app.schemas.generation import (
    ApplyEditsRequest,
    CampaignPlanResponse,
    CampaignRevisionResponse,
    GenerationEventResponse,
    GenerationRunCreate,
    GenerationRunResponse,
    RegenerateRequest,
    RegenerateResponse,
    VariantSelectionResponse,
)
from app.services.banners.generation_run_service import (
    CampaignGenerationRunNotFound,
    CampaignNotFound,
    GenerationRunNotFound,
    GenerationRunService,
    configured_service,
    configured_service_for_team,
)
from app.services.banners.revision_service import (
    CampaignNotFound as RevisionCampaignNotFound,
    RefinementRequestNotFound,
    RevisionNotFound,
    RevisionService,
    VariantNotFound,
    configured_service as configured_revision_service,
    configured_service_for_team as configured_revision_service_for_team,
)

router = APIRouter(tags=["generation"])

CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]
RunIdPath = Annotated[UUID, Path(description="Generation run UUID")]


def _default_service() -> GenerationRunService:
    return configured_service()


def _revision_service() -> RevisionService:
    return configured_revision_service()


_DEFAULT_GENERATION_FACTORY = _default_service
_DEFAULT_REVISION_FACTORY = _revision_service


def _context_for_default_factory(request: Request, factory: object) -> UserContext | None:
    if factory in (_DEFAULT_GENERATION_FACTORY, _DEFAULT_REVISION_FACTORY):
        return require_user_context(request)
    return None


def _generation_service_for_context(context: UserContext | None) -> GenerationRunService:
    return configured_service_for_team(context.team_id) if context is not None and _default_service is _DEFAULT_GENERATION_FACTORY else _default_service()


def _revision_service_for_context(context: UserContext | None) -> RevisionService:
    return configured_revision_service_for_team(context.team_id) if context is not None and _revision_service is _DEFAULT_REVISION_FACTORY else _revision_service()


@router.post("/campaigns/{campaign_id}/generation-runs", response_model=GenerationRunResponse)
def start_generation_run(
    campaign_id: CampaignIdPath,
    request_scope: Request,
    request: GenerationRunCreate | None = None,
) -> GenerationRunResponse:
    try:
        context = _context_for_default_factory(request_scope, _default_service)
        return _generation_service_for_context(context).start_generation_run(str(campaign_id), request or GenerationRunCreate())
    except CampaignNotFound:
        raise HTTPException(status_code=404, detail="resource not found")
    except GenerationRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/campaigns/{campaign_id}/generation-runs/latest", response_model=GenerationRunResponse)
def get_latest_generation_run(campaign_id: CampaignIdPath, request: Request) -> GenerationRunResponse:
    try:
        context = _context_for_default_factory(request, _default_service)
        return _generation_service_for_context(context).get_latest_for_campaign(str(campaign_id))
    except CampaignNotFound:
        raise HTTPException(status_code=404, detail="resource not found")
    except CampaignGenerationRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/generation-runs/{run_id}", response_model=GenerationRunResponse)
def get_generation_run(run_id: RunIdPath, request: Request) -> GenerationRunResponse:
    try:
        context = _context_for_default_factory(request, _default_service)
        return _generation_service_for_context(context).get_run(str(run_id))
    except CampaignNotFound:
        raise HTTPException(status_code=404, detail="resource not found")
    except GenerationRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/generation-runs/{run_id}/events", response_model=list[GenerationEventResponse])
def list_generation_events(run_id: RunIdPath, request: Request) -> list[GenerationEventResponse]:
    try:
        context = _context_for_default_factory(request, _default_service)
        return _generation_service_for_context(context).list_events(str(run_id))
    except CampaignNotFound:
        raise HTTPException(status_code=404, detail="resource not found")
    except GenerationRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/campaigns/{campaign_id}/variants/{variant_id}/select",
    response_model=VariantSelectionResponse,
)
def select_variant(campaign_id: CampaignIdPath, variant_id: UUID, request: Request) -> VariantSelectionResponse:
    try:
        context = _context_for_default_factory(request, _revision_service)
        return _revision_service_for_context(context).select_variant(str(campaign_id), str(variant_id))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RevisionCampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except VariantNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/campaigns/{campaign_id}/regenerate", response_model=RegenerateResponse)
def regenerate_campaign(
    campaign_id: CampaignIdPath,
    request_scope: Request,
    request: RegenerateRequest | None = None,
) -> RegenerateResponse:
    try:
        context = _context_for_default_factory(request_scope, _revision_service)
        return _revision_service_for_context(context).regenerate(str(campaign_id), request or RegenerateRequest())
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RevisionCampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (RevisionNotFound, RefinementRequestNotFound) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/campaigns/{campaign_id}/banner-edit", response_model=RegenerateResponse)
def banner_edit_campaign(
    campaign_id: CampaignIdPath,
    request_scope: Request,
    request: RegenerateRequest | None = None,
) -> RegenerateResponse:
    try:
        context = _context_for_default_factory(request_scope, _revision_service)
        return _revision_service_for_context(context).edit(str(campaign_id), request or RegenerateRequest())
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RevisionCampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (RevisionNotFound, RefinementRequestNotFound) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/campaigns/{campaign_id}/plan-runs", response_model=GenerationRunResponse)
def start_campaign_plan_run(
    campaign_id: CampaignIdPath,
    request_scope: Request,
    request: RegenerateRequest | None = None,
) -> GenerationRunResponse:
    """Start the cheap PLAN phase (concept + wireframe, no image) for review."""
    try:
        context = _context_for_default_factory(request_scope, _revision_service)
        return _revision_service_for_context(context).start_plan_run(str(campaign_id), request or RegenerateRequest())
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RevisionCampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/campaigns/{campaign_id}/plan", response_model=CampaignPlanResponse)
def get_campaign_plan(campaign_id: CampaignIdPath, request: Request) -> CampaignPlanResponse:
    try:
        context = _context_for_default_factory(request, _revision_service)
        return _revision_service_for_context(context).get_plan(str(campaign_id))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RevisionCampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RevisionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/campaigns/{campaign_id}/plan/iterate", response_model=GenerationRunResponse)
def iterate_campaign_plan(
    campaign_id: CampaignIdPath,
    request_scope: Request,
    request: RegenerateRequest | None = None,
) -> GenerationRunResponse:
    try:
        context = _context_for_default_factory(request_scope, _revision_service)
        return _revision_service_for_context(context).iterate_plan(str(campaign_id), request or RegenerateRequest())
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RevisionCampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RevisionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/campaigns/{campaign_id}/plan/approve", response_model=RegenerateResponse)
def approve_campaign_plan(
    campaign_id: CampaignIdPath,
    request_scope: Request,
    request: RegenerateRequest | None = None,
) -> RegenerateResponse:
    """Approve the latest plan and run the costly BUILD phase (image + render + audit)."""
    try:
        context = _context_for_default_factory(request_scope, _revision_service)
        return _revision_service_for_context(context).approve_plan(str(campaign_id), request or RegenerateRequest())
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RevisionCampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RevisionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/campaigns/{campaign_id}/apply-edits", response_model=RegenerateResponse)
def apply_campaign_edits(
    campaign_id: CampaignIdPath,
    request_scope: Request,
    request: ApplyEditsRequest,
) -> RegenerateResponse:
    """Direct, instant edit (move/resize/color/font/copy) — creates a new revision
    WITHOUT running the agent."""
    try:
        context = _context_for_default_factory(request_scope, _revision_service)
        return _revision_service_for_context(context).apply_edits(str(campaign_id), request)
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RevisionCampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RevisionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/campaigns/{campaign_id}/revisions", response_model=list[CampaignRevisionResponse])
def list_campaign_revisions(campaign_id: CampaignIdPath, request: Request) -> list[CampaignRevisionResponse]:
    try:
        context = _context_for_default_factory(request, _revision_service)
        return _revision_service_for_context(context).list_revisions(str(campaign_id))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RevisionCampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
