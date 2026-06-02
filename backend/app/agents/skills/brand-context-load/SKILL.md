---
name: brand-context-load
description: Load and normalize a brand context from Markdown files or API/DB dictionaries into a validated BrandContext Pydantic model. Graph root node (node 1) — every downstream skill depends on this output. Deterministic, no LLM.
---

# Brand Context Load

Load, validate, and normalize brand identity into the pipeline's shared BrandContext model.

> **Node Metadata** | node: 1 | type: deterministic | model: none | ticket: GH-8 | version: 0.2.0 | status: draft

## Node Invariants

1. **Always produces a valid BrandContext.** Missing optional fields get conservative defaults — never null where downstream skills expect values.
2. **Palette has at least one color.** Falls back to `[Ink #111111, Canvas #FFFFFF]` if input palette is empty or malformed.
3. **No LLM involvement.** This node is purely deterministic — parsing YAML frontmatter or normalizing dict input.
4. **Brand ID consistency.** The returned `BrandContext.id` matches the requested `brand_id` or the id embedded in the input data.

## Graph Entry Conditions

- **Upstream:** None — this is the graph root.
- **State preconditions:** `state.brand_id` is set (provided at session creation).
- **Retry re-entry:** Not applicable. `max_retries = 0` in graph.py. If this node fails, the pipeline halts.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| State | `brand_id` | `str` | Yes |
| Function param | `brand_context` | `BrandContext \| dict \| None` | Optional — if provided, normalization only (no file read) |

When `brand_context` is `None`, the skill reads from `brands/{brand_id}.md` via `brand_fs.read()`.

## Output Encoding

- **Model:** `app.schemas.brand.BrandContext` (Pydantic v2)
- **Key fields:** `id: str`, `name: str`, `palette: list[PaletteColor]`, `typography: Typography`, `voice: Voice`, `logo_url: str|None`, `image_style_directives: list[str]`, `shopify: Shopify`, `notes: str`
- **Text language:** Matches brand file language (typically Spanish or English).
- **Limits:** `name` ≤ 100 chars, `notes` ≤ 500 chars, `palette` 1-10 colors.

## Data Sources

| Source | Purpose |
|--------|---------|
| Tool: `brand_fs.read(brand_id)` | Load brand Markdown file with YAML frontmatter |
| Schema: `app.schemas.brand.BrandContext` | Pydantic validation and defaults |
| State: `brand_id` | File lookup key |

No prompts. No sub-agents.

## Workflow

1. If `brand_context` param is provided (dict or BrandContext), skip to step 3.
2. Call `brand_fs.read(brand_id)` to load `brands/{brand_id}.md`.
3. Normalize input via `normalize_brand_context()`:
   a. Extract `id`, `name` from input — apply fallback defaults.
   b. Parse `palette` — accept PaletteColor objects, dicts, or bare hex strings.
   c. Parse `voice` — normalize `tone`, `prohibited_words`, `required_phrases` to string lists.
   d. Parse `typography`, `shopify` — fill missing sub-fields with safe defaults.
   e. Coerce `image_style_directives` to string list.
4. Validate via `BrandContext.model_validate()`.
5. Return validated BrandContext.

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.brand_context` | `BrandContext` | Fully normalized brand identity |

Return type: `BrandContext`

## Data Provenance

| Output field | Provenance | Notes |
|-------------|-----------|-------|
| `id` | `[DETERMINISTIC]` | Parsed from input or filename |
| `name` | `[DETERMINISTIC]` | Parsed from input |
| `palette` | `[DETERMINISTIC]` | Parsed + defaults applied |
| `typography` | `[DETERMINISTIC]` | Parsed + defaults |
| `voice.tone` | `[DETERMINISTIC]` | Parsed to list |
| `voice.prohibited_words` | `[DETERMINISTIC]` | Parsed to list |
| `voice.required_phrases` | `[DETERMINISTIC]` | Parsed to list |
| `logo_url` | `[USER-PROVIDED]` | Pass-through |
| `image_style_directives` | `[USER-PROVIDED]` | Pass-through, normalized to list |
| `shopify` | `[DETERMINISTIC]` | Parsed + defaults |

## Pre/Post Conditions

**Pre:**
- `state.brand_id is not None and state.brand_id != ""`
- `state.brand_context is None` (first invocation)

**Post:**
- `state.brand_context is not None`
- `len(state.brand_context.palette) >= 1`
- `state.brand_context.id == state.brand_id` (or derived from input)
- `isinstance(state.brand_context.voice.prohibited_words, list)`

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| Brand file not found | `brand_fs.read()` raises `FileNotFoundError` → pipeline halts with clear error |
| YAML parse error | `brand_fs.read()` raises `ValueError` → pipeline halts |
| Pydantic validation fails | `ValidationError` raised → pipeline halts |
| Palette empty/malformed | Falls back to `[Ink #111111, Canvas #FFFFFF]` — does NOT halt |
| Voice field missing | Defaults to empty lists for `tone`, `prohibited_words`, `required_phrases` |
| Shopify config missing | Defaults to `example.myshopify.com` domain — downstream publish will fail-closed |

**No retry.** Brand context is foundational — if it cannot be loaded, the pipeline cannot proceed.

## Quality Criteria

- [ ] Valid YAML frontmatter parses without error for all seeded brands (`avocado_store`, `demo_apparel`, `maison`)
- [ ] `PydanticValidationError` raised when required fields are missing
- [ ] Brand ID mismatch between file and request raises clear error
- [ ] Empty palette input produces default `[Ink, Canvas]` palette
- [ ] Voice with string input (not dict) normalizes to `{tone: [string], prohibited_words: [], required_phrases: []}`
- [ ] Emits audit_log event `node: load_brand_context`

## Guardrails

- Never return a BrandContext with an empty palette — always fall back to defaults.
- Never silently change `brand_id` — if file ID and requested ID diverge, raise error.
- Never load brands from URLs or external sources — only local files or provided dicts.
- Never populate `prohibited_words` with defaults — an empty list is safer than guessed restrictions.

## Human Review Required

None. Automated node. No external writes.

## References

- Tool: `brand_fs` → `backend/app/agents/tools/brand_fs.py`
- Schema: `BrandContext` → `backend/app/schemas/brand.py`
- State: `BannerSessionState` → `backend/app/agents/state.py`
- Graph: `NodeSpec("load_brand_context", ...)` → `backend/app/agents/graph.py`
- Brand files: `brands/*.md` (YAML frontmatter + Markdown body)
