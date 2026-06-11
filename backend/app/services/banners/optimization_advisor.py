"""OptimizationAdvisor (F2) — fatigue signal → refresh suggestion.

Turns a :class:`FatigueSignal` into an ``agent_suggestions`` row
(kind='performance_refresh') with concrete proposed changes. Proposed changes
come from Gemini when available, else a deterministic Spanish refresh template.
Accepting the suggestion starts a refinement run with these instructions.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agents.tools import gemini_text
from app.services.banners.fatigue_detector import FatigueSignal

EST_ADVICE_USD = 0.002

def _deterministic_changes(lang: str) -> list[str]:
    from app.core.i18n import t

    return [t(lang, "perf.change_headline"), t(lang, "perf.change_background"), t(lang, "perf.change_cta")]


class _ProposedChanges(BaseModel):
    changes: list[str] = Field(default_factory=list)


async def _proposed_changes(signal: FatigueSignal, *, settings: Any = None, cost_guard: Any = None, lang: str = "es") -> tuple[list[str], str]:
    from app.core.i18n import lang_name

    fallback = _deterministic_changes(lang)
    if settings is None or not getattr(settings, "has_google_api_key", lambda: False)():
        return fallback, "deterministic"
    try:
        from app.services.gemini.cost_guard import get_default_cost_guard

        guard = cost_guard or get_default_cost_guard(settings)
        if not guard.check_and_reserve(EST_ADVICE_USD).allowed:
            return fallback, "deterministic"
        result = await gemini_text.generate(
            "An ecommerce banner is fatiguing: " + signal.reason + " Propose exactly 3 concrete refresh changes "
            f"(copy / background / CTA) a banner agent can apply, each ONE sentence in {lang_name(lang)}. "
            "Return JSON {changes:[...]}.",
            model=gemini_text.FLASH_MODEL,
            structured=_ProposedChanges,
        )
        changes = [c.strip()[:200] for c in (result.changes if isinstance(result, _ProposedChanges) else []) if c.strip()]
        return (changes[:3], "gemini") if changes else (fallback, "deterministic")
    except Exception:  # noqa: BLE001 — advice is best-effort
        return fallback, "deterministic"


async def propose_refresh(
    signal: FatigueSignal,
    *,
    suggestions: Any,  # SuggestionService
    campaign_title: str = "",
    settings: Any = None,
    cost_guard: Any = None,
    lang: str = "es",
) -> dict[str, Any]:
    """Upsert the performance_refresh suggestion for this campaign+signal."""
    from app.core.i18n import t

    changes, source = await _proposed_changes(signal, settings=settings, cost_guard=cost_guard, lang=lang)
    label = campaign_title or signal.campaign_id[:8]
    return suggestions.upsert_by_dedupe_key(
        kind="performance_refresh",
        dedupe_key=f"perf:{signal.campaign_id}:{signal.kind}",
        title=t(lang, "perf.title", label=label),
        rationale=signal.reason + t(lang, "perf.rationale_suffix"),
        payload={
            "trigger": {"kind": signal.kind, **signal.metrics},
            "proposed_changes": changes,
            "changes_source": source,
            "refresh_prompt": t(lang, "perf.refresh_prompt", changes=" ".join(changes)),
        },
        campaign_id=signal.campaign_id,
        source_refs=[{"type": "performance", "id": signal.campaign_id, "title": "Snapshots de performance"}],
    )


def refresh_prompt_from_suggestion(suggestion_row: dict[str, Any]) -> str:
    payload = dict(suggestion_row.get("payload") or {})
    prompt = str(payload.get("refresh_prompt") or "").strip()
    if prompt:
        return prompt
    changes = [str(c) for c in (payload.get("proposed_changes") or [])]
    from app.core.i18n import t

    lang = str((payload.get("trigger") or {}).get("lang") or "es")
    return t(lang, "perf.refresh_prompt", changes=" ".join(changes or _deterministic_changes(lang)))
