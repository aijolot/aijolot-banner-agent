"""refinement-route skill (F9).

Classify a free-text refinement prompt into pipeline target nodes. Deterministic
keyword routing (ES + EN); defaults to {concept, copy} when nothing matches.
Used as the deterministic fallback behind the LLM-based ``refinement-interpret``
skill (W0.1).
"""

from __future__ import annotations

import re

VALID_TARGETS = ("concept", "copy", "image", "background", "layout", "ink", "decor")

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "background": ("background", "fondo", "gradient", "gradiente", "color de fondo", "backdrop", "scrim"),
    "image": ("image", "imagen", "photo", "foto", "picture", "render", "product shot", "modelo", "model", "hero image",
              "escena", "scene", "fotografía", "fotografia"),
    "copy": ("copy", "texto", "headline", "título", "titulo", "subtitle", "subhead", "cta", "wording", "mensaje",
             "urgent", "urgente", "tono", "tone", "word", "palabra", "frase"),
    "layout": ("layout", "diseño", "diseno", "estructura", "structure", "composition", "composición", "grid", "placement", "posición"),
    "concept": ("concept", "concepto", "direction", "dirección", "vibe", "estilo", "style", "creative", "rework", "rehacer"),
    "ink": ("contrast", "contraste", "contrasta", "contrastan", "tinta", "ink", "legible", "legibilidad", "readable",
            "no se lee", "no se ve", "color del texto", "color de texto", "color de la fuente", "color de fuente",
            "fuente negra", "fuente blanca", "texto negro", "texto blanco"),
    "decor": ("svg", "icono", "iconos", "icon", "forma", "formas", "shape", "shapes", "círculo", "circulo", "circle",
              "círculos", "circulos", "estrella", "estrellas", "star", "motivo", "motif", "patrón", "patron",
              "pattern", "figura", "figuras", "blob", "blobs"),
}

# Multi-word phrases whose generic sub-tokens should NOT trigger other targets
# (e.g. "color de texto" is an ink request, not a copy rewrite; "color de fondo"
# stays a background request, not an ink one).
_SUPPRESSIONS: dict[str, tuple[tuple[str, str], ...]] = {
    # (phrase, target_to_suppress)
    "ink": (
        ("color de texto", "copy"), ("color del texto", "copy"), ("texto negro", "copy"), ("texto blanco", "copy"),
        ("no se lee", "copy"),
    ),
}


def route(prompt: str) -> list[str]:
    """Return the ordered set of target nodes implied by ``prompt``."""
    text = (prompt or "").lower()
    hits: list[str] = []
    for target in VALID_TARGETS:
        for token in _KEYWORDS[target]:
            if re.search(rf"(?<![\w]){re.escape(token)}", text):
                hits.append(target)
                break
    # Targeted phrase suppressions: a phrase that means "ink" must not also pull
    # in the broader target its sub-token belongs to.
    for owner, rules in _SUPPRESSIONS.items():
        if owner not in hits:
            continue
        for phrase, suppressed in rules:
            if phrase in text and suppressed in hits:
                others = _KEYWORDS[suppressed]
                # Keep the suppressed target only if another of its tokens hits
                # outside the suppressing phrase.
                reduced = text.replace(phrase, " ")
                if not any(re.search(rf"(?<![\w]){re.escape(tok)}", reduced) for tok in others):
                    hits.remove(suppressed)
    if not hits:
        return ["concept", "copy"]
    # Changing copy/concept also benefits from a layout/concept refresh; keep order stable.
    return [t for t in VALID_TARGETS if t in hits]


def normalize_targets(targets: list[str] | None, prompt: str) -> list[str]:
    """Use explicit targets when provided (filtered to valid), else classify."""
    if targets:
        cleaned = [t for t in targets if t in VALID_TARGETS]
        if cleaned:
            return [t for t in VALID_TARGETS if t in cleaned]
    return route(prompt)
