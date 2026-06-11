-- Aijolot Banner Agent — proactive agent infrastructure (Fase 0)
-- agent_suggestions: unified model behind the dashboard "el agente sugiere" panel
--   (calendar events, performance refreshes, catalog signals — F1/F2/F3 producers).
-- agent_jobs: recurring scan queue using the SAME backend-poll pattern as the
--   publish scheduler (pg_cron claims rows under SKIP LOCKED; the FastAPI poller
--   at /api/v1/agent-jobs/process executes them).

-- ----------------------------------------------------------------------------
-- 1. agent_suggestions
-- ----------------------------------------------------------------------------

create table if not exists public.agent_suggestions (
  id          uuid primary key default gen_random_uuid(),
  team_id     uuid not null references public.teams(id) on delete cascade,
  kind        text not null check (kind in ('calendar_event', 'performance_refresh', 'catalog_signal')),
  status      text not null default 'pending'
              check (status in ('pending', 'accepted', 'dismissed', 'expired')),
  title       text not null,
  rationale   text not null default '',
  -- Prefilled structured_brief / proposed changes / product refs, by kind.
  payload     jsonb not null default '{}'::jsonb,
  -- [{type:'kg_doc'|'snapshot'|'catalog_item'|'calendar_event', id, title}]
  source_refs jsonb not null default '[]'::jsonb,
  campaign_id uuid references public.campaigns(id) on delete set null,
  proposal_id uuid references public.optimization_proposals(id) on delete set null,
  dedupe_key  text,
  expires_at  timestamptz,
  acted_at    timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create unique index if not exists agent_suggestions_dedupe_uidx
  on public.agent_suggestions (team_id, dedupe_key)
  where dedupe_key is not null;
create index if not exists agent_suggestions_team_status_idx on public.agent_suggestions (team_id, status, created_at desc);

alter table public.agent_suggestions enable row level security;
drop policy if exists agent_suggestions_member_select on public.agent_suggestions;
create policy agent_suggestions_member_select on public.agent_suggestions
  for select using (public.is_team_member(team_id));
drop policy if exists agent_suggestions_member_update on public.agent_suggestions;
create policy agent_suggestions_member_update on public.agent_suggestions
  for update using (public.is_team_member(team_id)) with check (public.is_team_member(team_id));
-- Inserts come from the agent (service_role bypasses RLS); members only read/act.

-- ----------------------------------------------------------------------------
-- 2. agent_jobs (scan queue)
-- ----------------------------------------------------------------------------

create table if not exists public.agent_jobs (
  id                     uuid primary key default gen_random_uuid(),
  team_id                uuid not null references public.teams(id) on delete cascade,
  kind                   text not null check (kind in ('calendar_scan', 'performance_sync', 'catalog_scan')),
  status                 text not null default 'pending'
                         check (status in ('pending', 'processing', 'done', 'error')),
  run_after              timestamptz not null default now(),
  processing_started_at  timestamptz,
  attempt_count          integer not null default 0,
  error_detail           text,
  result_summary         jsonb,
  created_at             timestamptz not null default now()
);

create index if not exists agent_jobs_due_idx on public.agent_jobs (status, run_after);
create index if not exists agent_jobs_processing_idx on public.agent_jobs (status, processing_started_at)
  where status = 'processing';
-- Avoid piling up duplicate pending scans of the same kind for a team.
create unique index if not exists agent_jobs_pending_uidx on public.agent_jobs (team_id, kind)
  where status in ('pending', 'processing');

alter table public.agent_jobs enable row level security;
drop policy if exists agent_jobs_member_select on public.agent_jobs;
create policy agent_jobs_member_select on public.agent_jobs
  for select using (public.is_team_member(team_id));
-- Writes are service_role only (pg_cron functions + backend poller).

-- ----------------------------------------------------------------------------
-- 3. claim_due_agent_jobs_fn — claim pending+due rows under SKIP LOCKED
--    (same design as publish_due_banners_fn)
-- ----------------------------------------------------------------------------

create or replace function public.claim_due_agent_jobs_fn()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.agent_jobs
  set status = 'processing',
      processing_started_at = now(),
      attempt_count = attempt_count + 1
  where id in (
    select id from public.agent_jobs
    where status = 'pending' and run_after <= now()
    order by run_after
    limit 20
    for update skip locked
  );
end;
$$;

create or replace function public.cleanup_stale_agent_jobs_fn()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.agent_jobs
  set status = 'pending',
      processing_started_at = null,
      error_detail = 'reset after 15m timeout (attempt ' || attempt_count || ')'
  where status = 'processing'
    and processing_started_at < now() - interval '15 minutes';
end;
$$;

-- ----------------------------------------------------------------------------
-- 4. enqueue_agent_scans_fn — one job per kind per team with an active store
-- ----------------------------------------------------------------------------

create or replace function public.enqueue_agent_scans_fn(scan_kind text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.agent_jobs (team_id, kind)
  select t.id, scan_kind
  from public.teams t
  on conflict do nothing;  -- agent_jobs_pending_uidx dedupes per (team, kind)
end;
$$;

-- ----------------------------------------------------------------------------
-- 5. Cron registration (idempotent)
-- ----------------------------------------------------------------------------

do $$ begin perform cron.unschedule('claim_due_agent_jobs'); exception when others then null; end $$;
do $$ begin perform cron.unschedule('cleanup_stale_agent_jobs'); exception when others then null; end $$;
do $$ begin perform cron.unschedule('enqueue_calendar_scans'); exception when others then null; end $$;
do $$ begin perform cron.unschedule('enqueue_catalog_scans'); exception when others then null; end $$;
do $$ begin perform cron.unschedule('enqueue_performance_syncs'); exception when others then null; end $$;

select cron.schedule('claim_due_agent_jobs', '* * * * *',
  $cron$ select public.claim_due_agent_jobs_fn(); $cron$);
select cron.schedule('cleanup_stale_agent_jobs', '*/5 * * * *',
  $cron$ select public.cleanup_stale_agent_jobs_fn(); $cron$);
-- Daily proactive scans (06:00 UTC) + hourly performance sync.
select cron.schedule('enqueue_calendar_scans', '0 6 * * *',
  $cron$ select public.enqueue_agent_scans_fn('calendar_scan'); $cron$);
select cron.schedule('enqueue_catalog_scans', '15 6 * * *',
  $cron$ select public.enqueue_agent_scans_fn('catalog_scan'); $cron$);
select cron.schedule('enqueue_performance_syncs', '5 * * * *',
  $cron$ select public.enqueue_agent_scans_fn('performance_sync'); $cron$);
