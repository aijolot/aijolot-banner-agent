---
title: "Missing viewport meta tag causes banner content to render at desktop width on mobile"
kind: audit_failure
brand_id: null
metadata:
  category: mobile
  evidence_source: "HTML spec viewport meta; Lighthouse mobile audit 2026-05"
  applicable_when: "Shopify theme templates and section previews"
---

Without `<meta name="viewport" content="width=device-width, initial-scale=1">` in the document head, mobile browsers render the page at a fixed desktop width (typically 980px) and scale it down. All the responsive breakpoints in the banner section CSS (col-12 col-md-6, clamp font sizes, 390px mobile patterns) become irrelevant — the banner displays as a tiny scaled-down desktop layout. Lighthouse flags missing viewport meta as a critical mobile usability failure. This is rarely missing in a live Shopify theme, but is a common omission in standalone preview templates and liquid section development sandboxes.
