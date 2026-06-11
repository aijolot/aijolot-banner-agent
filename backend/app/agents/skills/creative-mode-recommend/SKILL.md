---
name: creative-mode-recommend
description: Recommend the banner's creative mode (composite product cut-out vs full-picture generated scene vs video) and whether humans should appear, from the campaign brief + brand context + placement. Gemini FLASH structured output with a deterministic vertical-keyword fallback. The recommendation is advisory — a user override (art_directions.mode_source='user') is always authoritative.
---

# Creative Mode Recommend (C0)

## Modes
- `composite`    — product cut-out over an AI background (today's default). Best for product-led promos, hardware, electronics, B2B.
- `full_picture` — Nano Banana generates the FULL scene (lifestyle/editorial, full-bleed); only text + CTA are HTML. Best for fashion, beauty, fragrance, lifestyle moods.
- `video`        — short Veo loop as the hero background. ONLY recommended when `VIDEO_GENERATION_ENABLED` and the placement is a main hero (it is expensive).

## include_humans
Recommend `true` for verticals where people sell the product (fashion, beauty, fitness, jewelry); `false` for tools, electronics, packaged goods. The image-prompt sanitizer keeps `people-free` unless this flag is set (C3).

## Invariants
1. **Deterministic-first.** Keyword rules over goal/audience/products/tone work offline; Gemini only sharpens.
2. **User override wins.** Never re-recommend over `mode_source='user'` (enforced by the orchestrator, not this skill).
3. **Video is gated.** Without the env flag the skill never returns `video`.

## Contract
`recommend(campaign, brand_context, *, placement="", settings=None, cost_guard=None) -> CreativeModeRecommendation`
