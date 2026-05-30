"""schedule-or-publish-route skill — see SKILL.md. Lands in GH-18."""

from app.agents.state import BannerSessionState


async def run(state: BannerSessionState) -> str:
    raise NotImplementedError("Lands in GH-18. Returns 'immediate' or 'scheduled'.")
