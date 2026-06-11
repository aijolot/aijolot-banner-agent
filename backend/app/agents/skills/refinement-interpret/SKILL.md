---
name: refinement-interpret
description: Interpret a free-text banner refinement prompt into a minimal set of DIRECTED edit operations (set_ink, change_decor, change_background, edit_copy, adjust_layout, redraft_concept) so plan-iterate only changes what the user asked for. Gemini FLASH structured output grounded in the current concept; deterministic keyword fallback via refinement-route. Explicit user targets bypass the LLM.
---

# Refinement Interpret (W0.1)

Turn "la fuente negra no contrasta bien" into `set_ink` (auto-contrast) and
"cambia el SVG de círculo por una estrella de mar" into `change_decor` — instead
of the legacy behavior where both fell into the default route and the background
was regenerated unconditionally.

## Operations
- `set_ink`           — text color / contrast / legibility. `value` = hex when named, empty = auto-contrast. Optional `section`.
- `change_decor`      — swap/edit decorative SVG shapes inside the background, keeping colors/gradient.
- `change_background` — regenerate the background treatment (instruction-led).
- `edit_copy`         — rewrite copy wording/tone (instruction-led).
- `adjust_layout`     — composition/structure changes.
- `redraft_concept`   — full creative re-draft (only when explicitly asked).

## Invariants
1. **Minimal ops.** Never add operations the user did not ask for.
2. **Explicit targets win.** When the caller passes targets (scoped UI control), they are mapped 1:1 to ops with no LLM call.
3. **Deterministic-first.** Without a Google API key (or on any LLM failure) the keyword router (`refinement-route`, extended with `ink` and `decor` targets) decides.
4. **Traceable.** The resulting plan carries `source` (`gemini` | `deterministic` | `explicit`) and op list; the orchestrator emits them in the generation event `output_summary.interpreted_ops`.

## Contract
`interpret(prompt, *, targets=None, concept=None, settings=None, cost_guard=None) -> RefinementPlan`
(`RefinementPlan` / `RefinementOp` live in `app.schemas.refinement`.)
