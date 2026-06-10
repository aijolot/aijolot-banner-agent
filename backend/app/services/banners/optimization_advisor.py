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

_DETERMINISTIC_CHANGES = [
    "Renueva el headline con un ángulo de beneficio distinto (mismo tono de marca).",
    "Cambia el fondo a una variante fresca de la paleta para romper la ceguera del banner.",
    "Prueba un CTA de acción distinta (p. ej. de 'Compra ahora' a 'Descubre la colección').",
]


class _ProposedChanges(BaseModel):
    changes: list[str] = Field(default_factory=list)


async def _proposed_changes(signal: FatigueSignal, *, settings: Any = None, cost_guard: Any = None) -> tuple[list[str], str]:
    if settings is None or not getattr(settings, "has_google_api_key", lambda: False)():
        return list(_DETERMINISTIC_CHANGES), "deterministic"
    try:
        from app.services.gemini.cost_guard import get_default_cost_guard

        guard = cost_guard or get_default_cost_guard(settings)
        if not guard.check_and_reserve(EST_ADVICE_USD).allowed:
            return list(_DETERMINISTIC_CHANGES), "deterministic"
        result = await gemini_text.generate(
            "An ecommerce banner is fatiguing: " + signal.reason + " Propose exactly 3 concrete refresh changes "
            "(copy / background / CTA) a banner agent can apply, each ONE sentence in Spanish. "
            "Return JSON {changes:[...]}.",
            model=gemini_text.FLASH_MODEL,
            structured=_ProposedChanges,
        )
        changes = [c.strip()[:200] for c in (result.changes if isinstance(result, _ProposedChanges) else []) if c.strip()]
        return (changes[:3], "gemini") if changes else (list(_DETERMINISTIC_CHANGES), "deterministic")
    except Exception:  # noqa: BLE001 — advice is best-effort
        return list(_DETERMINISTIC_CHANGES), "deterministic"


async def propose_refresh(
    signal: FatigueSignal,
    *,
    suggestions: Any,  # SuggestionService
    campaign_title: str = "",
    settings: Any = None,
    cost_guard: Any = None,
) -> dict[str, Any]:
    """Upsert the performance_refresh suggestion for this campaign+signal."""
    changes, source = await _proposed_changes(signal, settings=settings, cost_guard=cost_guard)
    label = campaign_title or signal.campaign_id[:8]
    return suggestions.upsert_by_dedupe_key(
        kind="performance_refresh",
        dedupe_key=f"perf:{signal.campaign_id}:{signal.kind}",
        title=f"Refresca el banner de «{label}»",
        rationale=signal.reason + " Propongo un refresh dirigido para recuperar el CTR.",
        payload={
            "trigger": {"kind": signal.kind, **signal.metrics},
            "proposed_changes": changes,
            "changes_source": source,
            "refresh_prompt": "Refresca el banner sin salir de marca: " + " ".join(changes),
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
    return "Refresca el banner sin salir de marca: " + " ".join(changes or _DETERMINISTIC_CHANGES)
