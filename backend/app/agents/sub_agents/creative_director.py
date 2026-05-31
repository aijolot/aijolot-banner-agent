"""CreativeDirector sub-agent — node 5 (draft_banner_concept).

Model: gemini-3.1-pro
Inputs: BrandContext, Campaign, Variants, top-K BestPractice docs from KG.
Output: Concept{copy, layout, palette_usage, image_prompt, hierarchy_notes}.

Constraints:
- Respect BrandContext.voice (tone, prohibited_words, required_phrases).
- image_prompt must NOT contain text/logos/UI/faces (safety + brand integrity).
- Concept must reuse palette tokens from BrandContext.palette.

Implementation deferred to GH-11 + GH-NEW6.
"""

from __future__ import annotations

import os

from app.agents.state import BannerSessionState, Concept


CREATIVE_DIRECTOR_MODEL = os.getenv("GEMINI_MODEL_PRO", "gemini-3.1-pro")


async def draft_concept(state: BannerSessionState) -> Concept:
    """Produce a Concept from BrandContext + Campaign + KG context."""
    raise NotImplementedError("Lands in GH-11 / GH-NEW6.")
