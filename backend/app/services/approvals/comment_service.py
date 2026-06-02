from __future__ import annotations

from datetime import UTC, datetime

from typing import Any

from app.schemas.approvals import CommentCreate, CommentResolve, CommentResponse
from app.services.approvals.approval_service import ApprovalThreadNotFound


class CommentNotFound(Exception):
    def __init__(self, comment_id: str) -> None:
        super().__init__(f"comment {comment_id} not found")


class CommentServiceUnavailable(Exception):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


class CommentService:
    def __init__(self, *, threads: Any, comments: Any) -> None:
        self.threads = threads
        self.comments = comments

    def create_comment(self, thread_id: str, request: CommentCreate) -> CommentResponse:
        thread = self.threads.get(thread_id=thread_id)
        if not thread:
            raise ApprovalThreadNotFound(thread_id)
        row = self.comments.create(
            data={
                "approval_thread_id": thread_id,
                "campaign_id": thread["campaign_id"],
                "revision_id": thread.get("revision_id"),
                "author_id": request.author_id,
                "body": request.body,
                "pin_x": request.pin_x,
                "pin_y": request.pin_y,
                "banner_variant_id": request.banner_variant_id,
                "layout_variant_key": request.layout_variant_key,
                "device_key": request.device_key,
                "resolved": False,
            }
        )
        return CommentResponse.model_validate(row)

    def resolve_comment(self, comment_id: str, request: CommentResolve) -> CommentResponse:
        if not self.comments.get(comment_id=comment_id):
            raise CommentNotFound(comment_id)
        row = self.comments.update(
            comment_id=comment_id,
            data={"resolved": True, "resolved_by": request.resolved_by, "resolved_at": _now()},
        )
        if not row:
            raise CommentNotFound(comment_id)
        return CommentResponse.model_validate(row)


def configured_service() -> CommentService:
    raise CommentServiceUnavailable("comment endpoints require request-scoped auth/client configuration")
