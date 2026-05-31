---
name: best-practices-retrieve
description: KG retrieval (pgvector) of top-K best-practice / brand-example / prior-banner docs.
metadata:
  type: retrieval
  embedding_model: text-embedding-005
  owner_node: 4
  ticket: GH-NEW8
---

## Inputs
- `campaign: Campaign`
- `brand_context: BrandContext`

## Outputs
- `list[KGDocument]` top-K (default 5) above similarity threshold (default 0.65).

## Acceptance criteria
- [ ] Query embed dim matches kg_documents.embedding (768)
- [ ] Hybrid filter respects `kinds=['best_practice','brand_example','prior_banner']`
- [ ] Returns empty list if zero docs above threshold (no padding)
- [ ] Cost <$0.0001 per retrieval (embed call only)
