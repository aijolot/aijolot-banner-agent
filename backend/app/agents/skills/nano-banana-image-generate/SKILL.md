---
name: nano-banana-image-generate
description: Generate a 16:9 banner image through the safe image-provider boundary.
metadata:
  type: provider-boundary
  model: gemini-3.1-pro-image
  owner_node: 6
  ticket: GH-12
---

## Inputs
- `prompt: str` or `concept.image_prompt` (normally refined by image-prompt-refine skill)
- `user_id: str | None`
- `team_id: str | None`
- `campaign_id: str | None`
- `aspect_ratio: str = "16:9"`

## Outputs
Returns a dict with:
- `image_bytes: bytes` raw provider image bytes, kept in memory for Task 13 optimization/upload
- `mime_type: str`
- `provider: str`
- `model: str`
- `prompt: str`
- `aspect_ratio: str`
- `usage: dict`
- `metadata.size_bytes: int`
- `metadata.usage_guard: dict` including count, limit, window, and warning

## Acceptance criteria
- [x] Real image provider is behind explicit configuration.
- [x] Fake provider is deterministic and default-safe for tests/demo paths.
- [x] Raw image bytes are returned for the asset optimization/upload step.
- [x] Usage warning metadata is attached per invocation.
- [x] Soft guard warns at 20 image generations per user per 15 minutes.
- [ ] Optimized/uploaded durable assets are produced by Task 13.
- [ ] Daily cost cap enforcement is deferred to later production hardening.
