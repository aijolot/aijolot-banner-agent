---
title: "Missing alt text on product images in banner sections fails WCAG 1.1.1 and hurts SEO"
kind: audit_failure
brand_id: null
metadata:
  category: alt_text
  evidence_source: "WCAG 2.1 SC 1.1.1; Drive corpus — beauty banner image audit 2026-05"
  applicable_when: "all Shopify banner sections containing img elements"
---

Product images in hero and promo banners must have descriptive alt text that conveys the image content to screen reader users. Empty alt="" is appropriate only for decorative images — a product image is never purely decorative, as it communicates what the product looks like. Common failure pattern: the Liquid image_tag helper is called without an alt parameter, defaulting to an empty string. Remediation: set alt to the product title or the section headline (as in BRANCY hero HTML which uses the headline text as alt). Lighthouse accessibility audit flags missing alt text as a critical issue; it also removes the image from Google Image search indexing.
