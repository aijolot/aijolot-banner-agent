"""art-prompt-propose skill (F8, step 1).

Propose descriptive image prompts (text only). Two modes:
- hero  → N distinct stylistic directions for the hero background/scene.
- usage → the SAME model/product description across predefined camera angles.
Also proposes model descriptions by gender. Gemini FLASH (structured) when
available + within cost cap; deterministic fallback otherwise. Every prompt is
sanitized through image-prompt-refine.
"""

from __future__ import annotations

from typing import Any

from app.agents.tools import gemini_text
from app.core.settings import Settings
from app.schemas.art_prompts import USAGE_ANGLES, PromptOption, PromptOptionsOutput

EST_ART_PROMPT_USD = 0.002
_LABELS = ("A", "B", "C", "D")
_HERO_STYLES = (
    ("Editorial studio", "studio lighting, seamless backdrop, premium editorial mood"),
    ("Lifestyle natural", "natural daylight lifestyle scene, soft shadows, airy negative space"),
    ("Bold graphic", "bold high-contrast graphic composition, saturated brand tones"),
    ("Minimal premium", "minimal premium set, generous negative space, refined neutral palette"),
)


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_refine() -> Any:
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "image-prompt-refine" / "impl.py"
    spec = importlib.util.spec_from_file_location("art_prompt_refine_dep", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _sanitize(prompt: str, brand_context: Any) -> str:
    refine = _load_refine()
    return await refine.run(prompt, brand_context=brand_context)


def _base_subject(concept: Any) -> str:
    copy = _get(concept, "copy", {}) or {}
    headline = _get(copy, "headline", "") if isinstance(copy, dict) else ""
    image_prompt = _get(concept, "image_prompt", "")
    return str(image_prompt or headline or "featured product scene")


async def _deterministic_hero(concept: Any, brand_context: Any, count: int) -> list[PromptOption]:
    base = _base_subject(concept)
    options: list[PromptOption] = []
    for index in range(count):
        name, style = _HERO_STYLES[index % len(_HERO_STYLES)]
        prompt = await _sanitize(f"{base}, {style}", brand_context)
        options.append(PromptOption(label=_LABELS[index], description=name, prompt=prompt))
    return options


async def _deterministic_usage(concept: Any, brand_context: Any, count: int, background_ref: str | None) -> list[PromptOption]:
    base = _base_subject(concept)
    options: list[PromptOption] = []
    for index in range(count):
        angle = USAGE_ANGLES[index % len(USAGE_ANGLES)]
        # Same subject description across angles for consistency; only the angle differs.
        prompt = await _sanitize(f"{base}, {angle.replace('_', ' ')} camera angle of the same subject", brand_context)
        options.append(
            PromptOption(
                label=_LABELS[index],
                description=f"{angle.replace('_', ' ').title()} angle",
                prompt=prompt,
                angle=angle,
                background_ref=background_ref,
            )
        )
    return options


async def _deterministic_models(concept: Any, brand_context: Any, gender: str, base_prompt: str, count: int) -> list[PromptOption]:
    subject = base_prompt or _base_subject(concept)
    looks = ("relaxed candid pose", "confident editorial pose", "dynamic in-motion pose", "calm seated pose")
    gender_phrase = f"{gender.strip()} model" if gender.strip() else "model"
    options: list[PromptOption] = []
    for index in range(count):
        look = looks[index % len(looks)]
        prompt = await _sanitize(f"{gender_phrase}, {look}, presenting {subject}", brand_context)
        options.append(PromptOption(label=_LABELS[index], description=look.title(), prompt=prompt))
    return options


def _resolved_settings(settings: Any) -> Settings:
    return settings or Settings.from_env()


def _guard_allows(cost_guard: Any, settings: Settings) -> bool:
    from app.services.gemini.cost_guard import get_default_cost_guard

    guard = cost_guard or get_default_cost_guard(settings)
    return bool(guard.check_and_reserve(EST_ART_PROMPT_USD).allowed)


async def _gemini_options(prompt: str, brand_context: Any, count: int, *, angles: list[str] | None, background_ref: str | None) -> list[PromptOption]:
    result = await gemini_text.generate(prompt, model=gemini_text.FLASH_MODEL, structured=PromptOptionsOutput)
    raw = list(getattr(result, "options", []) or [])[:count]
    options: list[PromptOption] = []
    for index, opt in enumerate(raw):
        sanitized = await _sanitize(str(_get(opt, "prompt", "")), brand_context)
        if not sanitized:
            continue
        options.append(
            PromptOption(
                label=_LABELS[index] if index < len(_LABELS) else str(index + 1),
                description=str(_get(opt, "description", "")),
                prompt=sanitized,
                angle=(angles[index] if angles and index < len(angles) else _get(opt, "angle", None)),
                background_ref=background_ref,
            )
        )
    return options


async def run(
    concept: Any,
    brand_context: Any,
    *,
    shot_type: str = "hero",
    count: int = 3,
    background_ref: str | None = None,
    settings: Any = None,
    cost_guard: Any = None,
) -> tuple[list[PromptOption], str]:
    count = max(1, min(int(count or 3), 4))
    resolved = _resolved_settings(settings)
    angles = list(USAGE_ANGLES[:count]) if shot_type == "usage" else None

    if resolved.has_google_api_key() and _guard_allows(cost_guard, resolved):
        try:
            base = _base_subject(concept)
            if shot_type == "usage":
                instruction = (
                    f"Propose {count} image prompts of the SAME subject from these camera angles: "
                    f"{', '.join(angles or [])}. Keep the model/product description IDENTICAL across all; "
                    f"only the angle changes. Subject: {base}."
                )
            else:
                instruction = (
                    f"Propose {count} DISTINCT stylistic directions for this banner hero image. Subject: {base}."
                )
            instruction += (
                " Each prompt describes photographic/background composition ONLY — no text, logos, UI, or faces "
                "baked into the image; leave clean negative space for HTML copy. Return JSON matching the schema."
            )
            options = await _gemini_options(instruction, brand_context, count, angles=angles, background_ref=background_ref)
            if options:
                return options, "gemini"
        except gemini_text.GeminiUnavailable:
            pass

    if shot_type == "usage":
        return await _deterministic_usage(concept, brand_context, count, background_ref), "deterministic"
    return await _deterministic_hero(concept, brand_context, count), "deterministic"


async def propose_models(
    concept: Any,
    brand_context: Any,
    *,
    gender: str = "",
    base_prompt: str = "",
    count: int = 3,
    settings: Any = None,
    cost_guard: Any = None,
) -> tuple[list[PromptOption], str]:
    count = max(1, min(int(count or 3), 4))
    resolved = _resolved_settings(settings)

    if resolved.has_google_api_key() and _guard_allows(cost_guard, resolved):
        try:
            subject = base_prompt or _base_subject(concept)
            gender_phrase = f"{gender.strip()} " if gender.strip() else ""
            instruction = (
                f"Propose {count} DISTINCT {gender_phrase}model descriptions presenting this product. "
                f"Reuse the SAME product description across variants; vary pose/styling/mood. Subject: {subject}. "
                "Describe photographic composition only — no baked-in text/logos/UI. Return JSON matching the schema."
            )
            options = await _gemini_options(instruction, brand_context, count, angles=None, background_ref=None)
            if options:
                return options, "gemini"
        except gemini_text.GeminiUnavailable:
            pass

    return await _deterministic_models(concept, brand_context, gender, base_prompt, count), "deterministic"
