"""ADK Tool: Gemini text generation (Pro for reasoning, Flash for structured).

Lands in GH-9 / GH-11 / GH-NEW6.
"""

from __future__ import annotations

import os


PRO_MODEL = os.getenv("GEMINI_MODEL_PRO", "gemini-3.1-pro")
FLASH_MODEL = os.getenv("GEMINI_MODEL_FLASH", "gemini-3.5-flash")


async def generate(prompt: str, *, model: str = PRO_MODEL, structured: type | None = None):
    """Return text or a Pydantic instance if `structured` is provided."""
    raise NotImplementedError("Lands in services/gemini/text.py + per-skill ticket.")
