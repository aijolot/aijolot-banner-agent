# Frontend Template Deep Dive

Source branch: `origin/frontend/design-implementation`
Pulled into current working tree via `git checkout origin/frontend/design-implementation -- frontend`.

## High-level state

The frontend is currently a static React 18 UMD/Babel prototype, not a Next.js app yet. It is located directly under `frontend/` and is loaded by `frontend/index.html` through browser-side Babel scripts.

There is no `package.json`, no Next.js routing, no API client layer, and no persistent backend integration yet. The current frontend should be treated as the UX/product prototype and migrated/adapted into the future Next.js + Tailwind frontend by the frontend owner.

## Main files

- `frontend/index.html`: loads React, ReactDOM, Babel, Lucide, CSS, and all JSX files as browser scripts.
- `frontend/App.jsx`: orchestrates navigation and the 6-step studio flow.
- `frontend/data.jsx`: static demo data and the current implicit data contract.
- `frontend/Shell.jsx`: sidebar, topbar, campaign dashboard/landing.
- `frontend/PlacementStage.jsx`: page/placement/scope selection.
- `frontend/BriefStage.jsx`: chat-style campaign brief and synced catalog preview.
- `frontend/ArtStage.jsx`: art direction composition step.
- `frontend/GenerateStage.jsx`: animated generation pipeline.
- `frontend/CanvasStage.jsx`: collaborative review canvas, variants, segments, comments, approvals, refinement, schedule/publish.
- `frontend/CanvasPanels.jsx`: approvals, comments, date/schedule, publish controls.
- `frontend/PerformanceStage.jsx`: performance dashboard, evolutionary memory, v2 proposal.
- `frontend/BrandContextView.jsx`: brand context import/edit/save UX.
- `frontend/Banner.jsx` + `frontend/banner.css`: generated banner preview/rendering contract.
- `frontend/StoreMocks.jsx`: mock Shopify storefront pages and insert zones.
- `frontend/layout.jsx`: banner-grid layout helpers.
- `frontend/ModelBank.jsx`: usage-shot/model selection and custom model creation.
- `frontend/image-slot.js`: custom image upload/drop component for prototype image placeholders.
- `frontend/tweaks-panel.jsx`: design tweak side panel.
- `frontend/tokens.css`: visual tokens/fonts/animations.

## Current UX modules and backend implications

### 1. Campaign dashboard

File: `Shell.jsx`

Functionality already mocked:
- KPI cards: active campaigns, banners published, average CTR, weight saved.
- Recent campaign list.
- Resume draft/review campaign.
- View performance for published campaigns.

Backend implications:
- Need campaign list endpoint with status, promotion window, aggregate approval progress, and performance summary.
- Campaign status labels should support draft, needs_review, approved, scheduled, published/live, failed, archived.

### 2. Brand context

File: `BrandContextView.jsx`

Functionality already mocked:
- Brand context page called “Guardián de identidad”.
- Import from PDF/Figma file.
- Edit mode and save confirmation.
- Logo slots.
- Palette display.
- Typography display.
- Tone/voice tags with add/remove.
- Allowed rules and forbidden rules.
- Product image references from catalog.

Backend implications:
- Full brand context CRUD is the correct backend direction.
- Need file import endpoint for PDF/Figma/brandbook extraction, even if initial implementation stores the upload and returns parsed mock/partial data.
- Brand context should include palette, fonts, voice/tone, allowed rules, forbidden rules, logos/assets, image directives, and Shopify product-image references.

### 3. Placement selection

File: `PlacementStage.jsx`

Functionality already mocked:
- Navigate store templates/pages.
- Current pages: home, collection, product, search.
- Select an existing Shopify theme placement.
- Or create/inject a new section by defining layout columns/rows/width/alignment and dragging into top/mid/bottom insert zones.
- Define scope rules for where the banner appears.
- Scope examples:
  - home: only home or whole store
  - collection: this collection, selected collections, all collections
  - product: this product, all PDPs from a brand, products with tag
  - search: query-triggered result page

Backend implications:
- Our previous plan supported home, collections, products, pages. The frontend adds search-result placement and explicit new-section insertion.
- Database should distinguish page/template type, target resources, placement slot, scope rule, and whether the campaign updates an existing section or injects a new section.
- Layout must be persisted as JSON, because new-section mode supports dynamic column/row grids.
- Shopify resource list/select endpoints should support collections/products/pages now, with search-result placement kept as a near-term extension because it already exists in UI.

### 4. Brief/chat

File: `BriefStage.jsx`

Functionality already mocked:
- Chat with the agent.
- Suggested prompt chips.
- “Use example brief”.
- Agent claims to query Shopify catalog, validate stock, and apply discount.
- Side panel shows synced product catalog, SKUs, stock, original/sale price.

Backend implications:
- Campaign brief should preserve raw user message and structured extracted campaign idea.
- Need catalog snapshot tied to campaign generation so later review/publish is reproducible even if Shopify catalog changes.
- Product selections should store SKU/product id, price, sale price, stock at generation time, and segment mapping.

### 5. Art direction

File: `ArtStage.jsx`

Functionality already mocked:
- Stage sequence: concept/message, product protagonist, background, composition/assembly.
- Background mode: hero shot vs usage shot.
- Hero style selection.
- Usage-shot model bank and custom model creation.
- Fold/above-the-fold percentage.
- Layout inherited from placement step.

Backend implications:
- Need art direction table/entity or JSON field to persist background mode, hero style, selected/custom model, fold percentage, and layout hints.
- Custom model/persona creation should be stored if used, but can be MVP-light.

### 6. Generation pipeline

File: `GenerateStage.jsx`

Functionality already mocked:
- 5 visible pipeline steps:
  1. Smart Querying
  2. Brand Guidelines Engine
  3. Generación Estética IA
  4. Compilador HTML / Liquid
  5. Core Web Vitals Shield
- Shows generated HTML/Liquid code lines.
- Shows metrics: PageSpeed, weight reduction, WCAG AA, SEO text.

Backend implications:
- Our 12-node ADK graph can be exposed to the frontend as this 5-step simplified progress stream.
- Need generation run table with node-level events and frontend-facing pipeline step mapping.
- Need audit report fields for pagespeed/performance, weight reduction, WCAG/contrast, and SEO/text-live status.

### 7. Canvas/review

Files: `CanvasStage.jsx`, `CanvasPanels.jsx`

Functionality already mocked:
- Choose layout variant: A Spotlight, B Split, C Minimal.
- Device preview: desktop/tablet/mobile.
- Segment preview: masculino, femenino, VIP.
- Comment pins on banner by x/y percentage coordinates.
- Comment resolve flow.
- Agent refinement prompt that can apply changes and resolve addressed comments.
- Approval panel with reviewers and statuses: approved, pending, changes.
- Publish panel locked until all reviewers approve.
- Publish now or schedule.
- Schedule start/end date-time with optional auto-unpublish.

Backend implications:
- Approval policy `all_members` matches current UI.
- Comments need optional pinned coordinates and variant/device context.
- Reviewer status should allow pending, approved, changes_requested.
- Refinement should be persisted as a new generation/revision event, not just mutate the same final asset silently.
- Schedule needs start/end and auto-unpublish flag.

### 8. Performance loop

File: `PerformanceStage.jsx`

Functionality already mocked:
- KPIs: impressions, load time, CTR, conversions.
- CTR trend.
- Segment performance split.
- Evolutionary memory cards.
- Agent-proposed Version 2 based on performance.
- Send Version 2 to approval.

Backend implications:
- Performance is marked out of scope in the original PDF for MVP optimization phase, but the frontend has it as a visible module.
- For MVP, store mock/manual performance snapshots or Shopify-derived placeholder metrics if analytics integration is not ready.
- Database should include performance snapshots and optimization insights so the UI can be powered without schema redesign later.

## Updated backend/API direction from frontend

Add/keep these concepts in the API plan:

- `brand_contexts` full CRUD.
- Brand import endpoint for PDF/Figma/brandbook upload.
- `campaign_catalog_snapshots` and `campaign_catalog_items`.
- Placement pages/resources/scope rules.
- New-section/injected placement mode with layout JSON.
- `art_directions` or campaign art direction JSON.
- `generation_runs` with user-visible pipeline step statuses.
- `banner_layout_variants` and personalized `banner_variants`.
- `banner_assets` with device/size/srcset metadata.
- Pinned `comments` with x/y coordinates.
- `approval_reviewers` with all-reviewers policy.
- `schedules` with auto-unpublish.
- `performance_snapshots` and `optimization_insights` as optional/post-MVP but schema-ready.

## Migration note

The frontend has valuable product decisions but is not yet structurally compatible with the planned Next.js frontend folder. Do not overwrite its UX decisions. When the frontend owner migrates it, preserve:

- 6-step studio flow.
- Brand context module.
- Placement existing-section vs new-section mode.
- Scope rules.
- Art direction step.
- 5-step generation progress facade.
- Canvas comments/approvals/scheduling.
- Performance/evolutionary memory module.
