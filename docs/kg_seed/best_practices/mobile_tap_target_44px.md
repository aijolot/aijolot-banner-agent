---
title: "CTA buttons must be at least 44×44px on mobile to meet touch target accessibility requirements"
kind: best_practice
brand_id: null
metadata:
  category: mobile
  evidence_source: "WCAG 2.5.5; Apple HIG; Drive corpus — salon booking CTAs 2026-05"
  applicable_when: "all banner CTAs rendered on mobile viewports"
---

WCAG 2.5.5 and Apple's Human Interface Guidelines both specify minimum 44×44px touch targets. Salon booking banners with "BOOKING APPOINTMENT" CTAs are high-risk for this failure because appointment links are often styled as text-only anchors without explicit padding. Set minimum `min-height: 44px; padding: 12px 24px` on all CTA anchor tags in Shopify sections. Undersized targets cause accidental misses on thumbs, reduce conversion, and fail automated Lighthouse accessibility audits — which in the banner agent pipeline triggers a performance-audit node retry.
