from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.approvals.approval_service import ApprovalService
from app.services.approvals.comment_service import CommentService
from tests.unit.test_approval_service import (
    CAMPAIGN_ID,
    COMMENT_ID,
    REVISION_ID,
    THREAD_ID,
    USER_1,
    USER_2,
    InMemoryCampaigns,
    InMemoryComments,
    InMemoryRefinements,
    InMemoryReviewers,
    InMemoryRevisions,
    InMemoryThreads,
)

client = TestClient(app)
UNKNOWN_CAMPAIGN_ID = "00000000-0000-0000-0000-000000000999"
UNKNOWN_THREAD_ID = "00000000-0000-0000-0000-000000000998"
UNKNOWN_COMMENT_ID = "00000000-0000-0000-0000-000000000997"
DEMO_TEAM_ID = "00000000-0000-0000-0000-000000000001"
DEMO_HEADERS = {"x-aijolot-user-id": USER_1, "x-aijolot-team-id": DEMO_TEAM_ID}


class FakeStack:
    def __init__(self) -> None:
        self.campaigns = InMemoryCampaigns()
        self.revisions = InMemoryRevisions()
        self.threads = InMemoryThreads()
        self.reviewers = InMemoryReviewers()
        self.comments = InMemoryComments()
        self.refinements = InMemoryRefinements()
        self.approval = ApprovalService(
            campaigns=self.campaigns,
            revisions=self.revisions,
            threads=self.threads,
            reviewers=self.reviewers,
            comments=self.comments,
            refinement_requests=self.refinements,
        )
        self.comment = CommentService(threads=self.threads, comments=self.comments)


def _install(monkeypatch) -> FakeStack:
    from app.api.v1 import approvals

    stack = FakeStack()
    monkeypatch.setattr(approvals, "_approval_service", lambda: stack.approval)
    monkeypatch.setattr(approvals, "_comment_service", lambda: stack.comment)
    return stack


def _request_approval() -> dict:
    response = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/approval/request",
        json={
            "requested_by": USER_1,
            "reviewers": [{"user_id": USER_1, "role_label": "Owner"}, {"user_id": USER_2}],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_approval_request_and_get_state(monkeypatch) -> None:
    stack = _install(monkeypatch)

    thread = _request_approval()
    state = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/approval")

    assert thread["id"] == THREAD_ID
    assert thread["revision_id"] == REVISION_ID
    assert [reviewer["status"] for reviewer in thread["reviewers"]] == ["pending", "pending"]
    assert stack.campaigns.rows[CAMPAIGN_ID]["status"] == "needs_review"
    assert state.status_code == 200
    assert state.json()["campaign_status"] == "needs_review"
    assert state.json()["thread"]["id"] == THREAD_ID


def test_comment_create_and_resolve(monkeypatch) -> None:
    _install(monkeypatch)
    _request_approval()

    created = client.post(
        f"/api/v1/approval-threads/{THREAD_ID}/comments",
        json={"author_id": USER_1, "body": "Logo overlaps text", "pin_x": 10, "pin_y": 25, "device_key": "mobile"},
    )
    resolved = client.patch(f"/api/v1/comments/{COMMENT_ID}/resolve", json={"resolved_by": USER_2})

    assert created.status_code == 200
    assert created.json()["body"] == "Logo overlaps text"
    assert created.json()["pin_x"] == 10
    assert created.json()["device_key"] == "mobile"
    assert resolved.status_code == 200
    assert resolved.json()["resolved"] is True
    assert resolved.json()["resolved_by"] == USER_2


def test_all_reviewers_approve_transitions_campaign_to_approved(monkeypatch) -> None:
    stack = _install(monkeypatch)
    _request_approval()

    first = client.post(f"/api/v1/approval-threads/{THREAD_ID}/approve", json={"user_id": USER_1, "note": "ok"})
    assert first.status_code == 200
    assert first.json()["status"] == "open"
    assert stack.campaigns.rows[CAMPAIGN_ID]["status"] == "needs_review"

    second = client.post(f"/api/v1/approval-threads/{THREAD_ID}/approve", json={"user_id": USER_2})

    assert stack.campaigns.rows[CAMPAIGN_ID]["status"] == "approved"
    assert second.status_code == 200
    assert second.json()["status"] == "approved"
    assert [reviewer["status"] for reviewer in second.json()["reviewers"]] == ["approved", "approved"]


def test_request_changes_and_refinement_request(monkeypatch) -> None:
    stack = _install(monkeypatch)
    _request_approval()

    changes = client.post(
        f"/api/v1/approval-threads/{THREAD_ID}/request-changes",
        json={"user_id": USER_2, "note": "Too muted", "prompt": "Use a brighter palette"},
    )
    refinement = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/refinement-requests",
        json={"requested_by": USER_1, "prompt": "Make hero image more seasonal"},
    )

    assert changes.status_code == 200
    assert changes.json()["status"] == "changes_requested"
    assert changes.json()["refinement_requests"][0]["prompt"] == "Use a brighter palette"
    assert refinement.status_code == 200
    assert refinement.json()["status"] == "queued"
    assert refinement.json()["result_revision_id"] is None
    assert stack.campaigns.rows[CAMPAIGN_ID]["status"] == "changes_requested"


def test_missing_resources_and_invalid_payloads_return_expected_errors(monkeypatch) -> None:
    _install(monkeypatch)

    assert client.get(f"/api/v1/campaigns/{UNKNOWN_CAMPAIGN_ID}/approval").status_code == 404
    assert client.post(f"/api/v1/campaigns/{UNKNOWN_CAMPAIGN_ID}/approval/request", json={"reviewers": [{"user_id": USER_1}]}).status_code == 404
    assert client.post(f"/api/v1/approval-threads/{UNKNOWN_THREAD_ID}/comments", json={"body": "x"}).status_code == 404
    assert client.patch(f"/api/v1/comments/{UNKNOWN_COMMENT_ID}/resolve", json={}).status_code == 404

    _request_approval()
    assert client.post(f"/api/v1/approval-threads/{THREAD_ID}/approve", json={"user_id": UNKNOWN_CAMPAIGN_ID}).status_code == 403
    assert client.post(f"/api/v1/approval-threads/{THREAD_ID}/comments", json={"body": "x", "pin_x": 10}).status_code == 422
    assert client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/approval/request",
        json={"reviewers": [{"user_id": USER_1}, {"user_id": USER_1}]},
    ).status_code == 422
    assert client.post("/api/v1/campaigns/not-a-uuid/approval/request", json={}).status_code == 422


def test_closed_thread_actions_return_conflict(monkeypatch) -> None:
    _install(monkeypatch)
    _request_approval()
    assert client.post(f"/api/v1/approval-threads/{THREAD_ID}/request-changes", json={"user_id": USER_1, "prompt": "Revise"}).status_code == 200

    assert client.post(f"/api/v1/approval-threads/{THREAD_ID}/approve", json={"user_id": USER_2}).status_code == 409
    assert client.post(f"/api/v1/approval-threads/{THREAD_ID}/request-changes", json={"user_id": USER_2, "prompt": "Again"}).status_code == 409


def test_default_unconfigured_endpoints_return_503(monkeypatch) -> None:
    from app.api.v1 import approvals
    from app.services.approvals.approval_service import configured_service as approval_configured
    from app.services.approvals.comment_service import configured_service as comment_configured

    monkeypatch.setattr(approvals, "_approval_service", approval_configured)
    monkeypatch.setattr(approvals, "_comment_service", comment_configured)

    response = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/approval")
    comment = client.post(f"/api/v1/approval-threads/{THREAD_ID}/comments", json={"body": "x"})

    assert response.status_code == 503
    assert comment.status_code == 503


def test_default_approval_endpoints_require_request_context(monkeypatch) -> None:
    from app.api.v1 import approvals

    monkeypatch.setattr(approvals, "_approval_service", approvals._DEFAULT_APPROVAL_SERVICE_FACTORY)
    monkeypatch.setattr(approvals, "_comment_service", approvals._DEFAULT_COMMENT_SERVICE_FACTORY)

    assert client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/approval").status_code == 401


def test_default_approval_endpoints_fail_closed_without_supabase(monkeypatch) -> None:
    from app.api.v1 import approvals

    monkeypatch.setattr(approvals, "_approval_service", approvals._DEFAULT_APPROVAL_SERVICE_FACTORY)
    monkeypatch.setattr(approvals, "_comment_service", approvals._DEFAULT_COMMENT_SERVICE_FACTORY)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    response = client.get(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/approval",
        headers=DEMO_HEADERS,
    )

    assert response.status_code == 503


def test_default_comment_routes_fail_closed_for_untrusted_demo_context(monkeypatch) -> None:
    from app.api.v1 import approvals

    monkeypatch.setattr(approvals, "_comment_service", approvals._DEFAULT_COMMENT_SERVICE_FACTORY)
    monkeypatch.setenv("APP_ENV", "production")
    production = client.post(
        f"/api/v1/approval-threads/{THREAD_ID}/comments",
        headers=DEMO_HEADERS,
        json={"body": "x"},
    )
    monkeypatch.setenv("APP_ENV", "test")
    wrong_team = client.post(
        f"/api/v1/approval-threads/{THREAD_ID}/comments",
        headers={"x-aijolot-user-id": USER_1, "x-aijolot-team-id": "00000000-0000-0000-0000-000000000099"},
        json={"body": "x"},
    )
    wrong_team_resolve = client.patch(
        f"/api/v1/comments/{COMMENT_ID}/resolve",
        headers={"x-aijolot-user-id": USER_1, "x-aijolot-team-id": "00000000-0000-0000-0000-000000000099"},
        json={},
    )

    assert production.status_code == 503
    assert wrong_team.status_code == 404
    assert wrong_team_resolve.status_code == 404


def test_default_approval_routes_bind_actor_fields_to_request_context(monkeypatch) -> None:
    from app.api.v1 import approvals

    stack = FakeStack()
    stack.approval.default_reviewers = [{"user_id": USER_1, "role_label": None}]
    monkeypatch.setattr(approvals, "_approval_service", approvals._DEFAULT_APPROVAL_SERVICE_FACTORY)
    monkeypatch.setattr(approvals, "_comment_service", approvals._DEFAULT_COMMENT_SERVICE_FACTORY)
    monkeypatch.setattr(approvals, "configured_approval_service_for_team", lambda _team_id: stack.approval)
    monkeypatch.setattr(approvals, "configured_comment_service_for_team", lambda _team_id: stack.comment)

    thread = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/approval/request",
        headers=DEMO_HEADERS,
        json={"requested_by": USER_2, "reviewers": [{"user_id": USER_1, "role_label": "Owner"}]},
    )
    comment = client.post(
        f"/api/v1/approval-threads/{THREAD_ID}/comments",
        headers=DEMO_HEADERS,
        json={"author_id": USER_2, "body": "Use backend actor"},
    )
    approve = client.post(
        f"/api/v1/approval-threads/{THREAD_ID}/approve",
        headers=DEMO_HEADERS,
        json={"user_id": USER_2, "note": "approve as request user"},
    )

    assert thread.status_code == 200
    assert comment.status_code == 200
    assert comment.json()["author_id"] == USER_1
    assert approve.status_code == 200
    assert approve.json()["reviewers"][0]["user_id"] == USER_1
    assert approve.json()["reviewers"][0]["status"] == "approved"
