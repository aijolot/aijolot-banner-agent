---
title: "Hero headlines must be at minimum 28px on 390px mobile viewports to remain legible"
kind: best_practice
brand_id: null
metadata:
  category: mobile
  evidence_source: "Drive corpus — Kylie Jenner, Bearen large-type mobile headers; WCAG 1.4.4 resize text 2026-05"
  applicable_when: "hero_main and collection_header on mobile"
---

At 390px viewport width, a hero headline at 16px is illegible in outdoor or low-contrast conditions. The beauty corpus banners that work on mobile use headlines of 28–40px — Kylie Jenner and Bearen use display type at 36–40px. Use responsive typography with CSS clamp — `font-size: clamp(28px, 6vw, 56px)` — rather than fixed sizes and separate media-query breakpoints for every step. Supporting copy should be no smaller than 14px on mobile; below 14px the 2x zoom requirement of WCAG 1.4.4 becomes triggered for a significant portion of users.
