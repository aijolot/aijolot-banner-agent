# Aijolot Banner Agent

Hackathon MVP for an agentic banner creation and publishing workflow using Google's ADK + Gemini.

License: MIT.

Goal: help marketing teams create, review, schedule, position, and publish store banners. MVP scope targets Shopify stores.

## Repository layout

```text
backend/      Python/FastAPI backend, ADK/Gemini agent graph, Shopify/Supabase services.
frontend/     Current static React UX prototype from frontend/design-implementation; future Next.js + Tailwind target.
obsidian/     Git-synced Obsidian vault for project notes and DB design.
brands/       Versioned brand context Markdown/YAML files used by the agent.
supabase/     Local Supabase config, migrations, seed data, storage buckets.
docs/         Architecture notes, extracted source docs, alignment notes, and implementation plans.
demo/         Demo scenarios, scripts, and presentation support.
scripts/      Developer automation scripts.
```

Current status: frontend prototype and database schema are in place; backend implementation comes next.

## Local Supabase setup

This project uses Supabase locally so every teammate and AI agent can run the same database, auth, storage buckets, seed records, and RLS policies.

### Prerequisites

Install:

- Docker Desktop
- Supabase CLI

Recommended versions used when this project was initialized:

```bash
supabase --version
# 2.98.2 or newer

docker --version
# Docker 29.x or compatible
```

On macOS with Homebrew:

```bash
brew install supabase/tap/supabase
brew install --cask docker
```

Start Docker Desktop before running Supabase commands.

### Files that define the local database

All team members must treat these files as the source of truth:

```text
supabase/config.toml
supabase/migrations/20260528190000_initial_schema.sql
supabase/seed.sql
.env.example
```

Migrations live only in:

```text
supabase/migrations/
```

Seed data lives in:

```text
supabase/seed.sql
```

Do not edit the local database manually and then rely on it. If the schema changes, create or edit a migration and reset locally so everyone gets the same state.

### First-time setup

From the repo root:

```bash
cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent

# Make sure Docker is running.
docker info

# Start Supabase local services for this project.
# We intentionally use project-specific 553xx ports in supabase/config.toml
# to avoid collisions with other local Supabase projects.
supabase start
```

The CLI prints local URLs and keys. Copy the printed values into a local env file:

```bash
cp .env.example .env.local
```

Then update at least these values in `.env.local` from the `supabase start` output:

```bash
SUPABASE_URL=http://127.0.0.1:55321
SUPABASE_ANON_KEY=<local anon key from supabase start>
SUPABASE_SERVICE_ROLE_KEY=<local service_role key from supabase start>
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:55321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<same local anon key>
```

Useful local URLs:

```text
API:    http://127.0.0.1:55321
Studio: http://127.0.0.1:55323
DB:     postgresql://postgres:***@127.0.0.1:55322/postgres
Emails: http://127.0.0.1:55324
```

Edge Functions and analytics are disabled in `supabase/config.toml` for the MVP local database workflow, so teammates do not need to pull or run those containers yet. If a later task needs Edge Functions or analytics, enable the relevant section in `supabase/config.toml`.

Note: the actual local DB password is printed by `supabase start`. Use the printed value if it differs from `postgres`.

### Apply migrations and seed data

For a clean aligned database:

```bash
supabase db reset
```

This command:

1. Drops the local database.
2. Re-applies every migration in `supabase/migrations/` in filename order.
3. Runs `supabase/seed.sql` because `supabase/config.toml` has seed enabled.

Use this whenever a teammate adds or changes migrations.

### Verify local DB state

Open Studio:

```bash
open http://127.0.0.1:55323
```

Or verify from the terminal:

```bash
psql postgresql://postgres:postgres@127.0.0.1:55322/postgres \
  -c "select key, label from public.placement_types order by key;"
```

If `psql` is not installed, use Supabase Studio table editor instead.

Expected seeded records:

- placement types for announcement bar, hero, promo card, collection header, PDP strip, PDP cross-sell, footer CTA, search-results banner
- demo team: `Aijolot Demo Team`
- demo store: `maison-store.myshopify.com`
- demo brand context: `Maison / Hugo Boss Demo`
- Shopify resource cache examples for collections, products, and pages
- optimization memory examples

### Stop local Supabase

```bash
supabase stop
```

Stop and delete local data volumes if you need a completely clean Docker state:

```bash
supabase stop --no-backup
```

Then recreate with:

```bash
supabase start
supabase db reset
```

## Database structure overview

The schema is based on the Obsidian note:

```text
obsidian/Notes/Database Structure Proposal.md
```

The actual executable schema is:

```text
supabase/migrations/20260528190000_initial_schema.sql
```

Main table groups:

### Identity and teams

- `profiles`
- `teams`
- `team_members`

Supabase Auth owns credentials. App tables reference `auth.users(id)` through `profiles.id`.

### Shopify/store integration

- `stores`
- `shopify_resource_cache`

The MVP uses token/custom app access. Products, collections, and pages are cached for list/select placement UX.

### Brand context

- `brand_contexts`
- `brand_assets`

Backend supports full CRUD. Brand context includes palette, typography, voice, allowed/forbidden rules, image directives, logos, and import metadata.

### Placement and campaign creation

- `placement_types`
- `campaigns`
- `campaign_placements`
- `campaign_messages`
- `campaign_catalog_snapshots`
- `campaign_catalog_items`

The frontend supports existing Shopify placements and new injected sections. New-section layouts are stored as JSON.

### Art direction and generation

- `art_directions`
- `generation_runs`
- `generation_events`

The backend ADK graph can be mapped to the frontend's 5 visible generation steps.

### Creative output

- `campaign_revisions`
- `banner_layout_variants`
- `banner_variants`
- `banner_assets`

Refinements should create new revisions or generation runs rather than silently overwriting final assets.

### Review and approval

- `approval_threads`
- `approval_reviewers`
- `comments`
- `refinement_requests`

MVP approval policy is `all_members`: all assigned reviewers must approve before scheduling or publishing.

Comments support canvas pins through `pin_x` and `pin_y` percentage coordinates.

### Scheduling and publishing

- `schedules`
- `publish_jobs`
- `scheduled_banners`

MVP scheduling is theme-enforced using campaign config dates. `scheduled_banners` is included for future Supabase `pg_cron` due-publish automation compatibility.

### Audit, usage, and performance

- `audit_reports`
- `audit_events`
- `generation_usage_events`
- `performance_snapshots`
- `optimization_insights`
- `optimization_proposals`

`generation_usage_events` supports the soft guard: warn after 20 image generations per authenticated user per 15 minutes. It is not a hard cap.

## Storage buckets

The initial migration creates these local Supabase Storage buckets:

```text
brand-assets
campaign-assets
rendered-previews
```

Recommended object path patterns:

```text
brand-assets/{team_id}/{brand_context_id}/{asset_id}-{filename}
campaign-assets/{team_id}/{campaign_id}/{revision_id}/{variant_key}/{size_key}.{format}
rendered-previews/{team_id}/{campaign_id}/{revision_id}/preview.html
```

For MVP, backend service-role uploads should own most storage writes. Direct authenticated storage policies are permissive locally to avoid slowing down the hackathon.

## Migration workflow for the team and agents

When changing the schema:

1. Create a new migration file:

```bash
supabase migration new describe_change_here
```

2. Edit the generated SQL file under `supabase/migrations/`.

3. Reset local DB to verify from scratch:

```bash
supabase db reset
```

4. If seed data must change, edit:

```text
supabase/seed.sql
```

5. Update these docs when relevant:

```text
README.md
obsidian/Notes/Database Structure Proposal.md
docs/plans/2026-05-28-banner-creator-mvp.md
```

6. Commit migrations and docs together.

Rules:

- Do not commit `supabase/.temp/`.
- Do not commit `.env.local` or real secrets.
- Do not rely on manual Studio changes unless they are converted into a migration/seed.
- Prefer additive migrations after this initial schema.
- If a migration fails on `supabase db reset`, fix it before pushing.

## Local env file

Use:

```text
.env.example
```

as the template for local development:

```bash
cp .env.example .env.local
```

`.env.local` is intentionally ignored and should contain local keys and secrets only.
