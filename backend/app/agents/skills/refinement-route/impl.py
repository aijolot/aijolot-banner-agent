"""refinement-route skill (F9).

Classify a free-text refinement prompt into pipeline target nodes. Deterministic
keyword routing (ES + EN); defaults to {concept, copy} when nothing matches.
"""

from __future__ import annotations

import re

VALID_TARGETS = ("concept", "copy", "image", "background", "layout")

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "background": ("background", "fondo", "gradient", "gradiente", "color de fondo", "backdrop", "scrim"),
    "image": ("image", "imagen", "photo", "foto", "picture", "render", "product shot", "modelo", "model", "hero image"),
    "copy": ("copy", "texto", "headline", "título", "titulo", "subtitle", "subhead", "cta", "wording", "mensaje",
             "urgent", "urgente", "tono", "tone", "word", "palabra", "frase"),
    "layout": ("layout", "diseño", "diseno", "estructura", "structure", "composition", "composición", "grid", "placement", "posición"),
    "concept": ("concept", "concepto", "direction", "dirección", "vibe", "estilo", "style", "creative", "rework", "rehacer"),
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
