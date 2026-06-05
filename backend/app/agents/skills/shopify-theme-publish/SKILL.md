---
name: shopify-theme-publish
description: Publish Liquid Section + optimized image assets to a Shopify theme via Admin API GraphQL themeFilesUpsert. WRITE ACTION — requires HITL approval upstream (node 10). Deterministic, no LLM. Node 12 in the ADK graph.
---

# Shopify Theme Publish

Push approved banner assets and Liquid config to the live Shopify theme.

> **Node Metadata** | node: 12 | type: deterministic | model: none | ticket: GH-19 | version: 0.3.0 | status: draft | policy: write-action

## Node Invariants

1. **HITL approval is mandatory upstream.** This node MUST NOT execute unless `state.hitl_decision.action in {"approve", "schedule-resolved"}` (campaign status `scheduled`/`published`). The Coordinator enforces this gate.
2. **Dry-run is the default.** `SHOPIFY_PUBLISH_DRY_RUN=true` (or `?dry_run=true`) simulates: it computes the config + idempotency key + a job row and returns `would_write_metafield`/`would_install`, WITHOUT touching the live theme/metafield. A real publish requires an explicit `dry_run=false`.
3. **Idempotent.** Payload hash check before upsert — re-running with the same assets does not duplicate (`create_or_get` job by stable key).
4. **Fail-closed.** Missing Shopify credentials, invalid campaign state, or API errors block publish — never silently succeed; the token never appears in payloads/logs.
5. **No LLM.** Pure API integration via Shopify Admin GraphQL.

## Graph Entry Conditions

- **Upstream:** `schedule_or_publish` (node 11) must have returned `"immediate"`, OR scheduled publish time has arrived.
- **State preconditions:** `state.hitl_decision is not None`, `state.hitl_decision.action in {"approve", "schedule-resolved"}`, `state.liquid_section is not None`, `state.assets is not None`.
- **Retry re-entry:** Not retried via graph audit loop. Internal retry is exponential 3x on 5xx.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| State | `hitl_decision` | `HITLDecision` | Yes — action must be approve/schedule-resolved |
| State | `liquid_section` | `str` | Yes |
| State | `assets` | `BannerAssets` | Yes |
| State/derived | `campaign_id` | `str` | Yes |

## Output Encoding

- **Model:** `app.agents.state.PublishResult` (Pydantic)
- **Key fields:** `shopify_section_id: str`, `theme_id: str`, `asset_urls: list[str]`

## Data Sources

| Source | Purpose |
|--------|---------|
| Service: `configured_publisher()` | Shopify publisher with credentials |
| Tool: `shopify.py` | Admin GraphQL `themeFilesUpsert` |
| State: campaign_id, liquid_section, assets | Payload construction |

No prompts. No sub-agents.

## Workflow

1. Validate HITL decision: `state.hitl_decision.action in {"approve", "schedule-resolved"}`.
2. Extract `campaign_id` from state.
3. Call `configured_publisher().publish_campaign(campaign_id)`.
4. Publisher internally:
   a. Build payload: `.liquid` section file + 4 WebP + 4 AVIF assets.
   b. Hash payload for idempotency check.
   c. Call Shopify Admin GraphQL `themeFilesUpsert`.
   d. On 5xx: exponential retry up to 3x.
   e. Update campaign metafield (`aijolot:banner_campaigns`).
5. Build `PublishResult` with `shopify_section_id`, `theme_id`, `asset_urls`.
6. Emit audit_log event with `shopify_section_id`.
7. Return `PublishResult`.

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.publish_result` | `PublishResult` | Shopify section ID + theme ID + asset URLs |

Return type: `PublishResult`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| `shopify_section_id` | `[PROVIDER]` — returned by Shopify Admin API |
| `theme_id` | `[PROVIDER]` — from Shopify store config |
| `asset_urls` | `[PROVIDER]` — Shopify CDN URLs for uploaded assets |

## Pre/Post Conditions

**Pre:**
- `state.hitl_decision is not None`
- `state.hitl_decision.action in {"approve", "schedule-resolved"}`
- `state.liquid_section is not None`
- `state.assets is not None`
- Shopify credentials configured (SHOPIFY_SHOP_DOMAIN, SHOPIFY_ADMIN_ACCESS_TOKEN)

**Post:**
- `state.publish_result is not None`
- `state.publish_result.shopify_section_id != ""`
- audit_log event emitted with `shopify_section_id`

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| HITL decision missing or invalid | Raise `ValueError("campaign_id is required")` → pipeline halts |
| Shopify credentials not configured | Publisher raises config error → pipeline halts (fail-closed) |
| Shopify API 5xx | Retry exponential 3x, then raise → pipeline halts |
| Shopify API 4xx (invalid payload) | Raise immediately (no retry) → pipeline halts |
| Duplicate publish (same hash) | Return existing `PublishResult` without re-uploading (idempotent) |
| `search_results_banner` placement | Publisher rejects with clear error — unsupported placement |

**Never auto-publish.** If any validation fails, halt with error rather than partially publishing.

## Quality Criteria

- [ ] Idempotent: same payload hash → no duplicate upsert
- [ ] Retry exponential 3x on Shopify 5xx errors
- [ ] Section .liquid + 4 WebP + 4 AVIF assets uploaded
- [ ] Emits audit_log with `shopify_section_id`
- [ ] Fails closed when Shopify credentials are missing
- [ ] Campaign metafield updated after successful publish

## Guardrails

- **NEVER publish without HITL approval.** Check `hitl_decision.action` before any API call.
- Never retry on 4xx — these indicate payload errors that retrying won't fix.
- Never partially publish — if any asset upload fails, roll back the entire operation.
- Never expose Shopify admin token in logs or error messages.
- Never publish to a placement type the theme doesn't support.

## Human Review Required

**Yes — indirectly.** This node does not request review itself, but it MUST NOT execute without prior HITL approval at node 10. The Coordinator enforces this gate.

Write actions performed:
- Shopify Admin GraphQL `themeFilesUpsert` (Liquid section + image assets)
- Shopify metafield update (`aijolot:banner_campaigns`)

## Publish Operations (F10 surface)

| Operation | Endpoint | Effect |
|-----------|----------|--------|
| Install placeholders | `POST /stores/{id}/shopify/install-theme-files` | Idempotent `put_theme_asset` of `aijolot-*` snippets/sections (append-only; never overwrites merchant templates). `?dry_run=` supported. |
| Publish | `POST /campaigns/{id}/publish` | Writes the `aijolot.banner_campaigns` shop metafield + theme assets. `?dry_run=true` simulates. |
| Unpublish | `POST /campaigns/{id}/unpublish` | Removes the campaign from the metafield array (cleans the anchor). `?dry_run=` supported. |

The publisher is request-scoped (`configured_publisher(team_id=…)`); `dry_run`
from `SHOPIFY_PUBLISH_DRY_RUN` is overridable per request. `search_results_banner`
remains rejected at publish (anchor preview only).

## Reuse vs Adopt — Shopify "build with AI"  [DECISION]

Evaluation of giving the agent Shopify's build-with-ai offering for publishing
(per the URL the operator referenced — grounded in what the page states, dated 2026-06-04):

- The page offers: AI app builders (v0/Lovable/Replit/Manus) for storefronts;
  chat assistants (ChatGPT/Claude/Perplexity) for merchant store management
  ("add products, check orders, update prices"); the **Shopify AI Toolkit**
  (a dev CLI/MCP across Claude Code/Cursor/Gemini CLI/VS Code/Codex); and
  **Sidekick** (merchant assistant). `[FACT]` (from the page).
- The page does **not** name a programmatic API/MCP for an agent to publish
  themes/sections/banners/metafields. `[FACT]` (absence on the page).
- Our publish primitive — Admin GraphQL `themeFilesUpsert` + `metafieldsSet` —
  is the correct, supported, already-verified-e2e path for programmatic banner
  publish. `[FACT]` (F10 e2e: metafield written + cleared).

**Decision: REUSE the native Admin GraphQL publisher.** The build-with-ai tools
are merchant-facing (Sidekick) or developer-workflow (AI Toolkit CLI) — not a
replacement for the agent's programmatic, idempotent, dry-run-gated publish.
`[INFERENCE]` from the above.

**Adopt-later candidate:** the Shopify AI Toolkit (MCP) could complement *developer*
workflows (scaffolding/extending the theme), not the runtime publish path. Mark
`[HYPOTHESIS]` — validate the MCP's capabilities + auth model before adopting; do
not assume it can replace `themeFilesUpsert`.

## References

- Service: `configured_publisher()` → `backend/app/services/shopify/publisher.py`
- Tool: `shopify` → `backend/app/agents/tools/shopify.py`
- State models: `PublishResult`, `HITLDecision` → `backend/app/agents/state.py`
- Config: `SHOPIFY_*` env vars → `backend/app/core/settings.py`
- Upstream skills: `schedule-or-publish-route` (node 11), `hitl-review-handoff` (node 10)
- Design reference: Source Technical Design §8 — publish_to_shopify via Admin API themeFilesUpsert

## Version History

| Version | Date       | Change                                                              | Owner   |
|---------|------------|---------------------------------------------------------------------|---------|
| 0.2.0   | 2026-05    | Initial publish contract (themeFilesUpsert + metafield, HITL gate)  | AIjolot |
| 0.3.0   | 2026-06-04 | F10 surface (dry-run default + ?dry_run, install-theme, unpublish, request-scoped publisher); Reuse-vs-Adopt decision on Shopify build-with-ai | AIjolot |
