---
title: "Mobile-first stacked hero — image top, copy below, CTA guaranteed above fold at 390px"
kind: liquid_pattern
brand_id: null
metadata:
  category: hero_layout
  evidence_source: "Drive corpus — Kylie Jenner product launch, Bearen mobile pattern 2026-05"
  applicable_when: "hero_main on mobile-primary storefronts, 390px viewport"
---

Mobile-first hero stack that guarantees the CTA appears above fold at 390×844 iPhone 14 viewport. Product image is constrained to 60% of viewport height (~470px) so that headline + copy + CTA fit in the remaining 40% (~318px). No text overlay — copy is below the image in document order, which also ensures correct reading flow for screen readers. Used by Kylie Jenner product launch and Bearen banners in mobile view.

{% schema %}{"name":"Mobile Stack Hero","settings":[{"type":"image_picker","id":"product_image","label":"Product image"},{"type":"text","id":"headline","label":"Headline"},{"type":"textarea","id":"subtext","label":"Supporting copy"},{"type":"text","id":"cta_label","label":"CTA label","default":"Shop Now"},{"type":"url","id":"cta_url","label":"CTA URL"}]}{% endschema %}

<section class="hero-stack">
  <div class="hero-stack__image" style="max-height:60vh;overflow:hidden;">
    {% if section.settings.product_image %}
      {{ section.settings.product_image | image_url: width: 390 | image_tag: width: 390, loading: 'eager', alt: section.settings.headline, style: 'width:100%;height:100%;object-fit:cover;' }}
    {% endif %}
  </div>
  <div class="hero-stack__copy" style="padding:20px 16px;">
    <h1 style="font-size:clamp(28px,6vw,40px);margin:0 0 8px;">{{ section.settings.headline | escape }}</h1>
    <p style="margin:0 0 16px;">{{ section.settings.subtext | escape }}</p>
    <a class="btn btn-dark" href="{{ section.settings.cta_url }}" style="min-height:44px;padding:12px 24px;display:inline-block;">{{ section.settings.cta_label | escape }}</a>
  </div>
</section>

clamp(28px,6vw,40px) ensures headline is legible at all viewport widths without fixed breakpoints. loading: 'eager' for LCP on the first visible image.
