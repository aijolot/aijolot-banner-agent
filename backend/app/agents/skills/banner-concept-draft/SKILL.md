---
name: banner-concept-draft
description: Draft a brand-aligned creative Concept (copy + layout + image_prompt + palette_usage) from BrandContext, Campaign, Variants, and KG best practices. Uses CreativeDirector sub-agent (Gemini 3.1 Pro) in design, deterministic in current impl. Enforces prohibited words, palette tokens, and image safety. Node 5 in the ADK graph.
---

# Banner Concept Draft

Produce the creative blueprint for a Shopify banner — copy, layout, palette, and image prompt.

> **Node Metadata** | node: 5 | type: llm | model: gemini-3.1-pro | sub_agent: creative_director | ticket: GH-11, GH-NEW6 | version: 0.2.0 | status: draft

## Node Invariants

1. **No prohibited words in copy.** Every text field in `concept.copy` is scrubbed against `brand_context.voice.prohibited_words`.
2. **Palette tokens by name, never hex.** `palette_usage` references token names from `BrandContext.palette`, not literal hex values.
3. **Image prompt is text/logo/UI/face-free.** All forbidden terms replaced with safe alternatives via substitution table.
4. **Required phrases included.** `brand_context.voice.required_phrases` are woven into copy when present.
5. **Retryable.** `max_retries = 2` in graph.py — audit can route back here.

## Graph Entry Conditions

- **Upstream:** `research_best_practices` (node 4) must have completed.
- **State preconditions:** `state.campaign is not None`, `state.brand_context is not None`. `state.variants` and `state.best_practices` may be empty lists.
- **Retry re-entry:** Entered when audit returns `retry_node_5`. Retries counter tracked in `state.retries["draft_banner_concept"]`.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| State | `campaign` | `Campaign \| dict` | Yes |
| State | `brand_context` | `BrandContext` | Yes |
| State | `variants` | `list[Variant]` | Optional (defaults to `[]`) |
| State | `best_practices` | `list[dict]` | Optional (defaults to `[]`) |
| Function param | `placement_context` | `Any` | Optional — placement type for layout |
| Function param | `catalog_context` | `Any` | Optional — product data for headline |
| Function param | `art_direction` | `Any` | Optional — background_mode, fold_percentage |

## Output Encoding

- **Model:** `app.agents.state.Concept` (Pydantic)
- **Fields:**
  - `layout: str` — placement-aware layout description
  - `copy: dict[str, str]` — `{headline, subheadline, cta, audience, rationale}`
  - `palette_usage: dict[str, str]` — `{background, text, cta_background, cta_text}` → token names
  - `image_prompt: str` — sanitized prompt for image generation
  - `hierarchy_notes: str` — design rationale
- **Limits:** headline ≤ 58 chars, subheadline ≤ 110 chars, CTA ≤ 28 chars.

## Data Sources

| Source | Purpose |
|--------|---------|
| State: campaign, brand_context, variants, best_practices | Creative inputs |
| Prompt: `draft_concept.md` | CreativeDirector prompt (when LLM active) |
| Sub-agent: `creative_director.py` | LLM reasoning (deferred: GH-11) |
| Internal: `_IMAGE_FORBIDDEN_REPLACEMENTS` | 30+ entry substitution table |
| Internal: `_remove_prohibited()` | Regex scrubber for prohibited words |
| Internal: `_append_required_phrase()` | Required phrase insertion |

## Workflow

1. Extract campaign brief fields: goal, audience, cta, tone, urgency, placement.
2. Extract catalog summary from `catalog_context` (product title + price if available).
3. Extract prohibited words and required phrases from `brand_context.voice`.
4. **Build headline:**
   a. Start with catalog line or goal text.
   b. Remove prohibited words via `_remove_prohibited()`.
   c. Append first required phrase via `_append_required_phrase()` (limit 58 chars).
5. **Build subheadline:**
   a. Compose from audience + urgency + tone.
   b. Remove prohibited words.
   c. Truncate to 110 chars.
6. **Build CTA:** Remove prohibited words from campaign CTA, truncate to 28 chars.
7. **Map palette:** Assign `primary`, `secondary`, `accent` from `brand_context.palette` to `background`, `text`, `cta_background`, `cta_text` token names.
8. **Build image prompt:**
   a. Compose from background_mode + catalog line + palette token names + safety suffix.
   b. Sanitize via `_sanitize_image_fragment()` — replace all forbidden terms.
9. **Build layout:** Format as `"{placement} split layout: copy block left, product/visual right, focal area safe within {fold}% fold"`.
10. **Build hierarchy notes:** Concatenate audience rationale, variant notes (top 2), best practice titles (top 2).
11. Return `Concept(...)`.

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.concept` | `Concept` | Creative blueprint for banner |

Return type: `Concept`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| `copy.headline` | `[DETERMINISTIC]` — constructed from campaign + catalog + brand rules |
| `copy.subheadline` | `[DETERMINISTIC]` — constructed from audience + urgency + tone |
| `copy.cta` | `[DETERMINISTIC]` — from campaign CTA, sanitized |
| `layout` | `[DETERMINISTIC]` — from placement + art_direction |
| `palette_usage` | `[DETERMINISTIC]` — mapped from brand_context.palette positions |
| `image_prompt` | `[DETERMINISTIC]` — constructed + sanitized |
| `hierarchy_notes` | `[DETERMINISTIC]` — concatenation of rationale + variants + best practices |

When CreativeDirector sub-agent is active (post GH-11), copy fields become `[LLM-GENERATED]`.

## Pre/Post Conditions

**Pre:**
- `state.campaign is not None`
- `state.brand_context is not None`
- `state.brand_context.palette` has ≥ 1 color

**Post:**
- `state.concept is not None`
- No word from `brand_context.voice.prohibited_words` appears in `state.concept.copy` values
- `state.concept.palette_usage` values are token names from `brand_context.palette`, not hex strings
- `state.concept.image_prompt` contains no forbidden terms (text, logo, face, ui, etc.)
- `len(state.concept.copy["headline"]) <= 58`

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| Campaign is None | Raise `ValueError` → pipeline halts |
| BrandContext is None | Raise `ValueError` → pipeline halts |
| Variants empty | Generate concept for default audience only — valid |
| Best practices empty | Generate concept without KG enrichment — valid |
| Catalog context empty | Use goal text as headline seed instead of product title |
| CreativeDirector sub-agent fails (post GH-11) | Fall back to deterministic `draft_concept()` |
| All prohibited word removal empties a field | Fall back to generic: "Featured offer" |

See `references/prohibited_content_rules.md` for the full substitution table and copy rules.

## Quality Criteria

- [ ] No `prohibited_words` in any copy field
- [ ] Palette references use token names, not hex
- [ ] `image_prompt` has no text/logos/UI/faces
- [ ] Concept respects `voice.tone`
- [ ] Headline ≤ 58 chars, subheadline ≤ 110, CTA ≤ 28
- [ ] Required phrases appear in headline when present
- [ ] Audit retry (2nd invocation) produces different concept based on updated inputs

## Guardrails

- Never include prohibited words in any output — scrub before returning.
- Never use hex color values in `palette_usage` — always map to token names.
- Never include negation patterns in `image_prompt` ("no text", "no logos").
- Never bake marketing copy into the image prompt — copy is rendered in HTML.
- Never exceed 2 retries — escalate to HITL after that.
- Never silently violate a constraint — explain in `hierarchy_notes`.

## Human Review Required

None. Automated node. Concept is reviewed at HITL (node 10). However, audit (node 9) may trigger retry.

## References

- Prompt: `draft_concept.md` → `backend/app/agents/prompts/draft_concept.md`
- Sub-agent: `creative_director` → `backend/app/agents/sub_agents/creative_director.py`
- State models: `Concept`, `Campaign`, `Variant` → `backend/app/agents/state.py`
- Schema: `BrandContext` → `backend/app/schemas/brand.py`
- Detail: `references/prohibited_content_rules.md`
- Upstream skill: `best-practices-retrieve` (node 4)
- Downstream skill: `image-prompt-refine` (node 5/6 boundary)
