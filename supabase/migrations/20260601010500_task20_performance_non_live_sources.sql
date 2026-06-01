-- Task 20: allow MVP manual/mock/seed/agent performance snapshot sources.
-- Existing live-oriented source labels stay valid for future imports, but the
-- Task 20 API only creates manual/mock/seed/agent rows and labels provenance.

alter table public.performance_snapshots
  drop constraint if exists performance_snapshots_source_check;

alter table public.performance_snapshots
  add constraint performance_snapshots_source_check
  check (source in ('manual', 'mock', 'seed', 'agent', 'shopify', 'analytics', 'lighthouse'));
