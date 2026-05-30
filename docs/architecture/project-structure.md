# Project Structure

```text
aijolot-banner-agent/
├── brands/                         # Versioned brand context Markdown/YAML files
├── backend/
│   ├── app/
│   │   ├── agents/                 # Google ADK graph, state, nodes, prompts, tools
│   │   │   ├── nodes/              # 12 graph node implementations
│   │   │   ├── prompts/            # Versioned prompt templates
│   │   │   └── tools/              # Agent-facing tools/adapters
│   │   ├── api/
│   │   │   └── routes/             # HTTP route modules
│   │   ├── core/                   # settings, logging, app bootstrap helpers
│   │   ├── db/
│   │   │   ├── models/             # persistence models / DB row mapping
│   │   │   └── repositories/       # Supabase data-access layer
│   │   ├── schemas/                # request/response/domain validation schemas
│   │   ├── services/
│   │   │   ├── approvals/          # review, comment, approval orchestration
│   │   │   ├── audit/              # Lighthouse/html/schema validation services
│   │   │   ├── banners/            # banner generation, variants, assets, placements
│   │   │   ├── gemini/             # Gemini image/text generation adapters
│   │   │   ├── shopify/            # Shopify Admin API integration
│   │   │   └── supabase/           # Supabase auth/storage/client helpers
│   │   ├── templates/
│   │   │   └── shopify/            # Liquid/Jinja templates for section/snippets
│   │   ├── workflows/              # end-to-end business workflows
│   │   └── utils/                  # shared utility functions
│   └── tests/
│       ├── unit/
│       └── integration/
├── frontend/
│   ├── app/                        # Future Next.js App Router pages/layouts
│   ├── components/                 # Future UI components
│   ├── lib/                        # Future API clients and shared frontend helpers
│   ├── public/                     # Future static assets
│   ├── styles/                     # Future Tailwind/global CSS
│   └── *.jsx/*.css                 # Current static React UX prototype from frontend/design-implementation
├── supabase/
│   ├── migrations/                 # SQL migrations
│   └── seed/                       # local/dev seed data
├── obsidian/                       # Git-synced Obsidian vault for project notes
├── docs/
│   ├── architecture/               # design docs, extracted source docs, alignment notes
│   ├── demo/                       # demo script and scenario docs
│   └── plans/                      # implementation plans
├── demo/                           # demo scenarios/assets
└── scripts/                        # dev scripts
```

Notes:
- Frontend contains structure only. No Next.js/Tailwind code or package files were created yet.
- Backend contains structure only. Python application code and dependency manifests are intentionally deferred to the next implementation task.
- `.gitkeep` files keep intentionally empty directories tracked by Git.
