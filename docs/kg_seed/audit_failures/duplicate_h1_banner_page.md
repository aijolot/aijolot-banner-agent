---
title: "Duplicate H1 — both the page title and the banner headline render as H1 — causes SEO dilution"
kind: audit_failure
brand_id: null
metadata:
  category: w3c
  evidence_source: "W3C HTML spec; Drive corpus — banner H1 vs page title conflict 2026-05"
  applicable_when: "hero_main banners on collection and homepage that include an H1 element"
---

When both the Shopify collection.title and the section headline render as H1 elements, crawlers see two competing H1s and may demote both in relevance scoring. Common failure pattern in beauty banners: the collection template renders an H1 with collection.title, and the collection-header banner section also uses an H1 for the section headline. Remediation: use H2 in the banner section when the page template already has an H1 (as in the BRANCY hero using h2 class "hero-slide-title" in some variants), or conditionally render H1 only when the section is the first heading on the page using a section setting. W3C validator reports "document has two main headings" with a low-severity warning that becomes a medium-severity issue for SEO tooling.
