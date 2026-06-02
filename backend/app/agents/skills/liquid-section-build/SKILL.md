---
name: liquid-section-build
description: Build a Shopify Liquid Section and block snippet with conditional customer.tags-based variant rendering from Concept + Variants + BrandContext. Deterministic Jinja2 rendering, no LLM. Node 8 (parallel) in the ADK graph.
---

# Liquid Section Build

Generate Shopify-compatible Liquid Section + snippet with customer.tags-based personalization.

> **Node Metadata** | node: 8 (parallel) | type: deterministic | model: none | ticket: GH-15 | version: 0.2.0 | status: draft

## Node Invariants

1. **Default variant always present.** The Liquid `{% case %}` block always includes a default/else branch.
2. **Liquid is syntactically valid.** Parseable by Shopify's Liquid engine without errors.
3. **Personalization via customer.tags only.** No JavaScript, no cookies, no external API calls in the Liquid output.
4. **No LLM.** Pure Jinja2 template rendering.

## Graph Entry Conditions

- **Upstream:** `optimize_assets` (node 7) must have completed.
- **State preconditions:** `state.concept is not None`, `state.variants is not None` (at least default), `state.brand_context is not None`.
- **Parallel with:** `banner-html-seo-render` (both are node 8 outputs).
- **Retry re-entry:** Same as `banner-html-seo-render` — audit retry routes to node 5.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| State | `concept` | `Concept` | Yes |
| State | `variants` | `list[Variant]` | Yes (≥1 with `customer_tag="default"`) |
| Function param | `brand` | `BrandContext` | Yes |
| Function param | `assets` | `BannerAssets \| None` | Optional — for image references |
| Function param | `placement` | `str \| dict \| None` | Optional — for section schema settings |

## Output Encoding

- **Type:** `dict[str, str]` with keys `section` and `block_snippet`.
- **`section`:** Complete Shopify Liquid Section (`.liquid` file content).
- **`block_snippet`:** Reusable snippet for variant-specific block rendering.
- **Language:** Liquid template language. Text content follows campaign language.

## Data Sources

| Source | Purpose |
|--------|---------|
| Tool: `liquid_render.render()` | Jinja2 → Liquid output |
| Templates: `banner_section.liquid.j2`, `banner_block.liquid.j2` | Section/snippet structure |

No prompts. No sub-agents.

## Workflow

1. Receive `concept`, `variants`, `brand`, optional `assets` and `placement`.
2. Call `liquid_render.render(concept, variants, brand=brand, assets=assets, placement=placement)`.
3. Tool internally:
   a. Build `{% case chosen %}` block with one branch per variant `customer_tag`.
   b. Default variant maps to `{% else %}`.
   c. Each branch renders via `{% render 'banner-block', variant: '<tag>' %}`.
   d. Section schema includes settings for default_variant, images, colors.
   e. Block snippet receives variant parameter and renders copy + image.
4. Return `{section: str, block_snippet: str}`.

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.liquid_section` | `str` | Complete Liquid Section content |

Return type: `dict[str, str]` — `{section, block_snippet}`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| Liquid section structure | `[DETERMINISTIC]` — Jinja2 template |
| `{% case %}` branches | `[DETERMINISTIC]` — derived from `variants` list |
| Copy per variant | `[DETERMINISTIC]` — from `concept.copy` + `variant.copy_override` |
| Schema settings | `[DETERMINISTIC]` — from concept + brand |
| Image references | `[DETERMINISTIC]` — from `assets` if provided |

## Pre/Post Conditions

**Pre:**
- `state.concept is not None`
- `state.variants is not None and len(state.variants) >= 1`
- `any(v.customer_tag == "default" for v in state.variants)`
- `state.brand_context is not None`

**Post:**
- `state.liquid_section is not None`
- `"{% case" in state.liquid_section or "case" in state.liquid_section`
- `"default" referenced in section output`

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| `concept` is None | Raise `ValueError` → pipeline halts |
| `variants` is empty | Raise `ValueError` → at least default variant required |
| `assets` is None | Render Liquid without image references — images set via Shopify section settings |
| Template missing | Raise `FileNotFoundError` → pipeline halts |
| Variant with unknown tag | Render as additional `{% when '<tag>' %}` branch — no filtering |

## Quality Criteria

- [ ] Default variant + N variants produce correct `customer.tags` case blocks
- [ ] Liquid is syntactically valid (parseable by Liquid linter)
- [ ] Snippet receives variant as parameter
- [ ] Section schema includes editable settings
- [ ] Output works without `assets` (images configurable via Shopify admin)

## Guardrails

- Never produce Liquid without a default/else branch — always handle unknown customer tags.
- Never embed JavaScript in Liquid output — Shopify Sections are server-rendered.
- Never hardcode image URLs — use section settings or asset references.
- Never include `customer.email` or PII in Liquid — only `customer.tags` for personalization.

## Human Review Required

None. Automated node. Liquid output is a build artifact — published only by node 12.

## References

- Tool: `liquid_render` → `backend/app/agents/tools/liquid_render.py`
- Templates: `backend/app/templates/banner_section.liquid.j2`, `banner_block.liquid.j2`
- State models: `Concept`, `Variant` → `backend/app/agents/state.py`
- Upstream skill: `image-asset-optimize` (node 7)
- Parallel skill: `banner-html-seo-render` (node 8)
- Downstream skill: `performance-audit` (node 9)
- Design reference: Source Technical Design §6 — Personalization via Shopify Sections
