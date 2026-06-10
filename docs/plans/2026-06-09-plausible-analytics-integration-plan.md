# Plausible Storefront Analytics Integration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task when the user approves execution.

**Goal:** Track published Shopify banner impressions and CTA clicks with Plausible, display those live metrics inside Aijolot Studio, and feed the agent with aggregated performance signals so it can recommend improvements for active banners and guide future banner generation.

**Architecture:** MVP analytics is storefront-only. Published Aijolot banners emit two privacy-safe Plausible custom events: `Banner: Impression` and `Banner: CTA Clicked`. The FastAPI backend fetches aggregate Plausible Stats API data by campaign/revision/variant/placement, stores normalized snapshots in the existing performance layer, exposes them to the Studio Performance stage, and runs a scheduled/triggered analysis job that generates optimization proposals. Studio-internal behavior tracking is explicitly post-MVP.

**Tech Stack:** Shopify Liquid/theme files, Plausible browser script/custom events, Plausible Stats API v2, FastAPI `/api/v1`, Supabase/Postgres, static React UMD/Babel frontend, existing performance/optimization proposal UI.

---

## Current repository reality

- The frontend is a static React prototype in `frontend/`, loaded by `frontend/index.html`.
- The visible Studio flow is: Placement → Brief → Art direction/Plan → Generation → Canvas/review → Performance.
- `docs/architecture/frontend-backend-contract.md` documents current `/api/v1` adapters and fallback rules.
- `frontend/PerformanceStage.jsx` already distinguishes backend/manual/mock/seed/agent metrics from live analytics.
- Backend includes performance endpoints under `/api/v1/campaigns/{campaign_id}/performance`, manual snapshots, and optimization proposals.
- Shopify publishing is handled through controlled theme files/publishing services and must remain gated by approval/schedule rules.
- Current git branch contains unrelated brand-color work. Do not mix analytics implementation with that branch unless explicitly approved.

## MVP scope decision

### In scope

1. Track banner impressions on the Shopify storefront.
2. Track CTA clicks on the Shopify storefront.
3. Fetch Plausible aggregate stats into Aijolot backend.
4. Display impressions/clicks/CTR inside Studio Performance stage.
5. Persist normalized analytics snapshots so the agent has historical context.
6. Add a cron/scheduled job or backend trigger that analyzes the fetched stats.
7. Generate actionable optimization proposals for:
   - currently active/published content, and
   - future banner generation guidance.
8. Preserve existing no-live/manual/mock/seed/agent labels when Plausible is unavailable.

### Explicitly out of scope for MVP

- Studio-internal product analytics events.
- Studio funnel tracking.
- Add-to-cart tracking.
- Purchase/revenue attribution.
- Google Search Console.
- Slack/email reporting.
- Public/shared dashboards.
- Session replay/person-level tracking.

## What we can track with high value

### Storefront event 1: `Banner: Impression`

Triggered when a published Aijolot banner becomes visible in the storefront viewport.

Value:
- Measures reach/exposure.
- Allows CTR calculation when paired with CTA clicks.
- Shows which placements and page types receive traffic.
- Gives the agent enough signal to avoid optimizing low-sample banners too early.

Trigger rule:
- Use `IntersectionObserver`.
- Fire once per banner instance per pageview.
- Recommended threshold: 50% visible for at least a short debounce window, e.g. 500ms, to avoid accidental scroll-by impressions.

### Storefront event 2: `Banner: CTA Clicked`

Triggered when the main CTA inside the banner is clicked.

Value:
- Measures engagement intent.
- Enables CTR = clicks / impressions.
- Lets Studio compare campaign/revision/variant/placement performance.
- Provides the primary signal for agent optimization.

Trigger rule:
- Fire immediately on click.
- Do not block navigation.
- If navigation races the event, use Plausible’s normal browser call and keep the payload tiny.

## Event taxonomy v1

Prefix public storefront events with `Banner:`.

| Event | Trigger | MVP | Props |
|---|---|---:|---|
| `Banner: Impression` | Banner visible in viewport once per pageview/banner | Yes | `campaign_key`, `revision_key`, `variant_key`, `placement_key`, `page_type`, `target_type`, `segment_key` |
| `Banner: CTA Clicked` | Main CTA clicked | Yes | same as impression + `cta_type` |
| `Banner: Add To Cart` | Shopify add-to-cart attributed to banner | No / post-MVP | same + attribution props |
| `Banner: Purchase` | Purchase attributed to banner | No / post-MVP | same + revenue if explicitly supported |
| `Banner: Load Metric` | Optional load/render sampling | No / post-MVP | `placement_key`, `page_type`, `weight_bucket`, `render_ms_bucket` |

## Custom property strategy

### Required MVP props

- `campaign_key`: stable public campaign identifier or short hash.
- `revision_key`: stable public revision identifier, revision number, or short hash.
- `variant_key`: stable public variant key, e.g. `A`, `B`, `C`, `vip`, `default`.
- `placement_key`: `announcement_bar`, `hero_main`, `promo_card`, `collection_header`, `pdp_strip`, etc.
- `page_type`: `home`, `collection`, `product`, `search`, `page`.
- `target_type`: `store`, `collection`, `product`, `search`, `page`.
- `segment_key`: broad segment label if applicable, otherwise `default`.
- `cta_type`: `primary`, `secondary`, `product`, `collection`, or `unknown` for click events.

### Optional MVP props

- `campaign_status`: `published`, `scheduled`, `active`, etc. only if easily available and low-cardinality.
- `content_type`: `promo`, `launch`, `seasonal`, `clearance`, etc. only if already structured.
- `layout_key`: broad layout template key if useful for agent guidance.

### Never send

- Email, name, username, phone, address.
- Shopify customer ID, order ID, checkout token, cart token.
- Raw campaign brief text.
- Prompt text.
- Brand guideline notes that may contain private client info.
- API keys/tokens/secrets.
- Full raw UUIDs if they create noisy/high-cardinality dashboards; prefer short public hashes or revision numbers.

## Data flow

```text
Published Shopify storefront
  -> Aijolot banner tracking script
  -> Plausible custom events
  -> Plausible Stats API v2
  -> FastAPI analytics sync service
  -> Supabase performance snapshots / analytics summaries
  -> Studio Performance stage
  -> Agent analytics analyzer
  -> Optimization proposals / future generation guidance
```

## Storage model recommendation

Keep Plausible as the aggregate analytics source, but copy normalized snapshots into Aijolot so the agent has durable, queryable history.

Recommended tables/records, adjust to existing schema before implementation:

1. `campaign_performance_snapshots` or existing performance snapshot table
   - `campaign_id`
   - `revision_id`
   - `variant_key`
   - `placement_key`
   - `page_type`
   - `date_range_start`
   - `date_range_end`
   - `impressions`
   - `clicks`
   - `ctr`
   - `source = plausible`
   - `sample_quality`
   - `created_at`

2. `campaign_optimization_proposals` or existing optimization proposal table
   - `campaign_id`
   - `source_revision_id`
   - `trigger_source = plausible_cron | plausible_threshold | manual`
   - `segment_key`
   - `rationale`
   - `recommended_change`
   - `supporting_metrics`
   - `status = draft | sent_to_approval | dismissed | applied`

3. Optional future guidance/memory table
   - `placement_key`
   - `page_type`
   - `content_type`
   - `winning_patterns`
   - `losing_patterns`
   - `confidence`
   - `last_updated_at`

If current performance tables already support these shapes, reuse them instead of adding duplicate tables.

## Studio UX target

### Performance stage should show

For the selected campaign/revision/variant:
- Impressions.
- CTA clicks.
- CTR.
- Date range used.
- Source label: `Plausible live analytics` or existing no-live fallback.
- Sample quality warning if impressions are too low.
- Breakdown by variant/segment when available.
- Trend over time when enough data exists.

### Agent recommendation card should show

- What the agent observed.
- Why it matters.
- Suggested change.
- Confidence level.
- Supporting metrics.
- Action buttons:
  - create V2 proposal,
  - send to approval,
  - dismiss,
  - use as guidance for next content.

Example recommendation:

```text
Observation: PDP strip banners with product-image-right layout have 1.8x higher CTR than centered copy variants over the last 7 days.

Suggested change: Create a V2 for this active banner using a stronger product-right layout, shorter headline, and higher-contrast CTA.

Evidence: 4,280 impressions, 196 clicks, 4.58% CTR vs 2.51% baseline.
Confidence: Medium, sample size sufficient.
```

## Agent analysis rules

The agent must not blindly suggest changes from tiny samples.

Recommended thresholds:
- Below 100 impressions: do not recommend content changes; label as insufficient data.
- 100-499 impressions: allow low-confidence observations only.
- 500+ impressions: allow medium-confidence recommendations.
- 1,000+ impressions and clear difference: allow high-confidence recommendations.

Analysis dimensions:
- campaign/revision CTR.
- variant CTR.
- placement CTR.
- page type CTR.
- segment CTR when `segment_key` exists.
- trend direction over last 7/14/30 days.
- active content vs historical baseline for same placement/page type.

Recommendation types:
- CTA copy too weak / low CTR.
- Placement underperforming compared with same campaign on another page type.
- Variant A/B/C winner detected.
- Segment-specific variant underperforming.
- Active banner needs V2 proposal.
- Future generation should prefer a winning layout/CTA/content pattern.

Hard guardrails:
- Do not claim causality; phrase as observed correlation.
- Do not optimize if sample size is too low.
- Do not use PII or person-level inference.
- Do not auto-publish changes. All generated V2 proposals still go through review/approval/publish workflow.
- Do not overwrite active content. Create a new revision/proposal.

## Trigger model

### Cron/scheduled sync

Recommended MVP:
- Run a backend scheduled job every 6 or 12 hours.
- Fetch Plausible stats for active/published campaigns from the last 7 days and optionally last 30 days.
- Store normalized snapshots.
- Run analyzer after snapshots are stored.
- Create/update optimization proposals only when thresholds are met.

### Event/threshold trigger

Optional after cron works:
- Trigger analysis when a campaign crosses 500 impressions.
- Trigger analysis when CTR drops below baseline by a chosen threshold.
- Trigger analysis when one variant clearly outperforms another.

### Manual trigger

Useful for demo/debug:
- Add backend endpoint or script to run analytics sync/analyzer for one campaign.
- Studio can expose a `Refresh Plausible analytics` button only if safe and useful.

## Proposed implementation phases

### Phase 0: Confirm analytics assumptions

Objective: lock decisions before implementation.

Decide:
1. Plausible Cloud vs Community Edition.
2. One Plausible site per Shopify storefront/domain.
3. How to configure Plausible site id/domain per store.
4. Public key format for `campaign_key`, `revision_key`, and `variant_key`.
5. Cron mechanism: app scheduler, external cron hitting an endpoint, or platform scheduler.
6. Minimum impression threshold for agent recommendations.

Recommended defaults:
- Use one Plausible site per storefront domain.
- Use public short hashes/keys instead of raw UUIDs in Plausible props.
- Start with 7-day and 30-day aggregate windows.
- Use 500 impressions as the first recommendation threshold.

### Phase 1: Add storefront tracking to published banner output

Objective: published Shopify banners emit impressions and CTA clicks.

Likely files:
- `backend/app/services/shopify/liquid_payload_builder.py`
- `backend/app/services/shopify/theme_files.py`
- `backend/app/services/shopify/publisher.py`
- `frontend/banner_template.js` only if preview parity needs the same data attributes.
- Tests near Shopify publisher/liquid payload builder.

Implementation shape:
- Ensure Plausible script is present on the storefront or document that it must already exist.
- Add safe `data-aijolot-*` attributes to the banner wrapper and CTA.
- Add a tiny storefront tracking script in the theme asset/section:
  - no-op if `window.plausible` is missing,
  - observe banner visibility,
  - emit `Banner: Impression`,
  - listen to CTA click,
  - emit `Banner: CTA Clicked`.

Verification:
- Published/preview markup escapes all attributes.
- Impression fires once per pageview/banner instance.
- CTA click fires and navigation still works.
- Script no-ops when Plausible is absent.
- No PII/secrets appear in markup or events.

### Phase 2: Add backend Plausible Stats API client

Objective: backend can fetch aggregate impressions/clicks by campaign/revision/variant/placement.

Likely files:
- Create: `backend/app/services/analytics/plausible_client.py`
- Create: `backend/app/services/analytics/plausible_mapper.py`
- Modify: `backend/app/core/settings.py`
- Tests under `backend/tests/unit`.

Implementation shape:
- Store API key only in backend env/settings.
- Query Plausible Stats API v2 for:
  - metric counts for `Banner: Impression`,
  - metric counts for `Banner: CTA Clicked`,
  - breakdowns by safe event props.
- Map API responses into normalized internal records.
- Handle missing config as disabled/no-live.
- Handle API failures as visible fallback, not crashes.

Verification:
- API key never reaches frontend.
- Mocked Plausible responses map to expected impressions/clicks/CTR.
- Missing config returns disabled state.
- Failed Plausible requests are surfaced safely.

### Phase 3: Persist Plausible performance snapshots

Objective: keep durable analytics history for Studio and the agent.

Likely files:
- Existing performance repository/service files under `backend/app/services` and `backend/app/db/repositories`.
- Existing performance schemas under `backend/app/schemas`.
- Supabase migration only if current schema cannot store source/range/breakdown/supporting metrics.
- Tests under `backend/tests/api` and `backend/tests/integration` if DB-backed.

Implementation shape:
- Upsert or append snapshots per campaign/revision/variant/date range.
- Store `source = plausible` and `data_source_label = Plausible live analytics`.
- Calculate CTR server-side as `clicks / impressions` with zero-impression guard.
- Store sample quality/confidence bucket.

Verification:
- Snapshots persist and reload.
- Duplicate cron runs do not create misleading duplicates for same range/key.
- Zero impressions does not divide by zero.
- No cross-team/store leakage.

### Phase 4: Display Plausible metrics in Studio Performance stage

Objective: users can analyze live impressions/clicks/CTR inside Studio.

Likely files:
- Modify: `backend/app/api/v1/performance.py`
- Modify: `backend/app/schemas/performance.py`
- Modify: `frontend/PerformanceStage.jsx`
- Possibly modify: `frontend/lib.jsx` if API envelope needs fields.

Implementation shape:
- Existing Performance API returns Plausible-backed latest snapshot when available.
- Frontend shows:
  - impressions,
  - clicks,
  - CTR,
  - source label,
  - date range,
  - sample quality,
  - trend/breakdown if available.
- Keep current fallback labels when no live analytics exists.

Verification:
- Performance stage shows `Plausible live analytics` only for Plausible-backed data.
- Manual/mock/seed/agent data is still labeled no-live.
- Backend API returns stable shape for frontend.
- Browser smoke accepts both live and no-live states.

### Phase 5: Add analytics sync + analyzer job

Objective: scheduled/triggered backend process fetches Plausible data and creates optimization guidance.

Likely files:
- Create: `backend/app/services/analytics/sync_service.py`
- Create: `backend/app/services/analytics/analyzer.py`
- Create: `backend/app/services/analytics/recommendation_rules.py`
- Create/modify cron/scheduler integration depending on existing scheduler architecture.
- Modify existing performance/optimization proposal service.
- Tests under `backend/tests/unit` and `backend/tests/api`.

Implementation shape:
- Find active/published campaigns eligible for analytics sync.
- Fetch Plausible stats for each configured storefront/domain.
- Persist snapshots.
- Run analyzer on fresh + historical snapshots.
- Generate optimization proposal records when thresholds are met.
- Do not auto-apply or auto-publish.

Verification:
- Job is idempotent.
- Low sample sizes produce no recommendation.
- Clear underperformance creates a draft proposal with supporting metrics.
- Re-running the job updates/keeps existing proposal instead of spamming duplicates.
- Failures in one campaign do not stop the whole job.

### Phase 6: Feed analytics guidance into future generation

Objective: generation can use historical performance as guidance on what works and what does not.

Likely files:
- Existing agent context/retrieval/generation services under `backend/app/agents` and `backend/app/services/banners`.
- New analytics guidance service if needed.

Implementation shape:
- Before drafting new banner concepts, retrieve relevant performance patterns by:
  - placement,
  - page type,
  - content type,
  - brand/store,
  - segment if applicable.
- Inject compact guidance into agent prompt/state:
  - winning patterns,
  - weak patterns,
  - confidence/sample size,
  - do-not-overfit caveat.
- Keep analytics guidance advisory, not hard constraints.

Verification:
- If no sufficient analytics exists, generation behaves normally.
- If guidance exists, prompt/state includes compact aggregate insights only.
- No raw PII/customer data appears in prompts.
- Tests verify analytics guidance is selected by placement/page type and threshold.

## Plausible query plan

Use Stats API v2 from the backend.

Needed queries:

1. Count impressions for a campaign/revision/date range.
2. Count CTA clicks for same keys/date range.
3. Breakdown by `variant_key`.
4. Breakdown by `placement_key`.
5. Breakdown by `page_type`.
6. Optional time-series grouped by day for trend.

Derived metrics:

```text
ctr = clicks / impressions
click_delta = current_period_clicks - previous_period_clicks
ctr_delta = current_period_ctr - previous_period_ctr
sample_quality = insufficient | low | medium | high
```

## Acceptance criteria

- Published banners emit `Banner: Impression` and `Banner: CTA Clicked` to Plausible.
- Events include only safe allowlisted props.
- Impression event fires once per banner per pageview.
- CTA click tracking does not break navigation.
- Backend can fetch Plausible aggregate stats without exposing API keys to frontend.
- Studio Performance stage displays impressions, clicks, and CTR from Plausible when configured.
- No-live/manual/mock/seed/agent fallbacks remain truthfully labeled.
- Analytics snapshots persist for agent analysis/history.
- Cron/trigger job can analyze snapshots and create optimization proposals.
- Agent recommendations include sample size/confidence and never auto-publish.
- Future generation can optionally consume aggregate analytics guidance.
- Studio-internal analytics are not implemented in MVP.

## Open questions

1. Plausible Cloud or self-hosted Community Edition?
2. Where will each store’s Plausible domain/site id/API token mapping live?
3. What public key format should represent campaign/revision/variant in Plausible props?
4. Which scheduler should run the cron: app-level scheduler, external cron endpoint, or deployment platform scheduler?
5. What minimum impression threshold should block recommendations? Default proposal: 500.
6. Should the first agent recommendations be created as draft optimization proposals only, or also surfaced as inline Performance-stage insights?

## Recommended MVP implementation order

1. Storefront tracking script + safe banner data attributes.
2. Plausible backend client + mapper.
3. Performance snapshot persistence from Plausible stats.
4. Studio Performance UI using Plausible live metrics.
5. Scheduled sync/analyzer that creates draft optimization proposals.
6. Future-generation guidance using aggregate winning/losing patterns.

## Post-MVP backlog

- Studio-internal product analytics.
- Add-to-cart tracking.
- Purchase/revenue attribution.
- Public/shared dashboards.
- Google Search Console integration.
- Slack/email reports.
- Advanced load/render metric sampling.
