---
title: "LCP exceeds 2.5s when hero image is not width-optimised and not eagerly loaded"
kind: audit_failure
brand_id: null
metadata:
  category: lighthouse
  evidence_source: "Core Web Vitals LCP threshold 2.5s; BRANCY hero image_tag pattern 2026-05"
  applicable_when: "hero_main banners with full-size product or lifestyle photography"
---

The Largest Contentful Paint element in a hero banner is almost always the product or background image. LCP > 2.5s fails Core Web Vitals and degrades Google Search ranking. Common failure causes: hero image served at full original resolution (2–3MB) without width sizing, missing loading: 'eager' (defaulting to lazy which delays load), and no preload hint. Remediation: use Shopify's image_url filter with explicit width parameter matching the largest rendered size (e.g. width: 1440 for full-bleed desktop), set loading: 'eager' on the hero image_tag, and add a <link rel="preload"> hint in the section's head content block. BRANCY hero HTML applies these correctly — it specifies width: 841 for the product column image and uses eager loading.
