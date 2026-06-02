# Audit Gate Thresholds

Threshold values for the performance-audit skill's quality gates.

## Lighthouse thresholds

| Metric | Pass | Warn | Fail |
|--------|------|------|------|
| Performance score | ≥ 90 | 70-89 | < 70 |
| LCP (ms) | < 1000 | 1000-2500 | > 2500 |
| CLS | < 0.1 | 0.1-0.25 | > 0.25 |
| SEO score | ≥ 90 | — | < 90 |

**Note:** In MVP, Lighthouse runs in `mock_manual` mode. Scores are seeded/manual unless Lighthouse CI is explicitly configured. Mock scores are labeled and produce a `severity: "warn"` finding.

## W3C HTML validation

| Finding | Severity |
|---------|----------|
| W3C error | `fail` |
| W3C warning | `warn` |
| W3C info | Ignored |

## JSON-LD schema validation

| Finding | Severity |
|---------|----------|
| Schema invalid | `fail` |
| Schema valid, missing optional fields | `warn` |
| Schema valid, all fields present | `pass` |

Required JSON-LD type: `PromotionalOffer`

## Asset weight budget

| 1280 WebP total weight | Severity |
|------------------------|----------|
| ≤ 300 KB | `pass` |
| 300-600 KB | `warn` |
| > 600 KB | `fail` |

Target from source design: < 80KB at 1280 WebP. The 300KB threshold allows room for complex images while flagging excess.

## AVIF handling

| Condition | Severity |
|-----------|----------|
| AVIF generated successfully | No finding |
| AVIF skipped (missing plugin) | `warn` with code `avif_skipped` |

AVIF is a progressive enhancement — its absence is a warning, not a failure.

## Retry routing decision tree (post GH-NEW7)

When status is `fail`, the Auditor sub-agent uses this logic:

```
1. Check retries count for each node
2. If retries["draft_banner_concept"] < 2 AND root_cause is creative:
   → retry_node_5 (palette contrast, copy length, prohibited words, layout)
3. If retries["render_html"] < 2 AND root_cause is rendering:
   → retry_node_8 (oversize image, missing alt, schema malformed, srcset)
4. If both nodes exhausted OR root_cause is ambiguous:
   → escalate_hitl
```

**Creative root causes:** palette contrast, copy length violations, prohibited words in output, layout mismatch
**Rendering root causes:** oversized assets, missing alt text, malformed JSON-LD, broken srcset, W3C errors

## Current decision logic (pre GH-NEW7)

In the current deterministic implementation:
- `pass` or `warn` → `"human_review_required"`
- `fail` → `"escalate_hitl"`

The Auditor sub-agent (gemini-3.5-flash) will add intelligent retry routing post GH-NEW7.
