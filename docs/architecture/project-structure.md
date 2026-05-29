# Project Structure

```text
aijolot-banner-agent/
├── backend/
│   ├── app/
│   │   ├── agents/                 # Google ADK agent definitions and instructions
│   │   ├── api/
│   │   │   └── routes/             # HTTP route modules
│   │   ├── core/                   # settings, logging, app bootstrap helpers
│   │   ├── db/
│   │   │   ├── models/             # persistence models / DB row mapping
│   │   │   └── repositories/       # Supabase data-access layer
│   │   ├── schemas/                # request/response/domain validation schemas
│   │   ├── services/
│   │   │   ├── approvals/          # review, comment, approval orchestration
│   │   │   ├── banners/            # banner generation, variants, assets, placements
│   │   │   ├── gemini/             # Gemini image/text generation adapters
│   │   │   ├── shopify/            # Shopify Admin API integration
│   │   │   └── supabase/           # Supabase auth/storage/client helpers
│   │   ├── workflows/              # end-to-end business workflows
│   │   └── utils/                  # shared utility functions
│   └── tests/
│       ├── unit/
│       └── integration/
├── frontend/
│   ├── app/                        # Next.js App Router pages/layouts
│   ├── components/                 # UI components
│   ├── lib/                        # API clients and shared frontend helpers
│   ├── public/                     # static assets
│   └── styles/                     # Tailwind/global CSS
├── supabase/
│   ├── migrations/                 # SQL migrations
│   └── seed/                       # local/dev seed data
├── docs/
│   ├── architecture/               # design docs and diagrams
│   └── plans/                      # implementation plans
└── scripts/                        # dev scripts
```

Notes:
- Frontend contains structure only. No Next.js/Tailwind code or package files were created yet.
- Backend contains structure only. Python application code and dependency manifests are intentionally deferred to the next implementation task.
- `.gitkeep` files keep intentionally empty directories tracked by Git.
