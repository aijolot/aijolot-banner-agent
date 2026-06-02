# Scenario: Onboarding scheduled campaign

Use this as the scheduling/repeatability scenario after the primary smoke path.

## Prompt

Create an onboarding banner for new Maison customers. Goal: introduce the fragrance collection, audience new subscribers, CTA "Explorar colección", placement home hero, elegant tone, medium urgency, schedule 2026-06-10 to 2026-06-12 Asia/Bishkek.

## Expected deterministic flow

- Intake captures a complete brief or asks for the missing schedule fields.
- Schedule creation is shown only after approval in the backend state machine.
- Static deterministic retrieval can cite onboarding/promo examples.
- A/B/C variants are deterministic/demo-labeled and safe to repeat.
- No cron automation is required for the chosen demo path; scheduled state can be shown via API/service response.

## Demo constraints

- Deterministic fallback is acceptable and expected without credentials.
- Live due-publish cron is optional and not required for this scenario.
- Shopify publish/unpublish remains manual-only unless safe credentials are configured.
- Lighthouse and performance metrics are manual/mock/non-live.
- PDF/Figma/brandbook import and custom model/persona are non-MVP for this scenario.
- AVIF is audit-labeled skipped in the smoke path.
