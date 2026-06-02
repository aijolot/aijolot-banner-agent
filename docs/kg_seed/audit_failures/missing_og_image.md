---
title: "Missing og:image meta tag on banner-heavy pages reduces click-through from social shares"
kind: audit_failure
brand_id: null
metadata:
  category: lighthouse
  evidence_source: "Open Graph protocol spec; Drive corpus — beauty brand social sharing audit 2026-05"
  applicable_when: "homepage and collection pages with promotional banners"
---

When a customer shares a banner-heavy homepage or collection page, the social platform uses og:image to generate the preview card. Without an explicit og:image tag, platforms fall back to the first image found on the page — often a navigation icon or thumbnail — producing an unattractive share card. For beauty brands like those in the corpus (Bearen, Kylie Jenner, Drunk Elephant), the hero banner image is the highest-quality visual asset and should be set as og:image. Remediation: in the theme layout head, render og:image using the first collection image or a Shopify metafield-defined share image, sized 1200×630px. Lighthouse audit reports missing og:image as a "Social" category failure.
