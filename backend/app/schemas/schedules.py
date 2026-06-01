from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
ScheduleStatus = Literal["pending", "active", "completed", "cancelled"]
PublishJobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
PublishAction = Literal["install_theme_files", "publish_config", "publish", "unpublish", "rollback"]


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    starts_at: str
    ends_at: str | None = None
    timezone: str = Field(default="UTC", min_length=1, max_length=80)
    auto_unpublish: bool = True
    created_by: str | None = Field(default=None, pattern=UUID_PATTERN)


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: str | None = None
    ends_at: str | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    auto_unpublish: bool | None = None

    @model_validator(mode="after")
    def _non_empty(self) -> "ScheduleUpdate":
        if not self.model_dump(exclude_none=True):
            raise ValueError("at least one field must be provided")
        return self


class ScheduleResponse(BaseModel):
    id: str
    campaign_id: str
    revision_id: str
    starts_at: str
    ends_at: str | None = None
    timezone: str = "UTC"
    auto_unpublish: bool = True
    status: ScheduleStatus = "pending"
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PublishJobResponse(BaseModel):
    id: str
    campaign_id: str
    revision_id: str
    schedule_id: str | None = None
    status: PublishJobStatus
    action: PublishAction
    shopify_resource_type: str | None = None
    shopify_resource_id: str | None = None
    request_payload: dict = Field(default_factory=dict)
    response_payload: dict = Field(default_factory=dict)
    error_message: str | None = None
    idempotency_key: str
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None
