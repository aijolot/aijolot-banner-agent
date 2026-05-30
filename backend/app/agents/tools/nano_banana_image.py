"""ADK Tool: Nano Banana Pro image generation.

Model: gemini-3.1-pro-image (resuelve GH-25 — reemplaza Imagen 4).
Constraints: aspect 16:9, safety_filter=block_some, no text/logos/faces.
Lands in GH-12.
"""

from __future__ import annotations

import os


IMAGE_MODEL = os.getenv("GEMINI_MODEL_IMAGE", "gemini-3.1-pro-image")


async def generate(prompt: str, *, aspect_ratio: str = "16:9") -> bytes:
    """Generate one 16:9 image. Logs cost_usd to audit_log."""
    raise NotImplementedError("Lands in services/gemini/image.py + GH-12.")
