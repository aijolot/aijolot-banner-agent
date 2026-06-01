# Static frontend ↔ FastAPI backend contract

The current frontend in `frontend/` is a static React 18 UMD/Babel prototype. It has no Next.js/Tailwind build step in this branch. Task 18 connected this prototype to local FastAPI APIs through small static adapters while keeping visible fallbacks for prototype-only state.

## Runtime API base

The prototype reads:

```js
window.AIJOLOT_API_BASE || "http://localhost:8000"
```

`frontend/lib.jsx` normalizes this to `window.API_BASE` and exposes:

- `AijolotApi.get/post/put/patch(path, body)`
- `AijolotApi.v1(path)` for `/api/v1` paths

Example override before loading the app:

```html
<script>window.AIJOLOT_API_BASE = "http://localhost:8000";</script>
```

## Auth context

Canonical `/api/v1` callers should send demo auth/team context. Accepted backend forms are documented in `docs/architecture/api-contract.md`:

- `X-Aijolot-User-Id`
- `X-Aijolot-Team-Id`
- optional `X-Aijolot-Store-Id`
- or `Authorization` using bearer format `Bearer demo:<user_id>:<team_id>[:<store_id>]`

The deterministic smoke script supplies these headers itself. Browser demos should verify the static frontend version being served includes/sends demo context before claiming an authenticated end-to-end API flow. Do not put real Gemini/Supabase/Shopify secrets in browser headers.

Demo fixture ids:

```text
team  = 00000000-0000-0000-0000-000000000001
user  = 00000000-0000-0000-0000-000000000601
store = 00000000-0000-0000-0000-000000000101
```

## Adapters exposed on `window`

Defined primarily in `frontend/lib.jsx` and `frontend/data.jsx`:

- `CampaignApi`
  - `GET /api/v1/campaigns`
  - `PATCH /api/v1/campaigns/{campaign_id}`
- `PlacementApi`
  - `POST /api/v1/campaigns/{campaign_id}/placement`
  - default seeded store id: `00000000-0000-0000-0000-000000000101`
  - prototype placement mapping uses seeded backend placement keys: `announcement_bar`, `hero_main`, `promo_card`, `collection_header`, `pdp_strip`, `pdp_cross_sell`, `footer_cta`, `search_results_banner`
  - collection/product target handles in the seeded fixture include `fragancias` and `boss-bottled-edp-100ml`
- `ArtDirectionApi`
  - `PUT /api/v1/campaigns/{campaign_id}/art-direction`
- `GenerationApi`
  - `POST /api/v1/campaigns/{campaign_id}/generation-runs`
  - `GET /api/v1/campaigns/{campaign_id}/generation-runs/latest`
- `ReviewApi`
  - canvas approval remains local/labeled until authenticated reviewer UUID and revision context are available in the static prototype
  - `POST /api/v1/campaigns/{campaign_id}/schedule`
  - `POST /api/v1/campaigns/{campaign_id}/publish`
- `BrandAPI`
  - `GET /api/v1/brands`
  - `GET /api/v1/brands/{brand_id}`
  - `PUT /api/v1/brands/{brand_id}`

Campaign intake streaming uses:

- `POST /api/v1/campaigns/intake`
- SSE lines: `data: { "type": "token", "text": ... }` and final `data: { "type": "done", "campaign": ..., "complete": ..., "missing": ... }`

## Prototype flow wiring

- Brand Context loads/saves through `BrandAPI`.
- Brief chat streams from `/api/v1/campaigns/intake` and stores the returned backend campaign object.
- Edited brief chips persist with `PATCH /api/v1/campaigns/{campaign_id}` when a backend campaign id/context is usable.
- Placement is selected before intake; once a backend campaign exists the adapter saves placement.
- Art direction is saved before generation.
- Generation starts a backend generation run when the campaign id is a UUID and auth context is accepted.
- Canvas approval controls are local/labeled in the static prototype because real reviewer/revision selection is not fully owned by this frontend.
- Schedule/publish controls call backend endpoints where possible. Backend rejections are shown and do not silently advance local scheduled/published state.

## Fallback and label rules

Fallbacks are allowed only when visible/labeled:

- Backend unreachable for brands: Brand Context shows offline/mock state.
- Local non-UUID campaign ids are prototype-only. UUID-typed backend stage APIs cannot persist placement/art/generation/schedule/publish for those ids; adapters show amber fallback notices.
- HTTP validation/status errors from backend are surfaced rather than silently swallowed for brand CRUD.
- Schedule/publish backend errors show amber notices and keep local state unchanged unless an explicit labeled fallback is used.
- Performance metrics shown in the frontend are manual/mock/seed/agent unless explicitly marked live; do not present them as live Shopify analytics.

## Manual local browser demo

Terminal 1:

```bash
cd backend
. .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2, from repo root:

```bash
python3 -m http.server 5500 --directory frontend
```

Browser:

1. Open `http://localhost:5500`.
2. Open backend API docs at `http://localhost:8000/docs` and verify `/health` plus `/api/v1` routes are present.
3. Brand Context:
   - navigate to Brand,
   - verify connected/offline status is truthfully displayed,
   - edit a safe field and save only if auth/context is accepted.
4. Studio flow:
   - create/resume a campaign,
   - choose placement,
   - enter a campaign brief in chat,
   - verify structured chips populate and edits persist or fallback is labeled,
   - advance to Art,
   - select background/model/fold and assemble,
   - verify art save notice,
   - verify generation progress displays,
   - review canvas and approvals,
   - schedule/publish only after backend status allows it,
   - verify controls stay locked until approval and backend/fallback status is visible.

For deterministic non-browser verification, prefer:

```bash
python3 scripts/reset-demo-data.py --local-only
python3 scripts/smoke-demo-flow.py
```

## Deferred/non-MVP gaps

- Full Next.js/Tailwind migration remains frontend-owned.
- Static adapters should be replaced during that migration.
- Authenticated reviewer identity, real approval-thread UI creation, generated revision selection, and live schedule/publish polling need future frontend app context.
- PDF/Figma extraction, live Shopify sync, custom persona/model support, live analytics ingestion, full Lighthouse automation, and live model-generated A/B/C exploration are not part of the deterministic smoke path.
