---
title: "Canonical URL tag on collection and promotional pages prevents duplicate content from URL parameter variants"
kind: seo_pattern
brand_id: null
metadata:
  category: canonical
  evidence_source: "Google Search Central canonical spec; Shopify canonical_url variable 2026-05"
  applicable_when: "collection pages, promotional landing pages, faceted filter pages"
---

Collection pages accessed with faceted filter parameters (?color=red&sort=price_asc), UTM tracking (?utm_source=instagram), or pagination (?page=2) produce URL variants that Google may index as separate pages, splitting PageRank. The canonical tag tells crawlers which URL is authoritative. Shopify provides the canonical_url global variable which resolves to the clean canonical URL for all page types. Pattern: `<link rel="canonical" href="{{ canonical_url }}">` in the theme layout head. For banner agent-generated promotional pages, the canonical should point to the root collection URL, not the promotional URL, unless the page has unique content merit.
