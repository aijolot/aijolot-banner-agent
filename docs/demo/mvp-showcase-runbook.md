# MVP showcase runbook

This runbook is the repeatable Phase 8 showcase path for Aijolot Banner Agent. It is safe by default: deterministic/local commands do not read secrets, do not call Gemini/Shopify/Supabase cloud, and do not mutate a live Shopify store.

## What to say up front

- The static frontend is a React/Babel prototype served from `frontend/`; no Next.js build is required for this showcase.
- `/api/v1` calls use demo auth context with seeded ids.
- Deterministic mode uses local/static skills, seeded resources, static KG retrieval, and dry-run/fail-closed publishing guardrails.
- Only claim Supabase, Gemini, vector KG, or live Shopify behavior if you deliberately configured and verified those providers outside the default smoke path.

Demo ids:

```text
team  = 00000000-0000-0000-0000-000000000001
user  = 00000000-0000-0000-0000-000000000601
store = 00000000-0000-0000-0000-000000000101
```

## Provider truth table

| Area | Default showcase mode | Optional provider-backed mode | What to claim in demo |
| --- | --- | --- | --- |
| Agent skills | Deterministic local skill pipeline and TestClient smoke fallback. No external calls. | Provider-backed ADK/Gemini orchestration only if credentials are intentionally configured for a live backend run. | Default: deterministic agent skills generated structured brief, KG event, and A/B/C artifacts. |
| Image/art provider | Fake/deterministic image/HTML preview artifacts or local fallback labels. | Gemini/image provider if configured by the operator before starting backend. | Default: image/art is deterministic or visibly labeled fallback, not live Gemini. |
| Knowledge graph | Static KG/best-practices retrieval from seeded corpus/events. | Vector/pgvector KG if Supabase is running with migrations/seed and retrieval is configured. | Default: static KG recommendations; vector KG only if verified in events/storage. |
| Persistence | In-process/local fallback for `scripts/smoke-demo-flow.py`; local Supabase optional for browser persistence and revisions. | Local Supabase started/reset with migrations and seed. | If Supabase is not running, say persistence-dependent preview/revisions/approval can fail closed. |
| Shopify resources | Seeded Shopify resource cache examples. | Live Shopify resource sync only with explicit safe credentials and manual verification. | Default: seeded resources, not live sync. |
| Publishing | Dry-run/fail-closed Shopify publisher. Backend must reject publish before approved/scheduled state. | Live Shopify mutation only if dry-run is disabled on a safe test store and rollback is verified manually. | Default: publish dry-run or fail-closed; no live mutation. |
| Performance | Manual/mock/seed/agent non-live metrics with labels. | Live analytics ingestion is outside MVP smoke unless separately implemented/configured. | Default: show `Resultados no-live` / `No-live visible`, not live Shopify analytics. |

## One-time setup

From the repository root:

```bash
cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cd ..
```

Do not copy, print, or commit secrets for the default deterministic demo.

## Fast deterministic confidence checks

Run these before the live showcase:

```bash
cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
python3 scripts/reset-demo-data.py --local-only
python3 scripts/smoke-demo-flow.py
node scripts/smoke-frontend-ui.mjs
```

Expected:

- reset exits 0,
- smoke demo prints that auth, seeded resources, intake, patch, static KG, and deterministic A/B/C generation passed,
- frontend UI smoke prints `frontend UI/static smoke passed`.

Optional API/real server smoke after starting backend:

```bash
cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
node scripts/smoke-frontend-backend-connection.mjs
```

Expected: backend health, brands, intake, placement, catalog/art direction, generation events/KG, preview/audit/revisions consistency, approval/schedule/publish fail-closed behavior, and non-live performance label checks pass.

## Start services for browser showcase

Terminal 1: optional local Supabase. Use this only if Docker/Supabase CLI are available and you want persistence-backed browser state.

```bash
cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
supabase start
python3 scripts/reset-demo-data.py --supabase
```

If this fails or is skipped, continue in deterministic/fallback mode and do not claim Supabase persistence.

Terminal 2: backend.

```bash
cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent/backend
. .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Check:

```bash
curl http://localhost:8000/health
```

Expected response contains `"status":"ok"`.

Terminal 3: static frontend.

```bash
cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
python3 -m http.server 5500 --directory frontend
```

Open:

```text
http://localhost:5500
http://localhost:8000/docs
```

## Browser demo script

1. Open `http://localhost:5500`.
2. On the campaign list, point out labels:
   - backend-loaded campaigns show `/api/v1`/backend labels,
   - fallback cards show `Demo/fallback` / `prototipo local`,
   - metrics show `Demo/fallback no live` when not backend-backed.
3. Click `Nueva campaña`.
4. Placement:
   - choose `Home · Hero principal` or equivalent seeded hero placement,
   - click `Continuar al brief`,
   - expected: either `Ubicación validada por el backend` or an amber backend validation/fallback notice.
5. Brief/intake:
   - paste this brief:

```text
Banner de Black Friday, 50% off perfumes Hugo Boss, para clientes VIP, CTA Comprar ahora, urgencia alta, en home hero.
```

   - submit the chat,
   - expected: structured chips populate; if backend is unavailable, the UI says extractor local/fallback instead of implying live AI.
6. Edit a chip (for example CTA `Comprar ahora`) and save/continue.
   - expected: green backend save notice or amber fallback/save-failed notice.
7. Art direction:
   - choose usage/background/model/fold defaults,
   - assemble/continue,
   - expected: catalog/art direction backend notice or labeled fallback/local preset notice.
8. Generate:
   - start generation,
   - expected: generation run/events show progress; failure is amber/fail-closed and should not be called success.
   - if configured with persistence, preview/revisions/audit should load; otherwise the canvas must label fallback/local state.
9. Canvas/review:
   - show backend creative iframe if available (`Backend-backed creative`), otherwise `Fallback local/prototipo`,
   - show audit label if present,
   - switch variants/segments; backend variant selection succeeds only with persisted revisions,
   - add/resolve a comment and approve; if approval service is unavailable, show `Aprobaciones locales/prototipo` and state it does not unlock backend schedule/publish.
10. Schedule:
    - try scheduling before a real backend-approved revision.
    - expected default: `Programación bloqueada`/fail-closed guardrail. With local Supabase and a real approved thread, schedule can be accepted and campaign status becomes scheduled.
11. Publish dry-run:
    - try publish before scheduled state.
    - expected default: `Publicación fail-closed`.
    - if scheduled and backend dry-run publisher is configured, expected label: `Simulación de publicación / dry-run · sin mutación live Shopify` or `Dry-run`.
12. Performance:
    - go to Performance,
    - click `Registrar snapshot`,
    - show labels `Resultados no-live`, `No-live visible`, and `manual/mock/seed/agent · no-live`,
    - state clearly that these are manual/mock/seed/agent metrics, not live Shopify analytics.

## API-only sequence for demo narration

If the browser is unstable, run the deterministic smoke and narrate the same flow from verified API output:

```bash
cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
python3 scripts/reset-demo-data.py --local-only
python3 scripts/smoke-demo-flow.py
```

Then, with backend running:

```bash
node scripts/smoke-frontend-backend-connection.mjs
```

This covers create/intake, placement, catalog/art direction, generation/events/KG, preview/audit/revision consistency where persistence exists, approval/schedule/publish dry-run/fail-closed behavior, and non-live performance labeling.

## Optional real-provider checklist

Only use this section with explicit safe credentials already configured by the operator. Do not print `.env` values.

- Supabase: `supabase start` then `python3 scripts/reset-demo-data.py --supabase`; verify seeded team/store/resources/revisions in local Studio or via API.
- Gemini/image provider: confirm backend config before starting; run a single generation and verify provider provenance in generation events/artifacts.
- Vector KG: verify KG migrations/seed and event keys/output indicate vector/pgvector retrieval, not only static retrieval.
- Shopify: keep dry-run enabled for MVP. If live mutation is intentionally tested, use a safe test store/theme, publish once, verify the banner, unpublish, and verify rollback.

## Exit criteria

A showcase run is acceptable when:

- deterministic smoke passes,
- frontend source smoke passes,
- browser labels never present fallback/prototype data as live backend/provider data,
- generation either succeeds or fails visibly,
- approval/schedule/publish cannot silently advance without backend prerequisites,
- performance is visibly non-live unless live analytics were separately configured and verified.
