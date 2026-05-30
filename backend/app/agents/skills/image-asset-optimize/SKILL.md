---
name: image-asset-optimize
description: Generate 4 breakpoints (WebP + AVIF) + JPG fallback + alt_text from a single image.
metadata:
  type: deterministic
  owner_node: 7
  ticket: GH-13
---

## Inputs
- `image_bytes: bytes`
- `alt_text_hint: str`

## Outputs
- `BannerAssets{webp{320,768,1280,1920}, avif{...}, fallback_jpg{1280}, alt_text_suggestion}`

## Acceptance criteria
- [ ] All 4 breakpoints generated for WebP + AVIF
- [ ] JPG fallback at 1280
- [ ] Weight cap <80KB @ 1280 WebP enforced (assertion in test)
- [ ] alt_text_suggestion ≤120 chars
