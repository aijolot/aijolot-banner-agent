"""campaign-intake skill — see SKILL.md. Lands in GH-9."""

from app.agents.state import Campaign


async def run(messages: list[dict], brand_context) -> Campaign | dict:
    """Return Campaign if complete, else {'question': '<next clarifying q>'}."""
    raise NotImplementedError("Lands in GH-9.")
