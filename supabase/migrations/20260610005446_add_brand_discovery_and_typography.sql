-- Brand discovery + font system persistence (Task 2 of the brand discovery plan).
--
-- brand_contexts gains two first-class JSONB columns:
--   - discovery_snapshot: latest BrandDiscoverySnapshot (raw Shopify evidence, not
--     approved brand context; BrandContext itself never exposes it).
--   - typography_system: the FULL Typography dump (display/body/headline/accent/
--     approved_fonts/discarded_fonts). The legacy `typography` column keeps the
--     two-key {display, body} shape so old readers stay stable.
--
-- brand_discovery_runs keeps per-run history (snapshot + recommendation draft)
-- for debuggability/audits; the latest applied evidence lives on brand_contexts.

alter table public.brand_contexts add column if not exists discovery_snapshot jsonb;
alter table public.brand_contexts add column if not exists typography_system jsonb;

create index if not exists brand_contexts_discovery_snapshot_gin_idx
    on public.brand_contexts using gin (discovery_snapshot);

create index if not exists brand_contexts_typography_system_gin_idx
    on public.brand_contexts using gin (typography_system);

create table if not exists public.brand_discovery_runs (
  id uuid primary key default gen_random_uuid(),
  team_id text not null,
  store_id text,
  brand_id text not null,
  status text not null check (status in ('pending', 'running', 'succeeded', 'failed', 'partial')),
  snapshot jsonb not null default '{}'::jsonb,
  recommendation jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists brand_discovery_runs_brand_idx
  on public.brand_discovery_runs (team_id, brand_id, created_at desc);

create or replace trigger brand_discovery_runs_set_updated_at
before update on public.brand_discovery_runs
for each row execute function public.set_updated_at();

-- RLS: backend access goes through the service-role client (bypasses RLS).
-- No anon/authenticated policies on purpose — raw discovery evidence is
-- team-internal and team_id is text (slug-friendly), so the uuid-based
-- is_team_member() helper does not apply.
alter table public.brand_discovery_runs enable row level security;
