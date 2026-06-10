---
id: maison
name: Maison
palette:
  - name: Noir base
    hex: "#0B1622"
  - name: Steel navy
    hex: "#1E3A52"
  - name: Boss gold
    hex: "#C9A24B"
  - name: Ivory
    hex: "#F5F2EC"
  - name: Rosé accent
    hex: "#B23A6B"
color_system:
  primary:
    key: primary
    label: Noir base
    hex: "#0B1622"
    usage_hint: Premium dark foundation for hero backgrounds, headline contrast, and luxury depth.
    agent_hint: Prefer for dominant brand surfaces, product framing, and high-contrast premium layouts.
    variants:
      - name: Noir base
        hex: "#0B1622"
        usage_hint: Dark hero background
        source: seed_migration
      - name: Steel navy
        hex: "#1E3A52"
        usage_hint: Layered dark panel
        source: seed_migration
      - name: Ivory
        hex: "#F5F2EC"
        usage_hint: Light text on noir
        source: seed_migration
  secondary:
    key: secondary
    label: Steel navy
    hex: "#1E3A52"
    usage_hint: Cool support color for secondary surfaces, glassmorphism depth, and refined balance.
    agent_hint: Use for gradient depth, panels, and supporting fields around the noir base.
    variants:
      - name: Steel navy
        hex: "#1E3A52"
        usage_hint: Secondary background
        source: seed_migration
      - name: Ivory
        hex: "#F5F2EC"
        usage_hint: Soft background
        source: seed_migration
      - name: Noir base
        hex: "#0B1622"
        usage_hint: Dark text
        source: seed_migration
  tertiary:
    key: tertiary
    label: Boss gold
    hex: "#C9A24B"
    usage_hint: Luxury accent for CTAs, premium badges, highlights, and small conversion moments.
    agent_hint: Use sparingly for CTA, badge, and promo emphasis while preserving premium restraint.
    variants:
      - name: Boss gold
        hex: "#C9A24B"
        usage_hint: CTA fill
        source: seed_migration
      - name: Rosé accent
        hex: "#B23A6B"
        usage_hint: Badge accent
        source: seed_migration
      - name: Ivory
        hex: "#F5F2EC"
        usage_hint: CTA text
        source: seed_migration
typography:
  display: Space Grotesk
  body: Inter
voice:
  tone:
    - Premium
    - Confident
    - Direct
  prohibited_words:
    - cheap
    - discount blowout
  required_phrases:
    - "logo always uppercase"
logo_url: https://cdn.maison.example/maison-mark.svg
image_style_directives:
  - At least one bottle visible
  - No rainbow gradients
  - CTA in AA+ contrast
shopify:
  store_domain: maison-store.myshopify.com
  theme_id: "100200300"
  default_placement: hero
---

# Maison — Brand Context

Luxury fragrance retailer (the prototype demo brand, Hugo Boss campaign). Keeps
the original glassmorphism palette. The product is sacred — never distort the
bottle, and headlines stay short and assured.
