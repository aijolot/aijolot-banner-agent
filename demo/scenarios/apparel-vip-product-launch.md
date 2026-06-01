# Scenario: Apparel VIP product launch

Use this if the audience wants a retail/product-launch story instead of the Black Friday path.

## Prompt

Create a Demo Apparel product launch banner for VIP customers. Feature the limited capsule, audience VIP members, CTA "Ver lanzamiento", placement product page strip, aspirational premium tone, high urgency, deadline 2026-09-15.

## Expected deterministic flow

- Brand context resolves from seeded/Markdown fallback for `demo_apparel`.
- Product/page/collection resources are seeded locked resources unless a real sync was explicitly run.
- Static deterministic retrieval supplies VIP/exclusivity learnings.
- A/B/C variants are deterministic/demo-labeled:
  - A: product-first launch strip.
  - B: VIP access framing.
  - C: urgency/countdown framing.
- Mock/manual performance guidance can be shown but must be labeled non-live.

## Demo constraints

- Deterministic fallback is acceptable and expected without credentials.
- PDF/Figma/brandbook import is partial/mock and not part of this flow.
- Custom model/persona is non-MVP; use fixed seeded brand voice.
- AVIF is audit-labeled skipped in smoke.
- Lighthouse is not automated in smoke; manual/mock only.
- Shopify publish/unpublish is manual-only unless safe credentials are configured.
