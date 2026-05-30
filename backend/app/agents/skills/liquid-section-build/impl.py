"""liquid-section-build skill — see SKILL.md. Lands in GH-15."""

from app.agents.state import Concept, Variant
from app.agents.tools import liquid_render


async def run(concept: Concept, variants: list[Variant], brand) -> dict[str, str]:
    return await liquid_render.render(concept, variants, brand=brand)
