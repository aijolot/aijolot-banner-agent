from __future__ import annotations

import copy

import pytest
from app.schemas.approvals import (
    ApprovalActionCreate,
    ApprovalRequestCreate,
    ChangeRequestCreate,
    CommentCreate,
    CommentResolve,
    RefinementRequestCreate,
    ReviewerAssignment,
)
from app.services.approvals.approval_service import (
    ApprovalReviewerNotFound,
    ApprovalService,
    ApprovalServiceUnavailable,
    ApprovalThreadClosed,
    CampaignRevisionMismatch,
    CampaignRevisionNotFound,
    DuplicateReviewer,
)
from app.services.approvals.comment_service import CommentService

CAMPAIGN_ID = "00000000-0000-0000-0000-000000000101"
REVISION_ID = "00000000-0000-0000-0000-000000000201"
OTHER_REVISION_ID = "00000000-0000-0000-0000-000000000202"
THREAD_ID = "00000000-0000-0000-0000-000000000301"
COMMENT_ID = "00000000-0000-0000-0000-000000000401"
REFINEMENT_ID = "00000000-0000-0000-0000-000000000501"
USER_1 = "00000000-0000-0000-0000-000000000601"
USER_2 = "00000000-0000-0000-0000-000000000602"


class InMemoryCampaigns:
    def __init__(self) -> None:
        self.rows = {CAMPAIGN_ID: {"id": CAMPAIGN_ID, "status": "draft", "selected_revision_id": REVISION_ID}}

    def get(self, *, campaign_id: str, team_id: str | None = None):
        return copy.deepcopy(self.rows.get(campaign_id))

    def update(self, *, campaign_id: str, data: dict, team_id: str | None = None):
        self.rows[campaign_id].update(data)
        return copy.deepcopy(self.rows[campaign_id])


class InMemoryRevisions:
    def __init__(self) -> None:
        self.rows = {
            REVISION_ID: {"id": REVISION_ID, "campaign_id": CAMPAIGN_ID, "revision_number": 1},
            OTHER_REVISION_ID: {"id": OTHER_REVISION_ID, "campaign_id": "00000000-0000-0000-0000-000000000102", "revision_number": 1},
        }

    def get(self, *, revision_id: str):
        return copy.deepcopy(self.rows.get(revision_id))

    def get_latest_by_campaign_id(self, *, campaign_id: str):
        for row in self.rows.values():
            if row["campaign_id"] == campaign_id:
                return copy.deepcopy(row)
        return None


class InMemoryThreads:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.next = 1

    def create(self, *, data: dict):
        row = {"id": THREAD_ID if self.next == 1 else f"00000000-0000-0000-0000-00000000030{self.next}", **data}
        self.next += 1
        self.rows[row["id"]] = row
        return copy.deepcopy(row)

    def get(self, *, thread_id: str):
        return copy.deepcopy(self.rows.get(thread_id))

    def get_latest_by_campaign_id(self, *, campaign_id: str):
        rows = [row for row in self.rows.values() if row["campaign_id"] == campaign_id]
        return copy.deepcopy(rows[-1]) if rows else None

    def update(self, *, thread_id: str, data: dict):
        self.rows[thread_id].update(data)
        return copy.deepcopy(self.rows[thread_id])


class InMemoryReviewers:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def create_many(self, *, reviewers: list[dict]):
        created = []
        for idx, data in enumerate(reviewers, start=1):
            row = {"id": f"00000000-0000-0000-0000-00000000070{idx}", "note": None, "decided_at": None, **data}
            self.rows.append(row)
            created.append(copy.deepcopy(row))
        return created

    def list_by_thread_id(self, *, thread_id: str):
        return copy.deepcopy([row for row in self.rows if row["approval_thread_id"] == thread_id])

    def get_for_user(self, *, thread_id: str, user_id: str):
        for row in self.rows:
            if row["approval_thread_id"] == thread_id and row["user_id"] == user_id:
                return copy.deepcopy(row)
        return None

    def update_for_user(self, *, thread_id: str, user_id: str, data: dict):
        for row in self.rows:
            if row["approval_thread_id"] == thread_id and row["user_id"] == user_id:
                row.update(data)
                return copy.deepcopy(row)
        return None


class InMemoryComments:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def create(self, *, data: dict):
        row = {"id": COMMENT_ID, "resolved": False, **data}
        self.rows[row["id"]] = row
        return copy.deepcopy(row)

    def get(self, *, comment_id: str):
        return copy.deepcopy(self.rows.get(comment_id))

    def list_by_thread_id(self, *, thread_id: str):
        return copy.deepcopy([row for row in self.rows.values() if row.get("approval_thread_id") == thread_id])

    def update(self, *, comment_id: str, data: dict):
        self.rows[comment_id].update(data)
        return copy.deepcopy(self.rows[comment_id])


class InMemoryRefinements:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def create(self, *, data: dict):
        row = {"id": REFINEMENT_ID, "result_revision_id": None, "status": "queued", **data}
        self.rows.append(row)
        return copy.deepcopy(row)

    def list_by_campaign_id(self, *, campaign_id: str):
        return copy.deepcopy([row for row in self.rows if row["campaign_id"] == campaign_id])


@pytest.fixture()
def services() -> tuple[ApprovalService, CommentService, InMemoryCampaigns, InMemoryRefinements]:
    campaigns = InMemoryCampaigns()
    revisions = InMemoryRevisions()
    threads = InMemoryThreads()
    reviewers = InMemoryReviewers()
    comments = InMemoryComments()
    refinements = InMemoryRefinements()
    approval = ApprovalService(
        campaigns=campaigns,
        revisions=revisions,
        threads=threads,
        reviewers=reviewers,
        comments=comments,
        refinement_requests=refinements,
    )
    comment = CommentService(threads=threads, comments=comments)
    return approval, comment, campaigns, refinements


def _request_thread(approval: ApprovalService):
    return approval.request_approval(
        CAMPAIGN_ID,
        ApprovalRequestCreate(
            requested_by=USER_1,
            reviewers=[{"user_id": USER_1, "role_label": "Owner"}, {"user_id": USER_2, "role_label": "Marketing"}],
        ),
    )


def test_request_approval_creates_thread_reviewers_and_sets_needs_review(services) -> None:
    approval, _comment, campaigns, _refinements = services

    thread = _request_thread(approval)

    assert thread.id == THREAD_ID
    assert thread.status == "open"
    assert [reviewer.user_id for reviewer in thread.reviewers] == [USER_1, USER_2]
    assert all(reviewer.status == "pending" for reviewer in thread.reviewers)
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "needs_review"


def test_request_approval_requires_selected_revision(services) -> None:
    approval, _comment, campaigns, _refinements = services
    campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] = None

    with pytest.raises(CampaignRevisionNotFound):
        approval.request_approval(CAMPAIGN_ID, ApprovalRequestCreate(reviewers=[ReviewerAssignment(user_id=USER_1)]))


def test_request_approval_derives_configured_demo_reviewers(services) -> None:
    approval, _comment, _campaigns, _refinements = services
    approval.default_reviewers = [
        {"user_id": USER_1, "role_label": "Owner"},
        {"user_id": USER_2, "role_label": "Marketing"},
    ]

    thread = approval.request_approval(CAMPAIGN_ID, ApprovalRequestCreate())

    assert [reviewer.user_id for reviewer in thread.reviewers] == [USER_1, USER_2]
    assert [reviewer.role_label for reviewer in thread.reviewers] == ["Owner", "Marketing"]


def test_request_approval_without_reviewers_fails_closed(services) -> None:
    approval, _comment, _campaigns, _refinements = services

    with pytest.raises(ApprovalServiceUnavailable):
        approval.request_approval(CAMPAIGN_ID, ApprovalRequestCreate())


def test_empty_thread_create_result_fails_closed(services) -> None:
    approval, _comment, _campaigns, _refinements = services

    class EmptyThreadCreate(InMemoryThreads):
        def create(self, *, data: dict):
            return {}

    approval.threads = EmptyThreadCreate()

    with pytest.raises(ApprovalServiceUnavailable):
        approval.request_approval(CAMPAIGN_ID, ApprovalRequestCreate(reviewers=[ReviewerAssignment(user_id=USER_1)]))


def test_all_reviewers_must_approve_before_campaign_is_approved(services) -> None:
    approval, _comment, campaigns, _refinements = services
    _request_thread(approval)

    first = approval.approve(THREAD_ID, ApprovalActionCreate(user_id=USER_1, note="Looks good"))
    assert first.status == "open"
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "needs_review"

    second = approval.approve(THREAD_ID, ApprovalActionCreate(user_id=USER_2))

    assert campaigns.rows[CAMPAIGN_ID]["status"] == "approved"
    assert second.status == "approved"
    assert [reviewer.status for reviewer in second.reviewers] == ["approved", "approved"]


def test_non_assigned_reviewer_cannot_approve(services) -> None:
    approval, _comment, _campaigns, _refinements = services
    _request_thread(approval)

    with pytest.raises(ApprovalReviewerNotFound):
        approval.approve(THREAD_ID, ApprovalActionCreate(user_id="00000000-0000-0000-0000-000000000699"))


def test_request_changes_sets_status_and_optionally_creates_refinement(services) -> None:
    approval, _comment, campaigns, refinements = services
    _request_thread(approval)

    thread = approval.request_changes(
        THREAD_ID,
        ChangeRequestCreate(user_id=USER_2, note="Change CTA", prompt="Make CTA stronger"),
    )

    assert thread.status == "changes_requested"
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "changes_requested"
    assert len(refinements.rows) == 1
    assert refinements.rows[0]["prompt"] == "Make CTA stronger"


def test_comment_service_creates_pinned_comment_and_resolves_it(services) -> None:
    approval, comment, _campaigns, _refinements = services
    _request_thread(approval)

    created = comment.create_comment(
        THREAD_ID,
        CommentCreate(author_id=USER_1, body="Move logo", pin_x=20.5, pin_y=40, device_key="desktop"),
    )
    resolved = comment.resolve_comment(COMMENT_ID, CommentResolve(resolved_by=USER_2))

    assert created.campaign_id == CAMPAIGN_ID
    assert created.revision_id == REVISION_ID
    assert created.pin_x == 20.5
    assert resolved.resolved is True
    assert resolved.resolved_by == USER_2


def test_create_refinement_request_stores_without_regeneration(services) -> None:
    approval, _comment, campaigns, refinements = services

    row = approval.create_refinement_request(
        CAMPAIGN_ID,
        RefinementRequestCreate(requested_by=USER_1, prompt="Try warmer colors", addressed_comment_ids=[]),
    )

    assert row.status == "queued"
    assert row.result_revision_id is None
    assert len(refinements.rows) == 1
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "changes_requested"


def test_create_refinement_request_requires_selected_or_explicit_revision(services) -> None:
    approval, _comment, campaigns, _refinements = services
    campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] = None

    with pytest.raises(CampaignRevisionNotFound):
        approval.create_refinement_request(
            CAMPAIGN_ID,
            RefinementRequestCreate(requested_by=USER_1, prompt="Try warmer colors", addressed_comment_ids=[]),
        )


def test_revision_must_belong_to_campaign_for_approval_and_refinement(services) -> None:
    approval, _comment, _campaigns, _refinements = services

    with pytest.raises(CampaignRevisionMismatch):
        approval.request_approval(
            CAMPAIGN_ID,
            ApprovalRequestCreate(revision_id=OTHER_REVISION_ID, requested_by=USER_1, reviewers=[ReviewerAssignment(user_id=USER_1)]),
        )

    with pytest.raises(CampaignRevisionMismatch):
        approval.create_refinement_request(
            CAMPAIGN_ID,
            RefinementRequestCreate(source_revision_id=OTHER_REVISION_ID, requested_by=USER_1, prompt="Change it"),
        )


def test_duplicate_reviewers_are_rejected_before_thread_creation(services) -> None:
    approval, _comment, _campaigns, _refinements = services

    with pytest.raises(DuplicateReviewer):
        approval.request_approval(
            CAMPAIGN_ID,
            ApprovalRequestCreate(reviewers=[ReviewerAssignment(user_id=USER_1), ReviewerAssignment(user_id=USER_1)]),
        )


def test_closed_thread_rejects_late_approval_or_changes(services) -> None:
    approval, _comment, _campaigns, _refinements = services
    _request_thread(approval)
    approval.request_changes(THREAD_ID, ChangeRequestCreate(user_id=USER_1, prompt="Revise"))

    with pytest.raises(ApprovalThreadClosed):
        approval.approve(THREAD_ID, ApprovalActionCreate(user_id=USER_2))

    with pytest.raises(ApprovalThreadClosed):
        approval.request_changes(THREAD_ID, ChangeRequestCreate(user_id=USER_2, prompt="Another revise"))
