"""user-personalization skill — see SKILL.md. Lands in GH-10."""

from app.agents.state import Campaign, Variant


async def run(campaign: Campaign) -> list[Variant]:
    raise NotImplementedError("Lands in GH-10.")
