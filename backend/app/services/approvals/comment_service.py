from __future__ import annotations

from datetime import UTC, datetime

from typing import Any

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.approval_threads import ApprovalThreadRepository
from app.db.repositories.campaigns import CampaignRepository
from app.db.repositories.comments import CommentRepository
from app.schemas.approvals import CommentCreate, CommentResolve, CommentResponse
from app.services.approvals.approval_service import (
    ApprovalThreadNotFound,
    _TeamScopedApprovalThreadRepository,
    _TeamScopedCampaignRepository,
)
from app.services.supabase.client import SupabaseClientFactory


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

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str) -> "CommentService":
        campaigns = _TeamScopedCampaignRepository(CampaignRepository(client), team_id=team_id)
        threads = _TeamScopedApprovalThreadRepository(ApprovalThreadRepository(client), campaigns=campaigns)
        return cls(
            threads=threads,
            comments=_TeamScopedCommentRepository(CommentRepository(client), threads=threads),
        )

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


def configured_service_for_team(team_id: str) -> CommentService:
    if not team_id:
        raise CommentServiceUnavailable("request team context is required")
    settings = Settings.from_env()
    if settings.app_env.lower() not in {"local", "test"}:
        raise CommentServiceUnavailable("comment demo service-role endpoints require local/demo APP_ENV")
    if settings.supabase_url is None or settings.supabase_service_role_key is None:
        raise CommentServiceUnavailable("comment endpoints require Supabase service configuration")
    try:
        client = SupabaseClientFactory(settings).service_role_client()
    except MissingSettingsError as exc:
        raise CommentServiceUnavailable(str(exc)) from None
    return CommentService.from_supabase_client(client, team_id=team_id)


class _TeamScopedCommentRepository:
    def __init__(self, repository: Any, *, threads: _TeamScopedApprovalThreadRepository) -> None:
        self.repository = repository
        self.threads = threads

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        thread_id = str(data.get("approval_thread_id") or "")
        if not thread_id or not self.threads.get(thread_id=thread_id):
            return {}
        return self.repository.create(data=data)

    def get(self, *, comment_id: str) -> dict[str, Any] | None:
        comment = self.repository.get(comment_id=comment_id)
        thread_id = str((comment or {}).get("approval_thread_id") or "")
        if not comment or not thread_id or not self.threads.get(thread_id=thread_id):
            return None
        return comment

    def list_by_thread_id(self, *, thread_id: str) -> list[dict[str, Any]]:
        if not self.threads.get(thread_id=thread_id):
            return []
        return self.repository.list_by_thread_id(thread_id=thread_id)

    def update(self, *, comment_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        if not self.get(comment_id=comment_id):
            return None
        return self.repository.update(comment_id=comment_id, data=data)
