"""performance-audit skill — invokes Auditor sub-agent. Lands in GH-16/GH-NEW7."""

from app.agents.state import AuditReport, BannerSessionState
from app.agents.sub_agents.auditor import decide


async def run(html: str, state: BannerSessionState) -> tuple[AuditReport, str]:
    raise NotImplementedError("Lands in GH-16/GH-NEW7.")
