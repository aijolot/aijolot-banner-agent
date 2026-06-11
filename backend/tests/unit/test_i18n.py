"""i18n ES/EN: el idioma gobierna todo lo que el cliente ve, sin mezclas."""

from __future__ import annotations

import asyncio
from datetime import date

from app.core.i18n import campaign_lang, lang_name, resolve_lang, t


def test_resolve_and_names() -> None:
    assert resolve_lang("EN") == "en"
    assert resolve_lang("es-MX") == "es"
    assert resolve_lang(None) == "es"
    assert resolve_lang("fr") == "es"  # no soportado → default
    assert lang_name("en") == "English"


def test_campaign_lang_reads_brief() -> None:
    assert campaign_lang({"structured_brief": {"language": "en"}}) == "en"
    assert campaign_lang({"structured_brief": {}}) == "es"


def test_catalog_has_both_langs_for_every_key() -> None:
    from app.core.i18n import _MESSAGES

    missing = [k for k, v in _MESSAGES.items() if "es" not in v or "en" not in v]
    assert not missing, f"keys sin ambos idiomas: {missing}"


def test_decision_trace_localizes_fully() -> None:
    from app.schemas.decision_trace import build_concept_trace

    class _Concept:
        layout = "Hero split layout"
        copy = {"copy_source": "deterministic"}
        source_refs = []

    es = build_concept_trace(concept=_Concept(), best_practices=[], brand=None, lang="es")
    en = build_concept_trace(concept=_Concept(), best_practices=[], brand=None, lang="en")
    assert any("determinista" in r for r in es.reasons)
    assert any("deterministic layout" in r for r in en.reasons)
    assert not any("determinista" in r for r in en.reasons)  # sin mezcla


def test_calendar_suggestions_in_english() -> None:
    from app.services.banners.calendar_service import CalendarService, InMemoryCalendarRepository
    from app.services.banners.suggestion_service import InMemoryAgentSuggestions, SuggestionService

    suggestions = SuggestionService(suggestions=InMemoryAgentSuggestions(), team_id="t-en")
    svc = CalendarService(repo=InMemoryCalendarRepository(), suggestions=suggestions, team_id="t-en")
    svc.update_settings({"lang": "en"})
    svc.scan_upcoming(today=date(2026, 6, 9))  # Día del Padre dentro de ventana
    padre = next(s for s in suggestions.list() if "Padre" in s.title)
    assert padre.title.startswith("Prepare your")
    brief = padre.payload["structured_brief"]
    assert brief["language"] == "en"
    assert brief["cta"] == "Shop now"
    assert "Agent-proposed brief" in padre.payload["raw_brief"]


def test_mode_and_pieces_localize() -> None:
    from app.workflows.banner_creation import _load_runtime_skill

    mode = _load_runtime_skill("creative-mode-recommend")
    rec_en = asyncio.run(mode.recommend({"structured_brief": {"goal": "fashion launch"}}, None, lang="en"))
    assert "Lifestyle/fashion" in rec_en.rationale

    pieces = _load_runtime_skill("placement-plan-recommend")
    plan_en = asyncio.run(pieces.recommend({"structured_brief": {"goal": "sale", "promo": "2x1"}}, None, lang="en"))
    assert "above-the-fold" in plan_en.pieces[0].rationale
    assert "store-wide" in plan_en.pieces[1].rationale


def test_intake_reply_in_english() -> None:
    from app.schemas.campaign import StructuredBrief
    from app.services.campaign_store import _agent_reply

    brief = StructuredBrief(language="en", goal="Summer sale")
    reply = _agent_reply(brief)
    assert "I still need" in reply or "the brief is complete" in reply
    assert "me falta" not in reply
