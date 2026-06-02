---
title: "Layout shift (CLS) caused by hero image loading without explicit width and height attributes"
kind: audit_failure
brand_id: null
metadata:
  category: lighthouse
  evidence_source: "Core Web Vitals CLS threshold 0.1; Shopify image_tag best practices 2026-05"
  applicable_when: "hero banners and promo cards with img elements"
---

When an img element has no width and height attributes, the browser does not reserve space for it during initial render. As the image loads, it shifts the layout — producing Cumulative Layout Shift (CLS) that fails Core Web Vitals (CLS > 0.1 is poor). Hero banners are the most common source of CLS on beauty storefronts because they are large images above the fold. Remediation: always pass explicit width and height to Shopify's image_tag helper — the BRANCY hero HTML passes width: 841, height: 832 to the product column image. For responsive images, use the aspect-ratio CSS property instead of fixed height: `aspect-ratio: 841 / 832` with width: 100%.
