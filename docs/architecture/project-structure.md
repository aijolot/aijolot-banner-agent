# Project Structure

```text
aijolot-banner-agent/
├── backend/
│   ├── app/
│   │   ├── agents/                 # ADK graph scaffold, skills, prompts, provider tools
│   │   │   ├── prompts/            # Versioned prompt templates
│   │   │   ├── skills/             # Implemented deterministic/provider skill functions
│   │   │   ├── sub_agents/         # Creative director/auditor sub-agent scaffolds
│   │   │   └── tools/              # Gemini, image, render, audit, KG, Shopify adapters
│   │   ├── api/                    # Root compatibility routes and canonical v1 routes
│   │   │   └── v1/                 # Auth-required /api/v1 integration API
│   │   ├── core/                   # Settings, auth, dependency boundaries
│   │   ├── db/
│   │   │   └── repositories/       # Supabase/in-memory repository adapters
│   │   ├── schemas/                # Pydantic request/response/domain schemas
│   │   ├── services/
│   │   │   ├── approvals/          # Approval threads, comments, refinement orchestration
│   │   │   ├── banners/            # Campaigns, placements, catalog, generation, assets, revisions, schedules, performance
│   │   │   ├── brands/             # Brand Supabase service and Markdown importer
│   │   │   ├── gemini/             # Text/image provider boundaries and fake provider support
│   │   │   ├── shopify/            # Resource cache, controlled Liquid/theme/metafield publishing
│   │   │   └── supabase/           # Supabase client/storage helpers
│   │   ├── templates/              # Shopify Liquid/Jinja templates
│   │   ├── workflows/              # Banner creation workflow helpers
│   │   └── utils/                  # Shared utility functions
│   ├── adk_agents/                 # ADK web-compatible banner coordinator entrypoint
│   ├── tests/                      # API/unit/integration tests
│   └── pyproject.toml              # Python package/dependency config
├── frontend/                       # Static React 18 UMD/Babel prototype; no Next.js build yet
│   ├── data.jsx                    # Prototype data plus BrandAPI adapter
│   ├── lib.jsx                     # Shared UI primitives and API adapters
│   ├── index.html                  # Static browser entrypoint
│   └── *.jsx/*.css                 # Prototype stages/components/styles
├── brands/                         # Versioned Markdown/YAML brand context import/fallback files
├── supabase/
│   ├── config.toml                 # Local Supabase ports/config
│   ├── migrations/                 # SQL migrations, including KG and Task 20 provenance update
│   └── seed.sql                    # Local/dev seed data
├── docs/
│   ├── architecture/               # API/frontend contracts, structure, design docs
│   ├── demo-script.md              # Constrained deterministic/real-provider demo script
│   └── plans/                      # Implementation plans and completion notes
├── demo/
│   └── scenarios/                  # Demo scenario notes
├── scripts/
│   ├── reset-demo-data.py          # Local/Supabase-aware reset helper
│   └── smoke-demo-flow.py          # Offline deterministic API smoke path
└── obsidian/                       # Git-synced Obsidian vault for project notes
```

Notes:

- The backend application is implemented and test-covered. It supports Python 3.11+ and normally runs from `backend/.venv` for local development.
- `/api/v1` is the canonical backend namespace and requires demo auth/team context. Root-level routes remain compatibility routes for older prototype flows.
- The frontend is still the static prototype. Future Next.js/Tailwind migration is frontend-owned and should replace static adapters rather than treating them as final architecture.
- Supabase migrations are additive and live under `supabase/migrations/`; seed data lives in `supabase/seed.sql`.
- The deterministic demo smoke path is `python3 scripts/smoke-demo-flow.py` from repo root and does not call external providers.
