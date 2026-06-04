---
title: "Collection header banner — title, description, and optional CTA above the product grid"
kind: liquid_pattern
brand_id: null
metadata:
  category: collection_header
  evidence_source: "Drive corpus — eco skincare 'Shop Our Collection', skincare brand 'Explore Now →' 2026-05"
  applicable_when: "collection_header placement above product grid"
---

Collection page header that renders the collection title, description, and an optional discovery CTA. The eco-friendly skincare and skincare essentials banners in the corpus both use this pattern — short copy ("Discover our curated selection of eco-friendly skincare essentials, thoughtfully crafted to nourish, protect, and enhance your skin") with a discovery CTA ("Explore Now →"). Uses Shopify's native collection object for SEO-friendly title rendering.

{% schema %}{"name":"Collection Header","settings":[{"type":"image_picker","id":"header_image","label":"Header image"},{"type":"text","id":"cta_label","label":"CTA label"},{"type":"url","id":"cta_url","label":"CTA URL"}]}{% endschema %}

<section class="collection-header">
  {% if section.settings.header_image %}
    {{ section.settings.header_image | image_url: width: 1440 | image_tag: width: 1440, height: 320, loading: 'eager', alt: collection.title }}
  {% endif %}
  <div class="collection-header__copy">
    <h1 class="collection-header__title">{{ collection.title }}</h1>
    {% if collection.description != blank %}
      <div class="collection-header__desc">{{ collection.description }}</div>
    {% endif %}
    {% if section.settings.cta_label != blank %}
      <a class="btn" href="{{ section.settings.cta_url }}" style="min-height:44px;padding:12px 24px;">{{ section.settings.cta_label | escape }}</a>
    {% endif %}
  </div>
</section>

Uses collection.title as image alt to avoid duplicate H1 and to provide SEO context for the header image.
