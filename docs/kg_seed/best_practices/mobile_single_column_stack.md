---
title: "All split hero layouts must collapse to a single-column stack on mobile — product first or copy first based on campaign goal"
kind: best_practice
brand_id: null
metadata:
  category: mobile
  evidence_source: "Drive corpus — BRANCY hero col-12 col-md-6 Bootstrap pattern 2026-05"
  applicable_when: "hero banners with split layout at desktop"
---

The BRANCY hero HTML uses Bootstrap col-12 (full-width mobile) collapsing from col-md-6 (half-width desktop ≥ 768px), correctly stacking to single column below 768px. Stack order should be: product image first for product launch and catalog campaigns where the visual drives the story; copy first for brand awareness and promotional campaigns where the message is the hook. Never render two equal-height columns side by side at 390px — both columns become 195px wide, making product images and text illegible and failing WCAG minimum size requirements.
