"""nano-banana-image-generate skill — see SKILL.md. Lands in GH-12."""

from app.agents.tools import nano_banana_image


async def run(prompt: str) -> bytes:
    return await nano_banana_image.generate(prompt, aspect_ratio="16:9")
