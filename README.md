# Aijolot Banner Agent

Hackathon MVP for an agentic banner creation and publishing workflow using Google's ADK + Gemini.

Goal: help marketing teams create, review, schedule, position, and publish store banners. MVP scope targets Shopify stores.

## Repository layout

```text
backend/      Python backend and ADK/Gemini agent workflows.
frontend/     Next.js + Tailwind admin panel structure only for now.
supabase/     Database migrations and seed data.
docs/         Architecture notes and implementation plans.
scripts/      Developer automation scripts.
```

Current status: base folder structure and implementation plan created. Backend/frontend code will be added in following tasks.

## Running locally

### Backend bridge (FastAPI)

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000   # OpenAPI docs at http://localhost:8000/docs
pytest                                       # run tests
```

### Frontend (static prototype)

The current frontend is a CDN React + Babel-standalone prototype (no build step):

```bash
python3 -m http.server 5500 --directory frontend
# open http://localhost:5500
```

The Brand Context view (sidebar → "Marca") talks to the bridge at
`http://localhost:8000` (override with `window.AIJOLOT_API_BASE`). If the bridge
is unreachable it falls back to in-memory brand seeds, so the UI stays usable
offline.

## Brand Context (GH-26)

Brands live as `brands/{id}.md` files — YAML frontmatter (the structured
`BrandContext`: palette, typography, voice, logo, image directives, Shopify
config) plus a free-form notes body. The bridge exposes:

| Method | Route            | Purpose                          |
| ------ | ---------------- | -------------------------------- |
| GET    | `/brands`        | list brand summaries             |
| GET    | `/brands/{id}`   | full `BrandContext`              |
| PUT    | `/brands/{id}`   | validate (Pydantic) and persist  |

Seeded brands: `avocado_store`, `demo_apparel`, `maison`.
