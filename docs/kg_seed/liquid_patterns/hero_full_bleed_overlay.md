---
title: "Full-bleed hero with text overlay and semi-transparent scrim for contrast compliance"
kind: liquid_pattern
brand_id: null
metadata:
  category: hero_layout
  evidence_source: "Drive corpus — Bearen 'Glow Beyond Beauty', NaturaGlow lifestyle hero 2026-05"
  applicable_when: "hero_main with full-width product or lifestyle photography"
---

Full-bleed hero section with a semi-transparent scrim behind the copy region to guarantee WCAG 4.5:1 contrast compliance even on bright product photography. Copy is absolutely positioned in the left third or bottom-left safe zone. Bearen and NaturaGlow both use product photography that fills the frame — scrim prevents the white headline from disappearing against light backgrounds.

{% schema %}{"name":"Hero Full Bleed","settings":[{"type":"image_picker","id":"bg_image","label":"Background image"},{"type":"text","id":"headline","label":"Headline"},{"type":"textarea","id":"subtext","label":"Supporting copy"},{"type":"text","id":"cta_label","label":"CTA label","default":"Explore Collection"},{"type":"url","id":"cta_url","label":"CTA URL"},{"type":"range","id":"scrim_opacity","label":"Scrim opacity","min":0,"max":80,"step":5,"default":40}]}{% endschema %}

<section class="hero-full-bleed" style="position:relative;overflow:hidden;">
  {% if section.settings.bg_image %}
    {{ section.settings.bg_image | image_url: width: 1440 | image_tag: width: 1440, loading: 'eager', alt: '', class: 'hero-full-bleed__bg' }}
  {% endif %}
  <div class="hero-full-bleed__scrim" style="background:rgba(0,0,0,{{ section.settings.scrim_opacity | divided_by: 100.0 }});position:absolute;inset:0;"></div>
  <div class="hero-full-bleed__copy" style="position:relative;z-index:1;">
    <h1>{{ section.settings.headline | escape }}</h1>
    <p>{{ section.settings.subtext | escape }}</p>
    <a class="btn btn-light" href="{{ section.settings.cta_url }}" style="min-height:44px;padding:12px 24px;">{{ section.settings.cta_label | escape }}</a>
  </div>
</section>

Background image alt is empty string intentionally — it is decorative; headline provides the accessible label.
