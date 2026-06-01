from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path

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
)
from app.services.approvals.comment_service import (
    CommentNotFound,
    CommentService,
    CommentServiceUnavailable,
    configured_service as configured_comment_service,
)

router = APIRouter(tags=["approvals"])

CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]
ThreadIdPath = Annotated[UUID, Path(description="Approval thread UUID")]
CommentIdPath = Annotated[UUID, Path(description="Comment UUID")]


def _approval_service() -> ApprovalService:
    return configured_approval_service()


def _comment_service() -> CommentService:
    return configured_comment_service()


@router.post("/campaigns/{campaign_id}/approval/request", response_model=ApprovalThreadResponse)
def request_approval(campaign_id: CampaignIdPath, request: ApprovalRequestCreate) -> ApprovalThreadResponse:
    try:
        return _approval_service().request_approval(str(campaign_id), request)
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
def get_campaign_approval(campaign_id: CampaignIdPath) -> ApprovalStateResponse:
    try:
        return _approval_service().get_campaign_approval(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ApprovalServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/approval-threads/{thread_id}/comments", response_model=CommentResponse)
def create_comment(thread_id: ThreadIdPath, request: CommentCreate) -> CommentResponse:
    try:
        return _comment_service().create_comment(str(thread_id), request)
    except ApprovalThreadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CommentServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.patch("/comments/{comment_id}/resolve", response_model=CommentResponse)
def resolve_comment(comment_id: CommentIdPath, request: CommentResolve | None = None) -> CommentResponse:
    try:
        return _comment_service().resolve_comment(str(comment_id), request or CommentResolve())
    except CommentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CommentServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/approval-threads/{thread_id}/approve", response_model=ApprovalThreadResponse)
def approve_thread(thread_id: ThreadIdPath, request: ApprovalActionCreate) -> ApprovalThreadResponse:
    try:
        return _approval_service().approve(str(thread_id), request)
    except ApprovalThreadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ApprovalReviewerNotFound as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ApprovalThreadClosed as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ApprovalServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/approval-threads/{thread_id}/request-changes", response_model=ApprovalThreadResponse)
def request_changes(thread_id: ThreadIdPath, request: ChangeRequestCreate) -> ApprovalThreadResponse:
    try:
        return _approval_service().request_changes(str(thread_id), request)
    except ApprovalThreadNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ApprovalReviewerNotFound as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ApprovalThreadClosed as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ApprovalServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/campaigns/{campaign_id}/refinement-requests", response_model=RefinementRequestResponse)
def create_refinement_request(campaign_id: CampaignIdPath, request: RefinementRequestCreate) -> RefinementRequestResponse:
    try:
        return _approval_service().create_refinement_request(str(campaign_id), request)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CampaignRevisionNotFound as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except CampaignRevisionMismatch as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ApprovalServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
