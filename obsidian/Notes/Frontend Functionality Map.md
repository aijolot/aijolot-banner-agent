---
title: Frontend Functionality Map
status: draft
source_branch: frontend/design-implementation
updated: 2026-05-28
---

# Frontend Functionality Map

This note summarizes the frontend prototype that now acts as the UX base for backend planning.

See also: [[Database Structure Proposal]]

## Architecture status

The current frontend is a static React prototype loaded by `frontend/index.html` with React UMD + Babel. It is not yet a Next.js app and has no backend API client. Its `frontend/data.jsx` file is the current source of truth for demo data and should be treated as the implied API/data contract.

## Studio flow

1. Placement
2. Brief
3. Art direction
4. Generation
5. Collaborative canvas
6. Performance

## Functional modules

### Campaign dashboard

Needs campaign list, campaign status, approval progress, active/published counters, average CTR, banners published, and saved weight metrics.

### Brand context

Needs full CRUD and import flow. Fields include logos, palette, typography, tone tags, allowed rules, forbidden rules, product imagery and image directives.

### Placement

Supports:

- home
- collection
- product
- search mock currently present in UI
- existing section update
- new section injection with layout JSON
- scope rules per page type

Backend MVP should support list/select resources. Search/autocomplete is deferred.

### Brief

Chat-like brief intake. Agent claims to query Shopify, validate stock, and calculate sale prices. Backend should persist raw brief, structured brief, catalog snapshot, and selected products.

### Art direction

Persists hero vs usage shot, hero style, selected/custom model, fold percentage, and inherited layout.

### Generation

Visible pipeline has 5 user-facing steps:

1. Smart Querying
2. Brand Guidelines Engine
3. AI aesthetic generation
4. HTML/Liquid compiler
5. Core Web Vitals Shield

These map onto the backend's 12-node ADK graph.

### Canvas/review

Needs:

- layout variants A/B/C
- desktop/tablet/mobile preview
- segment variants: masculine/feminine/VIP in demo
- pinned comments with x/y coordinates
- comment resolve state
- refinement requests and applied changes
- all-reviewers approval policy
- publish now or schedule
- auto-unpublish option

### Performance

Visible but can be mock/manual for MVP:

- impressions
- load time
- CTR
- conversions
- segment split
- trend data
- evolutionary memory
- agent-proposed version 2
