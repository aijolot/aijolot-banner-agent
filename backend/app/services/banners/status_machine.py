from __future__ import annotations

from app.schemas.campaign import StructuredBrief

DRAFT = "draft"
NEEDS_REVIEW = "needs_review"
CHANGES_REQUESTED = "changes_requested"
APPROVED = "approved"
ARCHIVED = "archived"

EDITABLE_STATUSES = {DRAFT, NEEDS_REVIEW, CHANGES_REQUESTED}
TERMINAL_STATUSES = {APPROVED, ARCHIVED, "published"}


def status_for_brief(brief: StructuredBrief, current_status: str = DRAFT) -> str:
    """Return the next intake status without crossing review/publish boundaries."""

    if current_status in TERMINAL_STATUSES:
        return current_status
    if brief.is_complete():
        return NEEDS_REVIEW
    return DRAFT


def can_patch_brief(status: str) -> bool:
    return status in EDITABLE_STATUSES
