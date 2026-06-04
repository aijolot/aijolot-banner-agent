# Runbook — Aijolot Banner Agent demo (end-to-end, real)

Status: **F0–F12 complete.** The demo runs end-to-end against a real Shopify
store and Supabase, with Gemini-backed generation and fail-safe deterministic
fallbacks. 315 backend tests pass (3 skipped) in a clean environment.

## 1. Services

```bash
# Supabase local (Docker) — Postgres on :55322, API on :55321
supabase start            # if not already running

# Backend (FastAPI :8000). venv is Python 3.11. Source .env for live providers.
cd backend && set -a && . ../.env; set +a
.venv/bin/uvicorn app.main:app --port 8000 --host 127.0.0.1
#  ⚠️ use --reload during dev; the server does NOT auto-reload otherwise.

# Frontend (static, no build). Babel-in-browser; default API base http://localhost:8000
python3 -m http.server 5500 --directory frontend
#  open http://localhost:5500/index.html
```

## 2. Environment flags (`.env`)

| Flag | Demo value | Effect |
|------|-----------|--------|
| `GOOGLE_API_KEY` | AI Studio key | enables Gemini (intake, KG embeddings, image, backgrounds, art/model prompts). Absent → deterministic fallbacks. |
| `AIJOLOT_INTAKE_PROVIDER` | `gemini` | F2 brief slot-filling via Gemini. |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | 768-dim KG embeddings (NOT `text-embedding-005`). |
| `KG_EMBEDDINGS_ENABLED` | `false` | `true` → vector KG retrieval; else DB-lexical + static floor. |
| `SHOPIFY_SHOP_DOMAIN` / `SHOPIFY_ADMIN_ACCESS_TOKEN` / `SHOPIFY_THEME_ID` | real demo store `aijolo-demo`, theme `188324807026` | live reads, placeholders, publish. |
| `SHOPIFY_PUBLISH_DRY_RUN` | `true` | **safe default** — publish simulates, never writes the metafield. Set `false` for a real publish (or use `?dry_run=false` per request). |
| `DAILY_COST_CAP_USD` | (set) | hard cap; Gemini calls fail closed to deterministic when reached. |

Demo auth headers (frontend sends them; full UUIDs):
`X-Aijolot-User-Id: …601`, `X-Aijolot-Team-Id: …001`, `X-Aijolot-Store-Id: …101`.

## 3. Tests (clean environment, like CI)

```bash
cd backend
env -i PATH="$PATH" HOME="$HOME" .venv/bin/python -m pytest -q      # 315 passed, 3 skipped
# Loading .env makes in-memory fallback tests see Supabase configured → run clean.
python ../scripts/smoke-demo-flow.py                                # end-to-end deterministic smoke
```

## 4. Full demo flow (curl; backend :8000)

```bash
H=(-H "x-aijolot-user-id: 00000000-0000-0000-0000-000000000601" \
   -H "x-aijolot-team-id: 00000000-0000-0000-0000-000000000001" \
   -H "x-aijolot-store-id: 00000000-0000-0000-0000-000000000101" \
   -H "Content-Type: application/json")
CID=<campaign-uuid>; SID=00000000-0000-0000-0000-000000000101
USER=00000000-0000-0000-0000-000000000601
```

1. **Intake (F2)** — one turn fills the brief, no re-prompt loop:
   `POST /api/v1/campaigns/intake {"message":"Promo de fin de semana para mujeres jóvenes, botón Comprar ya, en el hero"}` (SSE).
2. **Generate (F5/F6)** — real pipeline, persists revision + variants + audit + preview, KG-grounded layout:
   `POST /api/v1/campaigns/$CID/generation-runs` → `GET /generation-runs/{id}/events` (18 real per-node events).
   `GET /api/v1/campaigns/$CID/revisions` → `html_preview`, `concept.source_refs` (KG layout), preview in Storage.
3. **AI backgrounds (F7)** — `POST /api/v1/campaigns/$CID/background-options {"count":3}` → 3 sanitized `.aijolot-banner` CSS options.
4. **Art prompts (F8)** — `POST /api/v1/campaigns/$CID/art-prompts {"shot_type":"usage","count":4}` (angles consistent), `…/model-prompts`, then
   `POST /api/v1/campaigns/$CID/generate-art {"prompt":"…","shot_type":"usage","background_ref":"…","background_css":"…"}` → real image uploaded to Storage + composed_html.
5. **Agentic refine (F9)** — `POST /api/v1/campaigns/$CID/regenerate {"prompt":"copy más urgente y cambia el fondo"}` → new selected revision (real artifacts), targets auto-classified.
6. **Approve (gate)** — `POST /api/v1/campaigns/$CID/approval/request {"reviewers":[{"user_id":"'$USER'"}]}` → `POST /api/v1/approval-threads/{tid}/approve {"user_id":"'$USER'"}` → campaign `approved`.
7. **Schedule** — `POST /api/v1/campaigns/$CID/schedule {"starts_at":"2026-06-10T09:00:00+00:00"}` → `scheduled`.
8. **Install placeholders + publish (F10)**:
   - `POST /api/v1/stores/$SID/shopify/install-theme-files` (idempotent; `?dry_run=true` to simulate).
   - **Dry-run**: `POST /api/v1/campaigns/$CID/publish?dry_run=true` → `would_write_metafield`, campaign stays `scheduled`, metafield untouched.
   - **Real**: `POST /api/v1/campaigns/$CID/publish?dry_run=false` (or `SHOPIFY_PUBLISH_DRY_RUN=false`) → writes `shop.metafields.aijolot.banner_campaigns`, campaign `published`.
   - **Unpublish**: `POST /api/v1/campaigns/$CID/unpublish` → metafield cleared to `[]`, campaign `approved`.

## 5. Verified e2e (2026-06-04, store `aijolo-demo`)

- Intake → brief complete in one turn (Gemini).
- Generate → run `succeeded`, facade `f5-run-orchestrator`, 18 events, Gemini hero image ($0.04), KG layout `Full-bleed hero…`, audit `warn`, preview + variants persisted.
- Backgrounds → `source=gemini`, 3 sanitized options.
- Art/model prompts → `source=gemini`; generate-art uploaded a real image to Supabase Storage (`public_url`).
- Refine → revision #9, facade `f9-refine-orchestrator`, targets `[background, copy]`, AI background attached.
- Publish cycle → install (dry+real) → schedule → dry-run publish (metafield intact) → real publish (metafield written) → unpublish (metafield `[]`).
- Frontend (preview) → loads with no console errors; `BackgroundApi`/`ArtApi` return `source=gemini` from the page (CORS + auth OK).

## 6. Safety / gotchas

- **Dry-run is the default.** Real publish requires an explicit `?dry_run=false` or `SHOPIFY_PUBLISH_DRY_RUN=false`. Restore the safe default after a real-publish demo.
- **Fail-closed everywhere.** No key / cost cap / `GeminiUnavailable` → deterministic fallback (intake, KG, image→fake provider, backgrounds→palette gradients, art prompts→deterministic variants). The demo never hard-stops.
- **CSS sanitization** strips `@import`, external `url()`, `expression(`, `<script>`/`<iframe>`, inline `on*=` before any Gemini CSS reaches a preview.
- **`asset_kind`** must be one of `generated_background|product_image|logo|rendered_preview|liquid_asset` (usage shots → `product_image`).
- **`supabase db reset`** reverts the store row `…101` to the seed and drops the demo profile/auth user; re-point it to `aijolo-demo`/theme `188324807026` and re-seed the KG + demo reviewer profile (`…601`) afterward.
- Theme mutations are append-only `aijolot-*` assets via `put_theme_asset`; anchor `{% render %}` placement in the theme editor is a documented one-time manual step.
