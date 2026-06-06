from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.schemas.approvals import (
    ApprovalActionCreate,
    ApprovalRequestCreate,
    ApprovalStateResponse,
    ApprovalThreadResponse,
    ChangeRequestCreate,
    RefinementRequestCreate,
    RefinementRequestResponse,
)
from app.services.banners.status_machine import APPROVED, CHANGES_REQUESTED, NEEDS_REVIEW


class ApprovalError(Exception):
    pass


class CampaignNotFound(ApprovalError):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign {campaign_id} not found")


class ApprovalThreadNotFound(ApprovalError):
    def __init__(self, thread_id: str) -> None:
        super().__init__(f"approval thread {thread_id} not found")


class ApprovalReviewerNotFound(ApprovalError):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"approval reviewer {user_id} not found")


class CampaignRevisionNotFound(ApprovalError):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign {campaign_id} has no reviewable revision")


class CampaignRevisionMismatch(ApprovalError):
    def __init__(self, campaign_id: str, revision_id: str) -> None:
        super().__init__(f"revision {revision_id} does not belong to campaign {campaign_id}")


class DuplicateReviewer(ApprovalError):
    def __init__(self, user_id: str) -> None:
        super().__init__(f"reviewer {user_id} is assigned more than once")


class ApprovalThreadClosed(ApprovalError):
    def __init__(self, thread_id: str, status: str) -> None:
        super().__init__(f"approval thread {thread_id} is closed with status {status}")


class ApprovalServiceUnavailable(ApprovalError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ApprovalService:
    def __init__(
        self,
        *,
        campaigns: Any,
        revisions: Any,
        threads: Any,
        reviewers: Any,
        comments: Any,
        refinement_requests: Any,
    ) -> None:
        self.campaigns = campaigns
        self.revisions = revisions
        self.threads = threads
        self.reviewers = reviewers
        self.comments = comments
        self.refinement_requests = refinement_requests

    @classmethod
    def from_supabase_client(cls, client: Any) -> "ApprovalService":
        from app.db.repositories.approval_reviewers import ApprovalReviewerRepository
        from app.db.repositories.approval_threads import ApprovalThreadRepository
        from app.db.repositories.campaign_revisions import CampaignRevisionRepository
        from app.db.repositories.campaigns import CampaignRepository
        from app.db.repositories.comments import CommentRepository
        from app.db.repositories.refinement_requests import RefinementRequestRepository

        return cls(
            campaigns=CampaignRepository(client),
            revisions=CampaignRevisionRepository(client),
            threads=ApprovalThreadRepository(client),
            reviewers=ApprovalReviewerRepository(client),
            comments=CommentRepository(client),
            refinement_requests=RefinementRequestRepository(client),
        )

    def request_approval(self, campaign_id: str, request: ApprovalRequestCreate) -> ApprovalThreadResponse:
        campaign = self.campaigns.get(campaign_id=campaign_id)
        if not campaign:
            raise CampaignNotFound(campaign_id)

        revision_id = request.revision_id or campaign.get("selected_revision_id")
        revision = self.revisions.get(revision_id=revision_id) if revision_id else self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id)
        if not revision:
            raise CampaignRevisionNotFound(campaign_id)
        self._ensure_revision_belongs(campaign_id=campaign_id, revision=revision)
        reviewer_ids = [reviewer.user_id for reviewer in request.reviewers]
        duplicate_id = next((user_id for user_id in reviewer_ids if reviewer_ids.count(user_id) > 1), None)
        if duplicate_id:
            raise DuplicateReviewer(duplicate_id)
        revision_id = str(revision["id"])

        thread = self.threads.create(
            data={
                "campaign_id": campaign_id,
                "revision_id": revision_id,
                "approval_policy": request.approval_policy,
                "requested_by": request.requested_by,
                "status": "open",
            }
        )
        reviewer_rows = self.reviewers.create_many(
            reviewers=[
                {
                    "approval_thread_id": thread["id"],
                    "user_id": reviewer.user_id,
                    "role_label": reviewer.role_label,
                    "status": "pending",
                }
                for reviewer in request.reviewers
            ]
        )
        self.campaigns.update(campaign_id=campaign_id, data={"status": NEEDS_REVIEW})
        return self._build_thread_response(thread, reviewers=reviewer_rows)

    def get_campaign_approval(self, campaign_id: str) -> ApprovalStateResponse:
        campaign = self.campaigns.get(campaign_id=campaign_id)
        if not campaign:
            raise CampaignNotFound(campaign_id)
        thread = self.threads.get_latest_by_campaign_id(campaign_id=campaign_id)
        return ApprovalStateResponse(
            campaign_id=campaign_id,
            campaign_status=campaign.get("status"),
            thread=self._hydrate_thread(thread) if thread else None,
        )

    def approve(self, thread_id: str, request: ApprovalActionCreate) -> ApprovalThreadResponse:
        thread = self.threads.get(thread_id=thread_id)
        if not thread:
            raise ApprovalThreadNotFound(thread_id)
        if thread.get("status") != "open":
            raise ApprovalThreadClosed(thread_id, str(thread.get("status")))
        reviewer = self.reviewers.update_for_user(
            thread_id=thread_id,
            user_id=request.user_id,
            data={"status": "approved", "note": request.note, "decided_at": _now()},
        )
        if not reviewer:
            raise ApprovalReviewerNotFound(request.user_id)

        reviewers = self.reviewers.list_by_thread_id(thread_id=thread_id)
        all_approved = bool(reviewers) and all(row.get("status") == "approved" for row in reviewers)
        if all_approved:
            thread = self.threads.update(thread_id=thread_id, data={"status": "approved", "resolved_at": _now()}) or thread
            self.campaigns.update(campaign_id=thread["campaign_id"], data={"status": APPROVED})
        else:
            self.campaigns.update(campaign_id=thread["campaign_id"], data={"status": NEEDS_REVIEW})
        return self._hydrate_thread(thread)

    def request_changes(self, thread_id: str, request: ChangeRequestCreate) -> ApprovalThreadResponse:
        thread = self.threads.get(thread_id=thread_id)
        if not thread:
            raise ApprovalThreadNotFound(thread_id)
        if thread.get("status") != "open":
            raise ApprovalThreadClosed(thread_id, str(thread.get("status")))
        reviewer = self.reviewers.update_for_user(
            thread_id=thread_id,
            user_id=request.user_id,
            data={"status": "changes_requested", "note": request.note, "decided_at": _now()},
        )
        if not reviewer:
            raise ApprovalReviewerNotFound(request.user_id)
        thread = self.threads.update(thread_id=thread_id, data={"status": "changes_requested", "resolved_at": _now()}) or thread
        self.campaigns.update(campaign_id=thread["campaign_id"], data={"status": CHANGES_REQUESTED})
        if request.prompt:
            self.refinement_requests.create(
                data={
                    "campaign_id": thread["campaign_id"],
                    "source_revision_id": thread["revision_id"],
                    "requested_by": request.user_id,
                    "prompt": request.prompt,
                    "addressed_comment_ids": request.addressed_comment_ids,
                    "status": "queued",
                }
            )
        return self._hydrate_thread(thread)

    def create_refinement_request(self, campaign_id: str, request: RefinementRequestCreate) -> RefinementRequestResponse:
        campaign = self.campaigns.get(campaign_id=campaign_id)
        if not campaign:
            raise CampaignNotFound(campaign_id)
        source_revision_id = request.source_revision_id or campaign.get("selected_revision_id")
        revision = (
            self.revisions.get(revision_id=source_revision_id)
            if source_revision_id
            else self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id)
        )
        if not revision:
            raise CampaignRevisionNotFound(campaign_id)
        self._ensure_revision_belongs(campaign_id=campaign_id, revision=revision)
        row = self.refinement_requests.create(
            data={
                "campaign_id": campaign_id,
                "source_revision_id": revision["id"],
                "requested_by": request.requested_by,
                "prompt": request.prompt,
                "addressed_comment_ids": request.addressed_comment_ids,
                "status": "queued",
            }
        )
        self.campaigns.update(campaign_id=campaign_id, data={"status": CHANGES_REQUESTED})
        return RefinementRequestResponse.model_validate(row)

    @staticmethod
    def _ensure_revision_belongs(*, campaign_id: str, revision: dict[str, Any]) -> None:
        revision_campaign_id = revision.get("campaign_id")
        if revision_campaign_id is not None and str(revision_campaign_id) != str(campaign_id):
            raise CampaignRevisionMismatch(campaign_id, str(revision.get("id")))

    def _hydrate_thread(self, thread: dict[str, Any]) -> ApprovalThreadResponse:
        return self._build_thread_response(
            thread,
            reviewers=self.reviewers.list_by_thread_id(thread_id=thread["id"]),
            comments=self.comments.list_by_thread_id(thread_id=thread["id"]),
            refinement_requests=self.refinement_requests.list_by_campaign_id(campaign_id=thread["campaign_id"]),
        )

    @staticmethod
    def _build_thread_response(
        thread: dict[str, Any],
        *,
        reviewers: list[dict[str, Any]] | None = None,
        comments: list[dict[str, Any]] | None = None,
        refinement_requests: list[dict[str, Any]] | None = None,
    ) -> ApprovalThreadResponse:
        payload = {
            **thread,
            "reviewers": reviewers or [],
            "comments": comments or [],
            "refinement_requests": refinement_requests or [],
        }
        return ApprovalThreadResponse.model_validate(payload)


def configured_service() -> ApprovalService:
    from app.core.settings import Settings
    from app.services.supabase.client import SupabaseClientFactory

    settings = Settings.from_env()
    if settings.supabase_url is None or settings.supabase_service_role_key is None:
        raise ApprovalServiceUnavailable("approval endpoints require Supabase service-role configuration")
    client = SupabaseClientFactory(settings).service_role_client()
    return ApprovalService.from_supabase_client(client)
