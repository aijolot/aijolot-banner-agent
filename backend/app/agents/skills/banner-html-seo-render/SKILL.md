---
name: banner-html-seo-render
description: Render a standalone W3C-valid HTML banner with SEO meta tags, JSON-LD PromotionalOffer, and responsive picture srcset from Concept + BannerAssets + BrandContext. Deterministic Jinja2 rendering, no LLM. Node 8 in the ADK graph.
---

# Banner HTML SEO Render

Produce a self-contained HTML preview with full SEO markup from the creative concept and optimized assets.

> **Node Metadata** | node: 8 | type: deterministic | model: none | ticket: GH-14 | version: 0.2.0 | status: draft

## Node Invariants

1. **Output is W3C-valid HTML.** Validated by `audit_w3c` in node 9.
2. **SEO markup is always present.** `og:title`, `og:description`, `og:image` meta tags + JSON-LD `PromotionalOffer`.
3. **Responsive images via `<picture>`.** Full srcset with WebP, AVIF sources, and JPG fallback.
4. **No LLM.** Pure Jinja2 template rendering.

## Graph Entry Conditions

- **Upstream:** `optimize_assets` (node 7) must have completed.
- **State preconditions:** `state.concept is not None`, `state.assets is not None`, `state.brand_context is not None`.
- **Retry re-entry:** Can be re-entered if audit (node 9) returns `retry_node_8`. `max_retries = 0` on this node itself in graph.py, but audit can route back to node 5 which regenerates concept → re-triggers node 8.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| State | `concept` | `Concept` | Yes |
| State | `assets` | `BannerAssets` | Yes |
| Function param | `brand` | `BrandContext` | Yes |

## Output Encoding

- **Type:** `str` — self-contained HTML document.
- **Content:** Valid HTML5 with inline CSS, `<picture>` srcset, `<meta>` OG tags, `<script type="application/ld+json">` JSON-LD.
- **Language:** Text content follows brand/campaign language.

## Data Sources

| Source | Purpose |
|--------|---------|
| Tool: `html_render.render()` | Jinja2 template → HTML |
| Templates: `banner_section.liquid.j2`, related | HTML structure |

No prompts. No sub-agents.

## Workflow

1. Receive `concept`, `assets`, `brand` from state/params.
2. Call `html_render.render(concept, assets, brand=brand)`.
3. Tool internally:
   a. Build `<picture>` element with AVIF/WebP/JPG sources and srcset breakpoints.
   b. Inject copy (headline, subheadline, CTA) from `concept.copy`.
   c. Apply palette from `concept.palette_usage` + `brand.palette`.
   d. Generate OG meta tags from concept copy.
   e. Generate JSON-LD `PromotionalOffer` schema.
   f. Render via Jinja2 template.
4. Return HTML string.

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.html_standalone` | `str` | Self-contained HTML for preview |

Return type: `str`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| HTML structure | `[DETERMINISTIC]` — Jinja2 template |
| Copy text (headline, subheadline, CTA) | `[DETERMINISTIC]` — pass-through from `concept.copy` |
| Image srcset URLs | `[DETERMINISTIC]` — from `assets.webp/avif/fallback_jpg` |
| OG meta tags | `[DETERMINISTIC]` — derived from concept copy |
| JSON-LD schema | `[DETERMINISTIC]` — template-based from concept + brand |
| CSS styling | `[DETERMINISTIC]` — palette tokens mapped to colors |

## Pre/Post Conditions

**Pre:**
- `state.concept is not None`
- `state.assets is not None`
- `state.brand_context is not None`

**Post:**
- `state.html_standalone is not None`
- `state.html_standalone` contains `<!DOCTYPE html>` or `<html`
- `"og:title"` appears in `state.html_standalone`
- `"PromotionalOffer"` appears in `state.html_standalone`

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| `concept` is None | Raise `ValueError` → pipeline halts |
| `assets` is None | Raise `ValueError` → pipeline halts |
| Jinja2 template missing | Raise `FileNotFoundError` → pipeline halts |
| AVIF assets skipped | Render `<picture>` with WebP + JPG only — no crash |
| JSON-LD fields empty | Render minimal valid JSON-LD with available fields |

## Quality Criteria

- [ ] HTML passes W3C validation (validated by `audit_w3c` tool in node 9)
- [ ] Meta tags present: `og:title`, `og:description`, `og:image`
- [ ] JSON-LD `PromotionalOffer` validates against Rich Results test
- [ ] `<picture>` element contains full srcset (WebP + AVIF + JPG fallback)
- [ ] Inline CSS applies brand palette colors correctly

## Guardrails

- Never produce HTML without DOCTYPE — always generate valid HTML5.
- Never omit OG meta tags — even with minimal concept data, generate from available fields.
- Never render `<img>` without `alt` attribute — use `assets.alt_text_suggestion`.
- Never inline raw hex colors — map through `concept.palette_usage` token names.

## Human Review Required

None. Automated node. Output is a preview artifact — not published to any external system.

## References

- Tool: `html_render` → `backend/app/agents/tools/html_render.py`
- Templates: `backend/app/templates/`
- State models: `Concept`, `BannerAssets` → `backend/app/agents/state.py`
- Upstream skills: `image-asset-optimize` (node 7)
- Parallel skill: `liquid-section-build` (node 8)
- Downstream skill: `performance-audit` (node 9)
