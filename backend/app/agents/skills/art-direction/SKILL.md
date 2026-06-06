---
name: art-direction
description: Use this skill to turn a validated Campaign Brief into a proposed art concept per personalization variant — the orchestration step between Brief and Assembly in the Aijolot Banner Agent. From the brief it (1) retrieves a functional layout from the Knowledge Graph, (2) generates KG-grounded copy, (3) creates themed AI backgrounds, and (4) proposes a concrete art concept per variant (which featured product, hero vs usage shot, and for usage which model treatment per segment), with evidence — then lets the designer iterate before assembly. Trigger on phrases like "diseña el arte", "propón el concepto", "del brief al arte", "qué perfume y layout uso", "concepto para hombre/mujer", or when a Brief-Ready campaign enters the art phase. Produces an Art Concept proposal (per variant) in Draft Mode. Do NOT use to write the brief (use campaign-intake), to edit an already-assembled banner (use the banner-edit skill), or to publish (use the publish skill).
---

# Art Direction (art-direction)

Turn a Brief-Ready campaign into a **proposed art concept per personalization
variant**, composing layout retrieval, copy generation, backgrounds, and product/
model selection — for the designer to iterate before assembly.

> **Orchestration Metadata** | spans nodes 4–7 (research → concept → image) | type: orchestration (LLM + KG + provider) | executed by: `run_orchestrator` (concept portion) + the art endpoints | version: 0.1.0 | status: draft | upstream: campaign-intake (Brief-Ready) | downstream: assembly / banner-edit

## Core Mindset

1. **Composes, never re-implements.** This skill sequences the granular node-skills (`layout-retrieve`, `banner-concept-draft`, `background-options-generate`, `art-prompt-propose`). It adds the *cross-variant art concept* and the designer-iteration loop — it does not re-do their work.
2. **Propose with evidence, never assert.** "This perfume will have higher CTR" is only allowed as `[INFERENCE]` citing catalog/KG evidence (sales/stock = `[PROVIDER]`, prior-banner lift = `[KG-RETRIEVED]`) or `[HYPOTHESIS]` with a validation note. Never fabricate CTR/conversion numbers.
3. **One concept per variant.** Output is one art concept per `personalization_variant` (e.g. hombre, mujer), each self-consistent (layout + copy + background + product + model-if-usage). No variants in the brief → one default concept.
4. **Agent proposes, designer decides.** Human input is optional, not required: the agent proposes a full concept ("para hombre, el perfume en un layout de outfit varonil; para mujer, modelo aplicándose el perfume frente al espejo"). The designer iterates; the agent re-proposes on feedback. Nothing is committed to assembly until the designer accepts.
5. **Brand + safety first.** Backgrounds are sanitized; image prompts are mark/text/face-free and brand-safe; prohibited words never appear.

## Trigger Conditions

Use when: a Brief-Ready campaign enters the art phase; the operator says "diseña el arte", "propón el concepto", "del brief al arte", "qué producto/layout uso", "concepto para hombre/mujer".

Do NOT use for: writing/validating the brief (`campaign-intake`), editing an already-assembled banner from feedback (`banner-edit`), the raw image render/optimize/liquid steps in isolation (their node-skills), or publishing (`shopify-theme-publish` / publish skill).

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| Brief | `structured_brief` | `StructuredBrief` | Yes — must be Brief-Ready (gate passed by campaign-intake) |
| Brief | `personalization_variants` | `list[{key,label,audience,customer_tag}]` | Optional — one concept per entry; empty → one default |
| Catalog | snapshot items | `list` (Shopify) | Required to feature a product — `[PROVIDER]`; never invented |
| KG | `liquid_pattern`, `best_practice`, `brand_example`, `prior_banner` | docs | Optional — ground layout + concept + product rationale |
| Brand | `brand_context` | `BrandContext` | Optional — palette/voice/prohibited |
| Designer | feedback turns | text | Optional — drives the iteration loop |

Inputs are often partial. Mark gaps `[MISSING]`; never fabricate a product, audience, or metric.

## Output Language

Match the brief's language (typically Spanish). Field keys + origin tags stay English.

## Knowledge Priority

1. **Campaign Brief** — goal/audience/variants/promo → drives every choice (`[USER-PROVIDED]`).
2. **Shopify catalog snapshot** — the only source of products/prices/stock (`[PROVIDER]`).
3. **Knowledge Graph** — `liquid_pattern` (layout), `best_practice`/`brand_example`/`prior_banner` (concept + product rationale) → `[KG-RETRIEVED]`.
4. **Brand context** — palette/voice/prohibited.
5. **Gemini** — copy, background CSS, concept narrative, model/shot proposals → `[LLM-GENERATED]`. Never the source of facts (products, metrics).

## Workflow

```
   [GATE: Brief-Ready]  — refuse if the brief is incomplete (campaign-intake owns it)
        ↓
1. Layout — layout-retrieve(placement+goal+tone) → top KG liquid_pattern   [KG-RETRIEVED]
2. Copy   — banner-concept-draft (Gemini, KG best-practices) per variant     [LLM-GENERATED]
3. Backgrounds — background-options-generate(count=3), theme-aware, sanitized [LLM-GENERATED]
4. Product — choose featured product(s) from the catalog snapshot,
            with rationale grounded in stock/sales [PROVIDER] + KG lift [KG-RETRIEVED]/[HYPOTHESIS]
5. Per-variant concept — for each variant build a concept:
     • hero shot  → product-forward layout + scene
     • usage shot → propose a model treatment per segment (art-prompt-propose, usage)
   e.g. hombre: perfume en layout de outfit varonil; mujer: modelo aplicándose el perfume al espejo
        ↓
   [GATE: Art-Concept-Ready]
        ↓
6. Present concepts (per variant) to the designer → iterate on feedback (re-run the
   relevant step only) → on acceptance, hand off to Assembly.
```

### GATE: Brief-Ready (entry)
Refuse to start if the brief fails campaign-intake's Brief-Ready gate (required
fields empty, incoherent variants). Halt with the missing items; do not invent.

### GATE: Art-Concept-Ready (before assembly)
Halt unless, for **every** variant: a layout is chosen, copy is non-empty and
prohibited-word-free, a background is selected, a featured product is set from the
catalog, and (for usage shots) a model treatment is proposed. On failure, name the
variant + missing piece. **No bypass** — assembly must not start on a partial concept.

## Output Contract

Per variant, an **Art Concept**:
```
variant: { key, label, customer_tag }
layout:      <KG liquid_pattern title>            [KG-RETRIEVED]
copy:        { eyebrow, headline, subheadline, cta } [LLM-GENERATED]
background:  { name, css, rationale }              [LLM-GENERATED] (sanitized)
product:     { title, sku, price } + why-featured  [PROVIDER] + rationale tag
shot_type:   hero | usage
model:       (usage only) { segment, treatment, prompt } [LLM-GENERATED]/[HYPOTHESIS]
rationale:   why this concept fits the variant + evidence/origin tag
```
Plus a designer-facing summary listing the concepts with origin tags, and the
iteration state (proposed / accepted / changes-requested).

## Data Provenance (Origin Tags)

| Output | Provenance |
|--------|-----------|
| Layout | `[KG-RETRIEVED]` (liquid_pattern) |
| Copy | `[LLM-GENERATED]` (grounded in brief + KG) |
| Background CSS | `[LLM-GENERATED]`, sanitized |
| Featured product / price / stock | `[PROVIDER]` (catalog) |
| "higher CTR / best fit" claims | `[INFERENCE]` (cite prior_banner/stock) or `[HYPOTHESIS]` + validation note |
| Model/usage treatment | `[LLM-GENERATED]` (concept) / `[HYPOTHESIS]` (consistency caveat) |
| Missing product/variant data | `[MISSING]` |

## Quality Criteria

- [ ] One self-consistent concept per personalization variant (or one default).
- [ ] Layout comes from a real KG `liquid_pattern` (not invented).
- [ ] Copy is variant-specific, prohibited-word-free, ≤ limits, product/offer-aware.
- [ ] Backgrounds reflect the campaign theme/season and are sanitized.
- [ ] Featured product exists in the catalog snapshot; any CTR/sales claim carries `[INFERENCE]`/`[HYPOTHESIS]`, never a fabricated number.
- [ ] Usage concepts propose a distinct model treatment per segment; consistency caveat noted.
- [ ] Art-Concept-Ready gate blocks assembly until all variants are complete.
- [ ] Designer feedback re-runs only the affected step (copy/background/product/model), not the whole concept.

## Guardrails (Recommend Nothing)

- **No product, no concept.** If the catalog snapshot is empty or no product fits, do NOT invent one — halt with `[MISSING]` and request a catalog sync/selection.
- **No fabricated metrics.** Never state a CTR/conversion/sales figure that isn't from the catalog (`[PROVIDER]`) or KG (`[KG-RETRIEVED]`). "Mayor CTR" without evidence is `[HYPOTHESIS]`.
- **No forced variants.** If the brief has no personalization variants, propose one default concept — do not invent hombre/mujer.
- Never bypass the Art-Concept-Ready gate to "move faster".
- Image prompts: no baked-in text/logos/UI/faces; brand-safe; prohibited words removed.
- Never publish or assemble autonomously — concepts are proposals until the designer accepts.

## Human Review Required

- The designer **accepts** the per-variant concept before assembly (the iteration loop is the review).
- No external write occurs in this skill. Paid image generation (if a concept is rendered to preview) is cost-gated and degrades to a free provider.

## References

- `references/art_concept_proposal.md` — per-shot/per-variant concept taxonomy, product-rationale grounding rules, evidence→origin-tag mapping, designer iteration protocol.
- Step skills: `layout-retrieve`, `banner-concept-draft`, `background-options-generate`, `art-prompt-propose`.
- Runtime: `backend/app/services/banners/run_orchestrator.py` (concept/layout/background/variants), art endpoints (`/art-prompts`, `/model-prompts`, `/generate-art`, `/background-options`).
- Schema: `StructuredBrief`, `PersonalizationVariant` → `backend/app/schemas/campaign.py`.
- Second Brain: `04_tech/adk_workflow_pipeline.md`, `03_skills/graph_node_skill_contract.md`.

## Version History

| Version | Date       | Change                                   | Owner   |
|---------|------------|------------------------------------------|---------|
| 0.1.0   | 2026-06-04 | Initial Art Direction orchestration draft | AIjolot |
