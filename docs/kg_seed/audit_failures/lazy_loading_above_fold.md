---
title: "Applying loading='lazy' to the hero image delays LCP instead of the default eager load"
kind: audit_failure
brand_id: null
metadata:
  category: perf
  evidence_source: "Lighthouse LCP; Chrome Web Vitals spec; Drive corpus — hero image loading audit 2026-05"
  applicable_when: "hero_main banner sections — the first visible image on the page"
---

loading="lazy" tells the browser to defer image loading until the element is near the viewport. For the hero image — which IS in the viewport on page load — lazy loading actively delays the LCP element, degrading Core Web Vitals. This is the opposite of the intended behaviour. Lighthouse flags "Image elements do not have explicit width and height" and "Defer offscreen images" separately; it also flags eager-loadable images that are incorrectly marked lazy. Remediation: set loading="eager" explicitly on the primary hero image (as in the BRANCY hero HTML). Use loading="lazy" only for images below the fold — promo cards, testimonial avatars, footer images.
