---
title: "Skipping heading levels (H1 to H3, no H2) in banner sections breaks screen reader document navigation"
kind: audit_failure
brand_id: null
metadata:
  category: w3c
  evidence_source: "WCAG 1.3.1; W3C document structure; Drive corpus — multi-section homepage audit 2026-05"
  applicable_when: "homepage and collection pages with multiple banner sections"
---

When a homepage has an H1 hero headline followed by banner subsections using H3 or H4 (skipping H2), screen reader users navigating by headings encounter a broken document outline. WCAG 1.3.1 requires that structure be conveyed programmatically. Common failure on beauty homepages: the hero banner uses H1, a social proof banner uses H3 ("What Our Customers Say"), and a collection feature uses H4 — with no H2 to bridge them. Remediation: assign heading levels based on document hierarchy, not visual size. Use CSS to control visual scale independently of semantic heading level. H2 should introduce each major section of the homepage (featured collection, testimonials, brand story).
