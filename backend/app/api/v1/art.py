"""Campaign descriptive art/model prompt + art-generation endpoints (F8)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request

from app.core.auth import require_user_context
from app.core.settings import MissingSettingsError
from app.schemas.art_concepts import ArtConceptsRequest, ArtConceptsResponse
from app.schemas.art_prompts import (
    ArtPromptsRequest,
    ArtPromptsResponse,
    GenerateArtRequest,
    GenerateArtResponse,
    ModelPromptsRequest,
)
from app.services.banners.art_concept_service import (
    ArtConceptService,
    CampaignNotFound as ArtConceptCampaignNotFound,
    configured_service as configured_art_concept_service,
    configured_service_for_team as configured_art_concept_service_for_team,
)
from app.services.banners.art_service import (
    ArtService,
    CampaignNotFound,
    RevisionNotFound,
    configured_service,
    configured_service_for_team,
)

router = APIRouter(tags=["art"])

CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]


def _default_service() -> ArtService:
    return configured_service()


_DEFAULT_SERVICE_FACTORY = _default_service


def _service_for_request(request: Request) -> ArtService:
    context = require_user_context(request)
    if _default_service is _DEFAULT_SERVICE_FACTORY:
        return configured_service_for_team(context.team_id)
    return _default_service()


def _art_concept_service() -> ArtConceptService:
    return configured_art_concept_service()


_DEFAULT_ART_CONCEPT_FACTORY = _art_concept_service


def _art_concept_for_request(request: Request) -> ArtConceptService:
    context = require_user_context(request)
    if _art_concept_service is _DEFAULT_ART_CONCEPT_FACTORY:
        return configured_art_concept_service_for_team(context.team_id)
    return _art_concept_service()


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, (CampaignNotFound, RevisionNotFound)):
        raise HTTPException(status_code=404, detail=str(exc)) from None
    if isinstance(exc, MissingSettingsError):
        raise HTTPException(status_code=503, detail=str(exc)) from None
    raise exc


@router.post("/campaigns/{campaign_id}/art-prompts", response_model=ArtPromptsResponse)
def propose_art_prompts(
    campaign_id: CampaignIdPath,
    http_request: Request,
    request: ArtPromptsRequest | None = None,
) -> ArtPromptsResponse:
    try:
        return _service_for_request(http_request).propose_art_prompts(str(campaign_id), request or ArtPromptsRequest())
    except (CampaignNotFound, RevisionNotFound, MissingSettingsError) as exc:
        _raise_http(exc)
        raise


@router.post("/campaigns/{campaign_id}/model-prompts", response_model=ArtPromptsResponse)
def propose_model_prompts(
    campaign_id: CampaignIdPath,
    http_request: Request,
    request: ModelPromptsRequest | None = None,
) -> ArtPromptsResponse:
    try:
        return _service_for_request(http_request).propose_model_prompts(str(campaign_id), request or ModelPromptsRequest())
    except (CampaignNotFound, RevisionNotFound, MissingSettingsError) as exc:
        _raise_http(exc)
        raise


@router.post("/campaigns/{campaign_id}/art-concepts", response_model=ArtConceptsResponse)
def propose_art_concepts(
    campaign_id: CampaignIdPath,
    http_request: Request,
    request: ArtConceptsRequest | None = None,
) -> ArtConceptsResponse:
    try:
        return _art_concept_for_request(http_request).propose_concepts(str(campaign_id), request or ArtConceptsRequest())
    except ArtConceptCampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.post("/campaigns/{campaign_id}/generate-art", response_model=GenerateArtResponse)
def generate_art(
    campaign_id: CampaignIdPath,
    http_request: Request,
    request: GenerateArtRequest | None = None,
) -> GenerateArtResponse:
    try:
        return _service_for_request(http_request).generate_art(str(campaign_id), request or GenerateArtRequest())
    except (CampaignNotFound, RevisionNotFound, MissingSettingsError) as exc:
        _raise_http(exc)
        raise
