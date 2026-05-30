"""banner-concept-draft skill — invokes CreativeDirector sub-agent. Lands in GH-11/GH-NEW6."""

from app.agents.state import BannerSessionState, Concept
from app.agents.sub_agents.creative_director import draft_concept


async def run(state: BannerSessionState) -> Concept:
    return await draft_concept(state)
