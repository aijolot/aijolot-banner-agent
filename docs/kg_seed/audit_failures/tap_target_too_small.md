---
title: "CTA tap target smaller than 44×44px on mobile causes missed taps and fails WCAG 2.5.5"
kind: audit_failure
brand_id: null
metadata:
  category: mobile
  evidence_source: "WCAG 2.5.5; Apple HIG; Drive corpus — salon booking CTA links 2026-05"
  applicable_when: "all banner CTA buttons and text links on mobile viewports"
---

Salon booking banners in the corpus — "BOOKING APPOINTMENT >>" — are high-risk for undersized tap targets because they are often rendered as inline text links with default browser padding. On a mobile device at 390px, a text link without padding has a touch area of approximately 16–18px height — less than half the required 44px. Lighthouse accessibility audit reports undersized tap targets with the computed dimensions. Remediation: add explicit CSS `min-height: 44px; min-width: 44px; padding: 12px 24px; display: inline-block` to all anchor CTAs in banner sections, as applied in the PDPstrip and mobile stack hero patterns.
