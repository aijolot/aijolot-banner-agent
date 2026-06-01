# Static frontend ↔ FastAPI backend contract

Task 18 integrates the current static React 18 UMD/Babel prototype in `frontend/` with local FastAPI APIs without migrating to Next.js.

## Runtime API base

The prototype reads:

```js
window.AIJOLOT_API_BASE || "http://localhost:8000"
```

`frontend/lib.jsx` normalizes this to `window.API_BASE` and exposes a small reusable client:

- `AijolotApi.get/post/put/patch(path, body)`
- `AijolotApi.v1(path)` for canonical `/api/v1` paths

Example override before loading the app:

```html
<script>window.AIJOLOT_API_BASE = "http://localhost:8000";</script>
```

## Adapters exposed on `window`

Defined in `frontend/lib.jsx`:

- `CampaignApi`
  - `GET /api/v1/campaigns`
  - `PATCH /api/v1/campaigns/{campaign_id}`
- `PlacementApi`
  - `POST /api/v1/campaigns/{campaign_id}/placement`
  - default seeded store id: `00000000-0000-0000-0000-000000000101`
  - prototype placement mapping uses seeded backend placement keys (`announcement_bar`, `hero_main`, `promo_card`, `collection_header`, `pdp_strip`, `pdp_cross_sell`, `footer_cta`, `search_results_banner`) and seeded target handles (`fragancias`, `boss-bottled-edp-100ml`) for collection/product targets
- `ArtDirectionApi`
  - `PUT /api/v1/campaigns/{campaign_id}/art-direction`
- `GenerationApi`
  - `POST /api/v1/campaigns/{campaign_id}/generation-runs`
  - `GET /api/v1/campaigns/{campaign_id}/generation-runs/latest`
- `ReviewApi`
  - static approval adapter is visibly local until the prototype has revision/reviewer UUID context
  - `POST /api/v1/campaigns/{campaign_id}/schedule`
  - `POST /api/v1/campaigns/{campaign_id}/publish`
- `BrandAPI` in `frontend/data.jsx`
  - `GET /api/v1/brands`
  - `GET /api/v1/brands/{brand_id}`
  - `PUT /api/v1/brands/{brand_id}`

Campaign intake streaming uses:

- `POST /api/v1/campaigns/intake`
- Server-sent event lines: `data: { type: "token", text }` and final `data: { type: "done", campaign, complete, missing }`

## Prototype flow wiring

- Brand Context loads/saves via `BrandAPI`.
- Brief chat streams from `/api/v1/campaigns/intake` and exposes the backend campaign object.
- Edited brief chips persist with `PATCH /api/v1/campaigns/{campaign_id}`.
- Placement is selected before intake, so the app saves placement after the first backend campaign is available.
- Art direction is saved before entering generation.
- Generation starts a backend generation run when the campaign id is backend-compatible.
- Canvas approval controls remain local/labeled because the static prototype does not yet own authenticated reviewer UUIDs or generated revision UUID selection.
- Schedule/publish controls call backend schedule/publish where possible. Backend rejections are visibly reported and do not advance local scheduled/published state; explicit fallback responses may advance the prototype state with an amber notice.

## Fallback behavior

Fallbacks are preserved only when visible/labeled in the UI:

- Backend unreachable for brands: Brand Context shows `Modo offline · mock`.
- Local in-memory backend campaign ids (`cmp_0001`) are not UUIDs. Backend placement/art/generation/schedule/publish v1 routes are UUID-typed, so adapters return a visible amber notice explaining that prototype/local state is being used unless Supabase-backed UUID campaigns are configured.
- HTTP validation/status errors from backend are not silently swallowed for brand CRUD; they are surfaced.
- Schedule/publish backend errors show amber notices and keep the local schedule/publish state unchanged. Only backend success or explicit labeled fallback advances the prototype demo state.

## Manual demo steps

Terminal 1:

```bash
cd backend
. .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```bash
python3 -m http.server 5500 --directory frontend
```

Browser:

1. Open `http://localhost:5500`.
2. Brand Context:
   - navigate to Brand,
   - verify `Bridge conectado`,
   - edit a safe field and save.
3. Studio flow:
   - create/resume a campaign,
   - choose placement,
   - enter a campaign brief in chat,
   - verify structured chips populate and edits persist,
   - advance to Art,
   - select background/model/fold and assemble,
   - verify art save notice,
   - verify generation progress displays,
   - review canvas, approve all reviewers,
   - schedule and/or publish,
   - verify controls stay locked until all reviewers approve and backend/fallback status is visible.

## Deferred gaps

- Full Next.js/Tailwind migration remains frontend-owned.
- Static adapters should be removed/replaced during migration.
- Authenticated reviewer identity, real approval-thread creation, generated revision selection, and live schedule/publish status polling need the future frontend app context.
- With the no-Supabase local backend, campaign ids are prototype ids, so UUID-only backend stage APIs cannot persist placement/art/generation/schedule/publish; the UI labels this fallback explicitly.
