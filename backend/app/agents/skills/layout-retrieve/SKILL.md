---
name: layout-retrieve
description: Retrieve top-K liquid_pattern layout documents from the Knowledge Graph (2nd Brain) using placement + goal + tone, so the concept draft can ground its layout in evidence-backed Shopify section patterns. Tiered retrieval (vector → db lexical → static floor) with graceful fallback to deterministic layout when no candidates exist. Companion to best-practices-retrieve at node 5 (concept).
---

# Layout Retrieve

Query the Knowledge Graph for `liquid_pattern` documents that match the campaign's
placement, goal, and tone. The top candidate informs the banner concept's layout
direction (F6) and is recorded as provenance in `Concept.source_refs`.

## Invariants

1. **Placement-led query.** The query is built from `placement + goal + tone` so
   placement-specific patterns (hero, announcement bar, promo card, PDP strip,
   collection header, social proof) surface first.
2. **Kind filtering.** Only retrieves `liquid_pattern` documents.
3. **Graceful empty.** Returns `[]` when no `liquid_pattern` docs are reachable
   (e.g. no Supabase / static-only mode). The concept skill then keeps its
   deterministic layout string. Retrieval never fabricates patterns.
4. **Cost ceiling.** < $0.0001 per call (embed-only, shared with KG retrieval).
