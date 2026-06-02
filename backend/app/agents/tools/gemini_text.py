"""Small Gemini text-generation client used by ADK-compatible skills.

The module is safe to import without credentials or the Google SDK. Runtime calls
raise :class:`GeminiUnavailable` when Gemini cannot be used, allowing skills to
fall back deterministically in tests/dev.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

from pydantic import BaseModel, ValidationError

PRO_MODEL = os.getenv("GEMINI_MODEL_PRO", "gemini-3.1-pro")
FLASH_MODEL = os.getenv("GEMINI_MODEL_FLASH", "gemini-3.5-flash")


class GeminiUnavailable(RuntimeError):
    """Raised when Gemini is not configured or a generation call fails."""


def _api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        raise GeminiUnavailable("Gemini is unavailable: set GOOGLE_API_KEY or GEMINI_API_KEY")
    return key


def _json_from_text(text: str) -> Any:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.S | re.I)
    if fenced:
        cleaned = fenced.group(1).strip()
    return json.loads(cleaned)


def _coerce_structured(response: Any, structured: type[BaseModel]) -> BaseModel:
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        if isinstance(parsed, structured):
            return parsed
        if isinstance(parsed, BaseModel):
            return structured.model_validate(parsed.model_dump())
        return structured.model_validate(parsed)

    text = getattr(response, "text", None)
    if not text:
        raise GeminiUnavailable("Gemini response did not include structured output or text")
    try:
        return structured.model_validate(_json_from_text(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise GeminiUnavailable("Gemini structured response could not be parsed") from exc


def _generate_sync(prompt: str, *, model: str, structured: type[BaseModel] | None) -> str | BaseModel:
    try:
        from google import genai
        from google.genai import types
    except Exception as exc:  # pragma: no cover - depends on optional environment
        raise GeminiUnavailable("Gemini SDK is not installed or could not be imported") from exc

    config = None
    if structured is not None:
        schema = structured
        try:
            config = types.GenerateContentConfig(**{"response_mime_type": "application/json", "response_schema": schema})
        except TypeError:  # older SDKs accepted camelCase kwargs
            config = types.GenerateContentConfig(**{"responseMimeType": "application/json", "responseSchema": schema})

    try:
        client = genai.Client(api_key=_api_key())
        response = client.models.generate_content(model=model, contents=prompt, config=config)
    except GeminiUnavailable:
        raise
    except Exception as exc:  # no secrets in message
        raise GeminiUnavailable(f"Gemini generation failed: {exc.__class__.__name__}") from exc

    if structured is not None:
        return _coerce_structured(response, structured)

    text = getattr(response, "text", None)
    if text is None:
        raise GeminiUnavailable("Gemini response did not include text")
    return text


async def generate(prompt: str, *, model: str = PRO_MODEL, structured: type[BaseModel] | None = None) -> str | BaseModel:
    """Return generated text, or a Pydantic instance when ``structured`` is provided."""

    return await asyncio.to_thread(_generate_sync, prompt, model=model, structured=structured)
