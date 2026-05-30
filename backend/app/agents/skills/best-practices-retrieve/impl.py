"""best-practices-retrieve skill — see SKILL.md. Lands in GH-NEW8."""

from app.agents.tools import kg


async def run(campaign, brand_context, *, top_k: int = 5) -> list[dict]:
    query = f"{campaign.goal} for {campaign.audience} · tone={campaign.tone} · cta={campaign.cta}"
    return await kg.retrieve(
        query,
        kinds=["best_practice", "brand_example", "prior_banner"],
        brand_id=brand_context.brand_id,
        top_k=top_k,
    )
