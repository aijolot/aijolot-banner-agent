---
name: best-practices-retrieve
description: Retrieve top-K best-practice, brand-example, and prior-banner documents from the Knowledge Graph (2nd Brain) using semantic query construction from campaign + brand context. Lexical matching in MVP, pgvector cosine similarity post-MVP. Node 4 in the ADK graph.
---

# Best Practices Retrieve

Query the Knowledge Graph to retrieve contextually relevant ecommerce banner best practices for the creative pipeline.

> **Node Metadata** | node: 4 | type: retrieval | embedding_model: text-embedding-005 | ticket: GH-NEW8 | version: 0.2.0 | status: draft

## Node Invariants

1. **No padding.** Returns empty list if zero docs meet threshold — never fills with irrelevant results.
2. **Brand affinity bonus.** Documents matching `brand_id` get a +0.5 scoring bonus.
3. **Kind filtering.** Only retrieves `best_practice`, `brand_example`, `prior_banner` document kinds.
4. **Cost ceiling.** < $0.0001 per retrieval call (embed-only cost).

## Graph Entry Conditions

- **Upstream:** `capture_user_personalization` (node 3) must have completed.
- **State preconditions:** `state.campaign is not None`, `state.brand_context is not None`.
- **Retry re-entry:** Not retried. `max_retries = 0` in graph.py.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| State | `campaign` | `Campaign \| StructuredBrief \| dict` | Yes |
| State | `brand_context` | `BrandContext` | Yes |
| Function param | `top_k` | `int` | Optional — default 5 |

## Output Encoding

- **Type:** `list[dict[str, Any]]` — KG document dicts.
- **Each doc:** `{id, kind, title, body, metadata, brand_id, score}`.
- **Count:** 0 to `top_k` documents. Empty list is valid.
- **Threshold:** Default 0.65 similarity (configurable via `KG_SIMILARITY_THRESHOLD`).

## Data Sources

| Source | Purpose |
|--------|---------|
| Tool: `kg.retrieve()` | KG query execution (lexical or pgvector) |
| State: `campaign` | Query terms: goal, audience, tone, cta, placement, urgency |
| State: `brand_context` | Query enrichment: voice.tone; brand_id for affinity filter |
| KG corpus: `docs/kg_seed/` | ~65 seeded docs: best_practices, brand_examples, liquid_patterns, audit_failures, seo_patterns |

No prompts. No sub-agents.

## Workflow

1. Extract campaign fields: goal, audience, tone, cta, placement, urgency.
2. Extract brand voice tone tokens.
3. Construct semantic query string: `"goal · audience=X · tone=X · cta=X · placement=X · urgency=X · voice_tone"`.
4. Call `kg.retrieve(query, kinds=[...], brand_id=brand_context.id, top_k=top_k)`.
5. Tool internally:
   a. **MVP (lexical):** Tokenize query, match against doc title/body/metadata, score by overlap + kind bonus (+0.15 for best_practice) + brand_id bonus (+0.5).
   b. **Post-MVP (pgvector):** Embed query via `text-embedding-005`, cosine similarity search on `kg_documents.embedding`, filter by kinds, brand_id boost.
   c. Rank by score, return top-K above threshold.
6. Return list of KG document dicts.

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.best_practices` | `list[dict[str, Any]]` | Top-K relevant KG documents |

Return type: `list[dict[str, Any]]`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| Document list | `[KG-RETRIEVED]` — from KG corpus via lexical/vector search |
| Document score | `[DETERMINISTIC]` — computed by retrieval algorithm |
| Document content (title, body) | `[KG-RETRIEVED]` — authored corpus content |

## Pre/Post Conditions

**Pre:**
- `state.campaign is not None`
- `state.brand_context is not None`
- `state.brand_context.id is not None`

**Post:**
- `state.best_practices is not None` (may be empty list)
- `len(state.best_practices) <= top_k`
- `all(doc["kind"] in ["best_practice", "brand_example", "prior_banner"] for doc in state.best_practices)`

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| KG corpus empty | Return empty list — pipeline continues without best practices |
| No docs above threshold | Return empty list — do NOT lower threshold to force results |
| Campaign fields all empty | Construct minimal query from brand voice tone only |
| pgvector unavailable (MVP) | Use lexical fallback — always available |
| Embedding API fails (post-MVP) | Fall back to lexical retrieval with warning |

**Key:** Empty results are valid. The creative pipeline (node 5) operates without best practices — they are enrichment, not a hard dependency.

## Quality Criteria

- [ ] Query embed dim matches `kg_documents.embedding` (768) when using pgvector
- [ ] Hybrid filter respects `kinds=["best_practice", "brand_example", "prior_banner"]`
- [ ] Returns empty list if zero docs above threshold (no padding)
- [ ] Cost < $0.0001 per retrieval (embed call only)
- [ ] Brand-specific docs score higher than generic ones for matching brand_id
- [ ] Lexical fallback produces reasonable results for smoke test queries

## Guardrails

- Never pad results with irrelevant documents to fill `top_k` quota.
- Never lower the similarity threshold dynamically — use the configured value.
- Never retrieve `audit_failure` or `seo_pattern` kinds — those are for node 9 (audit).
- Never cache results across sessions — each campaign gets fresh retrieval.
- Never expose raw embedding vectors to downstream skills — only doc content + score.

## Human Review Required

None. Automated node. KG retrieval is read-only.

## References

- Tool: `kg` → `backend/app/agents/tools/kg.py`
- KG seed: `docs/kg_seed/` (best_practices/, brand_examples/, liquid_patterns/)
- KG seeder: `scripts/kg_seed.py`
- DB table: `kg_documents` → `supabase/migrations/20260529000000_kg_pgvector.sql`
- Config: `KG_RETRIEVAL_TOP_K`, `KG_SIMILARITY_THRESHOLD` → `backend/app/core/settings.py`
- Upstream skill: `user-personalization` (node 3)
- Downstream skill: `banner-concept-draft` (node 5)
