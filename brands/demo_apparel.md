---
id: demo_apparel
name: Demo Apparel
palette:
  - name: Ink
    hex: "#0E0E10"
  - name: Bone
    hex: "#EDE8E0"
  - name: Electric
    hex: "#3D5AFE"
  - name: Slate
    hex: "#2B2F36"
  - name: Acid
    hex: "#D4FF3F"
color_system:
  primary:
    key: primary
    label: Ink
    hex: "#0E0E10"
    usage_hint: Core black for bold identity, high-contrast type, and dominant streetwear framing.
    agent_hint: Prefer for primary text, stark backgrounds, and minimal premium-street layouts.
    variants:
      - name: Ink
        hex: "#0E0E10"
        usage_hint: Dark hero background
        source: seed_migration
      - name: Slate
        hex: "#2B2F36"
        usage_hint: Muted dark panel
        source: seed_migration
      - name: Bone
        hex: "#EDE8E0"
        usage_hint: Reverse text
        source: seed_migration
  secondary:
    key: secondary
    label: Bone
    hex: "#EDE8E0"
    usage_hint: Warm neutral for editorial backgrounds, cards, and breathing room around bold graphics.
    agent_hint: Use as the clean support surface for minimal compositions and strong ink typography.
    variants:
      - name: Bone
        hex: "#EDE8E0"
        usage_hint: Soft background
        source: seed_migration
      - name: Slate
        hex: "#2B2F36"
        usage_hint: Secondary text
        source: seed_migration
      - name: Ink
        hex: "#0E0E10"
        usage_hint: Text on bone
        source: seed_migration
  tertiary:
    key: tertiary
    label: Electric
    hex: "#3D5AFE"
    usage_hint: High-energy accent for CTAs, active states, drops, and small high-attention elements.
    agent_hint: Use sparingly for CTA emphasis, badges, and campaign highlights; pair with ink or bone.
    variants:
      - name: Electric
        hex: "#3D5AFE"
        usage_hint: CTA fill
        source: seed_migration
      - name: Acid
        hex: "#D4FF3F"
        usage_hint: Badge accent
        source: seed_migration
      - name: Ink
        hex: "#0E0E10"
        usage_hint: CTA text
        source: seed_migration
typography:
  display: Space Grotesk
  body: Inter
voice:
  tone:
    - Bold
    - Minimal
    - Street
  prohibited_words:
    - elegant
    - luxurious
    - timeless
  required_phrases: []
logo_url: https://cdn.demoapparel.example/wordmark.svg
image_style_directives:
  - High-contrast studio lighting
  - Model-forward, dynamic poses
  - Monochrome backdrops with one acid accent
shopify:
  store_domain: demo-apparel.myshopify.com
  theme_id: "98233410"
  default_placement: coll_top
---

# Demo Apparel — Brand Context

Direct-to-consumer streetwear. The voice is sharp and confident, never
aspirational-luxury. Acid green is the signature accent — use it sparingly on
type or CTA, never as a full background.
