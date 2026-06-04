---
title: "Missing canonical URL on promotional landing pages causes duplicate content dilution"
kind: audit_failure
brand_id: null
metadata:
  category: w3c
  evidence_source: "Google Search Central canonical spec; Drive corpus — promotional banner pages 2026-05"
  applicable_when: "standalone promotional pages and banner preview pages"
---

Promotional banner pages — flash sale landing pages, seasonal collection pages — often have multiple accessible URLs: with and without UTM parameters, with pagination, or with faceted filter parameters. Without a canonical tag, Google treats each URL variant as a separate page and splits ranking signals across them. Lighthouse reports missing canonical as a warning. Remediation: in the Shopify theme layout head, render `<link rel="canonical" href="{{ canonical_url }}">` — Shopify provides canonical_url as a global variable that resolves correctly for collections, products, and pages. For banner agent-generated standalone pages, set the canonical explicitly to the root collection or product URL.
