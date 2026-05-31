---
name: shopify-theme-publish
description: Publish Liquid Section + assets to Shopify theme via Admin API GraphQL themeFilesUpsert.
metadata:
  type: deterministic
  owner_node: 12
  ticket: GH-19
  policy: write-action — HITL approve required upstream
---

## Inputs
- `state: BannerSessionState` (must have hitl_decision.action in {approve, schedule-resolved})

## Outputs
- `PublishResult{shopify_section_id, theme_id, asset_urls}`

## Acceptance criteria
- [ ] Idempotent (payload hash check before upsert)
- [ ] Retry exponencial 3× on 5xx
- [ ] Section .liquid + 4 WebP + 4 AVIF assets uploaded
- [ ] Emits audit_log with shopify_section_id
