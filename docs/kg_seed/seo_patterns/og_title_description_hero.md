---
title: "Open Graph title and description meta tags for hero banner pages improve social share click-through"
kind: seo_pattern
brand_id: null
metadata:
  category: social_meta
  evidence_source: "Open Graph protocol; Drive corpus — beauty brand social sharing audit 2026-05"
  applicable_when: "homepage, collection, and promotional landing pages with hero banners"
---

When a hero banner page is shared on Facebook, WhatsApp, or LinkedIn, the platform reads og:title and og:description to build the preview card. Without these tags the platform falls back to the page title and first paragraph of text — which on a beauty storefront may be navigation text or lorem ipsum from an unseeded section. Recommended pattern for Shopify banner pages: `<meta property="og:title" content="{{ page_title }} — {{ shop.name }}">` and `<meta property="og:description" content="{{ page.description | default: collection.description | strip_html | truncate: 160 }}">`. For hero banners built by the banner agent, the campaign brief's goal field should populate og:description. Target og:title under 60 characters to avoid truncation in most platforms.
