---
name: image-prompt-refine
description: Strip unsafe content from Concept.image_prompt, enforce brand directives. Gemini 3.1 Pro.
metadata:
  type: llm
  model: gemini-3.1-pro
  owner_node: "5/6 boundary"
  ticket: GH-11
---

## Inputs
- `concept.image_prompt: str`
- `brand_context.image_style_directives: str`

## Outputs
- Refined prompt (60-120 words) safe for `gemini-3.1-pro-image`.

## Acceptance criteria
- [ ] No text/logos/UI/faces mentions in output
- [ ] Aspect 16:9 implied
- [ ] Brand directives applied
