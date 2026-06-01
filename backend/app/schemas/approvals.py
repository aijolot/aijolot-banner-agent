from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

ApprovalThreadStatus = Literal["open", "approved", "changes_requested", "rejected"]
ApprovalReviewerStatus = Literal["pending", "approved", "changes_requested", "rejected"]
ApprovalPolicy = Literal["all_members", "any_member", "required_members", "owner_only"]
DeviceKey = Literal["desktop", "tablet", "mobile"]
RefinementRequestStatus = Literal["queued", "running", "succeeded", "failed"]


class ReviewerAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., pattern=UUID_PATTERN)
    role_label: str | None = Field(default=None, max_length=80)


class ApprovalRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    requested_by: str | None = Field(default=None, pattern=UUID_PATTERN)
    approval_policy: Literal["all_members"] = "all_members"
    reviewers: list[ReviewerAssignment] = Field(default_factory=list, min_length=1)


class ApprovalActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., pattern=UUID_PATTERN)
    note: str | None = Field(default=None, max_length=2000)


class ChangeRequestCreate(ApprovalActionCreate):
    prompt: str | None = Field(default=None, min_length=1, max_length=8000)
    addressed_comment_ids: list[str] = Field(default_factory=list)

    @field_validator("addressed_comment_ids")
    @classmethod
    def _valid_comment_ids(cls, value: list[str]) -> list[str]:
        import re

        if any(re.match(UUID_PATTERN, item) is None for item in value):
            raise ValueError("addressed_comment_ids must contain UUID strings")
        return value


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    body: str = Field(..., min_length=1, max_length=4000)
    pin_x: float | None = Field(default=None, ge=0, le=100)
    pin_y: float | None = Field(default=None, ge=0, le=100)
    banner_variant_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    layout_variant_key: str | None = Field(default=None, max_length=120)
    device_key: DeviceKey | None = None

    @model_validator(mode="after")
    def _pin_pair(self) -> "CommentCreate":
        if (self.pin_x is None) != (self.pin_y is None):
            raise ValueError("pin_x and pin_y must be provided together")
        return self


class CommentResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolved_by: str | None = Field(default=None, pattern=UUID_PATTERN)


class RefinementRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_revision_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    requested_by: str | None = Field(default=None, pattern=UUID_PATTERN)
    prompt: str = Field(..., min_length=1, max_length=8000)
    addressed_comment_ids: list[str] = Field(default_factory=list)

    @field_validator("addressed_comment_ids")
    @classmethod
    def _valid_refinement_comment_ids(cls, value: list[str]) -> list[str]:
        import re

        if any(re.match(UUID_PATTERN, item) is None for item in value):
            raise ValueError("addressed_comment_ids must contain UUID strings")
        return value


class ApprovalReviewerResponse(BaseModel):
    id: str
    approval_thread_id: str
    user_id: str
    role_label: str | None = None
    status: ApprovalReviewerStatus
    note: str | None = None
    decided_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CommentResponse(BaseModel):
    id: str
    approval_thread_id: str | None = None
    campaign_id: str
    revision_id: str | None = None
    banner_variant_id: str | None = None
    layout_variant_key: str | None = None
    device_key: DeviceKey | None = None
    author_id: str | None = None
    body: str
    pin_x: float | None = None
    pin_y: float | None = None
    resolved: bool = False
    resolved_by: str | None = None
    resolved_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class RefinementRequestResponse(BaseModel):
    id: str
    campaign_id: str
    source_revision_id: str
    result_revision_id: str | None = None
    requested_by: str | None = None
    prompt: str
    addressed_comment_ids: list[str] = Field(default_factory=list)
    status: RefinementRequestStatus = "queued"
    result_summary: str | None = None
    created_at: str | None = None
    finished_at: str | None = None


class ApprovalThreadResponse(BaseModel):
    id: str
    campaign_id: str
    revision_id: str
    status: ApprovalThreadStatus
    approval_policy: ApprovalPolicy = "all_members"
    requested_by: str | None = None
    created_at: str | None = None
    resolved_at: str | None = None
    reviewers: list[ApprovalReviewerResponse] = Field(default_factory=list)
    comments: list[CommentResponse] = Field(default_factory=list)
    refinement_requests: list[RefinementRequestResponse] = Field(default_factory=list)


class ApprovalStateResponse(BaseModel):
    campaign_id: str
    campaign_status: str | None = None
    thread: ApprovalThreadResponse | None = None
