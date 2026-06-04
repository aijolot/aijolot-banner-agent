---
title: "Render-blocking CSS in banner sections delays First Contentful Paint and LCP"
kind: audit_failure
brand_id: null
metadata:
  category: perf
  evidence_source: "Lighthouse Performance audit; Core Web Vitals FCP; 2026-05"
  applicable_when: "Shopify banner sections with inline stylesheets or synchronous CSS imports"
---

Shopify section stylesheets that are loaded synchronously in the document head block rendering until the CSS is parsed. This delays First Contentful Paint and LCP for hero banners, which are the primary CWV element on most beauty storefronts. Common failure pattern: a section includes a large stylesheet with CSS for components that are not visible in the hero (accordion styles, modal styles) loaded unconditionally. Remediation: use Shopify's native stylesheet lazy loading for non-critical section CSS — include the section stylesheet inside the {% stylesheet %} tag rather than the head content block, so it loads asynchronously. Hero-critical styles (typography, layout, CTA button) should be inlined or included in the main theme stylesheet to avoid a separate network request.
