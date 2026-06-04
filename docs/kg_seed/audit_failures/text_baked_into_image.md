---
title: "Marketing text baked into the product image is not accessible and cannot be translated or updated without re-exporting the image"
kind: audit_failure
brand_id: null
metadata:
  category: alt_text
  evidence_source: "WCAG 1.4.5; Drive corpus — beauty brand banners with text-in-image pattern 2026-05"
  applicable_when: "any banner where copy is embedded in the image file rather than rendered as HTML text"
---

Several beauty banners in the corpus show text embedded in the image file — discount percentages, product names, CTAs rendered as rasterised type. This fails WCAG 1.4.5 (Images of Text), is invisible to screen readers, cannot be indexed by search engines as text, and requires re-exporting the image for every copy change. The banner agent explicitly avoids this: image generation prompts describe photographic assets only; all marketing text (headline, body, CTA) is rendered as HTML over the image. If a product image arrives with baked-in text, it must be rejected and a clean version requested, or the text region must be cropped out with a CSS mask.
