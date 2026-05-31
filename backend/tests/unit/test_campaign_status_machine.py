from __future__ import annotations

from app.schemas.campaign import StructuredBrief
from app.services.banners.status_machine import can_patch_brief, status_for_brief


def test_status_stays_draft_until_required_brief_fields_are_complete() -> None:
    assert status_for_brief(StructuredBrief(goal="Sale")) == "draft"


def test_status_moves_to_needs_review_when_brief_is_complete() -> None:
    brief = StructuredBrief(goal="Sale", audience="VIP", cta="Shop", urgency="high", placement="Home")
    assert status_for_brief(brief) == "needs_review"


def test_terminal_statuses_are_preserved() -> None:
    brief = StructuredBrief(goal="Sale", audience="VIP", cta="Shop", urgency="high", placement="Home")
    assert status_for_brief(brief, "approved") == "approved"
    assert can_patch_brief("approved") is False
    assert can_patch_brief("needs_review") is True
