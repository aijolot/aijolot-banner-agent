---
name: placement-plan-recommend
description: From the campaign brief (goal, urgency, promo, products, audience) propose the SET of banner pieces to design — which placements (hero, collection header, announcement bar, PDP cross-sell…), how many, what format (real dimensions from the placement-type catalog) and which creative mode per piece, each with a one-line rationale. Gemini FLASH structured output with deterministic brief-driven rules as fallback. The placement becomes a consequence of the brief, not a manual pre-step.
---

# Placement Plan Recommend

## Pieces logic (deterministic floor)
1. `hero_main` — always piece 1 (the one the approve/build generates), inheriting the campaign's creative mode.
2. `collection_header` — when the brief features products (their collection deserves the campaign look).
3. `announcement_bar` — when urgency is high or there is a promo (global text strip reinforces the offer).
4. `pdp_cross_sell` — when 2+ products (cross-pollination on detail pages).

Cap: 4 pieces. Formats come from the placement-type catalog's real desktop dimensions — never invented.

## Invariants
1. **Keys are validated** against the placement-type catalog; unknown keys from the LLM are dropped.
2. **Piece 1 is buildable now**: the orchestrator generates it on approve; the rest are the campaign roadmap (visible in the plan, applicable from the UI).
3. **Deterministic-first**: works with zero LLM; Gemini only refines selection + rationales.

## Contract
`recommend(campaign, brand_context, *, creative_mode="composite", settings=None, cost_guard=None) -> PlacementPlanProposal`
(`app.schemas.placement_plan`.)
