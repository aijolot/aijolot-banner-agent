---
title: "CTA button must achieve 4.5:1 contrast ratio against its background"
kind: best_practice
brand_id: null
metadata:
  category: cta
  evidence_source: "WCAG 2.1 SC 1.4.3; Drive corpus — BRANCY 'btn-border-dark' pattern 2026-05"
  applicable_when: "all banner CTAs with a button container"
---

WCAG 1.4.3 requires 4.5:1 contrast for normal text and 3:1 for large text (18pt+ or 14pt bold). In the beauty corpus, the best-performing pattern is a dark button on a light background — the BRANCY hero uses a "btn-border-dark" class, giving black button text against a white or light background. Avoid placing a white CTA button directly over a light product background: the button disappears on mobile in partial sunlight. When the hero uses a full-bleed product image, add a semi-transparent scrim (rgba 0,0,0 / 0.35) behind the CTA button to guarantee contrast compliance.
