---
title: "Promo card with discount badge — percentage overlay on product image with headline and CTA"
kind: liquid_pattern
brand_id: null
metadata:
  category: promo_card
  evidence_source: "Drive corpus — Botanical Republic 'Get Discount Up To 25%', Nature's Touch '25% Off' 2026-05"
  applicable_when: "promo_card placement, homepage promotional grid blocks"
---

Medium-format promotional card with a discount badge overlaid on the product image and a headline + CTA below. Pattern derived from Botanical Republic and Nature's Touch promo banners. Badge renders as an absolute-positioned pill on the top-right of the image. Percentage is a schema setting so merchants can update without code changes.

{% schema %}{"name":"Promo Card","settings":[{"type":"image_picker","id":"image","label":"Product image"},{"type":"text","id":"badge","label":"Discount badge (e.g. 25% OFF)"},{"type":"text","id":"headline","label":"Headline"},{"type":"text","id":"subtext","label":"Supporting copy"},{"type":"text","id":"cta_label","label":"CTA label","default":"Browse Product"},{"type":"url","id":"cta_url","label":"CTA URL"}]}{% endschema %}

<div class="promo-card">
  <div class="promo-card__image-wrap" style="position:relative;">
    {% if section.settings.image %}
      {{ section.settings.image | image_url: width: 600 | image_tag: width: 600, height: 300, loading: 'lazy', alt: section.settings.headline }}
    {% endif %}
    {% if section.settings.badge != blank %}
      <span class="promo-card__badge" aria-label="{{ section.settings.badge }}" style="position:absolute;top:12px;right:12px;background:#e53e3e;color:#fff;padding:4px 10px;border-radius:20px;font-weight:700;">{{ section.settings.badge | escape }}</span>
    {% endif %}
  </div>
  <div class="promo-card__copy">
    <h2>{{ section.settings.headline | escape }}</h2>
    <p>{{ section.settings.subtext | escape }}</p>
    <a class="btn" href="{{ section.settings.cta_url }}" style="min-height:44px;padding:12px 24px;">{{ section.settings.cta_label | escape }}</a>
  </div>
</div>

Badge has aria-label for screen readers. Image uses loading: 'lazy' as it is below-fold content.
