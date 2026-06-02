# Scenario: Avocado Black Friday

Primary hackathon path. Use this when time is short.

## Prompt

Create a Black Friday homepage hero for Avocado Store: 30% off selected products, VIP customers first, premium but urgent tone, CTA "Comprar ahora", deadline 2026-11-27.

## Expected deterministic flow

- Brand/store context resolves from seeded/Markdown fallback.
- Product resources use the locked seeded Maison/Hugo Boss fixture in the smoke harness; this is a resource-cache fixture, not live Avocado Shopify sync.
- Intake completes the brief in one turn.
- Static deterministic retrieval surfaces prior promo/VIP learnings.
- A/B/C variants are deterministic/demo-labeled:
  - A: bold offer-first hero.
  - B: split product/story layout.
  - C: VIP exclusivity treatment.
- Performance/Lighthouse numbers, if shown, are mock/manual/non-live.

## Demo constraints

- Deterministic fallback is acceptable and expected without credentials.
- PDF/Figma/brandbook input is partial/mock and not used here.
- Custom model/persona is non-MVP; use seeded brand voice.
- AVIF is audit-labeled skipped in this smoke path.
- Shopify publish/unpublish is manual-only unless safe credentials are configured.
