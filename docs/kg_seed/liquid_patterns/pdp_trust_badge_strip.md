---
title: "PDP trust-cue micro-banner strip — icon + label confidence cues directly under the buy button"
kind: liquid_pattern
brand_id: null
metadata:
  category: pdp_strip
  evidence_source: "Shopify Design micro-banner / trust-badge strategy (shopify.design); see best_practice pdp_micro_banner_trust_cues"
  applicable_when: "pdp placement immediately below the add-to-cart button"
---

Compact, non-promotional trust strip rendered directly beneath Add to Cart. Each cue is an icon plus a 2–4 word label (Secure checkout, Free shipping, 30-day returns). Distinct from the PDP promo strip: this carries confidence cues, not an offer, and must read quieter than the CTA above it. Renders as a wrap-friendly flex row so 2–4 cues fit on mobile without overflow.

{% schema %}{"name":"PDP Trust Strip","max_blocks":4,"settings":[{"type":"color","id":"icon_color","label":"Icon/text color","default":"#444"}],"blocks":[{"type":"cue","name":"Trust cue","settings":[{"type":"text","id":"label","label":"Label","default":"Secure checkout"},{"type":"text","id":"icon","label":"Inline SVG or emoji","default":"🔒"}]}]}{% endschema %}

<ul class="pdp-trust-strip" style="list-style:none;display:flex;flex-wrap:wrap;gap:16px;padding:12px 0;margin:0;color:{{ section.settings.icon_color }};" aria-label="Purchase guarantees">
  {% for block in section.blocks %}
    <li class="pdp-trust-strip__cue" style="display:flex;align-items:center;gap:6px;font-size:13px;" {{ block.shopify_attributes }}>
      <span class="pdp-trust-strip__icon" aria-hidden="true">{{ block.settings.icon }}</span>
      <span>{{ block.settings.label | escape }}</span>
    </li>
  {% endfor %}
</ul>

Icons are aria-hidden (decorative); the text label carries meaning. The strip is a list with an aria-label landmark so screen readers announce it as a grouped set of guarantees. Font size and weight are deliberately below the buy button so the strip reassures without competing for the click.
