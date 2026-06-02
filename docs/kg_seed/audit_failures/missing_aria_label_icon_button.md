---
title: "Icon-only buttons in banner navigation (carousel controls, close buttons) lack ARIA labels"
kind: audit_failure
brand_id: null
metadata:
  category: w3c
  evidence_source: "WCAG 2.1 SC 4.1.2; Drive corpus — BRANCY swiper carousel navigation 2026-05"
  applicable_when: "banner sections with carousel navigation, close buttons, or icon-only interactive elements"
---

The BRANCY hero uses a Swiper.js carousel with navigation buttons. Carousel previous/next buttons are typically rendered as SVG arrows or CSS icons with no visible text label. Without an aria-label attribute, screen readers announce these as "button" with no description of the action. WCAG 4.1.2 requires all interactive elements to have an accessible name. Remediation: add `aria-label="Next slide"` / `aria-label="Previous slide"` to carousel navigation buttons. Similarly, any close button rendered as an ×  character must have `aria-label="Close"`. Lighthouse accessibility audit flags these as "Links do not have a discernible name" failures.
