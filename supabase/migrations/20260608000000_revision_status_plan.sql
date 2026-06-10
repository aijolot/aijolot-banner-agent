-- Iterative campaign plan gate: a revision can now sit in a "plan" state — the
-- cheap, pre-build resume point produced by the plan phase (concept + wireframe,
-- no image/render/audit). Promotion to "selected" happens on approve+build.
-- Additive: widens the existing CHECK constraint, no data migration needed.

alter table public.campaign_revisions
  drop constraint if exists campaign_revisions_status_check;

alter table public.campaign_revisions
  add constraint campaign_revisions_status_check
  check (status in ('plan', 'draft', 'selected', 'superseded', 'approved', 'published'));
