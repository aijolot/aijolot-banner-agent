---
title: "BreadcrumbList JSON-LD schema on collection and product pages with banners enables Google breadcrumb rich results"
kind: seo_pattern
brand_id: null
metadata:
  category: structured_data
  evidence_source: "schema.org/BreadcrumbList; Google Rich Results spec; Drive corpus — beauty collection pages 2026-05"
  applicable_when: "collection and product pages with collection_header or pdp_strip banner placements"
---

Google shows breadcrumb trails in search results when BreadcrumbList schema is present — replacing the raw URL with a readable path like "Home > Skincare > Body Wash." For beauty collection pages (Bearen Collections, NaturaGlow Body Wash PDP), this increases CTR by giving users context before clicking. JSON-LD pattern: `{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"{{ shop.url }}"},{"@type":"ListItem","position":2,"name":"{{ collection.title }}","item":"{{ shop.url }}{{ collection.url }}"}]}`. Add a third item for product pages with the product.title and product.url.
