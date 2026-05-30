# Banner Creator MVP Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task after requirements are clarified.

**Goal:** Build a Shopify-focused agentic banner creator that lets marketing users define a brief, generate banner art/copy, request team review, approve, schedule, position, and publish banners to a Shopify store.

**Architecture:** A Python/FastAPI backend owns the business workflow, Google ADK 12-node agent graph, Gemini generation, Supabase persistence/storage/auth, approvals, scheduling, audit gates, and Shopify publishing. A Next.js + Tailwind frontend provides the admin panel and calls backend APIs. Shopify storefront rendering uses a controlled Online Store 2.0 Liquid section/snippet that reads campaign configuration from metafields/metaobjects and renders responsive HTML text over optimized image assets.

**Tech Stack:** Python, FastAPI, Google ADK, Gemini 2.5 Pro/Flash, Gemini image generation with a Vertex/Imagen-compatible adapter boundary, Supabase Postgres/Auth/Storage, optional Supabase pg_cron, Shopify Admin GraphQL API, Shopify Liquid sections/snippets, Pillow image optimization, Lighthouse/html validation/schema validation, Next.js, Tailwind CSS.

---

## 1. Confirmed MVP Scope

### In scope
- Shopify stores only.
- Admin panel for marketing users.
- User selects banner placement.
- User provides a brief/prompt.
- Backend generates banner concepts/art using Gemini.
- Backend keeps text/copy as HTML/Liquid-rendered elements, not as text inside generated images.
- Backend creates responsive image assets for mobile/tablet/desktop.
- Backend supports personalization variants, with Shopify `customer.tags` as the first concrete storefront mechanism.
- Backend uses portable brand context files as generation inputs.
- Backend optimizes generated assets to WebP/AVIF/srcset plus fallback JPG.
- Backend renders standalone HTML preview and Shopify Liquid output/config.
- Backend runs programmatic audit gates before human review where feasible.
- User can request team approval/comments.
- Human-in-the-loop approval is mandatory before publishing.
- Approved banner can be scheduled with an active period.
- Approved scheduled banner can be published to Shopify.
- Folder structure now; backend/frontend implementation later.

### Out of scope until clarified or explicitly added
- Multi-platform ecommerce support beyond Shopify.
- Multi-language banner generation.
- Advanced or automatic A/B testing.
- Post-publish analytics such as CTR/conversion optimization.
- Dynamic multi-theme switching.
- Real-time collaborative editing.
- Visual WYSIWYG/banner canvas editor.
- Historical banner library/management beyond minimal audit/demo records.
- Automatic periodic regeneration.
- Automated legal/brand compliance unless simplified to checklist or agent review.
- Payment/subscription functionality.

---

## 2. Clarifications Status

### Resolved decisions
- Backend framework: FastAPI.
- Agent framework: Google ADK.
- LLM: Gemini; use Pro for creative reasoning and Flash for faster structured tasks where possible.
- Image generation: Gemini image generation by default; keep adapter compatible with Vertex/Imagen because the source design had Imagen 4 vs Gemini Image as an open spike.
- Frontend: Next.js + Tailwind admin panel, not Streamlit.
- Auth: Supabase Auth.
- Storage: Supabase Storage for generated/optimized assets.
- Shopify auth: token/custom app access for MVP, not full OAuth.
- Shopify rendering: one controlled Shopify Liquid section/snippet reads campaign config.
- Publishing: use Shopify Admin API; `themeFilesUpsert` installs/updates reusable Liquid files, while campaign config is published as metafield/metaobject JSON.
- Scheduling: theme-enforced active dates for local MVP; keep schema/service compatible with future Supabase `pg_cron` due publishing.
- HITL: mandatory before publishing; no bypass.
- Approval/comments: per team member.
- Responsive sizes: mobile, tablet, desktop, plus optimized srcset widths.
- Personalization: multiple variants; Shopify `customer.tags` first, cookies/context later.
- Development/deployment: local-first for now.

### Resolved follow-up decisions
- Approval policy for MVP: all assigned reviewers must approve before the campaign can become approved.
- Brand context authoring: should be supported by backend APIs because the intended UX is UI-based editing. Repo Markdown brand files remain useful for seed/demo/versioned examples.
- First Shopify resource scope: support home, collections, products, and pages.
- Image provider adapter: keep Gemini as default and preserve Vertex/Imagen-compatible adapter boundary.
- Cost controls: do not hard-cap daily usage for the dev team during the hackathon. Track usage/costs and add a soft rate guard per short window, e.g. warnings or confirmation after N image generations per 15 minutes.
- Reviewer auth: reviewers log in with Supabase Auth; no anonymous approval links for MVP.
- License: MIT for the public/stable hackathon repo.

### Resolved final blocking decisions
- Soft image-generation warning threshold: 20 generations per authenticated user per 15 minutes. This is a warning/soft guard, not a hard cap.
- Brand context API depth: implement full backend CRUD for brand profiles.
- Shopify resource selection UX for MVP: backend supports list/select for home, collections, products, and pages. Search/autocomplete is deferred unless the frontend/product team requests it.

### Still open / needs product decision
1. Whether Shopify products/pages/collections search/autocomplete should be added after the MVP list/select flow is validated.

---

## 3. Confirmed Technical Decisions

These decisions were confirmed after initial clarification:

1. Use FastAPI for the Python backend HTTP API.
2. Use Google ADK for agent workflow orchestration, not for every simple CRUD action.
3. Use Gemini 2.5 Pro for heavier creative reasoning and Gemini Flash for fast structured extraction where possible.
4. Use Gemini for brief refinement, copy suggestions, generation prompt creation, and generative image creation. Keep the image-generation code behind an adapter so Vertex/Imagen can be swapped in if the hackathon environment requires it.
5. Generated images must not contain baked-in text, logos, or faces unless explicitly approved later.
6. Store generated image files in Supabase Storage.
7. Use Supabase Auth for real user authentication.
8. Use Shopify custom/private app token access for the MVP instead of full Shopify OAuth.
9. For Shopify demo reliability, use a custom Online Store 2.0 theme section/snippet that reads banner config from Shopify metafields/metaobjects. Use Shopify Admin GraphQL `themeFilesUpsert` only for installing/updating the reusable section/snippets/assets.
10. Keep banner text as HTML/CSS/Liquid-rendered elements, not baked into generated images.
11. Support responsive image/layout sizes for mobile, tablet, and desktop.
12. Support personalized banner variants, e.g. default, men, women, VIP, new_signup. First concrete storefront personalization mechanism: Shopify `customer.tags`; cookie/context matching can be added as an extension.
13. Represent scheduling in Shopify metafields and let the theme section show/hide based on dates for the MVP. Keep backend schedule records and design services so Supabase `pg_cron` due-publish automation can be added later without redesign.
14. Approval/commenting is per team member, not just one global approval action.
15. Programmatic audit gates should run before human review; failed audits retry upstream at most two times, then escalate to human review with root-cause hints.
16. Start with local development. Deployment will be planned in a later session.

## 3.1 Recommended MVP Decisions Still Open

1. Start with a controlled demo Shopify theme and one reusable banner section that can be inserted into multiple page templates.
2. Keep approval MVP simple but team-aware: each reviewer can comment and approve/request changes independently; the campaign becomes approved only after all assigned reviewers approve.
3. Begin with a small set of placement types, then make the placement registry extensible.
4. Publish configuration to Shopify as structured JSON in a metafield/metaobject read by the custom section.
5. Use Supabase RLS where practical, but prioritize reliable local demo flow first.

---

## 4. Domain Model Draft

### Main entities

#### `stores`
Represents a Shopify store connection.
- `id`
- `shop_domain`
- `access_token_secret_ref` or encrypted token field
- `shopify_api_version`
- `created_at`
- `updated_at`

#### `brand_contexts`
Portable brand/store generation context. Runtime records can be seeded from repo files under `brands/{brand_id}.md`.
- `id`
- `brand_key`
- `store_id`
- `name`
- `palette` JSON
- `typography` JSON
- `voice` JSON, including tone, prohibited words, required phrases
- `logo_url`
- `image_style_directives`
- `default_placement`
- `source_file_path` nullable
- `created_at`
- `updated_at`

#### `campaigns`
Top-level banner campaign.
- `id`
- `store_id`
- `title`
- `brief`
- `status`: `draft | generating | needs_review | changes_requested | approved | scheduled | publishing | published | failed | archived`
- `created_by`
- `approved_by`
- `created_at`
- `updated_at`

#### `placement_types`
Registry of supported banner/component types.
- `id`
- `key`: `hero_banner | promo_strip | collection_banner | popup_banner | inline_banner`
- `label`
- `description`
- `supported_targets` JSON, e.g. `home`, `collection`, `product`, `page`, `blog`
- `supported_slots` JSON, e.g. `top`, `after_header`, `above_product_grid`, `custom_section_anchor`
- `required_dimensions` JSON for mobile/tablet/desktop
- `config_schema` JSON for type-specific options
- `is_active`

#### `placements`
Selected destination for a campaign.
- `id`
- `campaign_id`
- `placement_type_id`
- `target_type`: `home | collection | product | page | blog | theme_template`
- `target_handle` nullable, e.g. collection/product/page handle
- `slot`: `top | after_header | above_product_grid | below_product_info | custom_section_anchor`
- `slot_order` integer for ordering when multiple banners exist in one slot
- `selector_hint` nullable for advanced/custom placement mapping
- `created_at`

#### `banner_variants`
Personalization-level variants generated for a campaign.
- `id`
- `campaign_id`
- `variant_key`: `default | men | women | vip | custom_segment_key`
- `variant_label`
- `audience_rule` JSON, e.g. cookie/customer/context matching rule
- `status`: `generated | selected | rejected`
- `generation_metadata` JSON
- `created_at`

#### `banner_assets`
Responsive assets for each personalized variant.
- `id`
- `banner_variant_id`
- `size_key`: `mobile | tablet | desktop`
- `width`
- `height`
- `image_prompt`
- `image_url`
- `alt_text`
- `created_at`

#### `banner_copy`
HTML-rendered text/copy for each personalized variant.
- `id`
- `banner_variant_id`
- `headline`
- `subheadline`
- `cta_text`
- `cta_url`
- `text_position`
- `theme_tokens` JSON for colors/typography/layout hints
- `created_at`

#### `approval_threads`
Review container for a selected campaign/variant set.
- `id`
- `campaign_id`
- `status`: `open | approved | changes_requested | rejected`
- `approval_policy`: `all_members` for MVP; schema can later allow `any_member | required_members | owner_only`
- `requested_by`
- `created_at`
- `resolved_at`

#### `approval_reviewers`
Per-team-member approval state.
- `id`
- `approval_thread_id`
- `user_id`
- `status`: `pending | approved | changes_requested | rejected`
- `last_comment_id`
- `created_at`
- `updated_at`

#### `comments`
Review comments.
- `id`
- `approval_thread_id`
- `author_id`
- `banner_variant_id` nullable, for variant-specific comments
- `banner_asset_id` nullable, for size-specific comments
- `body`
- `created_at`

#### `schedules`
Active period for approved banners.
- `id`
- `campaign_id`
- `starts_at`
- `ends_at`
- `timezone`
- `status`: `pending | active | completed | cancelled`
- `created_at`

#### `publish_jobs`
Publishing attempts to Shopify.
- `id`
- `campaign_id`
- `status`: `queued | running | succeeded | failed`
- `shopify_resource_type`
- `shopify_resource_id`
- `error_message`
- `created_at`
- `finished_at`

#### `audit_events`
Traceability for demo and debugging.
- `id`
- `campaign_id` nullable
- `trace_id`
- `session_id`
- `brand_context_id` nullable
- `actor_type`: `user | agent | system`
- `node`, e.g. `generate_image`, `audit`, `publish_to_shopify`
- `event_type`
- `duration_ms`
- `cost_usd`
- `audit_pass` nullable
- `review_decision` nullable
- `shopify_section_id` nullable
- `payload` JSON
- `created_at`

#### `audit_reports`
Structured validation result for generated preview/Liquid output.
- `id`
- `campaign_id`
- `html_w3c` JSON
- `lighthouse` JSON, including performance, lcp_ms, cls
- `schema_valid` boolean
- `breakpoints_render` JSON
- `asset_weight_report` JSON
- `root_cause_hint` nullable
- `retry_count`
- `status`: `pass | fail | escalated`
- `created_at`

#### `generation_usage_events`
Tracks Gemini/image generation usage for cost visibility and soft throttling.
- `id`
- `user_id`
- `campaign_id` nullable
- `event_type`: `text_generation | image_generation | asset_optimization`
- `provider`
- `model`
- `estimated_cost_usd` nullable
- `metadata` JSON
- `created_at`

## 4.1 Placement Selection Recommendation

The placement UX should separate "what kind of banner is this?" from "where should it appear?".

### Suggested user flow

1. User selects a banner type.
   - Hero banner
   - Promotional strip
   - Collection page banner
   - Product page banner
   - Inline content banner
   - Popup/modal banner, if desired later

2. Backend returns valid target types and slots for that banner type.
   - Example: `hero_banner` supports `home.top`, `collection.top`, `page.top`.
   - Example: `promo_strip` supports `home.after_header`, `collection.after_header`, `product.after_header`.

3. User selects the page/template target.
   - Home page
   - Collection page + collection handle
   - Product page + product handle
   - Custom page + page handle
   - Theme template/global slot
   - MVP scope supports all four primary Shopify page resources: home, collections, products, and pages.

4. User selects the slot/position inside that target.
   - Top of page
   - After header
   - Above product grid
   - Below product info
   - Custom section anchor

5. Backend validates that the selected banner type, target, and slot are compatible.

6. Publishing writes a normalized JSON config to Shopify. The custom theme section/snippet reads that config and decides which banner to render based on:
   - current page/template
   - selected slot
   - active start/end dates
   - personalization/audience rules
   - mobile/tablet/desktop viewport

### Why this model works

- It keeps the MVP manageable while still feeling flexible.
- It avoids arbitrary DOM injection into unknown Shopify themes.
- It gives the frontend a simple wizard-like selection flow.
- It lets us add new banner types later by adding rows/config instead of rewriting business logic.
- It supports multiple banners on the same page through `slot_order` and conflict rules.

### MVP placement types to start with

1. `hero_banner`
   - Targets: home, collection, page
   - Slots: top, after_header
   - Sizes: desktop/tablet/mobile

2. `promo_strip`
   - Targets: home, collection, product, page
   - Slots: after_header
   - Sizes: desktop/tablet/mobile, usually short height

3. `collection_banner`
   - Targets: collection
   - Slots: top, above_product_grid
   - Sizes: desktop/tablet/mobile

We can add product/inline/popup after the core flow is stable.

---

## 5. Agentic Workflow Design

The source technical design defines the workflow as a Google ADK graph with 12 nodes. The backend should expose this graph through normal FastAPI endpoints, but the agent execution boundary should remain explicit and testable.

### 12-node graph

1. `load_brand_context`
   - Input: `brand_id` / `store_id`.
   - Output: `BrandContext { name, palette, typography, voice, logo_url, image_style_directives, shopify }`.
   - Source: versioned `brands/{brand_id}.md` plus Supabase runtime records.

2. `intake_campaign_idea`
   - Input: raw user brief/prompt and selected placement.
   - Output: structured `Campaign { goal, audience, cta, tone, urgency, placement, deadline? }`.
   - Recommended model: Gemini Flash with structured output.

3. `capture_user_personalization`
   - Input: campaign, brand context, user-requested segments.
   - Output: `Variant[] { customer_tag, intent_delta, copy_override? }`.
   - MVP storefront mechanism: Shopify `customer.tags` with variants like `default`, `vip`, `new_signup`, `men`, `women`.

4. `research_best_practices`
   - Input: placement type and campaign goal.
   - Output: static best-practice guidance for layout/copy/accessibility/performance.
   - D1/MVP: static cheatsheet in repo. Later: RAG.

5. `draft_banner_concept`
   - Input: structured campaign, brand context, placement constraints, best practices.
   - Output: `Concept { layout, copy, palette_usage, image_prompt, hierarchy_notes }`.
   - Recommended model: Gemini 2.5 Pro for higher-quality creative reasoning.

6. `generate_image`
   - Input: concept image prompt and required responsive sizes.
   - Output: raw generated image(s).
   - Use Gemini image generation by default behind an adapter compatible with Vertex/Imagen if needed.
   - Prompt constraints: no embedded text, no logos, no faces unless explicitly allowed.

7. `optimize_assets`
   - Input: generated image(s).
   - Output: WebP/AVIF srcset assets, fallback JPG, alt text suggestion.
   - Target sizes: 320, 768, 1280, 1920 where applicable.
   - Target weight: under 80KB at 1280 WebP where feasible.

8. `render_html`
   - Input: selected/generated variants, copy, assets, placement config.
   - Output: standalone HTML preview plus Shopify Liquid/config payload.
   - Include SEO meta data and JSON-LD `PromotionalOffer` where applicable.

9. `audit`
   - Input: rendered preview/Liquid output and assets.
   - Output: `AuditReport { html_w3c, lighthouse, schema_valid, breakpoints_render, asset_weight_report, root_cause_hint? }`.
   - Max two retries upstream when failures can be fixed automatically; then escalate to human with root-cause hints.

10. `human_review`
   - Input: preview, variants, audit report, comments.
   - Output: approve/reject/edit_request/set_schedule.
   - Current UI: Next.js admin panel, not Streamlit. The source design's Streamlit UI is superseded by the current team split.
   - No bypass: publishing must never happen before human approval.

11. `schedule_or_publish`
   - Input: approved campaign and selected active period.
   - Output: immediate publish job or scheduled campaign config.
   - MVP: Shopify theme reads active dates from campaign config. Future-compatible path: Supabase `scheduled_banners` + pg_cron due-publish automation.

12. `publish_to_shopify`
   - Input: approved campaign, placement, schedule, Liquid/config payload.
   - Output: idempotent Shopify publish result.
   - Use Shopify Admin GraphQL. `themeFilesUpsert` installs/updates reusable Liquid section/snippets; campaign data is published as metafield/metaobject JSON consumed by that section.

### Human-in-the-loop boundaries
- Human selects placement and enters brief.
- Human chooses generated variant(s) or requests regeneration.
- Human requests team review.
- Each assigned reviewer can comment and approve/request changes.
- MVP approval policy requires all assigned reviewers to approve before scheduling/publishing is allowed.
- Human selects active period.
- Human confirms publish.

The agent can assist and automate inside each step but should not publish without explicit user approval for MVP safety.

---

## 6. Backend API Draft

Base path: `/api/v1`

### Campaigns
- `POST /campaigns`
  - Create campaign with title, brief, store, brand context, placement.
- `GET /campaigns`
  - List campaigns.
- `GET /campaigns/{campaign_id}`
  - Get campaign detail with variants, assets, copy, approval, schedule, audit report.
- `PATCH /campaigns/{campaign_id}`
  - Update draft campaign fields.

### Brand context
- `POST /brands`
  - Create a brand context/profile.
- `GET /brands`
  - List brand contexts available to the authenticated team.
- `GET /brands/{brand_id}`
  - Get brand context, including palette, typography, voice rules, logo, and image directives.
- `PATCH /brands/{brand_id}`
  - Update brand context/profile fields.
- `DELETE /brands/{brand_id}`
  - Archive/delete a brand context when it is not used by active campaigns.
- `POST /brands/import`
  - Optional local/demo helper to import `brands/{brand_id}.md` into Supabase.

### Generation
- `POST /campaigns/{campaign_id}/generate`
  - Run ADK/Gemini workflow through nodes 1-9 to generate variants, assets, HTML preview, Liquid/config payload, and audit report.
- `POST /campaigns/{campaign_id}/variants/{variant_id}/select`
  - Select final variant or personalized variant set.
- `POST /campaigns/{campaign_id}/variants/{variant_id}/regenerate`
  - Regenerate based on feedback.
- `GET /campaigns/{campaign_id}/preview`
  - Return standalone HTML preview URL/body and responsive asset/copy data.
- `GET /campaigns/{campaign_id}/audit-report`
  - Return latest audit report and root-cause hints.

### Approval
- `POST /campaigns/{campaign_id}/approval/request`
  - Open approval thread.
- `POST /approval-threads/{thread_id}/comments`
  - Add review comment.
- `POST /approval-threads/{thread_id}/approve`
  - Approve selected variant.
- `POST /approval-threads/{thread_id}/request-changes`
  - Mark changes requested.

### Scheduling
- `POST /campaigns/{campaign_id}/schedule`
  - Set start/end date and timezone.
- `PATCH /campaigns/{campaign_id}/schedule`
  - Update schedule before publish.
- `POST /campaigns/{campaign_id}/schedule/cancel`
  - Cancel schedule.

### Shopify
- `POST /stores/shopify/connect`
  - Save Shopify connection using custom/private app token for MVP.
- `GET /stores/{store_id}/placement-types`
  - Return supported banner/component types.
- `GET /stores/{store_id}/placement-types/{placement_type_key}/targets`
  - Return valid target types and slots for selected banner type.
- `GET /stores/{store_id}/shopify/resources`
  - Return selectable Shopify resources for placement targeting, e.g. collections, products, pages.
- `GET /stores/{store_id}/placements/preview`
  - Validate and preview a placement selection.
- `POST /campaigns/{campaign_id}/publish`
  - Publish approved scheduled banner config to Shopify metafield/metaobject consumed by the custom section.
- `POST /campaigns/{campaign_id}/unpublish`
  - Optional but recommended for rollback.

---

## 7. Frontend Screen Draft

Frontend implementation is owned by another team member, but backend should support these screens.

1. Dashboard
   - Campaign list by status.
   - Create campaign button.

2. Create campaign
   - Store selector.
   - Placement selector.
   - Brief/prompt textarea.
   - Optional brand/product context.

3. Generate banners
   - Trigger generation.
   - Show status/progress.
   - Display generated variants.
   - Select variant or regenerate.

4. Review/approval
   - Selected banner preview.
   - Comment thread.
   - Request approval button.
   - Approve / request changes actions.

5. Schedule
   - Start datetime.
   - End datetime.
   - Timezone.
   - Validation summary.

6. Publish
   - Final preview.
   - Shopify target placement.
   - Publish button.
   - Publish result/status.

7. Store settings
   - Shopify store connection status.
   - Supported placements.


---

## 7.1 Frontend Template Alignment

A static React prototype from `origin/frontend/design-implementation` is now pulled into `frontend/` and documented in `docs/architecture/frontend-template-deep-dive.md`. Treat it as the current UX base even though it is not yet a Next.js app.

Backend/data model changes driven by the frontend:

- The studio flow is 6 steps: placement, brief, art direction, generation, collaborative canvas, performance.
- Brand context needs full CRUD plus import from PDF/Figma/brandbook.
- Placement supports existing Shopify sections and new injected sections. New-section mode requires layout JSON for columns, rows, widths, alignment, and drop zone.
- Placement scope must support home, whole store, selected collections, all collections, single product, product brand, product tag, and search-query trigger. MVP API can expose list/select resources first; search/autocomplete is deferred.
- Brief generation needs a campaign catalog snapshot because the frontend expects Shopify SKU/stock/pricing validation.
- Art direction must persist background mode, hero style, selected/custom usage model, and fold percentage.
- The backend's 12-node ADK graph should map to the frontend's 5 visible pipeline steps: Smart Querying, Brand Guidelines Engine, IA Image Generation, HTML/Liquid Compiler, Core Web Vitals Shield.
- Review canvas needs layout variants A/B/C, device previews, segment variants, pinned comments with x/y coordinates, agent refinement events, all-reviewer approval, scheduling, and publish-now.
- Performance/evolutionary memory is visible in the frontend. Keep it schema-ready even if real analytics are post-MVP.

---

## 8. Implementation Phases

### Phase 0: Repository structure and docs
Status: done for initial scaffold.

Tasks:
1. Create `backend/`, `frontend/`, `supabase/`, `docs/`, `scripts/` folders.
2. Add `.gitkeep` placeholders.
3. Add root `.gitignore`.
4. Add README and project structure docs.
5. Add implementation plan.

Verification:
- `git status --short` shows created folders/docs.
- No backend/frontend code has been introduced yet.

### Phase 1: Backend foundation
Goal: runnable Python API skeleton.

Tasks:
1. Decide backend framework after clarification; recommended FastAPI.
2. Add backend dependency manifest.
3. Add settings loader for environment variables.
4. Add app bootstrap.
5. Add health endpoint.
6. Add test runner setup.
7. Add local dev instructions.

Expected files:
- `backend/pyproject.toml`
- `backend/app/main.py`
- `backend/app/core/settings.py`
- `backend/app/api/routes/health.py`
- `backend/tests/unit/test_health.py`

Verification:
- Backend starts locally.
- Health endpoint returns OK.
- Unit tests pass.

### Phase 2: Supabase schema
Goal: persistence for campaigns, variants, approvals, schedules, stores, audit.

Tasks:
1. Create first migration under `supabase/migrations/`.
2. Add tables listed in Domain Model Draft.
3. Add indexes for campaign status, store, schedule dates.
4. Add status check constraints or enum strategy.
5. Add seed data for demo store/campaign if useful.
6. Add repository tests with a local/test Supabase strategy or mocked client.

Expected files:
- `supabase/migrations/0001_initial_schema.sql`
- `supabase/seed/demo.sql`
- `backend/app/db/repositories/*.py`

Verification:
- Migration applies cleanly.
- Seed creates demo data.
- Backend can create/read campaigns.

### Phase 3: Campaign and placement API
Goal: frontend can create and inspect campaign drafts.

Tasks:
1. Add request/response schemas.
2. Add campaign repository.
3. Add campaign service.
4. Add campaign routes.
5. Add supported placements endpoint.
6. Add tests for create/list/detail/update.

Expected files:
- `backend/app/schemas/campaigns.py`
- `backend/app/services/banners/campaign_service.py`
- `backend/app/api/routes/campaigns.py`
- `backend/app/api/routes/stores.py`

Verification:
- Campaign CRUD works.
- Placement options are returned.
- Tests cover validation and status transitions.

### Phase 4: Google ADK + Gemini workflow
Goal: implement the source design's 12-node ADK graph up to audit-ready output.

Tasks:
1. Add ADK dependency and configuration.
2. Create graph state models for brand context, campaign, variants, assets, render output, audit report.
3. Create `load_brand_context` node.
4. Create `intake_campaign_idea` node.
5. Create `capture_user_personalization` node.
6. Create `research_best_practices` node using a static repo cheatsheet for MVP.
7. Create `draft_banner_concept` node.
8. Create `generate_image` node through an image-generation adapter.
9. Create `optimize_assets` node.
10. Create `render_html` node.
11. Create `audit` node with max-two-retry metadata.
12. Persist generated variants, assets, preview output, audit reports, and audit events.
13. Add tests around prompt construction, structured parsing, retry limits, and fallback behavior.

Expected files:
- `backend/app/agents/graph.py`
- `backend/app/agents/state.py`
- `backend/app/agents/nodes/load_brand_context.py`
- `backend/app/agents/nodes/intake_campaign_idea.py`
- `backend/app/agents/nodes/capture_user_personalization.py`
- `backend/app/agents/nodes/research_best_practices.py`
- `backend/app/agents/nodes/draft_banner_concept.py`
- `backend/app/agents/nodes/generate_image.py`
- `backend/app/agents/nodes/optimize_assets.py`
- `backend/app/agents/nodes/render_html.py`
- `backend/app/agents/nodes/audit.py`
- `backend/app/agents/prompts/*.md`
- `backend/app/workflows/banner_generation.py`

Verification:
- `POST /campaigns/{id}/generate` moves campaign from draft to generating to needs_review when audit passes or to audit_failed/escalated when audit cannot be fixed automatically.
- Generated variants, responsive assets, HTML preview, Liquid/config payload, and audit report are stored.
- Failures are captured without losing campaign state.

### Phase 5: Asset storage and optimization
Goal: generated image assets are optimized, durable, and previewable by frontend and Shopify Liquid.

Tasks:
1. Use Supabase Storage for MVP asset persistence.
2. Create storage adapter.
3. Create image optimizer using Pillow and AVIF/WebP support.
4. Generate responsive variants for 320, 768, 1280, 1920 widths where applicable.
5. Generate WebP/AVIF plus fallback JPG.
6. Save asset URLs and metadata in `banner_assets`.
7. Generate and store alt text suggestions.
8. Enforce/report target weight cap: under 80KB at 1280 WebP where feasible.
9. Add asset cleanup/update strategy.

Expected files:
- `backend/app/services/supabase/storage.py`
- `backend/app/services/banners/asset_service.py`
- `backend/app/services/banners/image_optimizer.py`

Verification:
- Frontend can load image URL.
- Shopify preview can use srcset data.
- Regeneration creates new assets without overwriting selected assets unexpectedly.
- Asset weight report is included in `audit_reports`.

### Phase 6: Approval workflow
Goal: human-in-the-loop approval with comments.

Tasks:
1. Add approval thread repository.
2. Add comments repository.
3. Add approval service and status transitions.
4. Add approval endpoints.
5. Add optional review assistant agent for comment summarization.
6. Add tests for approve/reject/request-changes transitions.

Expected files:
- `backend/app/services/approvals/approval_service.py`
- `backend/app/api/routes/approvals.py`
- `backend/app/agents/review_assistant_agent.py`

Verification:
- Only selected variants can be sent for approval.
- Only approved campaigns can move to scheduling.
- Comments are stored and returned.

### Phase 7: Scheduling
Goal: approved banners can be assigned active windows.

Tasks:
1. Add schedule service.
2. Validate start/end times and timezone.
3. Prevent scheduling non-approved campaigns.
4. Expose schedule endpoints.
5. Decide how schedule is enforced in Shopify publishing.

Expected files:
- `backend/app/services/banners/schedule_service.py`
- `backend/app/api/routes/schedules.py`

Verification:
- Approved campaigns can be scheduled.
- Invalid date ranges fail clearly.
- Campaign status moves to scheduled.

### Phase 8: Shopify publishing
Goal: publish scheduled approved banner to Shopify demo store.

Tasks:
1. Use token-based Shopify Admin API credentials for MVP.
2. Add Shopify GraphQL client wrapper with exponential backoff for rate limits.
3. Add store connection model/API.
4. Add reusable Liquid section/snippet templates.
5. Add `themeFilesUpsert` installer/updater for the controlled Shopify section/snippets.
6. Add publish payload builder for metafield/metaobject JSON config consumed by the section.
7. Add publish workflow agent/service.
8. Add publish endpoint.
9. Add rollback/unpublish endpoint if time allows.
10. Add integration test with mocked Shopify API.

Expected files:
- `backend/app/services/shopify/client.py`
- `backend/app/services/shopify/theme_files.py`
- `backend/app/services/shopify/publisher.py`
- `backend/app/agents/nodes/publish_to_shopify.py`
- `backend/app/workflows/shopify_publish.py`
- `backend/app/templates/shopify/banner_section.liquid.j2`
- `backend/app/templates/shopify/banner_block.liquid.j2`

Verification:
- Publish endpoint refuses non-approved/non-scheduled campaigns.
- Theme section/snippet install is idempotent.
- Campaign config publish/update is idempotent.
- Publish job records success/failure.
- Demo Shopify store shows the banner in the chosen placement.

### Phase 9: Frontend integration support
Goal: provide API contract and helper docs for the frontend owner.

Tasks:
1. Generate/maintain OpenAPI docs.
2. Add sample request/response docs.
3. Add status transition diagram.
4. Coordinate screen-by-screen API requirements.

Expected files:
- `docs/architecture/api-contract.md`
- `docs/architecture/status-flow.md`

Verification:
- Frontend can implement all MVP screens without backend ambiguity.

### Phase 10: Demo hardening
Goal: reliable hackathon presentation.

Tasks:
1. Seed a demo store/campaign.
2. Add deterministic fallback if generation API fails.
3. Add visible audit trail for agent actions.
4. Add clear loading/error states for long-running generation/publish.
5. Add one-click reset script for demo data.
6. Record expected demo path.

Expected files:
- `scripts/reset-demo-data.*`
- `docs/demo-script.md`

Verification:
- Demo can be run start-to-finish twice in a row.
- Failed external API calls fail gracefully.
- Published banner can be verified in Shopify.

---

## 9. Status Transition Draft

```text
draft
  -> generating
  -> audit_pending
  -> needs_review
  -> changes_requested
  -> generating
  -> audit_pending
  -> needs_review
  -> approved
  -> scheduled
  -> publishing
  -> published
```

Failure/escalation paths:
```text
generating -> failed -> draft or generating
audit_pending -> audit_retrying -> audit_pending
audit_pending -> audit_escalated -> needs_review
publishing -> failed -> scheduled or publishing
scheduled -> cancelled
published -> archived
```

Rules:
- Only `draft` or `changes_requested` campaigns can generate/regenerate.
- Only `needs_review` campaigns can be approved.
- Only `approved` campaigns can be scheduled.
- Only `scheduled` campaigns can be published.
- Publishing should be idempotent when possible.

---

## 10. Environment Variables Draft

Backend:
- `GOOGLE_API_KEY` or Google Cloud auth variables, depending on ADK/Gemini setup.
- `GOOGLE_CLOUD_PROJECT` if using Vertex-backed generation.
- `GOOGLE_CLOUD_LOCATION` if using Vertex-backed generation.
- `GEMINI_MODEL_PRO`
- `GEMINI_MODEL_FLASH`
- `GEMINI_MODEL_IMAGE`
- `IMAGE_GENERATION_PROVIDER`, e.g. `gemini` or `vertex_imagen`.
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET`
- `SHOPIFY_SHOP_DOMAIN`
- `SHOPIFY_ADMIN_ACCESS_TOKEN`
- `SHOPIFY_API_VERSION`
- `SHOPIFY_THEME_ID`
- `SHOPIFY_BANNER_METAFIELD_NAMESPACE`
- `SHOPIFY_BANNER_METAFIELD_KEY`
- `SOFT_IMAGE_GENERATION_LIMIT_PER_15_MINUTES`, default `20` per authenticated user
- `APP_ENV`
- `APP_BASE_URL`

Frontend:
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_SUPABASE_URL` if using Supabase Auth directly.
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` if using Supabase Auth directly.

Security note:
- Never expose Shopify Admin tokens or Supabase service role keys to the frontend.

---

## 11. Hackathon Risk Register

### Risk: Shopify theme integration takes too long
Mitigation: use one controlled demo store/theme, install one reusable Liquid section/snippet via `themeFilesUpsert`, and publish only config changes afterward.

### Risk: image generation quality is inconsistent
Mitigation: generate multiple variants, forbid embedded text/logos/faces in prompts, and keep a deterministic fallback demo asset.

### Risk: approval workflow scope expands
Mitigation: keep MVP to team-member reviewer statuses, comment thread, approve, reject, and request changes.

### Risk: schedule automation is too complex
Mitigation: for MVP, publish schedule metadata and let the Shopify section show/hide by date; preserve `scheduled_banners`/pg_cron-compatible schema for later automation.

### Risk: ADK integration slows basic product delivery
Mitigation: isolate ADK workflows under `backend/app/agents` and `backend/app/workflows`; keep CRUD/services normal and testable.

### Risk: frontend/backend contract mismatch
Mitigation: write OpenAPI/schema docs early and provide sample payloads.

### Risk: audit loop never converges
Mitigation: max two automatic retries, then escalate to human with root-cause hints.

### Risk: banner hurts storefront performance/LCP
Mitigation: optimize images, enforce/report size caps, run Lighthouse, and target performance score >= 90.

### Risk: Shopify API rate limits
Mitigation: exponential backoff up to 3 retries and idempotent publish jobs.

### Risk: image generation cost runaway
Mitigation: cost/usage logging in audit events, visible cost per banner where possible, and soft rate guard warnings per 15-minute window. Do not enforce hard daily caps during hackathon dev unless the team later requests them.

### Risk: invalid brand context
Mitigation: validate brand Markdown/YAML with Pydantic before generation.

---

## 12. Hackathon Success Criteria

Targets from the source technical design, adapted to the current Next/FastAPI plan:

- Intake to publish under 10 minutes for the main demo scenario.
- Audit pass first try >= 70%.
- HITL approval first try >= 60%.
- Lighthouse Performance >= 90 for published banners.
- LCP on 4G mobile under 1.0s target.
- Schedule accuracy within +/- 5 minutes for scheduled demo flow.
- Brand context reusable across at least 2 demo stores.
- Personalization demonstrates at least 3 variants.
- Three demo scenarios recorded or rehearsed:
  1. Avocado Store Black Friday immediate publish with default variant.
  2. Avocado Store onboarding scheduled campaign with `new_signup` variant.
  3. Demo Apparel product launch with `vip` + default variants and different brand context.

---

## 13. Immediate Next Steps

1. Start Phase 1 backend foundation with FastAPI.
2. Add brand context sample files, validation, and full backend CRUD APIs early because the 12-node graph and future UI editing depend on them.
3. Implement the placement registry before campaign creation so the frontend can build the selection wizard for home, collections, products, and pages.
4. Implement Shopify resource list/select endpoints for collections, products, and pages. Defer search/autocomplete unless requested.
5. Implement soft image-generation usage tracking: warn after 20 generations per authenticated user per 15 minutes.
6. Keep MIT LICENSE in place for public/stable hackathon release.
7. Share `docs/architecture/project-structure.md`, `docs/architecture/source-plan-alignment.md`, and this plan with the frontend teammate so they can align screens to API phases.
