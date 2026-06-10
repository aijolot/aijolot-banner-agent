"""Language plumbing (ES/EN) for every client-facing string the agent produces.

The language is a property of WHAT THE CLIENT SEES: it travels on the campaign
(``structured_brief.language``), is set from the UI switcher via the
``X-Aijolot-Lang`` header, and is threaded into every LLM prompt ("write in X")
and every deterministic template — so there is never a language mix in copy,
rationales, decision traces or suggestions.

KG citations (source titles) are shown verbatim as provenance, like quoting a
source — they are not translated.
"""

from __future__ import annotations

from typing import Any

SUPPORTED_LANGS = ("es", "en")
DEFAULT_LANG = "es"

_LANG_NAMES = {"es": "Spanish (Mexico)", "en": "English"}


def resolve_lang(value: Any) -> str:
    """Normalize any candidate ('ES', 'en-US', None…) to a supported lang."""
    cleaned = str(value or "").strip().lower()[:2]
    return cleaned if cleaned in SUPPORTED_LANGS else DEFAULT_LANG


def lang_name(lang: str) -> str:
    """Human name used inside LLM prompts ('Write in …')."""
    return _LANG_NAMES.get(resolve_lang(lang), _LANG_NAMES[DEFAULT_LANG])


def campaign_lang(campaign_row: Any) -> str:
    """Language of a campaign row/dict (structured_brief.language, default es)."""
    if campaign_row is None:
        return DEFAULT_LANG
    brief = campaign_row.get("structured_brief") if isinstance(campaign_row, dict) else getattr(campaign_row, "structured_brief", None)
    if isinstance(brief, dict):
        return resolve_lang(brief.get("language"))
    return resolve_lang(getattr(brief, "language", None))


def request_lang(request: Any) -> str:
    """Language from the X-Aijolot-Lang header (UI switcher)."""
    try:
        return resolve_lang(request.headers.get("X-Aijolot-Lang"))
    except Exception:  # noqa: BLE001
        return DEFAULT_LANG


def t(lang: str, key: str, **kwargs: Any) -> str:
    """Backend message catalog for deterministic client-facing strings."""
    lang = resolve_lang(lang)
    template = _MESSAGES.get(key, {}).get(lang) or _MESSAGES.get(key, {}).get(DEFAULT_LANG) or key
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


_MESSAGES: dict[str, dict[str, str]] = {
    # --- decision trace (F4) -------------------------------------------------
    "trace.decision.layout": {"es": "Layout: {layout}", "en": "Layout: {layout}"},
    "trace.decision.concept": {"es": "Concepto del banner", "en": "Banner concept"},
    "trace.layout_kg": {
        "es": "Layout «{title}» tomado del knowledge graph{when}.",
        "en": "Layout “{title}” retrieved from the knowledge graph{when}.",
    },
    "trace.layout_kg_when": {"es": " — aplica cuando: {when}", "en": " — applies when: {when}"},
    "trace.layout_deterministic": {
        "es": "Layout determinista por defecto: no hubo patrones del knowledge graph aplicables. [DETERMINISTIC]",
        "en": "Default deterministic layout: no applicable knowledge-graph patterns. [DETERMINISTIC]",
    },
    "trace.copy_gemini": {
        "es": "Copy redactado por el modelo a partir del brief, los productos y la voz de marca.",
        "en": "Copy written by the model from the brief, the products and the brand voice.",
    },
    "trace.copy_deterministic": {
        "es": "Copy de plantilla determinista (modelo no disponible o sin presupuesto). [DETERMINISTIC]",
        "en": "Deterministic template copy (model unavailable or out of budget). [DETERMINISTIC]",
    },
    "trace.best_practices": {"es": "Buenas prácticas aplicadas: {titles}.", "en": "Best practices applied: {titles}."},
    "trace.brand": {
        "es": "Paleta, tipografía y tono restringidos al brand context «{brand}».",
        "en": "Palette, typography and tone constrained to the “{brand}” brand context.",
    },
    # --- creative mode (C0) ---------------------------------------------------
    "mode.video": {
        "es": "El brief pide motion/lanzamiento en un hero principal y la generación de video está habilitada.",
        "en": "The brief calls for motion/launch on a main hero and video generation is enabled.",
    },
    "mode.composite": {
        "es": "Vertical orientado a producto/técnico: el recorte de producto sobre fondo de marca comunica mejor.",
        "en": "Product-led/technical vertical: a product cut-out over a brand background communicates best.",
    },
    "mode.full_picture": {
        "es": "Vertical lifestyle/moda: una escena completa generada vende el mood mejor que un recorte.",
        "en": "Lifestyle/fashion vertical: a fully generated scene sells the mood better than a cut-out.",
    },
    "mode.default": {
        "es": "Sin señales de lifestyle en el brief: recorte de producto (modo seguro por defecto).",
        "en": "No lifestyle signals in the brief: product cut-out (safe default mode).",
    },
    "mode.user": {"es": "Definido por el usuario.", "en": "Set by the user."},
    # --- placement plan -------------------------------------------------------
    "pieces.hero": {
        "es": "La pieza principal de la campaña: máximo impacto above-the-fold en la home.",
        "en": "The campaign's main piece: maximum above-the-fold impact on the home page.",
    },
    "pieces.collection": {
        "es": "Los productos del brief merecen su colección vestida con el mismo look de campaña.",
        "en": "The brief's products deserve their collection dressed in the same campaign look.",
    },
    "pieces.bar_promo": {
        "es": "La promo se refuerza en toda la tienda con una franja global.",
        "en": "The promo is reinforced store-wide with a global strip.",
    },
    "pieces.bar_urgency": {
        "es": "La urgencia amerita presencia global en la tienda.",
        "en": "The urgency warrants store-wide presence.",
    },
    "pieces.cross_sell": {
        "es": "Con varios productos, el cross-sell en PDP multiplica el alcance de la campaña.",
        "en": "With multiple products, PDP cross-sell multiplies the campaign's reach.",
    },
    "pieces.rationale": {
        "es": "{n} pieza(s) derivadas del brief: hero siempre; colección/franja/cross-sell según productos, promo y urgencia.",
        "en": "{n} piece(s) derived from the brief: hero always; collection/strip/cross-sell based on products, promo and urgency.",
    },
    # --- calendar suggestions (F1) --------------------------------------------
    "cal.title": {"es": "Prepara tu campaña de {name}", "en": "Prepare your {name} campaign"},
    "cal.campaign_title": {"es": "Campaña {name} {year}", "en": "{name} campaign {year}"},
    "cal.starts_in": {"es": "Empieza en {days} días ({date}).", "en": "Starts in {days} days ({date})."},
    "cal.today": {"es": "¡Es hoy! ({date}).", "en": "It's today! ({date})."},
    "cal.goal": {"es": "Campaña de {name}", "en": "{name} campaign"},
    "cal.raw_brief": {
        "es": "Brief propuesto por el agente para {name} ({date}). {note} Ajusta cualquier campo antes de planear.",
        "en": "Agent-proposed brief for {name} ({date}). {note} Adjust any field before planning.",
    },
    "cal.audience": {"es": "Clientes de la tienda", "en": "Store customers"},
    "cal.cta": {"es": "Compra ahora", "en": "Shop now"},
    "cal.tone_festive": {"es": "festivo", "en": "festive"},
    "cal.tone_warm": {"es": "cercano", "en": "warm"},
    "cal.placement": {"es": "Hero de la home", "en": "Home hero"},
    # --- catalog suggestions (F3) ----------------------------------------------
    "catalog.low_stock.title": {"es": "Últimas piezas de «{title}»", "en": "Last units of “{title}”"},
    "catalog.low_stock.rationale": {
        "es": "Quedan {stock} unidades en inventario — un banner de urgencia convierte la escasez en ventas.",
        "en": "Only {stock} units left in stock — an urgency banner turns scarcity into sales.",
    },
    "catalog.low_stock.goal": {"es": "Liquidar las últimas piezas de {title}", "en": "Sell out the last units of {title}"},
    "catalog.new.title": {"es": "Estrena «{title}» con un banner", "en": "Launch “{title}” with a banner"},
    "catalog.new.rationale": {
        "es": "Producto recién publicado sin campaña de lanzamiento.",
        "en": "Recently published product without a launch campaign.",
    },
    "catalog.new.goal": {"es": "Lanzamiento de {title}", "en": "{title} launch"},
    "catalog.best.title": {"es": "Destaca tu best-seller «{title}»", "en": "Spotlight your best-seller “{title}”"},
    "catalog.best.rationale": {
        "es": "Es tu producto más vendido y merece el hero principal.",
        "en": "It's your best-selling product and deserves the main hero.",
    },
    "catalog.best.proxy": {"es": " (ranking estimado por orden del catálogo)", "en": " (rank estimated from catalog order)"},
    "catalog.best.goal": {"es": "Destacar el best-seller {title}", "en": "Spotlight the best-seller {title}"},
    # --- performance advisor (F2) ------------------------------------------------
    "perf.title": {"es": "Refresca el banner de «{label}»", "en": "Refresh the “{label}” banner"},
    "perf.rationale_suffix": {
        "es": " Propongo un refresh dirigido para recuperar el CTR.",
        "en": " I propose a targeted refresh to recover CTR.",
    },
    "perf.ctr_decay": {
        "es": "El CTR cayó ~{decay}% en los últimos {window} días ({start} → {end}).",
        "en": "CTR dropped ~{decay}% over the last {window} days ({start} → {end}).",
    },
    "perf.banner_age": {
        "es": "El banner lleva {age} días publicado sin refresco (umbral: {max}).",
        "en": "The banner has been live {age} days without a refresh (threshold: {max}).",
    },
    "perf.refresh_prompt": {
        "es": "Refresca el banner sin salir de marca: {changes}",
        "en": "Refresh the banner while staying on brand: {changes}",
    },
    "perf.change_headline": {
        "es": "Renueva el headline con un ángulo de beneficio distinto (mismo tono de marca).",
        "en": "Renew the headline with a different benefit angle (same brand tone).",
    },
    "perf.change_background": {
        "es": "Cambia el fondo a una variante fresca de la paleta para romper la ceguera del banner.",
        "en": "Switch the background to a fresh palette variant to break banner blindness.",
    },
    "perf.change_cta": {
        "es": "Prueba un CTA de acción distinta (p. ej. de 'Compra ahora' a 'Descubre la colección').",
        "en": "Try a different action CTA (e.g. from 'Shop now' to 'Explore the collection').",
    },
}
