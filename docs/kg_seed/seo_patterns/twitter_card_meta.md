---
title: "Twitter Card meta tags for summary_large_image display the hero banner when shared on X (Twitter)"
kind: seo_pattern
brand_id: null
metadata:
  category: social_meta
  evidence_source: "Twitter/X Card spec; Drive corpus — Kylie Jenner, Bearen social presence 2026-05"
  applicable_when: "all Shopify pages with hero banners for brands with an X/Twitter presence"
---

Kylie Jenner Cosmetics and similar beauty brands with strong Twitter/X presence benefit from summary_large_image cards that display the hero banner image prominently in the feed. Required tags: `<meta name="twitter:card" content="summary_large_image">`, `<meta name="twitter:title" content="{{ page_title }}">`, `<meta name="twitter:description" content="{{ page.description | strip_html | truncate: 160 }}">`, `<meta name="twitter:image" content="{{ page_image | img_url: '1200x630', crop: 'center' }}">`. Twitter image must be at least 1200×630px and under 5MB. When og:image is set, Twitter falls back to it — but explicit twitter:image tags allow a different image optimised for the 2:1 Twitter crop ratio.
