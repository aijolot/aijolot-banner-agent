---
title: "Testimonial banner — named customer quote with role attribution and product reference"
kind: liquid_pattern
brand_id: null
metadata:
  category: social_proof
  evidence_source: "Drive corpus — cruelty-free brand testimonial 'Nusrat Jahan, Product designer' 2026-05"
  applicable_when: "homepage social proof section, brand awareness banners for cold audiences"
---

Named testimonial banner derived from the cruelty-free brand example: quote "I'm so happy to find a cruelty-free brand that actually works. My skin feels soft and hydrated!" — Nusrat Jahan, Product designer. Schema accepts quote text, attribution name, attribution role, and optional product reference. blockquote + cite provides semantic HTML for screen readers.

{% schema %}{"name":"Testimonial","settings":[{"type":"textarea","id":"quote","label":"Quote text"},{"type":"text","id":"name","label":"Customer name"},{"type":"text","id":"role","label":"Customer role or descriptor"},{"type":"image_picker","id":"avatar","label":"Customer photo (optional)"},{"type":"text","id":"product_ref","label":"Product referenced (optional)"}]}{% endschema %}

<section class="testimonial-banner" aria-label="Customer testimonial">
  <blockquote class="testimonial-banner__quote">
    <p>{{ section.settings.quote | escape }}</p>
    <footer>
      {% if section.settings.avatar %}<img src="{{ section.settings.avatar | image_url: width: 64 }}" width="64" height="64" alt="{{ section.settings.name | escape }}" loading="lazy" class="testimonial-banner__avatar">{% endif %}
      <cite class="testimonial-banner__attribution">
        <strong>{{ section.settings.name | escape }}</strong>
        {% if section.settings.role != blank %}<span>{{ section.settings.role | escape }}</span>{% endif %}
      </cite>
    </footer>
  </blockquote>
</section>

cite element is the correct semantic container for attribution. quote must be verbatim customer text; do not paraphrase as that changes the testimonial's legal status.
