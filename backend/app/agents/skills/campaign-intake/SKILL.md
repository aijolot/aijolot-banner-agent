---
name: campaign-intake
description: Free-form conversational intake → structured Campaign (Pydantic) via Gemini 3.5 Flash.
metadata:
  type: llm
  model: gemini-3.5-flash
  owner_node: 2
  ticket: GH-9
---

## Inputs
- `messages: list[ChatMessage]` (running transcript)
- `brand_context: BrandContext`

## Outputs
- `Campaign` once all required fields are present; otherwise a clarifying question turn.

## Acceptance criteria
- [ ] Asks ONE missing field at a time
- [ ] Structured output validates against `Campaign` schema
- [ ] 3 distinct prompts produce 3 valid Campaigns (test fixture)
- [ ] Cost per turn logged to audit_log
