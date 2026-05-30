---
name: nano-banana-image-generate
description: Generate a 16:9 banner image via Nano Banana Pro (gemini-3.1-pro-image).
metadata:
  type: deterministic-llm
  model: gemini-3.1-pro-image
  owner_node: 6
  ticket: GH-12
---

## Inputs
- `prompt: str` (refined by image-prompt-refine skill)

## Outputs
- `image_bytes: bytes` (16:9)

## Acceptance criteria
- [ ] Aspect 16:9 enforced
- [ ] Safety filter `block_some` enabled
- [ ] cost_usd logged per invocation
- [ ] Retry 1× if safety rejects (with adjusted prompt)
- [ ] Daily cost cap enforced (DAILY_COST_CAP_USD)
