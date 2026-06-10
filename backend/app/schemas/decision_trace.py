"""DecisionTrace (F4 — explicability): WHY the agent made each creative choice.

Attached to generation events (``output_summary.decision_trace``), to the plan
response, and to the revision concept so the UI can show "Decisión / Razones /
Fuentes" with KG citations instead of a black box.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DecisionSource(BaseModel):
    """One source the agent grounded a decision on."""

    type: str = Field(description="kg_doc | brand | catalog | performance")
    id: str | None = None
    title: str = ""
    score: float | None = None


class DecisionTrace(BaseModel):
    """A creative decision, its reasons, and the sources that grounded it."""

    decision: str = ""
    reasons: list[str] = Field(default_factory=list)
    sources: list[DecisionSource] = Field(default_factory=list)


def build_concept_trace(
    *,
    concept: Any,
    best_practices: list[dict[str, Any]] | None,
    brand: Any,
) -> DecisionTrace:
    """Trace for the draft_banner_concept decision (layout + copy + paleta)."""
    layout = str(getattr(concept, "layout", "") or "")
    copy = getattr(concept, "copy", None) or {}
    source_refs = list(getattr(concept, "source_refs", None) or [])
    selected = next((r for r in source_refs if r.get("selected")), source_refs[0] if source_refs else None)

    reasons: list[str] = []
    if selected:
        when = str(selected.get("applicable_when") or "").strip()
        reasons.append(
            f"Layout «{selected.get('title')}» tomado del knowledge graph"
            + (f" — aplica cuando: {when}" if when else "")
            + "."
        )
    else:
        reasons.append("Layout determinista por defecto: no hubo patrones del knowledge graph aplicables. [DETERMINISTIC]")
    if str(copy.get("copy_source") or "") == "gemini":
        reasons.append("Copy redactado por el modelo a partir del brief, los productos y la voz de marca.")
    else:
        reasons.append("Copy de plantilla determinista (modelo no disponible o sin presupuesto). [DETERMINISTIC]")
    top_bp = [d for d in (best_practices or []) if d.get("title")][:3]
    if top_bp:
        reasons.append(
            "Buenas prácticas aplicadas: " + "; ".join(str(d["title"]) for d in top_bp) + "."
        )
    brand_name = str(getattr(brand, "name", "") or "")
    if brand_name:
        reasons.append(f"Paleta, tipografía y tono restringidos al brand context «{brand_name}».")

    sources: list[DecisionSource] = []
    for ref in source_refs[:3]:
        sources.append(
            DecisionSource(
                type="kg_doc",
                id=str(ref.get("id")) if ref.get("id") else None,
                title=str(ref.get("title") or ""),
                score=ref.get("score") if isinstance(ref.get("score"), (int, float)) else None,
            )
        )
    for doc in top_bp:
        sources.append(
            DecisionSource(
                type="kg_doc",
                id=str(doc.get("id")) if doc.get("id") else None,
                title=str(doc.get("title") or ""),
                score=doc.get("score") if isinstance(doc.get("score"), (int, float)) else None,
            )
        )
    if brand_name:
        sources.append(DecisionSource(type="brand", id=str(getattr(brand, "id", "") or "") or None, title=brand_name))

    return DecisionTrace(decision=f"Layout: {layout}" if layout else "Concepto del banner", reasons=reasons, sources=sources)
