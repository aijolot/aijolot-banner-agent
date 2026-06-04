---
name: art-prompt-propose
description: Propose N descriptive image-generation prompts (text only — generation is a separate step) for a banner, in two modes. hero = distinct stylistic directions; usage = the SAME model/product description across predefined camera angles (front, three_quarter, top_down, in_use) for consistency, optionally tied to a background option from F7. Also proposes model/usage-shot descriptions by gender. Gemini FLASH (structured) when available + within cost cap; deterministic fallback otherwise. Every returned prompt is sanitized through image-prompt-refine (no text/logos/UI/faces-in-image, brand-safe).
---

# Art Prompt Propose

Step 1 of the two-step art contract (#7/#8): propose prompts cheaply, let the
designer pick, then generate the chosen one with `generate-art`.

## Invariants

1. **Sanitized.** Every prompt passes through `image-prompt-refine`, which strips
   text/logo/UI/face directives and enforces brand-safe, copy-space composition.
2. **Usage consistency.** In `usage` mode the model/product description is held
   constant across variants; only the camera angle changes, so the same subject
   is explored from `front, three_quarter, top_down, in_use`.
3. **Background-aware.** A `background_ref` (from F7) is carried on each usage
   option so generation can compose the chosen background behind the subject.
4. **Cost-capped, fail-closed.** Reserves the daily Gemini cost guard; on denial
   or `GeminiUnavailable`, returns deterministic variants instead.
