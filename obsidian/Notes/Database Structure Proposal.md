---
title: Database Structure Proposal
status: draft
updated: 2026-05-28
stack: Supabase Postgres/Auth/Storage
source_docs:
  - ../docs/architecture/frontend-template-deep-dive.md
  - ../docs/plans/2026-05-28-banner-creator-mvp.md
---

# Database Structure Proposal

Related: [[Frontend Functionality Map]]

This proposal aligns the backend database with the current frontend prototype from `frontend/design-implementation`, the source technical design PDF, and the latest product decisions.

Executable migration now exists at:

```text
../../supabase/migrations/20260528190000_initial_schema.sql
```

Local seed data exists at:

```text
../../supabase/seed.sql
```

## Principles

1. Use Supabase Auth as the identity source. Application tables reference `auth.users(id)`.
2. Keep campaign generation reproducible: snapshot Shopify catalog/product data used at generation time.
3. Keep generated creative immutable by revision. Refinements create new revisions or generation events instead of silently overwriting final assets.
4. Store flexible creative/layout/Shopify config as `jsonb` where the frontend already has dynamic structures.
5. Keep MVP simple but schema-ready for the visible frontend modules: performance, evolutionary memory, pinned comments, and new-section layout.
6. All assigned reviewers must approve before scheduling/publishing.
7. Track generation usage/costs with soft guard warnings, not hard caps.

## Recommended enums

Use Postgres enums or text columns with check constraints. For hackathon speed, check constraints are easier to evolve.

```sql
campaign_status:
  draft, generating, audit_pending, audit_retrying, audit_escalated,
  needs_review, changes_requested, approved, scheduled, publishing,
  published, failed, archived

approval_status:
  pending, approved, changes_requested, rejected

placement_mode:
  existing_section, new_section

target_type:
  home, collection, product, page, search, store

asset_kind:
  generated_background, product_image, logo, rendered_preview, liquid_asset

asset_size_key:
  mobile, tablet, desktop, srcset_320, srcset_768, srcset_1280, srcset_1920, original

publish_status:
  queued, running, succeeded, failed, cancelled

generation_event_type:
  text_generation, image_generation, asset_optimization, html_render, audit, publish
```

## Core identity and team tables

### `profiles`

Supabase Auth stores credentials. `profiles` stores app display data.

```sql
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null,
  avatar_url text,
  initials text,
  role_title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

### `teams`

```sql
create table teams (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  created_by uuid references profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

### `team_members`

```sql
create table team_members (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references teams(id) on delete cascade,
  user_id uuid not null references profiles(id) on delete cascade,
  role text not null default 'member', -- owner, admin, creator, reviewer, viewer
  created_at timestamptz not null default now(),
  unique(team_id, user_id)
);
```

## Shopify/store tables

### `stores`

One Shopify connection per store. Token should be encrypted or stored through a secret reference if available.

```sql
create table stores (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references teams(id) on delete cascade,
  shop_domain text not null,
  display_name text,
  access_token_secret_ref text,
  encrypted_access_token text,
  shopify_api_version text not null default '2026-01',
  theme_id text,
  banner_metafield_namespace text not null default 'aijolot',
  banner_metafield_key text not null default 'banner_campaigns',
  status text not null default 'connected',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(team_id, shop_domain)
);
```

### `shopify_resource_cache`

Powers list/select for collections, products, and pages. Search/autocomplete can query this later.

```sql
create table shopify_resource_cache (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references stores(id) on delete cascade,
  resource_type text not null, -- collection, product, page
  shopify_gid text not null,
  handle text,
  title text not null,
  vendor text,
  tags text[] not null default '{}',
  image_url text,
  status text,
  raw jsonb not null default '{}',
  synced_at timestamptz not null default now(),
  unique(store_id, resource_type, shopify_gid)
);

create index shopify_resource_cache_lookup_idx
  on shopify_resource_cache(store_id, resource_type, title);
```

## Brand context tables

### `brand_contexts`

Full CRUD. Repo Markdown files can seed this table.

```sql
create table brand_contexts (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references teams(id) on delete cascade,
  store_id uuid references stores(id) on delete set null,
  name text not null,
  slug text not null,
  description text,
  palette jsonb not null default '[]',
  typography jsonb not null default '{}',
  voice jsonb not null default '{}',
  allowed_rules text[] not null default '{}',
  forbidden_rules text[] not null default '{}',
  required_phrases text[] not null default '{}',
  prohibited_words text[] not null default '{}',
  image_style_directives text,
  logo_url text,
  source_file_path text,
  source_metadata jsonb not null default '{}',
  created_by uuid references profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz,
  unique(team_id, slug)
);
```

### `brand_assets`

Logos, product reference images, Figma/PDF imports, etc.

```sql
create table brand_assets (
  id uuid primary key default gen_random_uuid(),
  brand_context_id uuid not null references brand_contexts(id) on delete cascade,
  asset_type text not null, -- logo, product_reference, brandbook, figma_import, other
  storage_path text,
  public_url text,
  file_name text,
  mime_type text,
  metadata jsonb not null default '{}',
  created_by uuid references profiles(id),
  created_at timestamptz not null default now()
);
```

## Placement registry and campaign placement

### `placement_types`

Registry/config for banner kinds and supported targets.

```sql
create table placement_types (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  label text not null,
  description text,
  supported_targets text[] not null default '{}',
  supported_slots jsonb not null default '[]',
  default_dimensions jsonb not null default '{}',
  config_schema jsonb not null default '{}',
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);
```

Seed examples:

- announcement bar: home/store/collection/product/page
- hero main: home/collection/page
- promo left/right: home
- collection header: collection
- collection inline block: collection
- PDP strip: product
- PDP cross-sell: product
- footer CTA: home/collection/product/page/store
- search results banner: search, near-term extension

### `campaign_placements`

Stores what the frontend's PlacementStage produces.

```sql
create table campaign_placements (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null unique references campaigns(id) on delete cascade,
  placement_type_id uuid references placement_types(id),
  mode text not null, -- existing_section, new_section
  target_type text not null, -- home, collection, product, page, search, store
  target_resource_gid text,
  target_handle text,
  target_title text,
  existing_placement_key text,
  existing_placement_label text,
  existing_placement_size text,
  slot text, -- top, mid, bottom, hero, footer, etc.
  slot_order integer not null default 0,
  scope_rule jsonb not null default '{}',
  layout_json jsonb not null default '{"cols":[{"rows":1,"w":1,"align":"center"}]}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

Example `scope_rule` values:

```json
{ "kind": "home_only" }
{ "kind": "whole_store" }
{ "kind": "selected_collections", "handles": ["fragancias", "hombre"] }
{ "kind": "all_collections" }
{ "kind": "single_product", "handle": "boss-bottled" }
{ "kind": "product_vendor", "vendor": "Hugo Boss" }
{ "kind": "product_tag", "tag": "fragancia" }
{ "kind": "search_query", "query": "hugo boss" }
```

## Campaign and brief tables

### `campaigns`

```sql
create table campaigns (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references teams(id) on delete cascade,
  store_id uuid not null references stores(id) on delete cascade,
  brand_context_id uuid references brand_contexts(id) on delete set null,
  title text not null,
  promo_label text,
  promo_rule text,
  raw_brief text,
  structured_brief jsonb not null default '{}',
  status text not null default 'draft',
  created_by uuid references profiles(id),
  selected_revision_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz
);

create index campaigns_team_status_idx on campaigns(team_id, status, updated_at desc);
```

### `campaign_messages`

Stores brief chat transcript.

```sql
create table campaign_messages (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id) on delete cascade,
  author_type text not null, -- user, agent, system
  author_id uuid references profiles(id),
  body text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);
```

### `campaign_catalog_snapshots`

```sql
create table campaign_catalog_snapshots (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id) on delete cascade,
  source text not null default 'shopify',
  query_summary text,
  discount_rule jsonb not null default '{}',
  created_at timestamptz not null default now()
);
```

### `campaign_catalog_items`

```sql
create table campaign_catalog_items (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references campaign_catalog_snapshots(id) on delete cascade,
  shopify_product_gid text,
  shopify_variant_gid text,
  sku text,
  title text not null,
  segment_key text,
  price numeric(12,2),
  sale_price numeric(12,2),
  stock integer,
  image_url text,
  raw jsonb not null default '{}'
);
```

## Art direction and generation tables

### `art_directions`

Persists the frontend ArtStage choices.

```sql
create table art_directions (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null unique references campaigns(id) on delete cascade,
  background_mode text not null, -- hero, usage
  hero_style_key text,
  model_key text,
  custom_model jsonb,
  fold_percentage integer not null default 55,
  layout_hints jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

### `generation_runs`

One end-to-end graph execution. Refinements create new runs.

```sql
create table generation_runs (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id) on delete cascade,
  parent_run_id uuid references generation_runs(id),
  run_type text not null default 'initial', -- initial, refinement, v2_optimization
  status text not null default 'queued', -- queued, running, succeeded, failed, escalated
  frontend_step text, -- smart_querying, brand_engine, image_generation, compiler, shield
  adk_trace_id text,
  started_by uuid references profiles(id),
  started_at timestamptz,
  finished_at timestamptz,
  error_message text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);
```

### `generation_events`

Node-level logs from the 12-node ADK graph.

```sql
create table generation_events (
  id uuid primary key default gen_random_uuid(),
  generation_run_id uuid not null references generation_runs(id) on delete cascade,
  node_key text not null,
  frontend_step text,
  status text not null, -- started, succeeded, failed, retried, escalated
  input_summary jsonb not null default '{}',
  output_summary jsonb not null default '{}',
  duration_ms integer,
  cost_usd numeric(12,6),
  created_at timestamptz not null default now()
);
```

## Creative output tables

### `campaign_revisions`

Represents a complete generated creative set.

```sql
create table campaign_revisions (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id) on delete cascade,
  generation_run_id uuid references generation_runs(id) on delete set null,
  revision_number integer not null,
  status text not null default 'draft', -- draft, selected, superseded, approved, published
  concept jsonb not null default '{}',
  liquid_config jsonb not null default '{}',
  html_preview text,
  preview_storage_path text,
  created_at timestamptz not null default now(),
  unique(campaign_id, revision_number)
);
```

### `banner_layout_variants`

Frontend variants A/B/C.

```sql
create table banner_layout_variants (
  id uuid primary key default gen_random_uuid(),
  revision_id uuid not null references campaign_revisions(id) on delete cascade,
  key text not null, -- A, B, C
  name text not null,
  description text,
  layout_type text,
  is_recommended boolean not null default false,
  config jsonb not null default '{}',
  unique(revision_id, key)
);
```

### `banner_variants`

Personalization variants by segment/customer tag.

```sql
create table banner_variants (
  id uuid primary key default gen_random_uuid(),
  revision_id uuid not null references campaign_revisions(id) on delete cascade,
  segment_key text not null, -- default, masculino, femenino, vip, new_signup
  segment_label text not null,
  customer_tag text,
  audience_rule jsonb not null default '{}',
  product_snapshot_item_id uuid references campaign_catalog_items(id) on delete set null,
  eyebrow text,
  headline text,
  subheadline text,
  cta_text text,
  cta_url text,
  palette jsonb not null default '{}',
  unique(revision_id, segment_key)
);
```

### `banner_assets`

Stores generated/optimized assets.

```sql
create table banner_assets (
  id uuid primary key default gen_random_uuid(),
  banner_variant_id uuid references banner_variants(id) on delete cascade,
  revision_id uuid references campaign_revisions(id) on delete cascade,
  asset_kind text not null,
  size_key text not null,
  width integer,
  height integer,
  format text,
  storage_path text not null,
  public_url text,
  alt_text text,
  bytes integer,
  image_prompt text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);
```

## Review, comments, approvals

### `approval_threads`

```sql
create table approval_threads (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id) on delete cascade,
  revision_id uuid not null references campaign_revisions(id) on delete cascade,
  status text not null default 'open',
  approval_policy text not null default 'all_members',
  requested_by uuid references profiles(id),
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);
```

### `approval_reviewers`

```sql
create table approval_reviewers (
  id uuid primary key default gen_random_uuid(),
  approval_thread_id uuid not null references approval_threads(id) on delete cascade,
  user_id uuid not null references profiles(id),
  role_label text,
  status text not null default 'pending',
  note text,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(approval_thread_id, user_id)
);
```

### `comments`

Pinned comments support the canvas UI.

```sql
create table comments (
  id uuid primary key default gen_random_uuid(),
  approval_thread_id uuid references approval_threads(id) on delete cascade,
  campaign_id uuid not null references campaigns(id) on delete cascade,
  revision_id uuid references campaign_revisions(id) on delete set null,
  banner_variant_id uuid references banner_variants(id) on delete set null,
  layout_variant_key text,
  device_key text, -- desktop, tablet, mobile
  author_id uuid references profiles(id),
  body text not null,
  pin_x numeric(5,2),
  pin_y numeric(5,2),
  resolved boolean not null default false,
  resolved_by uuid references profiles(id),
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

### `refinement_requests`

Agent refinements from canvas prompt or comments.

```sql
create table refinement_requests (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id) on delete cascade,
  source_revision_id uuid not null references campaign_revisions(id) on delete cascade,
  result_revision_id uuid references campaign_revisions(id) on delete set null,
  requested_by uuid references profiles(id),
  prompt text not null,
  addressed_comment_ids uuid[] not null default '{}',
  status text not null default 'queued',
  result_summary text,
  created_at timestamptz not null default now(),
  finished_at timestamptz
);
```

## Scheduling and publishing

### `schedules`

```sql
create table schedules (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id) on delete cascade,
  revision_id uuid not null references campaign_revisions(id) on delete cascade,
  starts_at timestamptz not null,
  ends_at timestamptz,
  timezone text not null default 'UTC',
  auto_unpublish boolean not null default true,
  status text not null default 'pending',
  created_by uuid references profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (ends_at is null or ends_at > starts_at)
);
```

### `publish_jobs`

```sql
create table publish_jobs (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id) on delete cascade,
  revision_id uuid not null references campaign_revisions(id) on delete cascade,
  schedule_id uuid references schedules(id) on delete set null,
  status text not null default 'queued',
  action text not null default 'publish', -- install_theme_files, publish_config, unpublish, rollback
  shopify_resource_type text,
  shopify_resource_id text,
  request_payload jsonb not null default '{}',
  response_payload jsonb not null default '{}',
  error_message text,
  idempotency_key text not null,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  unique(idempotency_key)
);
```

## Audit, usage, and cost tracking

### `audit_reports`

```sql
create table audit_reports (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id) on delete cascade,
  revision_id uuid references campaign_revisions(id) on delete cascade,
  generation_run_id uuid references generation_runs(id) on delete set null,
  html_w3c jsonb not null default '{}',
  lighthouse jsonb not null default '{}',
  schema_valid boolean,
  breakpoints_render jsonb not null default '{}',
  asset_weight_report jsonb not null default '{}',
  wcag_report jsonb not null default '{}',
  seo_report jsonb not null default '{}',
  root_cause_hint text,
  retry_count integer not null default 0,
  status text not null default 'pending', -- pending, pass, fail, escalated
  created_at timestamptz not null default now()
);
```

### `audit_events`

General observability across ADK/backend/user actions.

```sql
create table audit_events (
  id bigserial primary key,
  team_id uuid references teams(id) on delete cascade,
  campaign_id uuid references campaigns(id) on delete cascade,
  trace_id text,
  session_id text,
  actor_type text not null, -- user, agent, system
  actor_id uuid references profiles(id),
  node text,
  event_type text not null,
  duration_ms integer,
  cost_usd numeric(12,6),
  audit_pass boolean,
  review_decision text,
  shopify_section_id text,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);
```

### `generation_usage_events`

Supports cost tracking and the 20 image generations/user/15 minutes warning.

```sql
create table generation_usage_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  team_id uuid not null references teams(id) on delete cascade,
  campaign_id uuid references campaigns(id) on delete set null,
  event_type text not null, -- text_generation, image_generation, asset_optimization
  provider text,
  model text,
  estimated_cost_usd numeric(12,6),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index generation_usage_user_window_idx
  on generation_usage_events(user_id, event_type, created_at desc);
```

Soft guard query:

```sql
select count(*)
from generation_usage_events
where user_id = :user_id
  and event_type = 'image_generation'
  and created_at >= now() - interval '15 minutes';
```

If count >= 20, warn the authenticated user but do not block generation.

## Performance and optimization loop

These tables can be mock/manual in MVP but keep the schema ready because the frontend shows this module.

### `performance_snapshots`

```sql
create table performance_snapshots (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id) on delete cascade,
  revision_id uuid references campaign_revisions(id) on delete set null,
  source text not null default 'manual', -- manual, shopify, analytics, lighthouse
  window_start timestamptz,
  window_end timestamptz,
  impressions integer,
  clicks integer,
  ctr numeric(8,4),
  conversions integer,
  conversion_rate numeric(8,4),
  load_p75_ms integer,
  weight_saved_pct numeric(6,2),
  segment_breakdown jsonb not null default '[]',
  trend jsonb not null default '{}',
  created_at timestamptz not null default now()
);
```

### `optimization_insights`

Evolutionary memory.

```sql
create table optimization_insights (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references teams(id) on delete cascade,
  campaign_id uuid references campaigns(id) on delete set null,
  segment_key text,
  tag text,
  insight text not null,
  lift_label text,
  source jsonb not null default '{}',
  created_at timestamptz not null default now()
);
```

### `optimization_proposals`

Agent-proposed Version 2.

```sql
create table optimization_proposals (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references campaigns(id) on delete cascade,
  source_revision_id uuid references campaign_revisions(id) on delete set null,
  proposed_revision_id uuid references campaign_revisions(id) on delete set null,
  segment_key text,
  rationale text not null,
  projected_lift jsonb not null default '{}',
  status text not null default 'draft', -- draft, sent_to_approval, accepted, rejected
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

## Storage buckets

Recommended Supabase Storage buckets:

- `brand-assets`
  - logos, brandbooks, imported Figma/PDF assets.
- `campaign-assets`
  - generated images, optimized variants, product cutouts, previews.
- `rendered-previews`
  - standalone HTML preview artifacts/screenshots if needed.

Suggested path patterns:

```text
brand-assets/{team_id}/{brand_context_id}/{asset_id}-{filename}
campaign-assets/{team_id}/{campaign_id}/{revision_id}/{variant_key}/{size_key}.{format}
rendered-previews/{team_id}/{campaign_id}/{revision_id}/preview.html
```

## RLS strategy

MVP policies should be simple:

- A user can access rows where they are a member of the row's `team_id`.
- Store tokens are never readable by regular frontend clients.
- Service-role backend performs Shopify publish and generation writes.
- Approval reviewers can read the campaign/revision they are assigned to and update only their own approval status.
- Comments can be created by team members; resolved by team members.

## Recommended implementation order

1. Identity/team/store basics.
2. Brand context CRUD and brand assets.
3. Placement registry + campaign placement.
4. Campaign + brief messages + catalog snapshot.
5. Art direction + generation runs/events.
6. Campaign revisions + variants + assets.
7. Comments + approval threads/reviewers.
8. Schedule + publish jobs.
9. Audit reports/events + generation usage soft guard.
10. Performance snapshots + optimization insights/proposals.

## Notes for backend API design

The frontend should not need to understand all tables directly. It should consume composed API responses:

- `GET /campaigns`: dashboard card/list shape.
- `GET /campaigns/{id}`: full campaign studio state.
- `GET /brands/{id}`: editable brand profile shape.
- `GET /stores/{id}/resources?type=collection|product|page`: list/select options.
- `POST /campaigns/{id}/generate`: starts generation run.
- `GET /campaigns/{id}/generation-runs/{run_id}` or SSE: frontend-facing 5-step progress.
- `GET /campaigns/{id}/canvas`: revision, variants, comments, approvals, schedule.
- `POST /campaigns/{id}/publish`: publish now.
- `POST /campaigns/{id}/schedule`: schedule publish/auto-unpublish.
