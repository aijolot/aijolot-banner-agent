---
name: image-asset-optimize
description: Generate responsive image breakpoints (WebP + AVIF + JPG fallback) from raw image bytes for Shopify banner srcset. Deterministic Pillow-based optimization, no LLM. Node 7 in the ADK graph.
---

# Image Asset Optimize

Generate 4-breakpoint responsive image set with WebP, AVIF, and JPG fallback from a single source image.

> **Node Metadata** | node: 7 | type: deterministic | model: none | ticket: GH-13 | version: 0.2.0 | status: draft

## Node Invariants

1. **All 4 breakpoints always generated.** Output contains 320, 768, 1280, 1920 widths for WebP and AVIF.
2. **Weight cap enforced.** 1280 WebP must be ≤80KB where feasible (assertion in tests, warn above 300KB).
3. **Alt text always present.** `alt_text_suggestion` is never empty — falls back to hint or generic description.
4. **No LLM.** Pure Pillow image processing.

## Graph Entry Conditions

- **Upstream:** `generate_image` (node 6) must have completed.
- **State preconditions:** `state.image_bytes is not None`.
- **Retry re-entry:** Not directly retried. If audit (node 9) detects weight issues, retry goes to node 5 or 8 — not this node.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| State | `image_bytes` | `bytes` | Yes |
| Function param | `alt_text_hint` | `str` | Yes |
| Function param | `campaign_id` | `str \| None` | Optional |
| Function param | `revision_id` | `str \| None` | Optional |
| Function param | `banner_variant_id` | `str \| None` | Optional |
| Function param | `mime_type` | `str \| None` | Optional — auto-detected if missing |
| Function param | `image_prompt` | `str \| None` | Optional — enriches alt text |
| Function param | `asset_service` | `BannerAssetService \| None` | Optional — for Supabase upload |

## Output Encoding

- **Model:** `app.agents.state.BannerAssets` (Pydantic)
- **Key fields:** `webp: dict[int, str]`, `avif: dict[int, str]`, `fallback_jpg: dict[int, str]`, `alt_text_suggestion: str`, `total_weight_kb_1280_webp: float`, `asset_records: list[dict]`, `optimization_report: dict`
- **Size keys:** `{320, 768, 1280, 1920}` — values are base64 data URIs or Supabase Storage URLs.
- **Limits:** `alt_text_suggestion` ≤ 120 chars.

## Data Sources

| Source | Purpose |
|--------|---------|
| Tool: `image_optim.optimize()` | Pillow-based resize + encode |
| Service: `BannerAssetService` | Optional Supabase Storage upload |

No prompts. No sub-agents.

## Workflow

1. Receive raw `image_bytes` from state (produced by node 6).
2. Call `image_optim.optimize()` with all params.
3. Tool internally:
   a. Detect source format (PNG/JPEG/WebP).
   b. Resize to 4 breakpoints: 320, 768, 1280, 1920 (maintain aspect ratio).
   c. Encode each size in WebP (quality ~82) + AVIF (quality ~60) + JPG fallback at 1280.
   d. Calculate total weight.
   e. Generate `alt_text_suggestion` from hint + image_prompt.
   f. If `asset_service` provided, upload to Supabase Storage.
4. Return `BannerAssets` Pydantic model.

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.assets` | `BannerAssets` | Responsive image set with all breakpoints |

Return type: `BannerAssets`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| `webp` | `[DETERMINISTIC]` — Pillow resize + encode |
| `avif` | `[DETERMINISTIC]` — Pillow + pillow-avif-plugin |
| `fallback_jpg` | `[DETERMINISTIC]` — Pillow JPEG encode |
| `alt_text_suggestion` | `[DETERMINISTIC]` — derived from `alt_text_hint` param |
| `total_weight_kb_1280_webp` | `[DETERMINISTIC]` — calculated from encoded bytes |
| `asset_records` | `[DETERMINISTIC]` — metadata list from tool |
| `optimization_report` | `[DETERMINISTIC]` — encode stats |

## Pre/Post Conditions

**Pre:**
- `state.image_bytes is not None`
- `len(state.image_bytes) > 0`

**Post:**
- `state.assets is not None`
- `all(size in state.assets.webp for size in [320, 768, 1280, 1920])`
- `1280 in state.assets.fallback_jpg`
- `len(state.assets.alt_text_suggestion) <= 120`
- `state.assets.alt_text_suggestion != ""`

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| `image_bytes` is empty/corrupt | Pillow raises `UnidentifiedImageError` → pipeline halts |
| AVIF encoding fails (missing plugin) | Mark `avif_skipped: True` in optimization_report, continue with WebP + JPG |
| Weight exceeds 80KB at 1280 | Warn in report but do NOT halt — audit node handles threshold |
| `alt_text_hint` is empty | Fall back to "Banner image" generic alt text |
| Supabase upload fails | Log warning, return base64 data URIs instead of URLs |

## Quality Criteria

- [ ] All 4 breakpoints generated for WebP + AVIF
- [ ] JPG fallback at 1280 exists
- [ ] Weight cap <80KB @ 1280 WebP enforced (assertion in test)
- [ ] `alt_text_suggestion` ≤ 120 chars and non-empty
- [ ] AVIF skip produces `avif_skipped: True` (not a crash)
- [ ] Base64 fallback works when Supabase is unavailable

## Guardrails

- Never discard breakpoints — always produce all 4 sizes, even if source is smaller (upscale if necessary).
- Never return empty alt text — always fall back to generic.
- Never fail the pipeline on AVIF skip — AVIF is a progressive enhancement.
- Never upload to Supabase without explicit `asset_service` — local/demo mode uses base64.

## Human Review Required

None. Automated node. No external writes (Supabase upload is optional and controlled by caller).

## References

- Tool: `image_optim` → `backend/app/agents/tools/image_optim.py`
- Service: `BannerAssetService` → `backend/app/services/banners/asset_service.py`
- State model: `BannerAssets` → `backend/app/agents/state.py`
- Upstream skill: `nano-banana-image-generate` (node 6)
- Downstream skills: `banner-html-seo-render` (node 8), `liquid-section-build` (node 8)
