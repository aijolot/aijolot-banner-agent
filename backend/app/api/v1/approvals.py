from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request

from app.core.auth import UserContext, require_user_context
from app.core.settings import Settings
from app.schemas.approvals import (
    ApprovalActionCreate,
    ApprovalRequestCreate,
    ApprovalStateResponse,
    ApprovalThreadResponse,
    ChangeRequestCreate,
    CommentCreate,
    CommentResolve,
    CommentResponse,
    RefinementRequestCreate,
    RefinementRequestResponse,
)
from app.services.approvals.approval_service import (
    ApprovalReviewerNotFound,
    ApprovalService,
    ApprovalServiceUnavailable,
    ApprovalThreadClosed,
    ApprovalThreadNotFound,
    CampaignNotFound,
    CampaignRevisionMismatch,
    CampaignRevisionNotFound,
    DuplicateReviewer,
    configured_service as configured_approval_service,
    configured_service_for_team as configured_approval_service_for_team,
)
from app.services.approvals.comment_service import (
    CommentNotFound,
    CommentService,
    CommentServiceUnavailable,
    configured_service as configured_comment_service,
    configured_service_for_team as configured_comment_service_for_team,
)

router = APIRouter(tags=["approvals"])

CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]
ThreadIdPath = Annotated[UUID, Path(description="Approval thread UUID")]
CommentIdPath = Annotated[UUID, Path(description="Comment UUID")]


def _approval_service() -> ApprovalService:
    return configured_approval_service()


def _comment_service() -> CommentService:
    return configured_comment_service()


_DEFAULT_APPROVAL_SERVICE_FACTORY = _approval_service
_DEFAULT_COMMENT_SERVICE_FACTORY = _comment_service


def _ensure_trusted_local_demo_context(context: UserContext) -> None:
    settings = Settings.from_env()
    if settings.app_env.lower() not in {"local", "test"}:
        raise ApprovalServiceUnavailable("approval demo endpoints require local/test APP_ENV")
    allowed_team_id = settings.supabase_team_id or "00000000-0000-0000-0000-000000000001"
    if context.team_id != allowed_team_id:
        raise CampaignNotFound("resource")


def _approval_context_and_service(request: Request) -> tuple[UserContext | None, ApprovalService]:
    if _approval_service is _DEFAULT_APPROVAL_SERVICE_FACTORY:
        context = require_user_context(request)
        _ensure_trusted_local_demo_context(context)
        return context, configured_approval_service_for_team(context.team_id)
    return None, _approval_service()


def _comment_context_and_service(request: Request) -> tuple[UserContext | None, CommentService]:
    if _comment_service is _DEFAULT_COMMENT_SERVICE_FACTORY:
        context = require_user_context(request)
        try:
            _ensure_trusted_local_demo_context(context)
        except ApprovalServiceUnavailable as exc:
            raise CommentServiceUnavailable(str(exc)) from None
        except CampaignNotFound as exc:
            raise ApprovalThreadNotFound(str(exc)) from None
        return context, configured_comment_service_for_team(context.team_id)
    return None, _comment_service()


def _approval_service_for_request(request: Request) -> ApprovalService:
    return _approval_context_and_service(request)[1]


def _comment_service_for_request(request: Request) -> CommentService:
    return _comment_context_and_service(request)[1]


@router.post("/campaigns/{campaign_id}/approval/request", response_model=ApprovalThreadResponse)
def request_approval(campaign_id: CampaignIdPath, request: ApprovalRequestCreate, http_request: Request) -> ApprovalThreadResponse:
    try:
        context, service = _approval_context_and_service(http_request)
        if context is not None:
            request = request.model_copy(update={"requested_by": context.user_id})
        return service.request_approval(str(campaign_id), request)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CampaignRevisionNotFound as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except CampaignRevisionMismatch as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except DuplicateReviewer as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ApprovalServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/campaigns/{campaign_id}/approval", response_model=ApprovalStateResponse)
def get_campaign_approval(campaign_id: CampaignIdPath, request: Request) -> ApprovalStateResponse:
    try:
        return _approval_service_for_request(request).get_campaign_approval(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ApprovalServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/approval-threads/{thread_id}/comments", response_model=CommentResponse)
def create_comment(thread_id: ThreadIdPath, request: CommentCreate, http_request: Request) -> CommentResponse:
    try:
        context, service = _comment_context_and_service(http_request)
        if context is not None:
            request = request.model_copy(update={"author_id": context.user_id})
        return service.create_comment(str(thread_id), request)
    except ApprovalThreadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CommentServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.patch("/comments/{comment_id}/resolve", response_model=CommentResponse)
def resolve_comment(comment_id: CommentIdPath, http_request: Request, request: CommentResolve | None = None) -> CommentResponse:
    try:
        context, service = _comment_context_and_service(http_request)
        payload = request or CommentResolve()
        if context is not None:
            payload = payload.model_copy(update={"resolved_by": context.user_id})
        return service.resolve_comment(str(comment_id), payload)
    except CommentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ApprovalThreadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CommentServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/approval-threads/{thread_id}/approve", response_model=ApprovalThreadResponse)
def approve_thread(thread_id: ThreadIdPath, request: ApprovalActionCreate, http_request: Request) -> ApprovalThreadResponse:
    try:
        context, service = _approval_context_and_service(http_request)
        if context is not None:
            request = request.model_copy(update={"user_id": context.user_id})
        return service.approve(str(thread_id), request)
    except ApprovalThreadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ApprovalReviewerNotFound as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ApprovalThreadClosed as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ApprovalServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/approval-threads/{thread_id}/request-changes", response_model=ApprovalThreadResponse)
def request_changes(thread_id: ThreadIdPath, request: ChangeRequestCreate, http_request: Request) -> ApprovalThreadResponse:
    try:
        context, service = _approval_context_and_service(http_request)
        if context is not None:
            request = request.model_copy(update={"user_id": context.user_id})
        return service.request_changes(str(thread_id), request)
    except ApprovalThreadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ApprovalReviewerNotFound as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ApprovalThreadClosed as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ApprovalServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/campaigns/{campaign_id}/refinement-requests", response_model=RefinementRequestResponse)
def create_refinement_request(campaign_id: CampaignIdPath, request: RefinementRequestCreate, http_request: Request) -> RefinementRequestResponse:
    try:
        context, service = _approval_context_and_service(http_request)
        if context is not None:
            request = request.model_copy(update={"requested_by": context.user_id})
        return service.create_refinement_request(str(campaign_id), request)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CampaignRevisionNotFound as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except CampaignRevisionMismatch as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ApprovalServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
