---
title: "PDP promo strip — compact offer banner below product info with single CTA"
kind: liquid_pattern
brand_id: null
metadata:
  category: pdp_strip
  evidence_source: "Drive corpus — NaturaGlow 'BUY NOW' product copy pattern 2026-05"
  applicable_when: "pdp_strip placement on product detail pages"
---

Compact full-width strip rendered below the product info section on PDP pages. Communicates a secondary offer or cross-sell. NaturaGlow's pattern — product name + one-line benefit description + BUY NOW — is the minimum viable template. Strip height is 90px desktop, 110px mobile per placement schema constraints.

{% schema %}{"name":"PDP Strip","settings":[{"type":"text","id":"eyebrow","label":"Eyebrow label (e.g. product name)"},{"type":"text","id":"message","label":"Offer message"},{"type":"text","id":"cta_label","label":"CTA label","default":"Buy Now"},{"type":"url","id":"cta_url","label":"CTA URL"},{"type":"color","id":"bg_color","label":"Background","default":"#f7f7f7"}]}{% endschema %}

<div class="pdp-strip" style="background:{{ section.settings.bg_color }};display:flex;align-items:center;justify-content:space-between;padding:12px 24px;min-height:90px;" role="complementary" aria-label="{{ section.settings.message | escape }}">
  <div class="pdp-strip__copy">
    {% if section.settings.eyebrow != blank %}<span class="pdp-strip__eyebrow">{{ section.settings.eyebrow | escape }}</span>{% endif %}
    <p class="pdp-strip__message">{{ section.settings.message | escape }}</p>
  </div>
  <a class="btn btn-dark" href="{{ section.settings.cta_url }}" style="min-height:44px;padding:12px 24px;white-space:nowrap;">{{ section.settings.cta_label | escape }}</a>
</div>

role="complementary" with aria-label makes the strip accessible as a landmark. flex layout keeps CTA right-aligned and message left-aligned at all viewports.
