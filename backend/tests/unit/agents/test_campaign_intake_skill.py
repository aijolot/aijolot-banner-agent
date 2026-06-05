from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from app.agents.tools import gemini_text
from app.schemas.campaign import StructuredBrief


def _load_skill():
    path = Path(__file__).resolve().parents[3] / "app" / "agents" / "skills" / "campaign-intake" / "impl.py"
    spec = importlib.util.spec_from_file_location("test_campaign_intake_impl", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_uses_deterministic_fallback_by_default(monkeypatch):
    monkeypatch.delenv("AIJOLOT_INTAKE_PROVIDER", raising=False)
    skill = _load_skill()

    result = asyncio.run(skill.run([
        {"author_type": "user", "body": "Black Friday 50% off para mujeres, urgencia alta, home hero"}
    ]))

    assert result.metadata["provider"] == "deterministic"
    assert result.metadata["fallback"] is True
    assert result.structured_brief.urgency == "high"
    assert "mujeres" in result.structured_brief.audience.lower()
    assert "cta" in result.structured_brief.missing()
    assert result.question


def test_brief_captures_promo_and_proposes_variants_on_split_cue(monkeypatch):
    monkeypatch.delenv("AIJOLOT_INTAKE_PROVIDER", raising=False)
    skill = _load_skill()

    result = asyncio.run(skill.run([{
        "author_type": "user",
        "body": "Promo de verano con 15% de descuento, personalizar por género hombre y mujer, jóvenes, botón Comprar ya, en el hero",
    }]))

    brief = result.structured_brief
    assert brief.promo == "15% OFF"
    assert brief.personalization_dimension == "gender"
    assert {v.key for v in brief.personalization_variants} == {"male", "female"}
    assert {v.customer_tag for v in brief.personalization_variants} == {"gender:male", "gender:female"}
    assert result.metadata["promo"] == "15% OFF"
    assert result.metadata["proposed_variants"] == ["male", "female"]
    # origin tags present + no fabricated facts
    assert result.metadata["origin_tags"]["personalization_variants"] == "[KG-RETRIEVED]"


def test_brief_does_not_force_variants_without_split_cue(monkeypatch):
    monkeypatch.delenv("AIJOLOT_INTAKE_PROVIDER", raising=False)
    skill = _load_skill()

    # A single-audience mention is NOT a split → Recommend-Nothing.
    result = asyncio.run(skill.run([{
        "author_type": "user",
        "body": "Banner para mujeres jóvenes, botón Comprar ya, en el hero, urgente",
    }]))

    assert result.structured_brief.personalization_variants == []
    assert result.metadata["proposed_variants"] == []


def test_skill_returns_monkeypatched_gemini_structured_success(monkeypatch):
    monkeypatch.setenv("AIJOLOT_INTAKE_PROVIDER", "gemini")
    skill = _load_skill()

    async def fake_generate(prompt, *, model, structured):
        assert "Conversation transcript JSON" in prompt
        assert '"role": "user"' in prompt
        assert "user: haz banner completo" not in prompt
        return structured(
            goal="Liquidar audífonos con 50% OFF",
            audience="mujeres 25-40",
            cta="Comprar ahora",
            tone="Premium",
            urgency="high",
            placement="Home · Hero",
            deadline=None,
            question=None,
        )

    monkeypatch.setattr(gemini_text, "generate", fake_generate)

    result = asyncio.run(skill.run([{"author_type": "user", "body": "haz banner completo"}]))

    assert result.metadata["provider"] == "gemini"
    assert result.metadata["fallback"] is False
    assert result.metadata["proposed_variants"] == []  # no split cue → Recommend-Nothing
    assert "origin_tags" in result.metadata
    assert result.complete is True
    assert result.question is None
    assert result.structured_brief.cta == "Comprar ahora"


def test_skill_falls_back_when_gemini_unavailable(monkeypatch):
    monkeypatch.setenv("AIJOLOT_INTAKE_PROVIDER", "gemini")
    skill = _load_skill()

    async def unavailable(*args, **kwargs):
        raise gemini_text.GeminiUnavailable("no credentials")

    monkeypatch.setattr(gemini_text, "generate", unavailable)

    result = asyncio.run(skill.run(
        [{"author_type": "user", "body": "CTA: Comprar ya"}],
        current_brief=StructuredBrief(goal="Promo", audience="clientes", urgency="medium", placement="Home · Hero"),
    ))

    assert result.metadata["provider"] == "deterministic"
    assert result.metadata["fallback"] is True
    assert "no credentials" in result.metadata["reason"]
    assert result.complete is True
    assert result.structured_brief.cta == "Comprar ya"


def test_deterministic_fallback_with_current_brief_uses_only_latest_user_turn(monkeypatch):
    monkeypatch.setenv("AIJOLOT_INTAKE_PROVIDER", "gemini")
    skill = _load_skill()

    async def unavailable(*args, **kwargs):
        raise gemini_text.GeminiUnavailable("no credentials")

    monkeypatch.setattr(gemini_text, "generate", unavailable)

    result = asyncio.run(skill.run(
        [
            {"author_type": "user", "body": "Campaña para mujeres, urgencia alta, home hero"},
            {"author_type": "agent", "body": "¿CTA?"},
            {"author_type": "user", "body": "CTA: Comprar ya"},
        ],
        current_brief=StructuredBrief(
            goal="Promo actual",
            audience="clientes VIP",
            urgency="medium",
            placement="Colección · Cabecera",
        ),
    ))

    assert result.metadata["provider"] == "deterministic"
    assert result.structured_brief.audience == "clientes VIP"
    assert result.structured_brief.urgency == "medium"
    assert result.structured_brief.placement == "Colección · Cabecera"
    assert result.structured_brief.cta == "Comprar ya"


def test_gemini_urgency_is_normalized_and_unknown_is_ignored(monkeypatch):
    monkeypatch.setenv("AIJOLOT_INTAKE_PROVIDER", "gemini")
    skill = _load_skill()

    async def asap_generate(*args, **kwargs):
        structured = kwargs["structured"]
        return structured(
            goal="Promo",
            audience="clientes",
            cta="Comprar",
            urgency="ASAP",
            placement="Home · Hero",
        )

    monkeypatch.setattr(gemini_text, "generate", asap_generate)
    result = asyncio.run(skill.run([{"author_type": "user", "body": "brief"}]))
    assert result.structured_brief.urgency == "high"
    assert result.complete is True

    async def unknown_generate(*args, **kwargs):
        structured = kwargs["structured"]
        return structured(
            goal="Promo",
            audience="clientes",
            cta="Comprar",
            urgency="whenever-ish",
            placement="Home · Hero",
        )

    monkeypatch.setattr(gemini_text, "generate", unknown_generate)
    result = asyncio.run(skill.run([{"author_type": "user", "body": "brief"}]))
    assert result.structured_brief.urgency == ""
    assert "urgency" in result.structured_brief.missing()
    assert result.complete is False


def test_gemini_empty_strings_do_not_erase_current_brief(monkeypatch):
    monkeypatch.setenv("AIJOLOT_INTAKE_PROVIDER", "gemini")
    skill = _load_skill()

    async def empty_string_generate(*args, **kwargs):
        structured = kwargs["structured"]
        return structured(
            goal="",
            audience="  ",
            cta="Comprar ahora",
            urgency="",
            placement=None,
        )

    monkeypatch.setattr(gemini_text, "generate", empty_string_generate)
    result = asyncio.run(skill.run(
        [{"author_type": "user", "body": "CTA: Comprar ahora"}],
        current_brief=StructuredBrief(
            goal="Promo actual",
            audience="clientes VIP",
            urgency="medium",
            placement="Home · Hero",
        ),
    ))

    assert result.structured_brief.goal == "Promo actual"
    assert result.structured_brief.audience == "clientes VIP"
    assert result.structured_brief.urgency == "medium"
    assert result.structured_brief.placement == "Home · Hero"
    assert result.structured_brief.cta == "Comprar ahora"
