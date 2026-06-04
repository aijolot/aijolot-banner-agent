---
title: "Low contrast CTA button fails WCAG 1.4.3 and reduces click visibility in outdoor conditions"
kind: audit_failure
brand_id: null
metadata:
  category: contrast
  evidence_source: "WCAG 2.1 SC 1.4.3; Drive corpus — light CTA on light background failures 2026-05"
  applicable_when: "banner CTAs with colour-matched or low-contrast button styles"
---

WCAG 1.4.3 requires 4.5:1 contrast ratio for normal text and 3:1 for large text (18pt+ bold). Common failure in beauty banners: white or cream CTA button placed over a light product background — the "btn-light" class on a white background. Lighthouse colour-contrast audit reports this as a critical failure with a specific element selector. Remediation: switch to a dark button (BRANCY's "btn-border-dark") or add a minimum scrim of rgba(0,0,0,0.35) behind the button area when the background is variable (full-bleed image). Test contrast with the actual rendered background colour, not the CSS colour value, because product images produce varying backgrounds across different page loads.
