# Runbook — DB migrations (self-hosted Supabase)

## TL;DR

After merging any change under `supabase/migrations/`, forward-migrate the
demo's self-hosted Supabase DB:

```bash
scripts/migrate-supabase-vm.sh
```

Migrations are idempotent, so re-running is safe. Verify the output ends with
the `campaign_revisions_status_check` constraint including `'plan'`.

## Why a dedicated script (topology)

The demo runs the app on **Cloud Run** and Supabase **self-hosted on a GCE VM**
(`supabase-vm`, `us-central1-a`). The VM exposes publicly only:

- `:8000` — Kong (REST/GoTrue/Realtime); how the app talks to Supabase.
- `:5432` — **Supavisor pooler** (`supabase-pooler`); needs a tenant-id in the
  username (`postgres.<tenant>`), so a plain `psql` fails with
  `no tenant identifier provided`.

The **raw Postgres** (`supabase-db`) listens only on the VM's internal docker
network — unreachable from Cloud Run or a laptop. So DDL is applied **inside the
container** via `docker exec`, which `scripts/migrate-supabase-vm.sh` automates
(scp the migrations to the VM → apply the `>= 20260608` idempotent batch in
`supabase-db`).

## History / why this exists

The Cloud Run deploy ships new code but never migrated the persistent VM DB, so
the schema drifted ~8 migrations behind `main`. The plan step then failed with
`campaign_revisions_status_check (23514)` because `status='plan'` was added in
`20260608000000_revision_status_plan.sql` but never applied. Fixed by running
the batch on the VM; this runbook prevents recurrence.

## Other paths

- `scripts/apply-migrations.sh` — generic, tracking-based, idempotent applier
  (uses `supabase_migrations.schema_migrations`, auto-baselines an existing
  untracked DB). Works against **any reachable raw-Postgres** `SUPABASE_DB_URL`
  (local dev, or a future setup that exposes raw PG). The entrypoint can run it
  on boot but it is **opt-in** (`RUN_DB_MIGRATIONS=1`) and only works when
  `SUPABASE_DB_URL` is a reachable raw-Postgres endpoint — not the pooler.
- Local dev: `supabase db reset` (drops + re-applies all migrations + seeds).

## Follow-ups (security)

- `:8000` is open to `0.0.0.0/0`; with the service-role key in play this is a
  risk — restrict by firewall.
- The runtime secret `banner-agent-runtime-env` was seeded from a local `.env`
  (`SUPABASE_DB_URL` points at the pooler). Clean it up to avoid confusion.
