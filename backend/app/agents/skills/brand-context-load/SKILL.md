---
name: brand-context-load
description: Load and validate a brand context file (brands/<id>.md) into a BrandContext Pydantic object.
metadata:
  type: deterministic
  owner_node: 1
  ticket: GH-8
---

## Inputs
- `brand_id: str`

## Outputs
- `BrandContext` (palette, typography, voice, logo_url, image_style_directives, shopify config)

## Acceptance criteria
- [ ] Frontmatter YAML parses without error
- [ ] Pydantic ValidationError raised on missing required fields
- [ ] Brand id mismatch (file vs requested) raises clear error
- [ ] Emits audit_log event `node: load_brand_context`
