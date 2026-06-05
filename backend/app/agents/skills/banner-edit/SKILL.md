---
name: banner-edit
description: Use this skill to apply a designer's feedback to an ALREADY-ASSEMBLED banner as a scoped, non-destructive edit that produces a new revision. It classifies the feedback into a target (text/copy, background HTML-CSS, product image, layout, concept) and edits ONLY that layer — text via copy regeneration, background via sanitized HTML/CSS, image via Nano Banana Pro — preserving everything else, then re-renders + re-audits. Trigger on phrases like "edita el banner", "cambia solo el texto", "ajusta el fondo", "regenera la imagen del producto", "haz el copy más urgente", "el diseñador pidió X", or feedback on an assembled/revised banner. Produces a new superseding revision in Draft Mode. Do NOT use to write the brief (campaign-intake), to propose the initial art concept (art-direction), or to publish (publish skill).
---

# Banner Edit (banner-edit)

Apply designer feedback to an assembled banner as a **scoped, non-destructive
edit** → a new revision. Edit only the layer the feedback targets; preserve the
rest; re-render + re-audit.

> **Orchestration Metadata** | post-assembly edit loop | type: orchestration (classifier + targeted edit) | executed by: `revision_service.regenerate` (agentic) + `run_orchestrator` (refine mode) | version: 0.1.0 | status: draft | upstream: art-direction / assembled revision | downstream: review → publish

## Core Mindset

1. **Scoped, not regenerate-everything.** A text tweak must not re-roll the
   background or image. Classify the target, edit that layer, preserve the rest.
2. **Non-destructive.** Every edit creates a NEW revision that supersedes the
   source; the previous revision is never mutated and stays recoverable.
3. **Ask before guessing.** If the feedback can't be classified to a target with
   confidence, ask ONE clarifying question — never apply a destructive edit on a
   guess (Recommend Nothing).
4. **Same guardrails as generation.** Sanitize background CSS; image prompts stay
   mark/text/face-free; prohibited words never appear; brand compliance is gated.

## Trigger Conditions

Use when: a designer gives feedback on an assembled or revised banner ("cambia el
texto", "ajusta el fondo", "regenera la imagen", "más urgente el copy", "el
diseñador pidió X").

Do NOT use for: writing the brief (`campaign-intake`), proposing the initial art
concept (`art-direction`), or publishing (`shopify-theme-publish`).

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| Source revision | `revision` (concept, copy, background, generated_art, html_preview, liquid_config) | dict | Yes — the assembled banner to edit |
| Designer | `feedback` / `prompt` | str | Yes — the change requested |
| Designer | `target_nodes` | `list[str]` | Optional — explicit targets override the classifier |
| Brand | `brand_context` | `BrandContext` | Optional — voice/prohibited/palette |
| Catalog | snapshot | dict | Required only if the edit changes the featured product |

Inputs may be ambiguous. If the target is unclear, mark `[MISSING]` and ask; never fabricate.

## Output Language

Match the feedback language (typically Spanish). Field keys + tags stay English.

## Knowledge Priority

1. **Designer feedback** — authoritative for what to change (`[USER-PROVIDED]`).
2. **Source revision** — the current state to preserve where untouched (`[UNCHANGED]`).
3. **Catalog snapshot** — for product swaps (`[PROVIDER]`).
4. **KG** — best-practices/layout when a layout/concept edit is requested (`[KG-RETRIEVED]`).
5. **Gemini / Nano Banana Pro** — copy / background CSS / image edit (`[LLM-GENERATED]`).

## Workflow

```
1. Classify feedback → target(s)  [refinement-route: text|background|image|layout|concept]
        ↓
   [GATE: Edit-Target Clarity]  — ambiguous → ask ONE question, do not edit
        ↓
2. Apply the SCOPED edit (preserve everything else):
     • text/copy   → regenerate ONLY copy (banner-concept-draft Gemini), keep bg + image
     • background  → new/edited sanitized HTML/CSS, keep copy + image
     • image       → edit the product image with Nano Banana Pro, keep copy + bg
     • layout/concept → deeper re-run via art-direction (re-propose, designer confirms)
3. Re-render HTML + Liquid with the edited layer + preserved layers
4. Re-audit (performance/brand)
        ↓
   [GATE: Brand-Compliance + Audit]  — fail → keep source selected, report findings
        ↓
5. Persist a NEW revision (supersede source), point the campaign at it,
   link the refinement request. Designer can iterate again.
```

See `references/edit_mechanics.md` for exactly how each target edit is performed.

### GATE: Edit-Target Clarity
Halt if the classifier returns no confident target AND no explicit `target_nodes`.
Emit one question ("¿edito el texto, el fondo, o la imagen?"). No destructive
edit on a guess. Bypass: explicit `target_nodes` from the designer.

### GATE: Brand-Compliance + Audit
Before the new revision is presented: background CSS sanitized, no prohibited
words in copy, image is brand-safe, audit not worse than source on blocking
checks. On failure, keep the source revision selected and report; do not silently
ship a regressed edit.

## Output Contract

A new `campaign_revision` (superseding the source) with:
```
edited_target:  text | background | image | layout | concept
changed:        { the edited layer }                 [LLM-GENERATED] / [PROVIDER]
preserved:      { copy | background | image | layout not targeted }  [UNCHANGED]
html_preview / liquid_config: re-rendered
audit:          re-run report
refinement_request: linked, status succeeded|failed
```
Plus a designer-facing diff summary: what changed (tagged) vs what was kept.

## Data Provenance (Origin Tags)

| Output | Provenance |
|--------|-----------|
| Edited copy | `[LLM-GENERATED]` (Gemini) |
| Edited background CSS | `[LLM-GENERATED]`, sanitized |
| Edited/regenerated image | `[PROVIDER]` (Nano Banana Pro) |
| Swapped product | `[PROVIDER]` (catalog) |
| Untouched layers | `[UNCHANGED]` (carried from source revision) |
| Ambiguous/missing target | `[MISSING]` |

## Quality Criteria

- [ ] A text-only edit leaves background + image byte-identical (preserved).
- [ ] A background edit leaves copy + image unchanged; new CSS is sanitized.
- [ ] An image edit (Nano Banana Pro) leaves copy + background unchanged.
- [ ] Every edit yields a NEW revision; the source is superseded, not mutated.
- [ ] Ambiguous feedback triggers a clarifying question, not a guess.
- [ ] Brand-Compliance + Audit gate blocks a regressed edit.
- [ ] The diff summary tags what changed vs what was kept.

## Guardrails (Recommend Nothing)

- If the target is ambiguous → ask, do not edit.
- Never regenerate untargeted layers ("while I'm here" edits are forbidden).
- Never mutate the source revision in place.
- Sanitize all background CSS (`@import`, external `url()`, `expression(`,
  `<script>`/`<iframe>`, inline handlers) before it reaches a preview.
- Image edits: mark/text/face-free, brand-safe; cost-gated, degrade to free
  provider on no-key/cost-cap.
- Never publish — edited revisions go to review/publish skills.

## Human Review Required

- The designer reviews the diff and accepts/iterates (the loop is the review).
- No external write. Paid image edits are cost-gated.

## References

- `references/edit_mechanics.md` — step-by-step for each target (text / background HTML-CSS / image via Nano Banana Pro), what is preserved, and revision bookkeeping.
- Classifier: `refinement-route` skill.
- Runtime: `backend/app/services/banners/revision_service.py` (`regenerate`, agentic), `run_orchestrator.py` (refine mode), art endpoints (`/generate-art`, `/background-options`).
- Schema: `RegenerateRequest` (prompt, target_nodes, structured_changes) → `backend/app/schemas/generation.py`.
- Second Brain: `04_tech/adk_workflow_pipeline.md`, `04_tech/observability.md`.

## Version History

| Version | Date       | Change                                  | Owner   |
|---------|------------|-----------------------------------------|---------|
| 0.1.0   | 2026-06-04 | Initial Banner Edit orchestration draft | AIjolot |
