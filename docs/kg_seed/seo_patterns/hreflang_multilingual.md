---
title: "hreflang tags on multilingual Shopify stores signal language-specific banner pages to Google"
kind: seo_pattern
brand_id: null
metadata:
  category: international
  evidence_source: "Google hreflang spec; Shopify Markets; Drive corpus — multilingual beauty store consideration 2026-05"
  applicable_when: "Shopify stores with multiple language markets"
---

Beauty brands like those in the corpus often serve Spanish, English, and Portuguese markets from a single Shopify store via Shopify Markets. Without hreflang tags, Google may show the English hero banner page to Spanish-speaking users and vice versa, reducing click-through. Pattern: for each language variant of a page, emit `<link rel="alternate" hreflang="es" href="{{ routes.root_url }}/es{{ page.url }}">` in the layout head. Shopify Markets provides the locales loop to generate these programmatically. The x-default hreflang should point to the store's primary language. Banner agent-generated campaigns should include hreflang in the performance-audit checklist for multilingual stores.
