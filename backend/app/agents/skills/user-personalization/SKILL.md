---
name: user-personalization
description: Derive 1-4 customer.tags-based Variants from a Campaign brief for Shopify Liquid personalization. Template-based variant generation with regex tag detection. LLM-backed in design (Gemini 3.5 Flash), deterministic in current impl. Node 3 in the ADK graph.
---

# User Personalization

Generate customer segment variants for Shopify `customer.tags`-based banner personalization.

> **Node Metadata** | node: 3 | type: llm | model: gemini-3.5-flash | ticket: GH-10 | version: 0.2.0 | status: draft

## Node Invariants

1. **Default variant always present.** Output always includes a variant with `customer_tag="default"` as the first element.
2. **Max 4 variants.** 1 default + up to 3 segments. Never exceeds this count.
3. **Every variant has non-empty fields.** `customer_tag` and `intent_delta` are always populated.
4. **Urgency propagation.** When campaign urgency is "high", all variants get urgency-specific copy overrides.

## Graph Entry Conditions

- **Upstream:** `intake_campaign_idea` (node 2) must have completed.
- **State preconditions:** `state.campaign is not None` (structured brief with goal, audience, cta, tone, urgency).
- **Retry re-entry:** Not retried. `max_retries = 0` in graph.py.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| State | `campaign` | `Campaign \| StructuredBrief \| dict` | Yes |
| Function param | `customer_tags` | `list[str] \| None` | Optional — explicit tags to include |
| Function param | `context` | `dict \| None` | Optional — additional context with `customer_tags` key |
| Function param | `max_variants` | `int` | Optional — default 3 (+ 1 default = 4 max) |

## Output Encoding

- **Model:** `list[app.agents.state.Variant]` (Pydantic)
- **Each variant:** `{customer_tag: str, intent_delta: str, copy_override: dict[str, str] | None}`
- **Recognized tags:** `default`, `vip`, `new_customer`, `deal_seeker`, `gift_buyer`, `category_browser`, `primary_audience`
- **`intent_delta`:** 1-2 sentence rationale for how this variant shifts the message.

## Data Sources

| Source | Purpose |
|--------|---------|
| State: `campaign` (or `structured_brief`) | Extract audience, goal, cta, urgency |
| Prompt: `personalization.md` | LLM prompt template (when Gemini is active) |
| Internal: `_tags_from_text()` | Regex pattern matching on campaign text |
| Internal: `templates` dict | Pre-defined rationale + copy_override per known tag |

No external tools. No sub-agents.

## Workflow

1. Extract `audience`, `goal`, `cta`, `urgency` from campaign brief.
2. Build ordered tag list:
   a. Start with `["default"]`.
   b. Add explicit `customer_tags` param if provided.
   c. Add tags from `context.customer_tags` if provided.
   d. Run `_tags_from_text()` regex matching on audience + goal + cta text.
   e. Append `"primary_audience"` as fallback.
   f. Deduplicate preserving order.
3. For each tag (up to `max_variants` + 1):
   a. Look up `(rationale, copy_override)` from templates dict.
   b. If tag not in templates, generate generic rationale.
   c. If urgency is "high", add `urgency: "Act now"` to copy_override.
   d. Create `Variant(customer_tag=tag, intent_delta=rationale, copy_override=overrides)`.
4. Return list of Variants.

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.variants` | `list[Variant]` | 1-4 personalization variants |

Return type: `list[Variant]`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| `customer_tag` | `[DETERMINISTIC]` — from regex matching or explicit input |
| `intent_delta` | `[DETERMINISTIC]` — from templates dict (current impl) / `[LLM-GENERATED]` (when Gemini active) |
| `copy_override` | `[DETERMINISTIC]` — from templates dict |

## Pre/Post Conditions

**Pre:**
- `state.campaign is not None` (or equivalent structured brief)
- Campaign has at least `audience` or `goal` populated

**Post:**
- `state.variants is not None`
- `len(state.variants) >= 1`
- `state.variants[0].customer_tag == "default"`
- `len(state.variants) <= 4`
- `all(v.customer_tag != "" and v.intent_delta != "" for v in state.variants)`

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| Campaign is None | Raise `ValueError` → pipeline halts |
| All campaign fields empty | Generate single default variant with generic rationale |
| No tags detected by regex | Return `[default, primary_audience]` — 2 variants minimum |
| `max_variants` < 1 | Clamp to 1 (always produce at least default) |
| Unknown tag requested | Generate generic rationale: "Personalize message emphasis for {tag}" |

## Quality Criteria

- [ ] Default variant always present as first element
- [ ] Max 4 variants enforced (1 default + 3 segments)
- [ ] Each variant has non-empty `customer_tag` and `intent_delta`
- [ ] High urgency campaign adds "Act now" to all variant copy_overrides
- [ ] Tags are normalized: lowercase, underscores, no special chars
- [ ] Campaign text "Black Friday 50% descuento" detects `deal_seeker` tag

## Guardrails

- Never return an empty variants list — always include at least default.
- Never exceed 4 variants — trim excess by order priority.
- Never duplicate tags — deduplicate preserving insertion order.
- Never use customer.email, customer.name, or PII in tags — only `customer.tags`.
- Never invent tags outside the recognized set without explicit user request.

## Human Review Required

None. Automated node. Variant selection is visible in HITL review (node 10).

## References

- Prompt: `personalization.md` → `backend/app/agents/prompts/personalization.md`
- State models: `Campaign`, `Variant` → `backend/app/agents/state.py`
- Schema: `StructuredBrief` → `backend/app/schemas/campaign.py`
- Upstream skill: `campaign-intake` (node 2)
- Downstream skill: `best-practices-retrieve` (node 4)
- Design reference: Source Technical Design §6 — Personalization via customer.tags
