---
title: "Design banners mobile-first at 390px viewport and expand to desktop, not the reverse"
kind: best_practice
brand_id: null
metadata:
  category: layout
  evidence_source: "Drive corpus — BRANCY hero col-12 col-md-6 Bootstrap grid; 390px Shopify standard 2026-05"
  applicable_when: "all Shopify banner placements"
---

The Shopify mobile viewport at 390px is the most constrained canvas — if the banner works here, it works everywhere. Start with a single-column stack: product image at top (square crop, 390×390), headline and copy below, CTA at bottom above the fold. The BRANCY hero uses col-12 (full-width on mobile) collapsing to col-md-6 (half-width on desktop ≥ 768px) — this is the correct mobile-first approach. Designing desktop-first and scaling down typically produces text that is too small or CTAs that fall below the fold on mobile, as seen in several beauty banners in the corpus that required manual override styles for the 390px breakpoint.
