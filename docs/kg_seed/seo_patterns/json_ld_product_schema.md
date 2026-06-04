---
title: "JSON-LD Product schema on PDP banner pages enables Google rich results for price and availability"
kind: seo_pattern
brand_id: null
metadata:
  category: structured_data
  evidence_source: "schema.org/Product; Google Rich Results spec; Drive corpus — NaturaGlow Body Wash, Kylie Jenner PDP banners 2026-05"
  applicable_when: "product detail pages with promotional banner sections (pdp_strip, pdp_cross_sell placements)"
---

Product pages with a PDP banner (like NaturaGlow Body Wash "BUY NOW" and Kylie Jenner "COCONUT WATER LIP STAIN") are eligible for Google Shopping rich results when JSON-LD Product schema is present. Schema must include: name, image, description, brand, offers (with price, priceCurrency, availability, url). Shopify product pages should emit JSON-LD in a script tag using product.title, product.featured_image, product.description, product.selected_variant.price. Availability should map from product.available: "https://schema.org/InStock" or "https://schema.org/OutOfStock". Banner agent output for PDP pages should verify JSON-LD is present in the Lighthouse structured-data audit.
