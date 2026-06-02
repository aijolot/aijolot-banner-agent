---
name: image-prompt-refine
description: Sanitize and refine a Concept image prompt for safe image generation. Strips text, logos, UI, faces references and enforces brand directives, aspect ratio 16:9, and 60-120 word limit. Deterministic in current impl (no LLM call). Node 5/6 boundary in the ADK graph.
---

# Image Prompt Refine

Produce a safe, brand-aligned image generation prompt from the creative concept.

> **Node Metadata** | node: 5/6 boundary | type: llm | model: gemini-3.1-pro | ticket: GH-11 | version: 0.2.0 | status: draft

## Node Invariants

1. **No text/logos/UI/faces in output.** All forbidden terms are replaced with safe alternatives — never just removed, always substituted.
2. **Word count enforced.** Output is 60-120 words. Below 60: quality language appended. Above 120: trimmed from end.
3. **Brand directives applied.** `image_style_directives` from BrandContext are always incorporated.
4. **16:9 aspect implied.** The prompt is structured for landscape ecommerce banner composition.

## Graph Entry Conditions

- **Upstream:** `draft_banner_concept` (node 5) must have completed.
- **State preconditions:** `state.concept is not None` (with `image_prompt` field).
- **Retry re-entry:** Re-entered when audit routes to `retry_node_5` → concept regenerated → prompt re-refined.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| State/param | `concept_or_prompt` | `Concept \| dict \| str` | Yes |
| Function param | `image_style_directives` | `str \| list[str] \| None` | Optional |
| Function param | `brand_context` | `BrandContext \| None` | Optional — provides palette + directives |
| Function param | `art_direction` | `dict \| None` | Optional — background_mode, fold_percentage |
| Function param | `catalog_context` | `dict \| None` | Optional — product title for catalog focus |

## Output Encoding

- **Type:** `str` — single paragraph, 60-120 words.
- **Language:** English (image gen prompts are always English).
- **Structure:** Descriptive paragraph safe for `gemini-3.1-pro-image`.

## Data Sources

| Source | Purpose |
|--------|---------|
| State: `concept.image_prompt` | Base prompt to refine |
| State: `brand_context.image_style_directives` | Style rules to incorporate |
| State: `brand_context.palette` | Color hex values for palette accents |
| Internal: `_FORBIDDEN_REPLACEMENTS` dict | 34-entry substitution table |

No external tools. No sub-agents. No prompt file loaded (self-contained logic).

## Workflow

1. Extract base prompt from `concept.image_prompt` (or raw string/dict).
2. Extract layout description from `concept.layout` if available.
3. Collect brand style directives from params + `brand_context.image_style_directives`.
4. Sanitize each directive via `_sanitize()` — replace forbidden terms with safe alternatives.
5. Extract palette hex colors from brand_context (up to 4).
6. Extract product title from catalog_context if available.
7. Extract background_mode and fold_percentage from art_direction.
8. Build prompt parts:
   a. "Create a 16:9 ecommerce banner background featuring {sanitized base}."
   b. "Use a responsive composition with generous blank copy space..."
   c. "Style it as {sanitized directives}."
   d. Palette accents (if available).
   e. Catalog focus (if available).
   f. Art direction (if available).
   g. Safety suffix: "mark-free, symbol-free, interface-free, people-free..."
9. Join into single paragraph.
10. **Word count gate:**
    - If < 60 words: append quality language ("Keep lighting polished...").
    - If > 120 words: trim from end, add period.
11. Return refined prompt string.

## Output Contract

No state field written directly — output is consumed by `nano-banana-image-generate` (node 6) as input parameter.

Return type: `str`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| Refined prompt | `[DETERMINISTIC]` — constructed from sanitized inputs (current impl) |
| Safety substitutions | `[DETERMINISTIC]` — from `_FORBIDDEN_REPLACEMENTS` lookup table |
| Word count adjustment | `[DETERMINISTIC]` — padding/trimming algorithm |

## Pre/Post Conditions

**Pre:**
- `concept_or_prompt is not None`
- If Concept: `concept.image_prompt != ""`

**Post:**
- Result is a non-empty string
- `60 <= word_count(result) <= 120`
- None of the forbidden terms appear in output: "text", "logo", "face", "ui", "button", "modal", "screen", "typography", "signage"
- Result does not start with "No" or contain negation patterns

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| `concept_or_prompt` is None/empty | Raise `ValueError` → pipeline halts |
| `image_style_directives` is None | Use generic "clean commercial ecommerce photography" |
| All brand palette colors missing | Omit palette accents section — still produces valid prompt |
| Prompt after sanitization is < 10 words | Rebuild from product/brand context with generic scene description |

## Quality Criteria

- [ ] No text/logos/UI/faces mentions in output
- [ ] Aspect 16:9 implied in prompt structure
- [ ] Brand directives applied (image_style_directives present in output)
- [ ] Word count between 60-120
- [ ] Forbidden term "text overlay" → replaced with "blank copy space"
- [ ] Forbidden term "no logos" → replaced with "mark-free brand-safe styling"

## Guardrails

- Never output negation patterns ("no text", "no logos") — image models interpret these as requests TO include them. Always use positive substitutions.
- Never include brand names other than the current brand in the prompt.
- Never include price, discount, or promotional copy — that belongs in HTML, not images.
- Never reference specific real people by name.
- Never exceed 120 words — image model quality degrades with long prompts.

## Human Review Required

None. Automated node. Image prompts are reviewed indirectly via HITL at node 10.

## References

- Prompt template: `image_prompt_refine.md` → `backend/app/agents/prompts/image_prompt_refine.md`
- State model: `Concept` → `backend/app/agents/state.py`
- Upstream skill: `banner-concept-draft` (node 5)
- Downstream skill: `nano-banana-image-generate` (node 6)
- Design reference: Source Technical Design §4 — [6] generate_image safety rules
