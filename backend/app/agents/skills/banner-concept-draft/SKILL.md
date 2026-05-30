---
name: banner-concept-draft
description: Brand-aligned Concept (copy + layout + image_prompt) via CreativeDirector (Gemini 3.1 Pro).
metadata:
  type: llm
  model: gemini-3.1-pro
  owner_node: 5
  sub_agent: creative_director
  ticket: GH-11, GH-NEW6
---

## Inputs
- `brand_context: BrandContext`
- `campaign: Campaign`
- `variants: list[Variant]`
- `best_practices: list[KGDocument]`

## Outputs
- `Concept{copy, layout, palette_usage, image_prompt, hierarchy_notes}`

## Acceptance criteria
- [ ] No `prohibited_words` in copy
- [ ] Palette references token names, not literal hex
- [ ] image_prompt has no text/logos/UI/faces
- [ ] Concept respects voice.tone
