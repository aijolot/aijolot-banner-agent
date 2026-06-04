---
name: refinement-route
description: Classify a free-text refinement prompt into the banner pipeline nodes to re-run (concept, copy, image, background, layout). Deterministic keyword routing (ES + EN) with an optional Gemini FLASH classifier; defaults to concept+copy when nothing matches. Used by the agentic refine box (F9) to drive a targeted re-generation.
---

# Refinement Route

Turn "make the copy more urgent and change the background" into a set of target
nodes so the orchestrator re-runs only what the designer asked for.

## Targets
- `concept`  — overall creative direction
- `copy`     — headline / subhead / CTA wording
- `image`    — regenerate the hero/product image
- `background` — propose/apply a new AI background (F7)
- `layout`   — re-query KG liquid_pattern layouts (F6)

## Invariants
1. **Never empty.** Falls back to `{concept, copy}` when no signal is found.
2. **Deterministic-first.** Keyword routing works offline; Gemini only sharpens
   ambiguous prompts and is skipped without a key / on cost denial.
