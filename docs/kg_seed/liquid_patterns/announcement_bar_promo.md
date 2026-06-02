---
title: "Announcement bar — slim promo strip with optional discount code and CTA link"
kind: liquid_pattern
brand_id: null
metadata:
  category: announcement_bar
  evidence_source: "Drive corpus — Flash Sale 'THIS WEEKEND ONLY', Nature's Touch promo patterns 2026-05"
  applicable_when: "announcement_bar placement, sitewide promotional messages"
---

Minimal announcement bar for flash sales and discount codes. Renders as a full-width strip above or below the header. Schema exposes message text, optional CTA label and URL, and background/text colour settings. Pattern derived from the corpus flash sale and nature's touch discount banners — both use a single line of copy with a CTA inline.

{% schema %}{"name":"Announcement Bar","settings":[{"type":"text","id":"message","label":"Message","default":"Flash Sale — This Weekend Only"},{"type":"text","id":"cta_label","label":"CTA label"},{"type":"url","id":"cta_url","label":"CTA URL"},{"type":"color","id":"bg_color","label":"Background","default":"#1a1a1a"},{"type":"color","id":"text_color","label":"Text","default":"#ffffff"}]}{% endschema %}

<div class="announcement-bar" style="background:{{ section.settings.bg_color }};color:{{ section.settings.text_color }};" role="banner">
  <div class="announcement-bar__inner">
    <span class="announcement-bar__message">{{ section.settings.message | escape }}</span>
    {% if section.settings.cta_label != blank %}
      <a class="announcement-bar__cta" href="{{ section.settings.cta_url }}">{{ section.settings.cta_label | escape }}</a>
    {% endif %}
  </div>
</div>

Minimum height 48px desktop, 56px mobile to meet touch target requirements for the inline CTA link.
