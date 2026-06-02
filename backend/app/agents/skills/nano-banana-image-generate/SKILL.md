---
name: nano-banana-image-generate
description: Generate a 16:9 banner background image through the safe image-provider boundary. Supports real Gemini image gen (opt-in) and deterministic fake provider (default). Integrates UsageGuardService for soft rate limits. Node 6 in the ADK graph.
---

# Nano Banana Image Generate

Produce a banner background image via the controlled image-provider boundary.

> **Node Metadata** | node: 6 | type: provider-boundary | model: gemini-3.1-pro-image | ticket: GH-12 | version: 0.2.0 | status: draft

## Node Invariants

1. **Real provider is opt-in.** Default is fake/deterministic provider for safety. Real Gemini requires explicit config (`GOOGLE_API_KEY` + `IMAGE_GENERATION_PROVIDER=gemini`).
2. **Raw bytes returned.** Image stays in-memory as bytes — no file system writes. Optimization is node 7.
3. **Usage guard always active.** Every invocation records to `UsageGuardService`. Soft warning at ≥20 images per user per 15 minutes.
4. **Prompt must be pre-sanitized.** Input prompt comes from `image-prompt-refine` — this node does NOT sanitize.

## Graph Entry Conditions

- **Upstream:** `draft_banner_concept` (node 5) must have completed (typically via `image-prompt-refine`).
- **State preconditions:** `state.concept is not None` (with `image_prompt`), or explicit prompt string provided.
- **Retry re-entry:** `max_retries = 1` in graph.py. Can be retried once if audit detects image quality issues.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| Function param | `prompt` | `str \| Any` | Yes (or `concept`) |
| Function param | `concept` | `Concept \| dict \| None` | Optional — fallback for prompt |
| Function param | `context` | `dict \| None` | Optional — additional context |
| Function param | `user_id` | `str \| None` | Optional — for usage tracking |
| Function param | `team_id` | `str \| None` | Optional — for usage tracking |
| Function param | `campaign_id` | `str \| None` | Optional — for usage tracking |
| Function param | `aspect_ratio` | `str` | Optional — default `"16:9"` |
| Function param | `provider` | `ImageProvider \| None` | Optional — override default provider |
| Function param | `usage_guard` | `UsageGuardService \| None` | Optional — override default guard |

## Output Encoding

- **Type:** `dict[str, Any]`
- **Fields:** `image_bytes: bytes`, `mime_type: str`, `provider: str`, `model: str`, `prompt: str`, `aspect_ratio: str`, `usage: dict`, `metadata: dict`
- **`metadata` includes:** `size_bytes: int`, `usage_guard: dict` (count, limit, window, warning)
- **Image format:** PNG or JPEG depending on provider. Fake provider returns a minimal valid PNG.

## Data Sources

| Source | Purpose |
|--------|---------|
| Tool: `nano_banana_image.generate()` | Image generation boundary |
| Service: `UsageGuardService` | Rate limit tracking |
| Service: `ImageProvider` | Provider abstraction (real/fake) |
| Config: `IMAGE_GENERATION_PROVIDER`, `GOOGLE_API_KEY` | Provider selection |

No prompts. No sub-agents.

## Workflow

1. **Resolve prompt:** Check `prompt` param → `concept.image_prompt` → `context["prompt"]` → `context["image_prompt"]`. First non-empty wins.
2. If no prompt found → raise `ValueError`.
3. Call `nano_banana_image.generate(prompt, aspect_ratio=..., user_id=..., provider=..., metadata=...)`.
4. Provider internally:
   a. **Fake provider:** Return deterministic minimal PNG (for tests/demo).
   b. **Real provider:** Call Gemini image API with prompt + aspect ratio.
5. Record usage via `usage_guard.record_image_generation(...)`.
6. Build response dict with image_bytes, mime_type, provider info, usage stats.
7. Attach usage guard metadata (count, limit, window, warning flag).
8. Return response dict.

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.image_bytes` | `bytes` | Raw image bytes for optimization |

Return type: `dict[str, Any]`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| `image_bytes` | `[PROVIDER]` — from Gemini image API or fake provider |
| `mime_type` | `[PROVIDER]` — from image API response |
| `provider`, `model` | `[DETERMINISTIC]` — from configuration |
| `prompt` | `[DETERMINISTIC]` — pass-through of input |
| `usage` | `[PROVIDER]` — token/cost data from API |
| `metadata.usage_guard` | `[DETERMINISTIC]` — from UsageGuardService |

## Pre/Post Conditions

**Pre:**
- At least one of: `prompt` (non-empty str), `concept` (with `image_prompt`), `context` (with prompt key)
- If real provider: `GOOGLE_API_KEY` configured

**Post:**
- `state.image_bytes is not None`
- `len(state.image_bytes) > 0`
- Response `mime_type` is valid image type
- Usage guard record created

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| No prompt resolvable | Raise `ValueError("Image generation prompt is required")` → pipeline halts |
| Real provider not configured | Use fake provider (default) — returns deterministic PNG |
| Gemini API error | Provider raises → pipeline halts (retry is via graph retry, not internal) |
| Usage guard limit reached (≥20/15min) | Warn in metadata but do NOT block — soft limit only |
| Image too large (>10MB) | Provider-side limit — raises error |

See `references/usage_guard_policy.md` for rate limiting details.

## Quality Criteria

- [ ] Real image provider is behind explicit configuration
- [ ] Fake provider is deterministic and safe for tests/demo paths
- [ ] Raw image bytes returned for asset optimization step
- [ ] Usage warning metadata attached per invocation
- [ ] Soft guard warns at 20 images per user per 15 minutes
- [ ] Prompt resolution follows priority: param → concept → context
- [ ] `ValueError` raised when no prompt is resolvable

## Guardrails

- Never call the image API without a sanitized prompt — trust upstream `image-prompt-refine`.
- Never write image bytes to disk — keep in-memory for node 7.
- Never block on usage guard — it's a soft limit with warnings, not a hard block.
- Never expose API keys in response metadata or logs.
- Never retry internally — graph-level retry (max_retries=1) handles this.

## Human Review Required

None. Automated node. Generated images are reviewed at HITL (node 10).

## References

- Tool: `nano_banana_image` → `backend/app/agents/tools/nano_banana_image.py`
- Service: `UsageGuardService` → `backend/app/services/banners/usage_guard_service.py`
- Service: `ImageProvider` → `backend/app/services/gemini/image_provider.py`
- Config: `IMAGE_GENERATION_PROVIDER`, `DAILY_COST_CAP_USD` → `backend/app/core/settings.py`
- Detail: `references/usage_guard_policy.md`
- Upstream skill: `image-prompt-refine` (node 5/6 boundary)
- Downstream skill: `image-asset-optimize` (node 7)
