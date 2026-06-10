---
title: "Resize category banners for mobile — a desktop landscape banner becomes a viewport-eating block on phones"
kind: best_practice
brand_id: null
metadata:
  category: mobile
  evidence_source: "Baymard Institute — category page & mobile UX research (baymard.com/learn/ecommerce-category-page; baymard.com/blog/ecommerce-homepage-ux)"
  applicable_when: "category and collection header banners rendered on mobile viewports"
---

A large landscape banner designed for desktop can consume the entire mobile viewport, pushing all subcategory navigation off the first screen and forcing unnecessary scroll before the user can act. Hero and category banners therefore need mobile-specific sizing, not a naive scale-down of the desktop asset — reduce banner height aggressively on mobile so navigation and the first product/subcategory tiles remain visible above the fold. On small screens it is even more important to surface the different product types immediately, so favor compact, scrollable category chips/strips (horizontally swipeable subcategory pills) over a tall image banner. The banner agent should generate a distinct mobile crop/height for any category header and prefer chip-style navigation on mobile rather than letting a single banner dominate the first screen.
