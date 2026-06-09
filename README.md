# Aijolot Banner Agent

Hackathon MVP for an agentic banner creation, review, scheduling, and Shopify publishing workflow using FastAPI, Supabase, Google ADK/Gemini provider boundaries, and the current static React prototype.

License: MIT.

Goal: help marketing teams create, review, edit, schedule, position, and publish store banners. MVP scope targets Shopify stores.

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full system design (diagrams, the 9-node ADK generation pipeline, provider boundaries, and skill contracts).

## Current status

The backend MVP is implemented on the feature branch. The documented demo path is deterministic/offline by default and uses seeded fixtures; real Gemini (text + image), Supabase, Shopify, and Lighthouse are opt-in/manual via provider flags and credentials.

The frontend is a static React 18 UMD/Babel prototype (not a Next.js app), but its API layer (`frontend/lib.jsx`) now sends demo auth headers on every `/api/v1` call and drives the real agentic backend: SSE-streamed brief intake, per-variant (product-grounded) art concepts, AI backgrounds, Nano Banana Pro art generation, generation runs, agentic refine, scoped banner-edit, approval, schedule, and publish/unpublish. Generation and editing run as **async background jobs** the frontend polls, and a shared `frontend/banner_template.js` renders the live banner identically in the browser and in the backend's headless visual self-review. Each AI node degrades to a deterministic fallback when provider env/credentials are absent. Backend tests: 357 passed, 3 skipped (clean env).

Important constraints:

- Canonical backend routes live under `/api/v1`; callers should send demo auth/team context. Most implemented v1 routes fail closed with 401 when it is missing, while approval/comment/refinement routes can currently return service-unavailable before auth when their service is not configured.
- Root routes such as `/brands`, `/campaigns/intake`, and `/campaigns/{id}` remain unauthenticated for prototype compatibility.
- Performance data shown in the MVP is manual/mock/seed/agent unless explicitly labeled `live_analytics` by a deliberately wired live ingestion path.
- Shopify publishing is fail-closed without real credentials and safe target store/theme configuration.
- The smoke path does not call Gemini, Shopify, Supabase, Lighthouse, or external networks.

## Repository layout

```text
backend/      Python/FastAPI backend, ADK/Gemini provider boundaries, Supabase/Shopify services, tests.
frontend/     Current static React 18 UMD/Babel prototype and static API adapters; no build step.
brands/       Versioned brand context Markdown/YAML import/fallback files.
supabase/     Local Supabase config, migrations, seed data, storage buckets.
docs/         Architecture docs, API/frontend contracts, demo docs, and implementation plans.
demo/         Demo scenarios and presentation support.
scripts/      Reset/smoke/developer automation scripts.
obsidian/     Git-synced Obsidian vault for project notes and DB design.
```

See also `docs/architecture/project-structure.md`.

## Backend local setup

Requires Python 3.11+.

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest -v
uvicorn app.main:app --reload --port 8000
```

Open API docs at:

```text
http://localhost:8000/docs
```

Health check:

```bash
curl http://localhost:8000/health
```

## Demo auth for `/api/v1`

Canonical `/api/v1` routes require request context. Use demo identity headers or a demo bearer token; never use real provider secrets here.

```text
X-Aijolot-User-Id: 00000000-0000-0000-0000-000000000601
X-Aijolot-Team-Id: 00000000-0000-0000-0000-000000000001
X-Aijolot-Store-Id: 00000000-0000-0000-0000-000000000101
Authorization demo bearer format: `Bearer demo:<user_id>:<team_id>[:<store_id>]`
```

Root compatibility routes are still unauthenticated for prototype/local compatibility, but new integrations should use `/api/v1`.

## Static frontend

The frontend is a CDN React + Babel-standalone prototype with no build step:

```bash
python3 -m http.server 5500 --directory frontend
# open http://localhost:5500
```

The static adapters use backend base:

```js
window.AIJOLOT_API_BASE || "http://localhost:8000"
```

New API calls target `/api/v1`. The `lib.jsx` adapters now bake in demo auth headers (`AIJOLOT_DEMO_AUTH_HEADERS`) and a demo identity/team/store, so canonical routes resolve without manual header wiring. The studio flows through six stages — placement → brief → art → generate → canvas → performance — each triggering its agentic backend action (intake is SSE-streamed; art/concepts/backgrounds/generate-art/refine/banner-edit hit the live LLM-backed endpoints when provider env is present, otherwise deterministic fallbacks). Adapters still show visible fallback notices for prototype-only states. See `docs/architecture/frontend-backend-contract.md` for exact adapter behavior.

## Deterministic demo smoke path

From repo root, after backend dependencies are installed:

```bash
python3 scripts/reset-demo-data.py --local-only
python3 scripts/smoke-demo-flow.py  # first run
python3 scripts/smoke-demo-flow.py  # second run verifies repeatability
```

Expected: both smoke runs exit 0 and print that auth, seeded resources, intake, patch, static KG, and deterministic A/B/C generation passed.

The smoke script runs FastAPI in-process via TestClient, forces deterministic fallback mode, and does not call external providers. The chosen scenario and demo limitations are documented in `docs/demo-script.md`.

Optional real local Supabase reset when Docker and Supabase CLI are available:

```bash
python3 scripts/reset-demo-data.py --supabase
# or directly:
supabase db reset
```

If Supabase reset is skipped or fails, do not claim it passed; use the local-only smoke path.

## Local Supabase setup

This project uses local Supabase for shared database/auth/storage schema and seeds.

Prerequisites:

- Docker Desktop
- Supabase CLI

Start Docker Desktop, then from repo root:

```bash
supabase start
cp .env.example .env.local
```

Copy local keys printed by `supabase start` into `.env.local`. Do not commit `.env.local` or real secrets.

Useful local URLs:

```text
API:    http://127.0.0.1:55321
Studio: http://127.0.0.1:55323
DB:     postgresql://postgres:***@127.0.0.1:55322/postgres
Emails: http://127.0.0.1:55324
```

Apply migrations and seed data:

```bash
supabase db reset
```

Executable schema/seed sources:

```text
supabase/config.toml
supabase/migrations/20260528190000_initial_schema.sql
supabase/migrations/20260529000000_kg_pgvector.sql
supabase/migrations/20260601010500_task20_performance_non_live_sources.sql
supabase/seed.sql
supabase/seeds/kg_documents.sql
.env.example
```

Expected seeded records include placement types, demo team/store, demo brand context, Shopify resource cache examples, KG/static recommendations, and optimization/performance examples.

### Knowledge graph (`kg_documents`) auto-seed

The KG corpus is populated automatically on every fresh environment: `supabase
db reset` applies migrations and then loads `supabase/seeds/kg_documents.sql`
(wired via `config.toml [db.seed].sql_paths`). That file ships the full corpus
**with embeddings baked in**, so a new database needs **no `GOOGLE_API_KEY` and
no Gemini calls** to come up fully seeded. The seed is authoritative and
idempotent (`delete` + `insert`), safe to re-apply.

Source of truth is still the Markdown under `docs/kg_seed/**/*.md`. Regenerate
the SQL seed whenever the corpus changes:

```bash
python scripts/kg_seed.py        # docs/kg_seed/**/*.md -> embeddings -> kg_documents (needs GOOGLE_API_KEY)
python scripts/kg_export_sql.py  # kg_documents -> supabase/seeds/kg_documents.sql (no Gemini calls)
```

`supabase/seeds/kg_documents.sql` is a generated artifact — edit the Markdown,
not the SQL, then re-run the two commands above and commit the result.

Stop local Supabase:

```bash
supabase stop
```

## Backend capabilities and known MVP labels

Implemented capability groups:

- Brand context CRUD/import with Supabase-first storage and Markdown fallback.
- Campaign create/list/intake/get/patch with Supabase-first persistence and team-isolated no-Supabase fallback.
- SSE-streamed conversational brief intake producing the Campaign Brief (v0.3.0): goal/audience/CTA/tone/urgency plus personalization variants and promo, Gemini-backed with deterministic fallback.
- Per-variant art direction: art concepts, art/model prompts, sanitized AI background options (incl. SVG-pattern backgrounds), agent-chosen typography, and art generation.
- Variant-aware, product-grounded generation: one `banner_variant` per personalization variant, each grounded on its own featured Shopify product, with variant-specific copy and a shared palette.
- Nano Banana Pro image generation with chroma-key background removal for transparent, composited product heroes.
- Percentage-first, breakpoint-aware composition via a shared `banner_template.js` (browser + backend headless parity).
- Autonomous visual self-review loop: headless screenshots at 3 breakpoints critiqued by a Gemini vision model, with deterministic contrast/layout/overflow corrections.
- Async generation/edit as background jobs with run + event polling.
- Live on-demand Shopify product resolution (search + persist) and banner-image rehosting to Shopify Files for real publish.
- Multivariant publish: Liquid served by `customer.tags` (one audience-specific variant per tag).
- Store/resource cache APIs using seeded/cached Shopify resources.
- Placement validation and campaign placement persistence.
- Catalog snapshot persistence from cached resources.
- Art direction persistence.
- Generation run/event tracking with five frontend-visible progress steps.
- Deterministic/Gemini provider boundaries for text/image generation.
- Asset optimization/upload plumbing with WebP/JPG and optional AVIF; AVIF skipped must be labeled.
- Preview HTML, controlled Shopify Liquid payloads, and audit reports; Lighthouse is mock/manual unless run separately.
- Approval threads, comments, all-reviewer approval, refinement requests, agentic regeneration, scoped non-destructive banner-edit (copy/background/image/layout), and revision history.
- Scheduling plus Shopify publish/unpublish through controlled theme assets/metafield config when real credentials are configured.
- Performance/evolutionary memory APIs with explicit non-live provenance labels.

MVP/documented constraints:

- PDF/Figma/brandbook import is partial/mock only outside Markdown import.
- Live Shopify resource sync and live analytics ingestion are non-MVP/manual.
- Custom model/persona support is metadata-only/non-MVP.
- Deterministic A/B/C variants are demo-labeled in smoke; not live model exploration.
- Static KG retrieval is sufficient for smoke; vector/embedding retrieval is not required for the chosen path.

## Migration workflow

When changing schema:

1. Create a migration under `supabase/migrations/`.
2. Edit SQL and seed data as needed.
3. Run `supabase db reset`.
4. Run backend tests.
5. Update docs when behavior changes.

When changing the KG corpus (`docs/kg_seed/**/*.md`): re-run `python
scripts/kg_seed.py` then `python scripts/kg_export_sql.py` to regenerate
`supabase/seeds/kg_documents.sql`, and commit the regenerated seed so fresh
environments pick up the change via `supabase db reset`.

Rules:

- Do not commit `supabase/.temp/`.
- Do not commit `.env.local` or real secrets.
- Do not rely on manual Studio changes unless converted into migration/seed.
- Prefer additive migrations.
- If `supabase db reset` fails, fix it before handoff.
