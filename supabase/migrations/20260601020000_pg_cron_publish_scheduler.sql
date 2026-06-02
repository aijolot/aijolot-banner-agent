-- Aijolot Banner Agent — pg_cron publish scheduler
-- Closes GH-7 (publish_due_banners_fn + cron.schedule) and GH-4 (scheduled_banners tracking columns).
-- Design: backend-poll, NOT pg_net. pg_cron marks rows as 'processing' (FOR UPDATE SKIP LOCKED),
-- then the FastAPI scheduler endpoint at /api/v1/scheduler/process picks them up and marks 'published'.

-- ----------------------------------------------------------------------------
-- 1. Ensure pg_cron is available (idempotent — already in initial_schema.sql)
-- ----------------------------------------------------------------------------

create extension if not exists pg_cron with schema extensions;

-- ----------------------------------------------------------------------------
-- 2. Tracking columns on scheduled_banners
-- ----------------------------------------------------------------------------

alter table public.scheduled_banners
  add column if not exists processing_started_at timestamptz,
  add column if not exists attempt_count         integer not null default 0,
  add column if not exists error_detail          text;

create index if not exists scheduled_banners_processing_idx
  on public.scheduled_banners (status, processing_started_at)
  where status = 'processing';

-- ----------------------------------------------------------------------------
-- 3. publish_due_banners_fn — claim pending+due rows under SKIP LOCKED
-- ----------------------------------------------------------------------------

create or replace function public.publish_due_banners_fn()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.scheduled_banners
  set status = 'processing',
      processing_started_at = now(),
      attempt_count = attempt_count + 1
  where id in (
    select id from public.scheduled_banners
    where status = 'pending' and target_publish_at <= now()
    order by target_publish_at
    limit 20
    for update skip locked
  );
end;
$$;

-- ----------------------------------------------------------------------------
-- 4. cleanup_stale_processing_banners_fn — reset rows stuck > 10 min
-- ----------------------------------------------------------------------------

create or replace function public.cleanup_stale_processing_banners_fn()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.scheduled_banners
  set status = 'pending',
      processing_started_at = null,
      error_detail = 'reset after 10m timeout (attempt ' || attempt_count || ')'
  where status = 'processing'
    and processing_started_at < now() - interval '10 minutes';
end;
$$;

-- ----------------------------------------------------------------------------
-- 5. Register cron jobs (idempotent: unschedule first, ignore missing)
-- ----------------------------------------------------------------------------

do $$ begin perform cron.unschedule('publish_due_banners'); exception when others then null; end $$;
do $$ begin perform cron.unschedule('cleanup_stale_processing_banners'); exception when others then null; end $$;

select cron.schedule('publish_due_banners', '* * * * *',
  $cron$ select public.publish_due_banners_fn(); $cron$);

select cron.schedule('cleanup_stale_processing_banners', '*/5 * * * *',
  $cron$ select public.cleanup_stale_processing_banners_fn(); $cron$);
