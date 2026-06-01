# Aijolot Banner Agent hackathon demo script

This is the constrained, repeatable demo path for Task 21. It is intentionally scoped so the demo can run twice after reset with either real providers or the deterministic fallback.

## One-command reset and smoke

From the repo root:

```bash
python3 scripts/reset-demo-data.py --local-only
python3 scripts/smoke-demo-flow.py
python3 scripts/smoke-demo-flow.py
```

Optional real database reset, only when Supabase CLI and Docker are available:

```bash
python3 scripts/reset-demo-data.py --supabase
```

If `--supabase` fails or is skipped, do not claim a Supabase reset occurred. The smoke path remains offline and deterministic.

## Chosen demo path

Primary scenario: `demo/scenarios/avocado-black-friday.md`.

1. Start from clean deterministic demo state.
2. Open the app/backend demo environment.
3. Use the demo auth identity/team/store from the smoke script:
   - team: `00000000-0000-0000-0000-000000000001`
   - store: `00000000-0000-0000-0000-000000000101`
4. Show seeded brand context plus the locked seeded resource fixture. The deterministic smoke fixture currently uses the seeded Maison/Hugo Boss product cache as the Shopify resource example; do not present that as live Avocado Shopify sync.
5. Run intake for a Black Friday campaign.
6. Review generated brief fields and deterministic A/B/C variants.
7. Show static KG recommendations and non-live performance notes.
8. If real Shopify credentials are configured, manually verify publish/unpublish. Otherwise state that the smoke path uses deterministic fallback and does not touch Shopify.

## Explicit non-MVP/demo constraints

These constraints prevent overclaiming during the hackathon demo:

- PDF/Figma/brandbook import: partial/mock only. Markdown brand files are supported; PDF/Figma extraction is not part of the chosen smoke path.
- Live Shopify resource sync: demo is locked to seeded locked resources unless credentials and an explicit sync/import step are run outside the smoke path.
- Custom model/persona: non-MVP. The demo uses fixed brand context/personality from seed/Markdown content.
- AVIF: dependency support exists in backend image tooling, but AVIF is audit-labeled skipped in the chosen smoke path; WebP/PNG-safe assets are sufficient for demo.
- Lighthouse: no automated Lighthouse run in smoke. Metrics shown in demo are mock/manual/non-live and must be labeled as such.
- A/B/C layout variants: generated as deterministic/demo-labeled variants for the smoke path, not live model exploration.
- KG retrieval: static deterministic retrieval in smoke. Embedding/vector RAG can be seeded separately but is not required for the chosen demo path.

## Real provider mode checklist

Only use this section when credentials are already configured in the operator environment. Do not paste, print, or embed secrets.

- Supabase: run `python3 scripts/reset-demo-data.py --supabase`; confirm the script reports `PASSED`. For the Avocado story, either stay in deterministic fallback mode or explicitly import/sync the Avocado brand/resources after reset; the real Supabase seed currently includes the locked Maison/Hugo Boss resource fixture used by smoke.
- Gemini/image provider: enable only if provider env is present; otherwise leave fallback mode.
- Shopify: verify target theme/store is safe, publish once, confirm metafield/theme asset changed, unpublish, then confirm cleanup.
- Lighthouse: if needed, run manually and label results as manual metrics.

## Pass criteria

- `python3 scripts/reset-demo-data.py --local-only` exits 0.
- `python3 scripts/smoke-demo-flow.py` exits 0 twice in a row without network credentials.
- Backend tests pass in the configured backend Python environment.
- Any unavailable external verification is reported with the exact reason, not marked as passed.
