---
name: campaign-intake
description: Use this skill to turn free-form client/designer input into a complete, validated Campaign Brief — the input contract for the Art phase of the Aijolot Banner Agent. It extracts goal, audience, cta, tone, urgency, placement, deadline, and proposes the personalization dimension + variants (1 campaign, N variants served by customer tag), the promo/discount, and the featured Shopify products. Trigger on phrases like "tengo notas para una campaña", "armemos el brief", "banner para promo de…", "campaña de…", "personalizar por género/segmento", or when raw campaign notes arrive at node 2. Supports Gemini (opt-in) with a deterministic fallback; asks only for genuinely missing fields. Do NOT use for the art/concept step (use banner-concept-draft), for store reads (use the catalog/sync skills), or for Discovery-phase consulting briefs (use aijolot-discovery-execution).
---

# Campaign Brief (campaign-intake)

Transform conversational client/designer input into a structured, validated **Campaign Brief** that is the contract the Art phase consumes.

> **Node Metadata** | node: 2 | node_key: `intake_campaign_idea` | type: llm multi-turn | model: gemini-3.5-flash (opt-in) | version: 0.3.0 | status: draft | upstream: brand-context-load (1) | downstream: capture_user_personalization (3) → best-practices-retrieve (4) → banner-concept-draft (5)

## Core Mindset

1. **Contract, not chat.** The job is a complete, machine-checkable brief — not a conversation. Every turn moves toward a brief that passes the Brief-Ready gate.
2. **Capture what's given; ask only what's missing.** When the input already carries fields, accept them all in one turn. Never re-ask an answered field; never batch unrelated questions.
3. **Propose, never invent.** Personalization variants, promo, and featured products are *proposed* from the objective + evidence (KG segments, catalog) for the designer to confirm — never fabricated. Products and prices come only from the real Shopify catalog snapshot.
4. **Deterministic floor.** Gemini is opt-in (`AIJOLOT_INTAKE_PROVIDER=gemini`); any failure falls back transparently to the rule-based extractor. The brief is never blocked by provider availability.

## Trigger Conditions

Use when: raw campaign notes/turns arrive for a banner campaign; the operator says "armemos el brief", "banner para promo de X", "personalizar por género"; node 2 is invoked by the pipeline.

Do NOT use for: the creative concept/art (`banner-concept-draft`), live store reads or catalog snapshots (catalog/sync skills), or Discovery-phase client briefs (`aijolot-discovery-execution`).

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| Function param | `messages` | `list[dict]` | Yes — running transcript `[{author_type, body}]` |
| Function param | `brand_context` | `BrandContext \| Any` | Optional — tone/voice/segment awareness |
| Function param | `current_brief` | `StructuredBrief \| dict \| None` | Optional — accumulated brief so far |
| `ctx.state` / repo | catalog snapshot | `dict` | Optional — real Shopify products for the "featured products" proposal |
| `ctx.state` / KG | segment evidence | `list[dict]` | Optional — `brand_example`/`prior_banner` to ground variant proposals |

Inputs are usually incomplete. Mark unprovided required fields `[MISSING]`; never guess.

## Output Language

Match the input language. AIjolot campaign input is typically Spanish — keep the brief's values in the operator's language; field keys/tags stay English.

## Knowledge Priority

1. **Client/designer input** (the transcript) — authoritative for stated fields → `[USER-PROVIDED]`.
2. **Shopify catalog snapshot** — authoritative for products/prices → `[PROVIDER]`. Never invent SKUs/prices.
3. **Knowledge Graph (2nd brain)** — `brand_example`, `prior_banner`, segments to ground variant/audience proposals → `[KG-RETRIEVED]`.
4. **Brand context** — voice/tone/prohibited words.
5. **Gemini** — extraction + proposals → `[LLM-GENERATED]`. Last resort for anything not above; never `[USER-PROVIDED]`.

## Output Encoding (to ctx.state)

- **Model:** `CampaignIntakeResult` (Pydantic) → `structured_brief: StructuredBrief`, `question: str | None`, `complete: bool`, `metadata: dict`.
- **`StructuredBrief` fields:** `goal, audience, cta, tone, urgency (low|medium|high), placement, deadline (ISO|null)`, plus **`personalization_dimension: str`** and **`personalization_variants: list[{key,label,audience,customer_tag}]`**.
- **Promo/discount:** captured to `campaign.promo_label` / `promo_rule` (e.g. "15% OFF") — read downstream by generation and folded into the CTA.
- **Featured products:** referenced via the catalog snapshot (not copied into the brief); the brief records the operator's intent/selection.
- **`metadata`:** `provider` ("gemini"|"deterministic"), `fallback` (bool), `reason` (str).
- When complete and gated, `state.campaign` is populated.

## Workflow

```
1. Resolve current_brief → StructuredBrief (dict→model)
2. Extract stated fields from this turn (Gemini if enabled, else deterministic)
   — preserve-filled merge: never blank or overwrite a non-empty field with empty
3. Map natural ES/EN phrases → fields (see references/brief_field_extraction.md)
4. Propose personalization dimension + variants from the goal + KG/segments  [proposal, designer confirms]
5. Propose promo/discount + featured products from input + catalog snapshot   [proposal, designer confirms]
        ↓
   [GATE: Brief-Ready]
        ↓
6. If gated open → complete=True, question=None, populate state.campaign
   else → ask exactly ONE missing required field (question != None)
```

### GATE: Brief-Ready (Stage Gate)

**Halt condition (brief is NOT ready) when any holds:**
- A required field is empty: `goal, audience, cta, urgency, placement`.
- `personalization_variants` is non-empty but a variant is missing `key`/`audience`, or `customer_tag`s collide.
- A promo/discount was mentioned but not parseable into a label.

**When halted:** set `complete=False` and emit ONE question for the single highest-priority missing/ambiguous item. Do not advance to Art. **Bypass:** none — the Art phase must not start on an incomplete brief.

## Output Contract

- `CampaignIntakeResult` with a `StructuredBrief` that, when `complete=True`, has all required fields + a coherent (possibly empty) variant set.
- A short brief summary with **origin tags** on every value: each field shows `[USER-PROVIDED]` / `[KG-RETRIEVED]` / `[PROVIDER]` / `[LLM-GENERATED]` / `[MISSING]`.
- `state.campaign` (final turn only).

## Data Provenance (Origin Tags)

| Output field | Provenance |
|--------------|-----------|
| Fields the user stated | `[USER-PROVIDED]` |
| Fields extracted by Gemini from user text | `[LLM-GENERATED]` (still grounded in user text) |
| Fields from the deterministic extractor | `[DETERMINISTIC]` |
| Proposed variants/audiences grounded in KG segments | `[KG-RETRIEVED]` |
| Featured products / prices | `[PROVIDER]` (Shopify catalog) |
| Unprovided required fields | `[MISSING]` |

## Quality Criteria

- [ ] A single input turn that contains all fields completes the brief in ONE turn (no re-ask loop).
- [ ] ES phrases map correctly: "fin de semana"→urgency, "para mujeres jóvenes"→audience/variant, "15% OFF"→promo.
- [ ] Proposed `personalization_variants` each have `key`, `label`, `audience`, distinct `customer_tag`.
- [ ] No product/price appears that is not in the catalog snapshot.
- [ ] Every brief value carries an origin tag; `[MISSING]` is shown, never fabricated.
- [ ] Brief-Ready gate blocks Art when a required field is empty.
- [ ] Deterministic fallback produces a valid (if sparser) brief with `provider="deterministic"`.

## Guardrails (Recommend Nothing)

- If the input does not justify a variant split, propose **no variants** (single default audience) — do not invent hombre/mujer to look sophisticated.
- If no promo is stated, leave promo empty — do not invent a discount.
- Never fabricate field values, SKUs, prices, audiences, or ROI.
- Never re-ask an answered field; never batch questions.
- Never overwrite a user-confirmed field with a Gemini re-extraction.
- Never send real customer PII to Gemini — only campaign brief metadata.
- Never advance to Art on a brief that fails the Brief-Ready gate.

## Human Review Required

None for extraction (automated node). The designer **confirms** proposed variants/promo/products at the brief UI before Art. The brief is visible in HITL review (node 10). No external write here.

## References

- `references/brief_field_extraction.md` — ES/EN phrase→field map, personalization variant/tag taxonomy, Brief-Ready validation rules.
- `references/gemini_fallback_matrix.md` — provider fallback decision matrix.
- Schema: `StructuredBrief`, `PersonalizationVariant` → `backend/app/schemas/campaign.py`
- Prompt: `backend/app/agents/prompts/intake.md`
- Tool: `backend/app/agents/tools/gemini_text.py`
- Service: `backend/app/services/campaign_store.py`
- Generation consumer: `backend/app/services/banners/run_orchestrator.py` (reads variants + promo + catalog)
- Second Brain: `03_skills/graph_node_skill_contract.md`, `04_tech/adk_workflow_pipeline.md`

## Version History

| Version | Date       | Change                                                                 | Owner   |
|---------|------------|------------------------------------------------------------------------|---------|
| 0.2.0   | 2026-05    | Initial intake contract (goal..deadline, one-field-at-a-time)          | AIjolot |
| 0.3.0   | 2026-06-04 | Elevate to Campaign Brief: personalization variants, promo, featured products, Brief-Ready gate | AIjolot |
