# Source Technical Design v0.1 Alignment Notes

Source PDF: `/Users/pk/Downloads/Aijolot-Shopify Banner Agent — Technical Design (Hackathon v0.1)-290526-031138.pdf`
Extracted text: `docs/architecture/source-technical-design-v0.1-extracted.md`
Current plan updated: `docs/plans/2026-05-28-banner-creator-mvp.md`

## What the source design adds to the current plan

1. A 12-node agent graph:
   - load_brand_context
   - intake_campaign_idea
   - capture_user_personalization
   - research_best_practices
   - draft_banner_concept
   - generate_image
   - optimize_assets
   - render_html
   - audit
   - human_review
   - schedule_or_publish
   - publish_to_shopify

2. Brand context as versioned Markdown/YAML files in repo.
   - The source design uses `brands/{brand_id}.md` with skill-like frontmatter.
   - This should coexist with Supabase persistence: repo files are portable seed/versioned source of truth; Supabase stores runtime/store-specific records.

3. Render output is more concrete.
   - Standalone HTML preview for the admin panel/demo.
   - Shopify Liquid section/snippets for storefront rendering.
   - Text remains HTML/Liquid, not baked into images.
   - Images should avoid text/logos/faces.

4. Personalization mechanism is more concrete.
   - Source design prioritizes Shopify Liquid and `customer.tags`.
   - Our newer plan also mentions cookies/context. Alignment: MVP should support `customer.tags` first, then cookie/context rules later where theme constraints allow.

5. Asset optimization is required.
   - Generate WebP/AVIF/srcset sizes: roughly 320, 768, 1280, 1920.
   - Keep weight cap target: `<80KB @1280 WebP` where feasible.
   - Produce fallback JPG and alt text suggestion.

6. Audit is a formal graph node, not just logging.
   - HTML validation.
   - Lighthouse performance/LCP/CLS.
   - Schema.org JSON-LD validation.
   - Breakpoint rendering checks.
   - Max two upstream retries; then escalate to human.

7. Scheduling had an original pg_cron design.
   - Source design: Supabase `scheduled_banners` + pg_cron fires publish function every minute.
   - Newer decision: Shopify theme reads active dates for MVP.
   - Alignment: keep theme-enforced schedule as local MVP path, but model scheduler tables/services so pg_cron publishing can be added without redesign.

8. Publishing is more concrete.
   - Source design uses Shopify Admin GraphQL `themeFilesUpsert` for Liquid section/snippets/assets.
   - Newer decision says one custom section reads config.
   - Alignment: use `themeFilesUpsert` to install/update the reusable section/snippets, then publish banner campaign config via metafield/metaobject JSON consumed by that section.

9. Observability fields are specified.
   - `event`, `node`, `trace_id`, `session_id`, `brand_id`, `timestamp`, `duration_ms`, `cost_usd`, `audit_pass`, `review_decision`, `shopify_section_id`.
   - Store in Supabase audit log and keep ADK traces/Cloud Logging later.

10. Success criteria are specified.
   - Intake to publish under 10 minutes.
   - Audit pass first try >= 70%.
   - HITL approval first try >= 60%.
   - Lighthouse Performance >= 90 for published banners.
   - LCP on 4G mobile < 1.0s target.
   - Schedule accuracy +/- 5 minutes.
   - Reusable brand context for at least 2 demo stores.
   - At least 3 personalization variants in demo.

## Decisions from newer context that supersede the source design

1. Frontend is Next.js + Tailwind, not Streamlit.
   - The source design mentions Streamlit as fast HITL UI.
   - Current team split says another team member owns frontend; backend should support a Next admin panel.

2. Backend API is FastAPI.
   - Source design focuses on ADK/agent graph and repo structure, but does not require a specific web framework.

3. Shopify auth is token-based for MVP.

4. Supabase Auth is used for admin users/team members.

5. Images are stored in Supabase Storage first.

6. Initial development is local-first; deployment is deferred.

## Resolved follow-up items

1. Image generation provider:
   - Default to Gemini image generation.
   - Keep the `image_generation` adapter compatible with Vertex/Imagen because the source design had that as an open spike.

2. Approval policy:
   - MVP requires all assigned reviewers to approve.

3. Brand sources:
   - Intended UX is UI-based brand context editing, so backend should expose brand context APIs.
   - Repo Markdown files remain useful for seeded/demo/versioned examples.

4. Shopify target resource fetching:
   - MVP should support home, collections, products, and pages.

5. Cost controls:
   - Track usage/costs and add soft rate guard warnings per 15-minute window.
   - Warning threshold is 20 image generations per authenticated user per 15 minutes.
   - Do not hard-cap daily usage during hackathon dev.

6. Reviewer auth:
   - Reviewers use Supabase Auth; no anonymous reviewer links for MVP.

7. License:
   - MIT is approved/required for the public stable hackathon repo.

## Resolved final blocking items

1. Brand context API depth:
   - Implement full backend CRUD for brand profiles.

2. Shopify resource picker:
   - MVP uses list/select for collections, products, and pages.
   - Search/autocomplete is deferred unless requested after consultation.

## Remaining open items

1. Whether Shopify products/pages/collections search/autocomplete should be added after MVP list/select is validated.
