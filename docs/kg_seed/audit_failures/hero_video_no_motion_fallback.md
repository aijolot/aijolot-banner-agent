---
title: "Video hero banners without a prefers-reduced-motion fallback cause distress for users with vestibular disorders"
kind: audit_failure
brand_id: null
metadata:
  category: w3c
  evidence_source: "WCAG 2.3.3; WCAG 2.1 SC 2.3.1; Drive corpus — animated banner patterns 2026-05"
  applicable_when: "hero banners with CSS animations, video backgrounds, or auto-playing carousels"
---

Auto-playing video backgrounds and parallax scroll animations in hero banners can trigger vestibular disorder symptoms (dizziness, nausea) for users with motion sensitivity. WCAG 2.3.3 recommends providing a mechanism to pause or stop animations. The prefers-reduced-motion media query gives a CSS-only solution. For Shopify video hero sections, add `@media (prefers-reduced-motion: reduce) { .hero-video { display: none; } .hero-fallback-image { display: block; } }` and always provide a static fallback image. Carousel auto-play should default to off or respect prefers-reduced-motion, with a play/pause toggle as the accessible override.
