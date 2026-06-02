"""campaign-intake skill — see SKILL.md.

Gemini-backed structured extraction is opt-in via AIJOLOT_INTAKE_PROVIDER=gemini.
All other modes, missing credentials, or provider failures use the deterministic
extractor already exercised by backend API tests.
"""

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents.tools import gemini_text
from app.schemas.campaign import StructuredBrief

_PROVIDER_ENV = "AIJOLOT_INTAKE_PROVIDER"
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "intake.md"


class GeminiIntakeOutput(BaseModel):
    """Strict JSON shape requested from Gemini for one intake turn."""

    goal: str | None = None
    audience: str | None = None
    cta: str | None = None
    tone: str | None = None
    urgency: Literal["low", "medium", "high"] | str | None = None
    placement: str | None = None
    deadline: str | None = None
    question: str | None = None


class CampaignIntakeResult(BaseModel):
    """Skill result consumed by the service layer and unit tests."""

    structured_brief: StructuredBrief = Field(default_factory=StructuredBrief)
    question: str | None = None
    complete: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


def _prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _message_text(message: dict[str, Any]) -> str:
    body = message.get("body", message.get("content", message.get("text", "")))
    return str(body or "")


def _author(message: dict[str, Any]) -> str:
    return str(message.get("author_type", message.get("role", "user")) or "user")


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if _author(message) == "user":
            return _message_text(message)
    return _message_text(messages[-1]) if messages else ""


def _brief_has_values(brief: StructuredBrief | None) -> bool:
    if brief is None:
        return False
    return any((value or "").strip() if isinstance(value, str) else value for value in brief.model_dump().values())


def _fallback(messages: list[dict[str, Any]], current_brief: StructuredBrief | None, *, reason: str) -> CampaignIntakeResult:
    from app.services.campaign_store import _agent_reply, extract_into

    brief = current_brief or StructuredBrief()
    # When a current brief exists, only apply the latest user turn. Replaying the
    # whole transcript can let stale historical text overwrite manually patched
    # or otherwise current values because extract_into uses "new values win".
    source_messages = messages
    if _brief_has_values(current_brief):
        latest_user = next((message for message in reversed(messages) if _author(message) == "user"), None)
        source_messages = [latest_user] if latest_user is not None else []
    for message in source_messages:
        if _author(message) == "user":
            brief = extract_into(brief, _message_text(message))
    question = None if brief.is_complete() else _agent_reply(brief)
    return CampaignIntakeResult(
        structured_brief=brief,
        question=question,
        complete=brief.is_complete(),
        metadata={"provider": "deterministic", "fallback": True, "reason": reason},
    )


def _normalize_urgency(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if text in {"high", "alta", "urgent", "urgente", "asap", "cuanto antes", "ya", "ya mismo"}:
        return "high"
    if text in {"medium", "media", "soon", "pronto"}:
        return "medium"
    if text in {"low", "baja", "no rush", "sin prisa", "no hay prisa"}:
        return "low"
    return ""


def _merge_output(current_brief: StructuredBrief | None, output: GeminiIntakeOutput) -> StructuredBrief:
    data = (current_brief or StructuredBrief()).model_dump()
    for key in ("goal", "audience", "cta", "tone", "urgency", "placement", "deadline"):
        value = getattr(output, key)
        if value is not None:
            if key == "urgency":
                urgency = _normalize_urgency(value)
                if urgency:
                    data[key] = urgency
                continue
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    data[key] = stripped
            else:
                data[key] = value
    # The app schema uses empty strings for missing text fields.
    for key in ("goal", "audience", "cta", "tone", "urgency", "placement"):
        if data.get(key) is None:
            data[key] = ""
    return StructuredBrief(**data)


def _render_prompt(messages: list[dict[str, Any]], brand_context: Any, current_brief: StructuredBrief | None) -> str:
    transcript = json.dumps(
        [{"role": _author(message), "body": _message_text(message)} for message in messages],
        ensure_ascii=False,
    )
    try:
        brand_payload = brand_context.model_dump() if hasattr(brand_context, "model_dump") else brand_context
        brand_json = json.dumps(brand_payload, ensure_ascii=False, default=str)
    except TypeError:
        brand_json = json.dumps(str(brand_context), ensure_ascii=False)
    return (
        f"{_prompt_template()}\n\n"
        "Return only JSON matching the schema. Preserve known fields unless the latest user turn updates them.\n\n"
        f"Current brief JSON:\n{(current_brief or StructuredBrief()).model_dump_json()}\n\n"
        f"Brand context JSON:\n{brand_json}\n\n"
        f"Conversation transcript JSON:\n{transcript}\n\n"
        f"Latest user message JSON:\n{json.dumps(_last_user_text(messages), ensure_ascii=False)}"
    )


async def run(
    messages: list[dict[str, Any]],
    brand_context: Any = None,
    current_brief: StructuredBrief | dict[str, Any] | None = None,
) -> CampaignIntakeResult:
    """Extract/merge structured campaign intake from a transcript.

    Set ``AIJOLOT_INTAKE_PROVIDER=gemini`` to enable Gemini. Without that flag,
    or when Gemini is unavailable, the deterministic extractor is returned.
    """

    brief = current_brief if isinstance(current_brief, StructuredBrief) else StructuredBrief(**(current_brief or {}))
    provider = os.getenv(_PROVIDER_ENV, "").strip().lower()
    if provider != "gemini":
        return _fallback(messages, brief, reason=f"{_PROVIDER_ENV} is not 'gemini'")

    try:
        output = await gemini_text.generate(
            _render_prompt(messages, brand_context, brief),
            model=gemini_text.FLASH_MODEL,
            structured=GeminiIntakeOutput,
        )
    except Exception as exc:
        return _fallback(messages, brief, reason=str(exc))

    if not isinstance(output, GeminiIntakeOutput):
        return _fallback(messages, brief, reason="Gemini returned an unexpected output type")

    merged = _merge_output(brief, output)
    question = (output.question or "").strip() or None
    if merged.is_complete():
        question = None
    elif question is None:
        from app.services.campaign_store import _agent_reply

        question = _agent_reply(merged)
    return CampaignIntakeResult(
        structured_brief=merged,
        question=question,
        complete=merged.is_complete(),
        metadata={"provider": "gemini", "fallback": False},
    )
