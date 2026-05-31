---
name: user-personalization
description: Derive 1..N customer.tags-based Variants from a Campaign (Gemini 3.5 Flash).
metadata:
  type: llm
  model: gemini-3.5-flash
  owner_node: 3
  ticket: GH-10
---

## Inputs
- `campaign: Campaign`

## Outputs
- `Variants[]` with at least one `default` variant.

## Acceptance criteria
- [ ] Default variant always present
- [ ] Max 4 variants (1 default + 3 segments)
- [ ] Each variant has non-empty `customer_tag` and `intent_delta`
