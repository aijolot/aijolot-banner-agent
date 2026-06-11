"""Schemas for grounded refinement interpretation (W0.1).

A free-text refinement prompt is interpreted into a small set of *directed
operations* so plan-iterate / refine only touches what the user asked for,
instead of re-drafting (and re-backgrounding) everything.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# Operations the orchestrator knows how to apply. Anything else is dropped.
VALID_OPS = (
    "set_ink",  # change text color (value=hex, or empty → auto-contrast)
    "change_background",  # regenerate the background treatment (instruction-led)
    "change_decor",  # swap/edit decorative shapes (SVG motifs) inside the background
    "edit_copy",  # rewrite specific copy fields (instruction-led)
    "adjust_layout",  # nudge composition/structure
    "set_image_prompt",  # change WHAT the generated image/scene shows (instruction = the scene)
    "redraft_concept",  # full creative re-draft
)

COPY_SECTIONS = ("headline", "subheadline", "eyebrow", "cta")


class RefinementOp(BaseModel):
    """One directed edit derived from the user's feedback."""

    op: str = Field(description="One of: " + ", ".join(VALID_OPS))
    section: str | None = Field(
        default=None,
        description="Optional copy/text section the op applies to: headline|subheadline|eyebrow|cta|all",
    )
    value: str | None = Field(default=None, description="Direct value when applicable (e.g. a hex color for set_ink)")
    instruction: str | None = Field(
        default=None, description="Directed natural-language instruction for generative ops"
    )

    @field_validator("op")
    @classmethod
    def _valid_op(cls, v: str) -> str:
        if v not in VALID_OPS:
            raise ValueError(f"invalid op '{v}'")
        return v

    @field_validator("section")
    @classmethod
    def _valid_section(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip().lower()
        if cleaned in ("", "all"):
            return None
        return cleaned if cleaned in COPY_SECTIONS else None


class RefinementPlan(BaseModel):
    """Interpretation of a refinement prompt: targets (legacy routing) + ops."""

    targets: list[str] = Field(default_factory=list)
    ops: list[RefinementOp] = Field(default_factory=list)
    rationale: str = Field(default="")
    source: str = Field(default="deterministic", description="'gemini' or 'deterministic'")

    def op_names(self) -> list[str]:
        return [o.op for o in self.ops]

    def has(self, *names: str) -> bool:
        wanted = set(names)
        return any(o.op in wanted for o in self.ops)
