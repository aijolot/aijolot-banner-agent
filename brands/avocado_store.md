---
id: avocado_store
name: Avocado Store
palette:
- name: Forest
  hex: '#1F4D2E'
- name: Avocado
  hex: '#7CB342'
- name: Cream
  hex: '#F4F1E8'
- name: Charcoal
  hex: '#22281F'
- name: Coral pop
  hex: '#FF6B5C'
color_system:
  primary:
    key: primary
    label: Forest
    hex: '#1F4D2E'
    usage_hint: Main brand green for identity, hero anchors, and dark natural backgrounds.
    agent_hint: Prefer for dominant brand moments, headline contrast, and organic visual weight.
    variants:
    - name: Forest
      hex: '#1F4D2E'
      usage_hint: Dark hero background
      source: seed_migration
    - name: Charcoal
      hex: '#22281F'
      usage_hint: Dark text
      source: seed_migration
    - name: Cream
      hex: '#F4F1E8'
      usage_hint: Light text on forest
      source: seed_migration
  secondary:
    key: secondary
    label: Avocado
    hex: '#7CB342'
    usage_hint: Fresh support green for secondary surfaces, product accents, and natural balance.
    agent_hint: Use to soften forest-heavy layouts and add fresh grocery energy without overpowering CTAs.
    variants:
    - name: Avocado
      hex: '#7CB342'
      usage_hint: Fresh accent fill
      source: seed_migration
    - name: Cream
      hex: '#F4F1E8'
      usage_hint: Soft background
      source: seed_migration
    - name: Forest
      hex: '#1F4D2E'
      usage_hint: Text on light surfaces
      source: seed_migration
  tertiary:
    key: tertiary
    label: Coral pop
    hex: '#FF6B5C'
    usage_hint: Warm accent reserved for CTAs, promotional badges, and high-attention details.
    agent_hint: Use sparingly for CTA and badge emphasis; avoid full coral backgrounds.
    variants:
    - name: Coral pop
      hex: '#FF6B5C'
      usage_hint: CTA fill
      source: seed_migration
    - name: Avocado
      hex: '#7CB342'
      usage_hint: CTA hover
      source: seed_migration
    - name: Cream
      hex: '#F4F1E8'
      usage_hint: CTA text
      source: seed_migration
typography:
  display: Space Grotesk
  body: Inter
voice:
  tone:
  - Fresh
  - Friendly
  - Confident
  prohibited_words:
  - cheap
  - guys
  - crazy deal
  required_phrases:
  - free shipping over $50
logo_url: https://cdn.avocadostore.example/logo.svg
image_style_directives:
- Natural daylight, soft shadows
- Product centered, generous negative space
- Organic textures (wood, linen, stone)
shopify:
  store_domain: avocado-store.myshopify.com
  theme_id: '128934771'
  default_placement: hero
---

# Avocado Store — Brand Context

Sustainable home & kitchen goods. The brand leans warm, natural, and a little
playful. Banners should feel like a sunny morning kitchen — never loud or
discount-y. The coral accent is reserved for CTAs only.
