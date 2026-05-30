---
name: banner-html-seo-render
description: Render standalone HTML + meta tags + JSON-LD PromotionalOffer from Concept + assets.
metadata:
  type: deterministic
  owner_node: 8
  ticket: GH-14
---

## Inputs
- `concept: Concept`
- `assets: BannerAssets`
- `brand: BrandContext`

## Outputs
- `html: str` (standalone, self-contained for preview)

## Acceptance criteria
- [ ] HTML W3C valid (validated by audit_w3c tool)
- [ ] Meta tags: og:title, og:description, og:image
- [ ] JSON-LD PromotionalOffer valida Rich Results
- [ ] `<picture>` with full srcset (WebP + AVIF + JPG fallback)
