-- Aijolot Banner Agent — F3: catalog awareness
-- Extracted columns for queryable inventory/recency + a materialized signal
-- table the catalog_scan job maintains (suggestions derive from these rows).

alter table public.shopify_resource_cache
  add column if not exists inventory_quantity integer,
  add column if not exists sales_rank         integer,
  add column if not exists published_at_shop  timestamptz;

create table if not exists public.catalog_signals (
  id           uuid primary key default gen_random_uuid(),
  team_id      uuid not null references public.teams(id) on delete cascade,
  store_id     uuid,
  product_gid  text not null,
  signal_type  text not null check (signal_type in ('low_stock', 'best_seller', 'new_product', 'no_active_banner')),
  value        jsonb not null default '{}'::jsonb,
  computed_at  timestamptz not null default now(),
  unique (team_id, product_gid, signal_type)
);

create index if not exists catalog_signals_team_idx on public.catalog_signals (team_id, computed_at desc);

alter table public.catalog_signals enable row level security;
drop policy if exists catalog_signals_member_select on public.catalog_signals;
create policy catalog_signals_member_select on public.catalog_signals
  for select using (public.is_team_member(team_id));
-- Writes come from the catalog_scan job (service_role).
