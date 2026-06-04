---
title: "Missing lang attribute on the HTML element prevents screen readers from using the correct language and pronunciation"
kind: audit_failure
brand_id: null
metadata:
  category: w3c
  evidence_source: "WCAG 3.1.1; W3C HTML spec; Drive corpus — multilingual store consideration 2026-05"
  applicable_when: "all Shopify theme templates and banner section previews"
---

Without `<html lang="es">` (or the appropriate language code), screen readers default to the user's system language and may mispronounce content. For beauty brands targeting Spanish-speaking markets — a primary segment for many Shopify stores using the banner agent — this means Spanish copy gets read with English phoneme rules. WCAG 3.1.1 requires the language of the page to be programmatically determinable. In Shopify themes, use `<html lang="{{ request.locale.iso_code }}">` to dynamically set the lang attribute based on the active locale. Lighthouse reports missing lang as an accessibility failure in the "Internationalization" category.
