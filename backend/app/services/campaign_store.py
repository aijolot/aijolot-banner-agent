"""Campaign intake store + rule-based brief extractor (GH-27).

In-memory campaign store (mirrors the ``campaigns`` / ``campaign_messages``
tables) plus a deterministic, rule-based "intake agent" that extracts a
StructuredBrief from free text. This is the seam where a real Gemini Flash call
plugs in later — :func:`extract_into` would be replaced by a model call, the
rest of the plumbing (store, messages, SSE) stays the same.
"""

from __future__ import annotations

import itertools
import re

from app.schemas.campaign import Campaign, CampaignMessage, StructuredBrief

_campaigns: dict[str, Campaign] = {}
_ids = itertools.count(1)

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


# ---- store ----
def create_campaign() -> Campaign:
    cid = f"cmp_{next(_ids):04d}"
    c = Campaign(id=cid)
    _campaigns[cid] = c
    return c


def get_campaign(cid: str) -> Campaign | None:
    return _campaigns.get(cid)


def intake(message: str, campaign_id: str | None) -> tuple[Campaign, str]:
    """Process one user turn. Returns (campaign, agent_reply_text)."""
    c = (_campaigns.get(campaign_id) if campaign_id else None) or create_campaign()
    c.messages.append(CampaignMessage(author_type="user", body=message))
    if not c.raw_brief:
        c.raw_brief = message
    c.structured_brief = extract_into(c.structured_brief, message)
    if not c.title:
        c.title = _title(c.structured_brief, message)
    reply = _agent_reply(c.structured_brief)
    c.messages.append(CampaignMessage(author_type="agent", body=reply))
    _campaigns[c.id] = c
    return c, reply
