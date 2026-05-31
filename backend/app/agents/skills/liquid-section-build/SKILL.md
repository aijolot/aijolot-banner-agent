---
name: liquid-section-build
description: Build Shopify Liquid Section + block snippet with conditional variants by customer.tags.
metadata:
  type: deterministic
  owner_node: 8 (parallel)
  ticket: GH-15
---

## Inputs
- `concept: Concept`
- `variants: list[Variant]`
- `brand: BrandContext`

## Outputs
- `{section: str, block_snippet: str}` (both Liquid)

## Acceptance criteria
- [ ] Default variant + N variants with `customer.tags` case blocks
- [ ] Liquid sintácticamente válido (parse with Liquid linter)
- [ ] Snippet receives variant as parameter
