---
name: background-options-generate
description: Generate N (default 3) self-contained HTML/CSS background treatments for the .aijolot-banner surface from the banner concept + brand palette. Uses Gemini FLASH with structured output, gated by the daily cost guard, and fails closed to deterministic brand-palette gradients. All returned CSS/HTML is sanitized before it can reach a preview (no @import, external url(), expression(), script/iframe, inline event handlers).
---

# Background Options Generate

Propose distinct, accessible background looks for the banner hero surface. The
options feed the canvas/art stage (F7) and later art generation (F8).

## Invariants

1. **Self-contained.** Every option's CSS is scoped to `.aijolot-banner` and uses
   no external assets — gradients, colors, and brand palette tokens only.
2. **Sanitized.** CSS/HTML is stripped of `@import`, external `url(http…)`,
   `expression(`, `javascript:`, `<script>`, `<iframe>`, and inline `on*=`
   handlers before return. An option whose CSS is emptied by sanitization is
   replaced with a deterministic gradient.
3. **Cost-capped, fail-closed.** Reserves against the daily Gemini cost guard;
   on denial or `GeminiUnavailable`, returns deterministic brand-palette
   gradients instead. Retrieval/generation never blocks the demo.
4. **Accessible contrast.** Fallback gradients pair brand background tones with a
   contrasting text token so HTML copy stays legible.
