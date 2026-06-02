---
name: campaign-intake
description: Conversational campaign intake that extracts a structured Campaign brief from free-form user turns. Supports Gemini 3.5 Flash (opt-in) with deterministic fallback. Asks one missing field at a time. Produces StructuredBrief with goal, audience, cta, tone, urgency, placement, deadline. Node 2 in the ADK graph.
---

# Campaign Intake

Extract a structured campaign brief from conversational user input, one field at a time.

> **Node Metadata** | node: 2 | type: llm | model: gemini-3.5-flash | ticket: GH-9 | version: 0.2.0 | status: draft

## Node Invariants

1. **One field at a time.** When the brief is incomplete, ask exactly ONE missing field — never batch questions.
2. **Gemini is opt-in.** Set `AIJOLOT_INTAKE_PROVIDER=gemini` to enable. All other modes use the deterministic extractor.
3. **Deterministic fallback is always available.** If Gemini fails (timeout, error, unexpected output), the skill falls back transparently.
4. **Never fabricate field values.** If the user hasn't provided a field, it stays empty — never guess.

## Graph Entry Conditions

- **Upstream:** `load_brand_context` (node 1) must have completed.
- **State preconditions:** `state.brand_context is not None`.
- **Multi-turn:** This node is invoked repeatedly (once per user turn) until the brief is complete.
- **Retry re-entry:** Not retried via audit. `max_retries = 0` in graph.py.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| Function param | `messages` | `list[dict]` | Yes — running transcript `[{author_type, body}]` |
| Function param | `brand_context` | `BrandContext \| Any` | Optional — for tone/brand awareness |
| Function param | `current_brief` | `StructuredBrief \| dict \| None` | Optional — accumulated brief so far |

## Output Encoding

- **Model:** `CampaignIntakeResult` (Pydantic)
- **Fields:** `structured_brief: StructuredBrief`, `question: str | None`, `complete: bool`, `metadata: dict`
- **`StructuredBrief` fields:** `goal, audience, cta, tone, urgency, placement, deadline` (all `str | None`)
- **`metadata` includes:** `provider` ("gemini" or "deterministic"), `fallback` (bool), `reason` (str)

## Data Sources

| Source | Purpose |
|--------|---------|
| Tool: `gemini_text.generate()` | LLM structured extraction (when Gemini enabled) |
| Prompt: `intake.md` | Interview rules + output schema |
| Internal: `campaign_store._agent_reply()` | Deterministic question generation |
| Internal: `campaign_store.extract_into()` | Rule-based field extraction |
| Config: `AIJOLOT_INTAKE_PROVIDER` env var | Provider selection |

No sub-agents.

## Workflow

1. Resolve `current_brief` to `StructuredBrief` (dict → model coercion).
2. Check provider env: `AIJOLOT_INTAKE_PROVIDER`.
3. **If provider != "gemini":** go to step 7 (deterministic path).
4. **Gemini path:**
   a. Render prompt from `intake.md` template + current brief JSON + brand context + transcript.
   b. Call `gemini_text.generate()` with `GeminiIntakeOutput` structured output schema.
   c. If call fails → go to step 7 (fallback).
   d. If output is not `GeminiIntakeOutput` → go to step 7 (fallback).
   e. Merge Gemini output into current brief via `_merge_output()`.
   f. Normalize urgency (Spanish/English bilingual mapping).
   g. Generate question for next missing field (or None if complete).
   h. Return `CampaignIntakeResult(provider="gemini", fallback=False)`.
5. **GATE: Completeness check** — if all 6 required fields are populated, `complete=True`, `question=None`.
6. Return result.
7. **Deterministic path:**
   a. If current brief has values, apply only latest user turn (avoid stale overwrites).
   b. Run `extract_into(brief, user_text)` for each user message.
   c. Generate question via `_agent_reply(brief)` for next missing field.
   d. Return `CampaignIntakeResult(provider="deterministic", fallback=True, reason=...)`.

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.campaign` | `Campaign` | Populated when brief is complete |

Return type: `CampaignIntakeResult`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| `structured_brief` fields (Gemini path) | `[LLM-GENERATED]` — extracted by gemini-3.5-flash |
| `structured_brief` fields (deterministic path) | `[DETERMINISTIC]` — regex/rule-based extraction |
| `question` | `[DETERMINISTIC]` — template-based from missing fields |
| `complete` | `[DETERMINISTIC]` — all-fields-populated check |
| `metadata.provider` | `[DETERMINISTIC]` — env var check |

## Pre/Post Conditions

**Pre:**
- `messages is not None and len(messages) >= 1`
- At least one message has `author_type == "user"`

**Post (per turn):**
- Result has `structured_brief` (may be partially populated)
- If `complete == True`: all 6 required fields are non-empty
- If `complete == False`: `question is not None`
- `metadata.provider` is either `"gemini"` or `"deterministic"`

**Post (final turn):**
- `state.campaign` is a valid `Campaign` with all fields

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| `AIJOLOT_INTAKE_PROVIDER` != "gemini" | Use deterministic extractor — not an error |
| Gemini API timeout/error | Fall back to deterministic, log reason in `metadata.reason` |
| Gemini returns unexpected type | Fall back to deterministic, log reason |
| All messages empty | Return empty brief with question for first field |
| User provides multiple fields at once | Accept all silently — do not re-ask answered fields |
| Urgency in Spanish ("alta", "urgente") | Normalize to English ("high") via bilingual mapping |

See `references/gemini_fallback_matrix.md` for the complete decision matrix.

## Quality Criteria

- [ ] Asks ONE missing field at a time (never batches)
- [ ] Structured output validates against `StructuredBrief` schema
- [ ] 3 distinct prompts produce 3 valid Campaigns (test fixture)
- [ ] Cost per turn logged in metadata
- [ ] Deterministic fallback produces same output for same input
- [ ] Urgency bilingual normalization: "alta" → "high", "baja" → "low"
- [ ] Multi-field user turn: "Black Friday, audience VIP, urgente" → extracts 3 fields

## Guardrails

- Never fabricate field values — if user didn't say it, leave it empty.
- Never ask more than one question per turn — even if multiple fields are missing.
- Never override a user-confirmed field with a Gemini re-extraction (merge favors existing values unless user explicitly updates).
- Never expose Gemini API key in logs or error messages.
- Never send real customer data to Gemini — only campaign brief metadata.

## Human Review Required

None. Automated node. Campaign briefs are visible in HITL review (node 10).

## References

- Prompt: `intake.md` → `backend/app/agents/prompts/intake.md`
- Tool: `gemini_text` → `backend/app/agents/tools/gemini_text.py`
- Service: `campaign_store` → `backend/app/services/campaign_store.py`
- Schema: `StructuredBrief` → `backend/app/schemas/campaign.py`
- State model: `Campaign` → `backend/app/agents/state.py`
- Config: `AIJOLOT_INTAKE_PROVIDER` → env var
- Detail: `references/gemini_fallback_matrix.md`
- Upstream skill: `brand-context-load` (node 1)
- Downstream skill: `user-personalization` (node 3)
