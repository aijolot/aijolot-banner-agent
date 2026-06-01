"""schedule-or-publish-route skill — route approved campaign to immediate or scheduled publish."""

from __future__ import annotations

from app.agents.state import BannerSessionState


async def run(state: BannerSessionState) -> str:
    schedule = getattr(state, "schedule", None) or getattr(state, "publish_schedule", None)
    if isinstance(schedule, dict) and schedule.get("starts_at"):
        return "scheduled"
    if schedule:
        return "scheduled"
    return "immediate"
