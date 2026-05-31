# KG seed corpus

Source-of-truth markdown docs that populate `public.kg_documents` via `scripts/kg_seed.py`.

## Layout

```
docs/kg_seed/
├── best_practices/      # ~30 docs · ecommerce banner principles
├── brand_examples/      # ~2 per brand · voice/tone exemplars
├── liquid_patterns/     # ~8 docs · Shopify Section snippets
├── audit_failures/      # ~15 docs · Lighthouse/W3C failure → remediation
└── seo_patterns/        # ~10 docs · OG meta, JSON-LD templates
```

## Doc format

Each file has YAML frontmatter + markdown body:

```markdown
---
title: "CTA copy under 5 words drives 22% lift"
kind: best_practice
brand_id: null            # optional, omit for cross-brand
metadata:
  category: cta
  evidence_source: "Baymard 2024"
  applicable_when: "performance + urgency >= medium"
---

Short, action-only CTAs (Buy now, Claim 50%, Shop the drop) outperform
descriptive CTAs by 18–24% on hero banners across apparel and beauty.
...
```

Body is embedded with `text-embedding-005`; frontmatter populates `metadata` and `brand_id`.

## Seeding

```
python scripts/kg_seed.py            # production seed
python scripts/kg_seed.py --dry-run  # parse + validate only
```

Adding docs post-hackathon: drop new markdown, re-run seed. The script upserts by `(kind, title, brand_id)` — no duplicates.

Total target seed: ~65 docs before D2.
