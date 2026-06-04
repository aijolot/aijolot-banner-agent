---
title: "Offer and SpecialAnnouncement schema mark up flash sale and promotional banners for Google rich results"
kind: seo_pattern
brand_id: null
metadata:
  category: structured_data
  evidence_source: "schema.org/Offer; schema.org/SpecialAnnouncement; Drive corpus — Flash Sale, Nature's Touch 25% Off 2026-05"
  applicable_when: "promotional banner pages and flash sale landing pages"
---

For promotional banners like the Flash Sale "THIS WEEKEND ONLY" and Nature's Touch "25% Off All Cosmetic Creams", schema.org/Offer can mark up the discount for Google Shopping rich results. Embed within the Product schema: `"offers":{"@type":"Offer","priceValidUntil":"2026-06-02","price":"...", "priceCurrency":"USD","availability":"InStock"}`. For sitewide events use schema.org/SpecialAnnouncement with `"category":"https://www.wikidata.org/wiki/Q309823"` and `"expires"` set to the offer end date. Expired schema without an end date continues to show stale discounts in rich results — always set priceValidUntil and remove or update schema when the promotion ends.
