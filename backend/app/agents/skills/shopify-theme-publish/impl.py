"""shopify-theme-publish skill — see SKILL.md. WRITE ACTION. Lands in GH-19."""

from app.agents.state import BannerSessionState, PublishResult
from app.agents.tools import shopify


async def run(state: BannerSessionState) -> PublishResult:
    raise NotImplementedError("Lands in GH-19. HITL approve enforced upstream.")
