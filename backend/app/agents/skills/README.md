# Skills index

| # | Skill | Node | Type | Model | Ticket |
|---|---|---|---|---|---|
| 1 | `brand-context-load` | 1 | deterministic | — | GH-8 |
| 2 | `campaign-intake` | 2 | llm | gemini-3.5-flash | GH-9 |
| 3 | `user-personalization` | 3 | llm | gemini-3.5-flash | GH-10 |
| 4 | `best-practices-retrieve` | 4 | retrieval | text-embedding-005 | GH-NEW8 |
| 5 | `banner-concept-draft` | 5 | llm (CreativeDirector) | gemini-3.1-pro | GH-11, GH-NEW6 |
| 6 | `image-prompt-refine` | 5/6 | llm | gemini-3.1-pro | GH-11 |
| 7 | `nano-banana-image-generate` | 6 | deterministic-llm | gemini-3.1-pro-image | GH-12 |
| 8 | `image-asset-optimize` | 7 | deterministic | — | GH-13 |
| 9 | `banner-html-seo-render` | 8 | deterministic | — | GH-14 |
| 10 | `liquid-section-build` | 8 (parallel) | deterministic | — | GH-15 |
| 11 | `performance-audit` | 9 | hybrid (Auditor) | gemini-3.5-flash | GH-16, GH-NEW7 |
| 12 | `schedule-or-publish-route` | 11 | deterministic | — | GH-18 |
| 13 | `shopify-theme-publish` | 12 | deterministic · **WRITE** | — | GH-19 |

**Node 10 (HITL human_review)** is NOT a skill — it's a human decision orchestrated by Coordinator + React Canvas (GH-30).

## Anatomy

```
skills/<skill_id>/
├── SKILL.md     Frontmatter (name, description, metadata) + inputs/outputs/ACs
├── impl.py      Async `run(...)` function
└── tests/       (added per ticket)
```

## Packaging

Internal modules now. Post-hackathon high-value skills (banner-concept-draft, performance-audit, brand-context-load) get packaged to `~/.aijolot/skills/` for cross-project reuse per `aijolot-skill-creator`.
