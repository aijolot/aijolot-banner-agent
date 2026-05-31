"""Campaign intake service facade + rule-based brief extractor.

Runtime storage is Supabase-backed when the required Supabase/team/store
settings are configured. In local tests/dev with no Supabase configuration, the
service falls back to an in-memory store while preserving the existing SSE
contract and deterministic extraction seam.
"""

from __future__ import annotations

import os
import re

from app.core.settings import MissingSettingsError, Settings
from app.schemas.campaign import Campaign, StructuredBrief
from app.services.banners.campaign_service import CampaignService
from app.services.supabase.client import SupabaseClientFactory

FIELD_LABELS_ES = {
    "goal": "objetivo de la campaña",
    "audience": "audiencia",
    "cta": "texto del botón (CTA)",
    "urgency": "urgencia",
    "placement": "ubicación",
}


# ---- extraction ----
def _urgency(text: str) -> str:
    t = text.lower()
    if re.search(r"urgenc\w*\s*(alta|máxima|maxima)|alta\s*urgenc|black\s*friday|hoy|última hora|ultima hora|cuanto antes|ya mismo|urgent", t):
        return "high"
    if re.search(r"urgenc\w*\s*media|pronto|esta semana|this week|soon|medium", t):
        return "medium"
    if re.search(r"urgenc\w*\s*baja|sin prisa|no hay prisa|no rush|low", t):
        return "low"
    return ""


def _audience(text: str) -> str:
    m = re.search(r"\b(?:a|para)\s+((?:mujeres|hombres|clientes|j[oó]venes|adultos|ni[ñn]os|gen\s*z|millennials|vip)[^.,;\n]*)", text, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"audiencia[:\s]+([^.,;\n]+)", text, re.I)
    return m.group(1).strip() if m else ""


def _placement(text: str) -> str:
    t = text.lower()
    mapping = [
        (r"\bhero\b", "Home · Hero"),
        (r"\b(home|inicio|portada)\b", "Home · Hero"),
        (r"\b(colecci[oó]n|collection)\b", "Colección · Cabecera"),
        (r"\b(producto|product|pdp)\b", "Producto · Franja"),
        (r"\b(b[uú]squeda|search)\b", "Búsqueda · Resultados"),
        (r"\bfooter\b", "Footer · CTA"),
    ]
    for pat, label in mapping:
        if re.search(pat, t):
            return label
    return ""


def _promo(text: str) -> str:
    m = re.search(r"(\d{1,3})\s*%\s*(?:off|de\s+descuento|descuento|dto)", text, re.I)
    if m:
        return f"{m.group(1)}% OFF"
    if re.search(r"\b2x1\b", text, re.I):
        return "2x1"
    if re.search(r"\bbogo\b", text, re.I):
        return "BOGO"
    return ""


def _cta(text: str) -> str:
    m = re.search(r'\bcta[:\s]+["“]?([^"”.\n]{2,40})', text, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r'bot[oó]n[:\s]+["“]?([^"”.\n]{2,40})', text, re.I)
    return m.group(1).strip() if m else ""


def _deadline(text: str) -> str | None:
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if m:
        return m.group(1)
    m = re.search(r"del\s+\d{1,2}\s+al\s+\d{1,2}\s+de\s+\w+", text, re.I)
    return m.group(0) if m else None


def _tone(text: str) -> str:
    t = text.lower()
    for kw, label in [("premium", "Premium"), ("elegante", "Elegante"), ("divertid", "Divertido"),
                      ("urgent", "Urgente"), ("minimal", "Minimal"), ("aspiracional", "Aspiracional")]:
        if kw in t:
            return label
    return ""


def extract_into(brief: StructuredBrief, text: str) -> StructuredBrief:
    """Merge fields extracted from ``text`` into ``brief`` (new values win)."""
    data = brief.model_dump()
    promo = _promo(text)
    found = {
        "audience": _audience(text),
        "placement": _placement(text),
        "cta": _cta(text),
        "tone": _tone(text),
        "urgency": _urgency(text),
        "deadline": _deadline(text),
    }
    for k, v in found.items():
        if v:
            data[k] = v
    # goal: keep the first solid statement; seed from the message + promo.
    if not data["goal"].strip():
        goal = text.strip()
        if promo and promo.lower() not in goal.lower():
            goal = f"{goal} ({promo})"
        data["goal"] = goal[:160]
    return StructuredBrief(**data)


def _title(brief: StructuredBrief, text: str) -> str:
    if re.search(r"black\s*friday", text, re.I):
        return "Black Friday"
    promo = _promo(text)
    return (promo + " — campaña").strip(" —") if promo else (brief.goal[:40] or "Nueva campaña")


def _agent_reply(brief: StructuredBrief) -> str:
    missing = brief.missing()
    if not missing:
        return ("Listo — tengo el brief completo. Revisa los campos a la derecha, "
                "ajústalos si hace falta y avanza a Arte cuando quieras.")
    labels = [FIELD_LABELS_ES[f] for f in missing]
    captured = []
    if brief.audience: captured.append(f"audiencia «{brief.audience}»")
    if brief.placement: captured.append(f"ubicación «{brief.placement}»")
    if brief.urgency: captured.append(f"urgencia {brief.urgency}")
    pre = ("Voy capturando " + ", ".join(captured) + ". ") if captured else ""
    need = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " y " + labels[-1]
    return f"{pre}Para cerrar el brief me falta: {need}. ¿Me lo confirmas?"


# ---- store/service facade ----
_service: CampaignService | None = None


def _configured_service() -> CampaignService:
    settings = Settings.from_env()
    has_supabase_signal = any(
        (
            settings.supabase_url,
            settings.supabase_service_role_key,
            settings.supabase_team_id,
            settings.supabase_store_id,
        )
    )
    has_supabase = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    team_id = settings.supabase_team_id
    store_id = settings.supabase_store_id or os.getenv("CAMPAIGN_STORE_ID")
    if not has_supabase_signal:
        return CampaignService()
    if not has_supabase:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID",))

    client = SupabaseClientFactory(settings).service_role_client()
    if not store_id:
        from app.db.repositories.campaigns import CampaignRepository

        store_id = CampaignRepository(client).first_store_id(team_id=team_id)
    if not store_id:
        raise MissingSettingsError(("SUPABASE_STORE_ID",))
    return CampaignService.from_supabase_client(client, team_id=team_id, store_id=store_id)


def get_service() -> CampaignService:
    global _service
    if _service is None:
        _service = _configured_service()
    return _service


def set_service(service: CampaignService | None) -> None:
    """Override the runtime service in tests; pass None to rebuild from env."""

    global _service
    _service = service


def list_campaigns(limit: int = 100) -> list[Campaign]:
    return get_service().list_campaigns(limit=limit)


def create_campaign(title: str = "", raw_brief: str = "") -> Campaign:
    return get_service().create_campaign(title=title, raw_brief=raw_brief)


def get_campaign(cid: str) -> Campaign | None:
    return get_service().get_campaign(cid)


def apply_patch(cid: str, fields: dict) -> Campaign | None:
    """Apply a partial brief update (GH-28). Returns None if campaign unknown."""

    return get_service().apply_patch(cid, fields)


def intake(message: str, campaign_id: str | None) -> tuple[Campaign, str]:
    """Process one user turn. Returns (campaign, agent_reply_text)."""

    return get_service().intake(
        message,
        campaign_id,
        extractor=extract_into,
        title_builder=_title,
        reply_builder=_agent_reply,
    )
