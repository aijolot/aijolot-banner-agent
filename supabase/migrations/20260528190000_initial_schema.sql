-- Aijolot Banner Agent — initial Supabase schema
-- This migration implements the DB structure proposed in obsidian/Notes/Database Structure Proposal.md.

create extension if not exists pgcrypto;
create extension if not exists pg_cron with schema extensions;

-- ----------------------------------------------------------------------------
-- Shared helpers
-- ----------------------------------------------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ----------------------------------------------------------------------------
-- Identity / teams
-- ----------------------------------------------------------------------------

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null,
  avatar_url text,
  initials text,
  role_title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create table public.teams (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger teams_set_updated_at
before update on public.teams
for each row execute function public.set_updated_at();

create table public.team_members (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references public.teams(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'admin', 'creator', 'reviewer', 'viewer', 'member')),
  created_at timestamptz not null default now(),
  unique(team_id, user_id)
);

create index team_members_user_idx on public.team_members(user_id);

create or replace function public.is_team_member(team_id_to_check uuid)
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.team_members tm
    where tm.team_id = team_id_to_check
      and tm.user_id = auth.uid()
  );
$$;

-- ----------------------------------------------------------------------------
-- Shopify stores and resource cache
-- ----------------------------------------------------------------------------

create table public.stores (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references public.teams(id) on delete cascade,
  shop_domain text not null,
  display_name text,
  access_token_secret_ref text,
  encrypted_access_token text,
  shopify_api_version text not null default '2026-01',
  theme_id text,
  banner_metafield_namespace text not null default 'aijolot',
  banner_metafield_key text not null default 'banner_campaigns',
  status text not null default 'connected' check (status in ('connected', 'disconnected', 'needs_attention')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(team_id, shop_domain)
);

create index stores_team_idx on public.stores(team_id);
create trigger stores_set_updated_at
before update on public.stores
for each row execute function public.set_updated_at();

create table public.shopify_resource_cache (
  id uuid primary key default gen_random_uuid(),
  store_id uuid not null references public.stores(id) on delete cascade,
  resource_type text not null check (resource_type in ('collection', 'product', 'page')),
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

create index shopify_resource_cache_lookup_idx on public.shopify_resource_cache(store_id, resource_type, title);
create index shopify_resource_cache_handle_idx on public.shopify_resource_cache(store_id, resource_type, handle);

-- ----------------------------------------------------------------------------
-- Brand context
-- ----------------------------------------------------------------------------

create table public.brand_contexts (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references public.teams(id) on delete cascade,
  store_id uuid references public.stores(id) on delete set null,
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
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz,
  unique(team_id, slug)
);

create index brand_contexts_team_idx on public.brand_contexts(team_id, archived_at);
create trigger brand_contexts_set_updated_at
before update on public.brand_contexts
for each row execute function public.set_updated_at();

create table public.brand_assets (
  id uuid primary key default gen_random_uuid(),
  brand_context_id uuid not null references public.brand_contexts(id) on delete cascade,
  asset_type text not null check (asset_type in ('logo', 'product_reference', 'brandbook', 'figma_import', 'other')),
  storage_path text,
  public_url text,
  file_name text,
  mime_type text,
  metadata jsonb not null default '{}',
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now()
);

create index brand_assets_context_idx on public.brand_assets(brand_context_id, asset_type);

-- ----------------------------------------------------------------------------
-- Placement registry and campaign placement
-- ----------------------------------------------------------------------------

create table public.placement_types (
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

-- ----------------------------------------------------------------------------
-- Campaigns, brief, catalog snapshots
-- ----------------------------------------------------------------------------

create table public.campaigns (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references public.teams(id) on delete cascade,
  store_id uuid not null references public.stores(id) on delete cascade,
  brand_context_id uuid references public.brand_contexts(id) on delete set null,
  title text not null,
  promo_label text,
  promo_rule text,
  raw_brief text,
  structured_brief jsonb not null default '{}',
  status text not null default 'draft' check (status in (
    'draft', 'generating', 'audit_pending', 'audit_retrying', 'audit_escalated',
    'needs_review', 'changes_requested', 'approved', 'scheduled', 'publishing',
    'published', 'failed', 'archived'
  )),
  created_by uuid references public.profiles(id) on delete set null,
  selected_revision_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz
);

create index campaigns_team_status_idx on public.campaigns(team_id, status, updated_at desc);
create index campaigns_store_idx on public.campaigns(store_id);
create trigger campaigns_set_updated_at
before update on public.campaigns
for each row execute function public.set_updated_at();

create table public.campaign_placements (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null unique references public.campaigns(id) on delete cascade,
  placement_type_id uuid references public.placement_types(id) on delete set null,
  mode text not null check (mode in ('existing_section', 'new_section')),
  target_type text not null check (target_type in ('home', 'collection', 'product', 'page', 'search', 'store')),
  target_resource_gid text,
  target_handle text,
  target_title text,
  existing_placement_key text,
  existing_placement_label text,
  existing_placement_size text,
  slot text,
  slot_order integer not null default 0,
  scope_rule jsonb not null default '{}',
  layout_json jsonb not null default '{"cols":[{"rows":1,"w":1,"align":"center"}]}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger campaign_placements_set_updated_at
before update on public.campaign_placements
for each row execute function public.set_updated_at();

create table public.campaign_messages (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  author_type text not null check (author_type in ('user', 'agent', 'system')),
  author_id uuid references public.profiles(id) on delete set null,
  body text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index campaign_messages_campaign_idx on public.campaign_messages(campaign_id, created_at);

create table public.campaign_catalog_snapshots (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  source text not null default 'shopify',
  query_summary text,
  discount_rule jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table public.campaign_catalog_items (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references public.campaign_catalog_snapshots(id) on delete cascade,
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

create index campaign_catalog_items_snapshot_idx on public.campaign_catalog_items(snapshot_id);

-- ----------------------------------------------------------------------------
-- Art direction and generation
-- ----------------------------------------------------------------------------

create table public.art_directions (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null unique references public.campaigns(id) on delete cascade,
  background_mode text not null check (background_mode in ('hero', 'usage')),
  hero_style_key text,
  model_key text,
  custom_model jsonb,
  fold_percentage integer not null default 55 check (fold_percentage between 0 and 100),
  layout_hints jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger art_directions_set_updated_at
before update on public.art_directions
for each row execute function public.set_updated_at();

create table public.generation_runs (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  parent_run_id uuid references public.generation_runs(id) on delete set null,
  run_type text not null default 'initial' check (run_type in ('initial', 'refinement', 'v2_optimization')),
  status text not null default 'queued' check (status in ('queued', 'running', 'succeeded', 'failed', 'escalated')),
  frontend_step text,
  adk_trace_id text,
  started_by uuid references public.profiles(id) on delete set null,
  started_at timestamptz,
  finished_at timestamptz,
  error_message text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index generation_runs_campaign_idx on public.generation_runs(campaign_id, created_at desc);

create table public.generation_events (
  id uuid primary key default gen_random_uuid(),
  generation_run_id uuid not null references public.generation_runs(id) on delete cascade,
  node_key text not null,
  frontend_step text,
  status text not null check (status in ('started', 'succeeded', 'failed', 'retried', 'escalated')),
  input_summary jsonb not null default '{}',
  output_summary jsonb not null default '{}',
  duration_ms integer,
  cost_usd numeric(12,6),
  created_at timestamptz not null default now()
);

create index generation_events_run_idx on public.generation_events(generation_run_id, created_at);

-- ----------------------------------------------------------------------------
-- Creative output
-- ----------------------------------------------------------------------------

create table public.campaign_revisions (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  generation_run_id uuid references public.generation_runs(id) on delete set null,
  revision_number integer not null,
  status text not null default 'draft' check (status in ('draft', 'selected', 'superseded', 'approved', 'published')),
  concept jsonb not null default '{}',
  liquid_config jsonb not null default '{}',
  html_preview text,
  preview_storage_path text,
  created_at timestamptz not null default now(),
  unique(campaign_id, revision_number)
);

create index campaign_revisions_campaign_idx on public.campaign_revisions(campaign_id, revision_number desc);

alter table public.campaigns
  add constraint campaigns_selected_revision_fk
  foreign key (selected_revision_id)
  references public.campaign_revisions(id)
  on delete set null;

create table public.banner_layout_variants (
  id uuid primary key default gen_random_uuid(),
  revision_id uuid not null references public.campaign_revisions(id) on delete cascade,
  key text not null,
  name text not null,
  description text,
  layout_type text,
  is_recommended boolean not null default false,
  config jsonb not null default '{}',
  unique(revision_id, key)
);

create table public.banner_variants (
  id uuid primary key default gen_random_uuid(),
  revision_id uuid not null references public.campaign_revisions(id) on delete cascade,
  segment_key text not null,
  segment_label text not null,
  customer_tag text,
  audience_rule jsonb not null default '{}',
  product_snapshot_item_id uuid references public.campaign_catalog_items(id) on delete set null,
  eyebrow text,
  headline text,
  subheadline text,
  cta_text text,
  cta_url text,
  palette jsonb not null default '{}',
  unique(revision_id, segment_key)
);

create index banner_variants_revision_idx on public.banner_variants(revision_id);

create table public.banner_assets (
  id uuid primary key default gen_random_uuid(),
  banner_variant_id uuid references public.banner_variants(id) on delete cascade,
  revision_id uuid references public.campaign_revisions(id) on delete cascade,
  asset_kind text not null check (asset_kind in ('generated_background', 'product_image', 'logo', 'rendered_preview', 'liquid_asset')),
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
  created_at timestamptz not null default now(),
  check (banner_variant_id is not null or revision_id is not null)
);

create index banner_assets_variant_idx on public.banner_assets(banner_variant_id, size_key);
create index banner_assets_revision_idx on public.banner_assets(revision_id, asset_kind);

-- ----------------------------------------------------------------------------
-- Review, comments, approvals
-- ----------------------------------------------------------------------------

create table public.approval_threads (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  revision_id uuid not null references public.campaign_revisions(id) on delete cascade,
  status text not null default 'open' check (status in ('open', 'approved', 'changes_requested', 'rejected')),
  approval_policy text not null default 'all_members' check (approval_policy in ('all_members', 'any_member', 'required_members', 'owner_only')),
  requested_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create index approval_threads_campaign_idx on public.approval_threads(campaign_id, created_at desc);

create table public.approval_reviewers (
  id uuid primary key default gen_random_uuid(),
  approval_thread_id uuid not null references public.approval_threads(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role_label text,
  status text not null default 'pending' check (status in ('pending', 'approved', 'changes_requested', 'rejected')),
  note text,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(approval_thread_id, user_id)
);

create trigger approval_reviewers_set_updated_at
before update on public.approval_reviewers
for each row execute function public.set_updated_at();

create or replace function public.is_approval_reviewer(thread_id_to_check uuid)
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.approval_reviewers ar
    where ar.approval_thread_id = thread_id_to_check
      and ar.user_id = auth.uid()
  );
$$;

create table public.comments (
  id uuid primary key default gen_random_uuid(),
  approval_thread_id uuid references public.approval_threads(id) on delete cascade,
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  revision_id uuid references public.campaign_revisions(id) on delete set null,
  banner_variant_id uuid references public.banner_variants(id) on delete set null,
  layout_variant_key text,
  device_key text check (device_key is null or device_key in ('desktop', 'tablet', 'mobile')),
  author_id uuid references public.profiles(id) on delete set null,
  body text not null,
  pin_x numeric(5,2),
  pin_y numeric(5,2),
  resolved boolean not null default false,
  resolved_by uuid references public.profiles(id) on delete set null,
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((pin_x is null and pin_y is null) or (pin_x between 0 and 100 and pin_y between 0 and 100))
);

create index comments_campaign_idx on public.comments(campaign_id, created_at desc);
create index comments_thread_idx on public.comments(approval_thread_id, resolved);
create trigger comments_set_updated_at
before update on public.comments
for each row execute function public.set_updated_at();

create table public.refinement_requests (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  source_revision_id uuid not null references public.campaign_revisions(id) on delete cascade,
  result_revision_id uuid references public.campaign_revisions(id) on delete set null,
  requested_by uuid references public.profiles(id) on delete set null,
  prompt text not null,
  addressed_comment_ids uuid[] not null default '{}',
  status text not null default 'queued' check (status in ('queued', 'running', 'succeeded', 'failed')),
  result_summary text,
  created_at timestamptz not null default now(),
  finished_at timestamptz
);

-- ----------------------------------------------------------------------------
-- Scheduling and publishing
-- ----------------------------------------------------------------------------

create table public.schedules (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  revision_id uuid not null references public.campaign_revisions(id) on delete cascade,
  starts_at timestamptz not null,
  ends_at timestamptz,
  timezone text not null default 'UTC',
  auto_unpublish boolean not null default true,
  status text not null default 'pending' check (status in ('pending', 'active', 'completed', 'cancelled')),
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (ends_at is null or ends_at > starts_at)
);

create index schedules_campaign_idx on public.schedules(campaign_id, starts_at desc);
create index schedules_due_idx on public.schedules(status, starts_at, ends_at);
create trigger schedules_set_updated_at
before update on public.schedules
for each row execute function public.set_updated_at();

create table public.publish_jobs (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  revision_id uuid not null references public.campaign_revisions(id) on delete cascade,
  schedule_id uuid references public.schedules(id) on delete set null,
  status text not null default 'queued' check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  action text not null default 'publish' check (action in ('install_theme_files', 'publish_config', 'publish', 'unpublish', 'rollback')),
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

create index publish_jobs_campaign_idx on public.publish_jobs(campaign_id, created_at desc);
create index publish_jobs_status_idx on public.publish_jobs(status, created_at);

-- Future-compatible scheduled publish table from source design.
create table public.scheduled_banners (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid references public.campaigns(id) on delete cascade,
  brand_id text,
  payload jsonb not null,
  target_publish_at timestamptz not null,
  status text not null default 'pending' check (status in ('pending', 'processing', 'published', 'failed', 'cancelled')),
  created_at timestamptz not null default now()
);

create index scheduled_banners_due_idx on public.scheduled_banners(status, target_publish_at);

-- ----------------------------------------------------------------------------
-- Audit, usage, cost tracking
-- ----------------------------------------------------------------------------

create table public.audit_reports (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  revision_id uuid references public.campaign_revisions(id) on delete cascade,
  generation_run_id uuid references public.generation_runs(id) on delete set null,
  html_w3c jsonb not null default '{}',
  lighthouse jsonb not null default '{}',
  schema_valid boolean,
  breakpoints_render jsonb not null default '{}',
  asset_weight_report jsonb not null default '{}',
  wcag_report jsonb not null default '{}',
  seo_report jsonb not null default '{}',
  root_cause_hint text,
  retry_count integer not null default 0,
  status text not null default 'pending' check (status in ('pending', 'pass', 'fail', 'escalated')),
  created_at timestamptz not null default now()
);

create index audit_reports_campaign_idx on public.audit_reports(campaign_id, created_at desc);

create table public.audit_events (
  id bigserial primary key,
  team_id uuid references public.teams(id) on delete cascade,
  campaign_id uuid references public.campaigns(id) on delete cascade,
  trace_id text,
  session_id text,
  actor_type text not null check (actor_type in ('user', 'agent', 'system')),
  actor_id uuid references public.profiles(id) on delete set null,
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

create index audit_events_campaign_idx on public.audit_events(campaign_id, created_at desc);
create index audit_events_trace_idx on public.audit_events(trace_id);

create table public.generation_usage_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  team_id uuid not null references public.teams(id) on delete cascade,
  campaign_id uuid references public.campaigns(id) on delete set null,
  event_type text not null check (event_type in ('text_generation', 'image_generation', 'asset_optimization')),
  provider text,
  model text,
  estimated_cost_usd numeric(12,6),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index generation_usage_user_window_idx on public.generation_usage_events(user_id, event_type, created_at desc);
create index generation_usage_team_idx on public.generation_usage_events(team_id, created_at desc);

-- ----------------------------------------------------------------------------
-- Performance and optimization loop
-- ----------------------------------------------------------------------------

create table public.performance_snapshots (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  revision_id uuid references public.campaign_revisions(id) on delete set null,
  source text not null default 'manual' check (source in ('manual', 'shopify', 'analytics', 'lighthouse')),
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

create index performance_snapshots_campaign_idx on public.performance_snapshots(campaign_id, created_at desc);

create table public.optimization_insights (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references public.teams(id) on delete cascade,
  campaign_id uuid references public.campaigns(id) on delete set null,
  segment_key text,
  tag text,
  insight text not null,
  lift_label text,
  source jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index optimization_insights_team_idx on public.optimization_insights(team_id, created_at desc);

create table public.optimization_proposals (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(id) on delete cascade,
  source_revision_id uuid references public.campaign_revisions(id) on delete set null,
  proposed_revision_id uuid references public.campaign_revisions(id) on delete set null,
  segment_key text,
  rationale text not null,
  projected_lift jsonb not null default '{}',
  status text not null default 'draft' check (status in ('draft', 'sent_to_approval', 'accepted', 'rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger optimization_proposals_set_updated_at
before update on public.optimization_proposals
for each row execute function public.set_updated_at();

-- ----------------------------------------------------------------------------
-- Storage buckets
-- ----------------------------------------------------------------------------

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('brand-assets', 'brand-assets', false, 52428800, array['image/png', 'image/jpeg', 'image/webp', 'image/avif', 'image/svg+xml', 'application/pdf']::text[]),
  ('campaign-assets', 'campaign-assets', false, 52428800, array['image/png', 'image/jpeg', 'image/webp', 'image/avif', 'text/html', 'application/json']::text[]),
  ('rendered-previews', 'rendered-previews', false, 10485760, array['text/html', 'image/png', 'image/jpeg', 'image/webp']::text[])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- ----------------------------------------------------------------------------
-- RLS
-- ----------------------------------------------------------------------------

alter table public.profiles enable row level security;
alter table public.teams enable row level security;
alter table public.team_members enable row level security;
alter table public.stores enable row level security;
alter table public.shopify_resource_cache enable row level security;
alter table public.brand_contexts enable row level security;
alter table public.brand_assets enable row level security;
alter table public.campaigns enable row level security;
alter table public.campaign_placements enable row level security;
alter table public.campaign_messages enable row level security;
alter table public.campaign_catalog_snapshots enable row level security;
alter table public.campaign_catalog_items enable row level security;
alter table public.art_directions enable row level security;
alter table public.generation_runs enable row level security;
alter table public.generation_events enable row level security;
alter table public.campaign_revisions enable row level security;
alter table public.banner_layout_variants enable row level security;
alter table public.banner_variants enable row level security;
alter table public.banner_assets enable row level security;
alter table public.approval_threads enable row level security;
alter table public.approval_reviewers enable row level security;
alter table public.comments enable row level security;
alter table public.refinement_requests enable row level security;
alter table public.schedules enable row level security;
alter table public.publish_jobs enable row level security;
alter table public.scheduled_banners enable row level security;
alter table public.audit_reports enable row level security;
alter table public.audit_events enable row level security;
alter table public.generation_usage_events enable row level security;
alter table public.performance_snapshots enable row level security;
alter table public.optimization_insights enable row level security;
alter table public.optimization_proposals enable row level security;

-- Profiles: users can read team-member profiles through joins in app APIs; direct self-management here.
create policy profiles_select_self on public.profiles for select using (id = auth.uid());
create policy profiles_update_self on public.profiles for update using (id = auth.uid()) with check (id = auth.uid());
create policy profiles_insert_self on public.profiles for insert with check (id = auth.uid());

create policy teams_member_select on public.teams for select using (public.is_team_member(id));
create policy teams_member_update on public.teams for update using (public.is_team_member(id)) with check (public.is_team_member(id));

create policy team_members_select on public.team_members for select using (public.is_team_member(team_id) or user_id = auth.uid());
create policy team_members_insert_self on public.team_members for insert with check (user_id = auth.uid());

-- Team-scoped tables with direct team_id.
create policy stores_team_all on public.stores for all using (public.is_team_member(team_id)) with check (public.is_team_member(team_id));
create policy brand_contexts_team_all on public.brand_contexts for all using (public.is_team_member(team_id)) with check (public.is_team_member(team_id));
create policy campaigns_team_all on public.campaigns for all using (public.is_team_member(team_id)) with check (public.is_team_member(team_id));
create policy audit_events_team_select on public.audit_events for select using (team_id is null or public.is_team_member(team_id));
create policy usage_events_team_select on public.generation_usage_events for select using (public.is_team_member(team_id));
create policy usage_events_team_insert on public.generation_usage_events for insert with check (public.is_team_member(team_id) and user_id = auth.uid());
create policy optimization_insights_team_all on public.optimization_insights for all using (public.is_team_member(team_id)) with check (public.is_team_member(team_id));

-- Store children.
create policy shopify_resource_cache_team_select on public.shopify_resource_cache for select using (
  exists (select 1 from public.stores s where s.id = store_id and public.is_team_member(s.team_id))
);

-- Brand children.
create policy brand_assets_team_all on public.brand_assets for all using (
  exists (select 1 from public.brand_contexts b where b.id = brand_context_id and public.is_team_member(b.team_id))
) with check (
  exists (select 1 from public.brand_contexts b where b.id = brand_context_id and public.is_team_member(b.team_id))
);

-- Placement registry is readable by all authenticated users; writes go through service role.
create policy placement_types_read on public.placement_types for select using (auth.uid() is not null);

-- Campaign child helper pattern.
create policy campaign_placements_team_all on public.campaign_placements for all using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
) with check (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy campaign_messages_team_all on public.campaign_messages for all using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
) with check (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy campaign_catalog_snapshots_team_select on public.campaign_catalog_snapshots for select using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy campaign_catalog_items_team_select on public.campaign_catalog_items for select using (
  exists (
    select 1 from public.campaign_catalog_snapshots s
    join public.campaigns c on c.id = s.campaign_id
    where s.id = snapshot_id and public.is_team_member(c.team_id)
  )
);

create policy art_directions_team_all on public.art_directions for all using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
) with check (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy generation_runs_team_select on public.generation_runs for select using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy generation_events_team_select on public.generation_events for select using (
  exists (
    select 1 from public.generation_runs gr
    join public.campaigns c on c.id = gr.campaign_id
    where gr.id = generation_run_id and public.is_team_member(c.team_id)
  )
);

create policy campaign_revisions_team_select on public.campaign_revisions for select using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy banner_layout_variants_team_select on public.banner_layout_variants for select using (
  exists (
    select 1 from public.campaign_revisions r
    join public.campaigns c on c.id = r.campaign_id
    where r.id = revision_id and public.is_team_member(c.team_id)
  )
);

create policy banner_variants_team_select on public.banner_variants for select using (
  exists (
    select 1 from public.campaign_revisions r
    join public.campaigns c on c.id = r.campaign_id
    where r.id = revision_id and public.is_team_member(c.team_id)
  )
);

create policy banner_assets_team_select on public.banner_assets for select using (
  exists (
    select 1 from public.campaign_revisions r
    join public.campaigns c on c.id = r.campaign_id
    where r.id = revision_id and public.is_team_member(c.team_id)
  ) or exists (
    select 1 from public.banner_variants bv
    join public.campaign_revisions r on r.id = bv.revision_id
    join public.campaigns c on c.id = r.campaign_id
    where bv.id = banner_variant_id and public.is_team_member(c.team_id)
  )
);

create policy approval_threads_team_all on public.approval_threads for all using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
) with check (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy approval_reviewers_team_select on public.approval_reviewers for select using (
  exists (
    select 1 from public.approval_threads t
    join public.campaigns c on c.id = t.campaign_id
    where t.id = approval_thread_id and public.is_team_member(c.team_id)
  )
);

create policy approval_reviewers_update_self on public.approval_reviewers for update using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy comments_team_all on public.comments for all using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
) with check (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy refinement_requests_team_all on public.refinement_requests for all using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
) with check (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy schedules_team_all on public.schedules for all using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
) with check (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy publish_jobs_team_select on public.publish_jobs for select using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy scheduled_banners_team_select on public.scheduled_banners for select using (
  campaign_id is null or exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy audit_reports_team_select on public.audit_reports for select using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy performance_snapshots_team_select on public.performance_snapshots for select using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

create policy optimization_proposals_team_all on public.optimization_proposals for all using (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
) with check (
  exists (select 1 from public.campaigns c where c.id = campaign_id and public.is_team_member(c.team_id))
);

-- Storage policies: authenticated users can read/write objects through app/team paths.
-- Strict path-level team enforcement is deferred to backend service-role uploads for MVP.
create policy storage_authenticated_read on storage.objects for select using (auth.role() = 'authenticated');
create policy storage_authenticated_insert on storage.objects for insert with check (auth.role() = 'authenticated');
create policy storage_authenticated_update on storage.objects for update using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
