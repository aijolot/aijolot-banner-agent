alter table public.brand_contexts add column if not exists color_system jsonb;

create index if not exists brand_contexts_color_system_gin_idx
    on public.brand_contexts using gin (color_system);