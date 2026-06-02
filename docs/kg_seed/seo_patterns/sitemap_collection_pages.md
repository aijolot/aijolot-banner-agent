---
title: "Collection and promotional landing pages must appear in sitemap.xml for Google crawl discovery"
kind: seo_pattern
brand_id: null
metadata:
  category: crawl
  evidence_source: "Google Search Central sitemap spec; Shopify sitemap.xml 2026-05"
  applicable_when: "collection pages and promotional landing pages with hero banners"
---

Shopify automatically generates sitemap.xml including all published collections, products, and pages. Banner agent-generated promotional landing pages (flash sale pages, seasonal collection pages) are only included in the sitemap if they are published as Shopify pages or collections — not if they exist only as section configurations on an existing page. For standalone promotional pages, ensure they are created as Shopify page objects so they appear in sitemap.xml and can be crawled. Noindex meta tags must not be applied to pages with unique promotional content — noindex is appropriate only for preview, staging, and draft versions of pages.
