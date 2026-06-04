---
title: "Hero split section — product image column + copy column with Bootstrap col-md-6 grid"
kind: liquid_pattern
brand_id: null
metadata:
  category: hero_layout
  evidence_source: "Drive corpus — BRANCY cosmetics hero HTML snippet 2026-05"
  applicable_when: "hero_main Shopify section with product image and headline copy"
---

Real-world pattern derived from BRANCY cosmetics hero. Uses Bootstrap responsive grid: col-12 (full-width) on mobile collapses to col-md-6 (half-width) on desktop >= 768px. Copy column contains h1 headline, p description, a.btn CTA. Product image uses eager loading (LCP element). Schema exposes headline, subtext, cta_label, cta_url, product_image as merchant-editable settings.

{% schema %}{"name":"Hero Split","settings":[{"type":"text","id":"headline","label":"Headline"},{"type":"textarea","id":"subtext","label":"Supporting copy"},{"type":"text","id":"cta_label","label":"CTA label","default":"Shop Now"},{"type":"url","id":"cta_url","label":"CTA URL"},{"type":"image_picker","id":"product_image","label":"Product image"}]}{% endschema %}

<section class="hero-split">
  <div class="container">
    <div class="row align-items-center">
      <div class="col-12 col-md-6">
        <div class="hero-copy">
          <h1 class="hero-title">{{ section.settings.headline | escape }}</h1>
          <p class="hero-desc">{{ section.settings.subtext | escape }}</p>
          <a class="btn btn-dark" href="{{ section.settings.cta_url }}">{{ section.settings.cta_label | escape }}</a>
        </div>
      </div>
      <div class="col-12 col-md-6">
        {% if section.settings.product_image %}
          {{ section.settings.product_image | image_url: width: 841 | image_tag: width: 841, height: 832, loading: 'eager', alt: section.settings.headline }}
        {% endif %}
      </div>
    </div>
  </div>
</section>

Key notes: loading: 'eager' on hero image for LCP optimisation; alt attribute set to headline text; col-12 col-md-6 stacks cleanly at 390px mobile viewport.
