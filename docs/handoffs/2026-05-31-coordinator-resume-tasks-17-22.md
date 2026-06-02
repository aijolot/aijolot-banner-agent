# Aijolot Banner Agent Coordinator Handoff: Resume Tasks 17-22

Generated: 2026-05-31 20:38:39 CST
Project root: `/Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent`
Branch at handoff: `feature/backend-mvp-implementation`
Remote: `origin https://github.com/aijolot/aijolot-banner-agent.git`
Active plan: `docs/plans/2026-05-28-banner-creator-mvp.md`

Use this file as the first context document in a fresh session to continue as the coordinator for the remaining backend MVP tasks.

---

## 1. Fresh-session startup instructions

In the new session, ask the agent to load these Hermes skills before acting:

1. `aijolot-banner-agent-project`
2. `subagent-driven-development`
3. `test-driven-development` if implementation subagents are expected to write code/tests
4. `requesting-code-review` if doing final broad review

Then do this pre-flight before starting Task 17:

```bash
cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
git status --short --branch
git log --oneline -8
. backend/.venv/bin/activate
cd backend
pytest -q
cd ..
```

Expected baseline at handoff:

```text
Branch: feature/backend-mvp-implementation
Latest commits:
5fbb4ec feat: add regeneration revision flow
a4da315 feat: add approval workflow
aeeac33 feat: add preview rendering and audit gate
c8d4c6c feat: add image asset optimization and storage
7cb396d feat: add image provider and usage guard
bae91b4 feat: implement context and concept skills
5db47bb feat: track generation run progress
28b6754 feat: wire gemini intake fallback

Full backend tests: 199 passed, 3 skipped, 2 pre-existing Pydantic warnings
```

The two known warnings are in `backend/app/agents/state.py`:

- `Concept.copy` shadows `BaseModel.copy`
- class-based Pydantic config deprecation

They predate Tasks 15-16 and are not blockers unless Task 21/22 chooses to clean them.

---

## 2. Coordinator operating mode

Continue using the established coordinator flow:

1. Read the active plan section for the current task.
2. Mark the current task `in_progress` in the Hermes todo list.
3. Dispatch a fresh implementation subagent with the full task text and project constraints.
4. Parent coordinator verifies implementation directly:
   - `git status --short`
   - read changed files
   - focused tests from the task spec
   - full `pytest -q`
   - `git diff --check`
   - secret/unsafe-execution smoke checks
5. Dispatch two review subagents:
   - spec compliance review
   - quality/security review
6. Fix all critical/important issues and rerun verification.
7. Request final narrow review after fixes if review found blockers.
8. Add a completion note to `docs/plans/2026-05-28-banner-creator-mvp.md` under the completed task.
9. Mark the task completed in the Hermes todo list.
10. Commit the task with a focused commit message.
11. Move to the next task.

Do not skip review loops. Do not rely only on subagent self-report. Re-read files and run tests in the parent session.

Suggested parent verification command after each backend task:

```bash
cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
rm -f backend/uv.lock
. backend/.venv/bin/activate
cd backend
pytest <focused-tests> -v
pytest -q
cd ..
git diff --check
git diff | grep '^+' | grep -iE "(api_key|secret|password|token|passwd)\s*=\s*['\"][^'\"]{6,}['\"]" || true
git diff | grep '^+' | grep -E "os\.system\(|subprocess.*shell=True" || true
git diff | grep '^+' | grep -E "\beval\(|\bexec\(" || true
git diff | grep '^+' | grep -E "pickle\.loads?\(" || true
```

---

## 3. Current completed scope

Tasks 11-16 are complete and committed on `feature/backend-mvp-implementation`.

Completed tasks visible in current Hermes todo:

- task-11: Brand/personalization/best-practices/concept ADK skills
- task-12: Image provider, image generation skill, usage soft guard
- task-13: Asset optimization and Supabase Storage upload
- task-14: HTML/Liquid rendering and audit skills
- task-15: Review comments, refinement requests, approval workflow
- task-16: Regeneration/revision path

Key recent completions:

### Task 15 commit

Commit: `a4da315 feat: add approval workflow`

Implemented approval/comment/refinement schemas, repositories, services, and API routes. MVP approval policy is `all_members`. Duplicate reviewers are rejected. Explicit revision IDs must belong to the campaign. Closed threads reject late approval/change actions. Real endpoints fail closed until Task 19 request-scoped auth/client wiring.

### Task 16 commit

Commit: `5fbb4ec feat: add regeneration revision flow`

Implemented revision/regeneration service, banner layout/variant repositories, variant selection, regeneration, and revision-listing endpoints. Regeneration creates a new generation run and new selected campaign revision, preserves old revisions, supersedes the previously selected revision, updates queued refinement requests to `succeeded`, uses deterministic A/B/C layout fallback, does not call Gemini/Shopify, escapes prompt text before HTML preview markers, and does not reuse old preview storage paths.

Important Task 16 safety behavior:

- `RevisionService.configured_service()` fails closed for service-role writes unless `AIJOLOT_TRUSTED_DEMO_SERVICE_ROLE_WRITES=1` is explicitly set.
- Task 19 still owns request-scoped auth/RLS alignment.

---

## 4. Remaining active task list

Current remaining tasks:

- [ ] task-17. Task 17: Scheduling and Shopify publishing
- [ ] task-18. Task 18: Static frontend integration with backend APIs
- [ ] task-19. Task 19: Auth/team context and RLS alignment
- [ ] task-20. Task 20: Performance/evolutionary memory API
- [ ] task-21. Task 21: Demo hardening and carry-over gap closure
- [ ] task-22. Task 22: Documentation cleanup and handoff

Recommended next action: start Task 17.

---

## 5. Task 17 full task text

Source: `docs/plans/2026-05-28-banner-creator-mvp.md`

### Task 17: Implement scheduling and Shopify publishing

Goal: Schedule approved campaigns and publish campaign config to Shopify through a controlled Liquid section.

Expected result: Approved campaigns can be scheduled, theme files can be idempotently installed, campaign config can be published/unpublished, and publish jobs are recorded.

Files:

- Create: `backend/app/schemas/schedules.py`
- Create: `backend/app/db/repositories/schedules.py`
- Create: `backend/app/db/repositories/scheduled_banners.py`
- Create: `backend/app/db/repositories/publish_jobs.py`
- Create: `backend/app/services/banners/schedule_service.py`
- Modify: `backend/app/agents/skills/schedule-or-publish-route/impl.py`
- Modify: `backend/app/agents/tools/shopify.py`
- Modify: `backend/app/agents/skills/shopify-theme-publish/impl.py`
- Create: `backend/app/services/shopify/client.py`
- Create: `backend/app/services/shopify/theme_files.py`
- Create: `backend/app/services/shopify/metafields.py`
- Create: `backend/app/services/shopify/publisher.py`
- Create: `backend/app/api/v1/schedules.py`
- Create: `backend/app/api/v1/publishing.py`
- Modify: `backend/app/api/v1/router.py`
- Optional migration: `supabase/migrations/<timestamp>_cron_due_publish.sql`
- Test: `backend/tests/unit/test_schedule_service.py`
- Test: `backend/tests/unit/test_shopify_publisher.py`
- Test: `backend/tests/api/test_schedules.py`
- Test: `backend/tests/api/test_publishing.py`

Endpoints:

- `POST /api/v1/campaigns/{campaign_id}/schedule`
- `PATCH /api/v1/campaigns/{campaign_id}/schedule`
- `POST /api/v1/campaigns/{campaign_id}/schedule/cancel`
- `POST /api/v1/campaigns/{campaign_id}/publish`
- `POST /api/v1/campaigns/{campaign_id}/unpublish`

Implementation notes:

- MVP default: publish active dates in config and let Shopify Liquid show/hide.
- pg_cron due-publish is optional because local `pg_cron`/`pg_net` exist, but do not require cron for demo unless explicitly chosen.
- Search-result placement must either publish correctly or return a clear unsupported error.

Verification:

```bash
cd backend
pytest tests/unit/test_schedule_service.py -v
pytest tests/unit/test_shopify_publisher.py -v
pytest tests/api/test_schedules.py -v
pytest tests/api/test_publishing.py -v
pytest -v
```

Manual with Shopify credentials:

- Install/update Liquid files.
- Publish approved scheduled campaign.
- Verify target Shopify page displays the banner.
- Unpublish and verify rollback.

Carry-over bugs/gaps:

- No active pg_cron job is acceptable if theme-enforced dates are used.
- If demo requires automatic due-publish, cron must be implemented here.

Task 17 constraints and recommendations:

- Do not make live Shopify calls in automated tests. Use fake HTTP/client adapters.
- Publishing must require approved/scheduled state as appropriate.
- Do not publish before HITL approval.
- Treat Shopify credentials as secrets; never read or print real `.env.local` values.
- Shopify API client should be injectable/testable.
- Theme file install/update should be idempotent.
- Publish jobs should record attempts/status/errors.
- If service-role/database writes are required before Task 19, use explicit fail-closed or trusted-demo opt-in patterns like Task 16.
- Search-result placement must be honest: either implemented or return an explicit unsupported error.

---

## 6. Task 18 full task text

### Task 18: Integrate current static frontend with backend APIs

Goal: Connect the existing prototype to real backend endpoints without doing the full Next.js migration.

Expected result: The static frontend can exercise the demo flow against FastAPI.

Files:

- Modify: `frontend/lib.jsx`
- Modify: `frontend/data.jsx` only where API-backed adapters replace static data.
- Modify relevant frontend stage files only when necessary for API wiring.
- Create: `docs/architecture/frontend-backend-contract.md`
- Test/manual: browser flow.

Implementation notes:

- Use `window.AIJOLOT_API_BASE` defaulting to `http://localhost:8000`.
- Preserve mock fallback only if visibly labeled.
- Prefer `/api/v1` routes for new code.
- Root compatibility routes can remain only while needed by the prototype.

Verification:

Terminal 1:

```bash
cd backend
. .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```bash
python3 -m http.server 5500 --directory frontend
```

Manual:

- Brand loads/saves.
- Campaign intake works.
- Placement saves.
- Art direction saves.
- Generation progress displays.
- Review/approval works.
- Schedule/publish controls respect backend status.

Carry-over bugs/gaps:

- Full Next.js migration remains frontend-owned.
- Static adapters should be removed during migration, not by backend MVP work.

---

## 7. Task 19 full task text

### Task 19: Auth/team context and RLS alignment

Goal: Add enough user/team scoping for MVP without exposing service role secrets.

Expected result: Backend can associate records to a user/team and enforce no cross-team leakage through API responses.

Files:

- Create: `backend/app/core/auth.py`
- Create: `backend/app/services/auth/user_context.py`
- Modify: `backend/app/api/v1/*.py`
- Optional migration: `supabase/migrations/<timestamp>_rls_policy_refinement.sql`
- Test: `backend/tests/unit/test_auth_context.py`
- Test: `backend/tests/api/test_auth_boundaries.py`

Verification:

```bash
cd backend
pytest tests/unit/test_auth_context.py -v
pytest tests/api/test_auth_boundaries.py -v
pytest -v
cd ..
supabase db reset
```

Carry-over bugs/gaps:

- Fully polished login UX is frontend-owned.
- No backend leakage of service role keys or cross-team data is allowed.

Task 19 should revisit all prior fail-closed/trusted-demo routes, especially generation/revision/scheduling/publishing and preview routes.

---

## 8. Task 20 full task text

### Task 20: Performance/evolutionary memory API

Goal: Power the prototype's performance screen with schema-backed mock/manual metrics.

Expected result: Performance snapshots, optimization insights, and proposed V2 campaigns can be displayed without claiming live analytics.

Files:

- Create: `backend/app/schemas/performance.py`
- Create: `backend/app/db/repositories/performance_snapshots.py`
- Create: `backend/app/db/repositories/optimization_insights.py`
- Create: `backend/app/db/repositories/optimization_proposals.py`
- Create: `backend/app/services/banners/performance_service.py`
- Create: `backend/app/api/v1/performance.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/unit/test_performance_service.py`
- Test: `backend/tests/api/test_performance.py`

Verification:

```bash
cd backend
pytest tests/unit/test_performance_service.py -v
pytest tests/api/test_performance.py -v
pytest -v
```

Carry-over bugs/gaps:

- Live Shopify/analytics ingestion is non-MVP unless the team changes scope.

---

## 9. Task 21 full task text

### Task 21: Demo hardening and carry-over gap closure

Goal: Remove or explicitly constrain every gap that could break the hackathon demo.

Expected result: The chosen demo path can run twice after reset with real providers or deterministic fallback.

Files:

- Create: `docs/demo-script.md`
- Create: `demo/scenarios/avocado-black-friday.md`
- Create: `demo/scenarios/onboarding-scheduled.md`
- Create: `demo/scenarios/apparel-vip-product-launch.md`
- Create: `scripts/reset-demo-data.sh` or `scripts/reset-demo-data.py`
- Create: `scripts/smoke-demo-flow.py`
- Modify: `supabase/seed.sql` if needed.
- Modify: this plan if any gap changes.

Must decide/fix here:

- PDF/Figma/brandbook import: real extraction or clearly labeled partial/mock.
- Live Shopify resource sync: real sync or demo locked to seeded resources.
- Custom model/persona: real support or explicitly non-MVP.
- AVIF: enabled or audit-labeled skipped.
- Lighthouse: real automation or labeled mock/manual metrics.
- A/B/C layout variants: real generated variants or deterministic/demo-labeled variants.
- KG retrieval: embeddings or static deterministic retrieval.

Verification:

```bash
supabase db reset
cd backend
pytest -v
cd ..
python3 scripts/smoke-demo-flow.py
```

Manual:

- Run complete demo flow twice.
- Verify Shopify publish/unpublish if credentials are available.

Carry-over bugs/gaps: none allowed for the chosen demo path.

---

## 10. Task 22 full task text

### Task 22: Documentation cleanup and handoff

Goal: Keep docs accurate after implementation.

Expected result: README, API docs, frontend contract, and this plan match real behavior.

Files:

- Modify: `README.md`
- Modify: `docs/architecture/api-contract.md`
- Modify: `docs/architecture/frontend-backend-contract.md`
- Modify: `docs/architecture/project-structure.md`
- Modify: `docs/plans/2026-05-28-banner-creator-mvp.md`

Verification:

```bash
git status --short
cd backend
pytest -v
cd ..
supabase db reset
```

Manual:

- Follow README from fresh setup.
- Open backend API docs.
- Open static frontend.
- Complete documented demo path.

Carry-over bugs/gaps: none in docs. If a feature is incomplete, docs must say so.

---

## 11. Current API routes of interest

Already implemented by previous tasks:

- `POST /api/v1/campaigns/{campaign_id}/generation-runs`
- `GET /api/v1/campaigns/{campaign_id}/generation-runs/latest`
- `GET /api/v1/generation-runs/{run_id}`
- `GET /api/v1/generation-runs/{run_id}/events`
- `GET /api/v1/campaigns/{campaign_id}/preview`
- `GET /api/v1/campaigns/{campaign_id}/audit-report`
- `POST /api/v1/campaigns/{campaign_id}/approval/request`
- `GET /api/v1/campaigns/{campaign_id}/approval`
- `POST /api/v1/approval-threads/{thread_id}/comments`
- `PATCH /api/v1/comments/{comment_id}/resolve`
- `POST /api/v1/approval-threads/{thread_id}/approve`
- `POST /api/v1/approval-threads/{thread_id}/request-changes`
- `POST /api/v1/campaigns/{campaign_id}/refinement-requests`
- `POST /api/v1/campaigns/{campaign_id}/variants/{variant_id}/select`
- `POST /api/v1/campaigns/{campaign_id}/regenerate`
- `GET /api/v1/campaigns/{campaign_id}/revisions`

Still planned:

- `POST /api/v1/campaigns/{campaign_id}/schedule`
- `PATCH /api/v1/campaigns/{campaign_id}/schedule`
- `POST /api/v1/campaigns/{campaign_id}/schedule/cancel`
- `POST /api/v1/campaigns/{campaign_id}/publish`
- `POST /api/v1/campaigns/{campaign_id}/unpublish`
- `GET /api/v1/campaigns/{campaign_id}/performance`
- `POST /api/v1/campaigns/{campaign_id}/performance/snapshots`
- `POST /api/v1/campaigns/{campaign_id}/optimization-proposals`

---

## 12. Known carry-over ledger from plan

Important remaining gaps from the active plan ledger:

- Live Shopify resource sync missing. Owner: Task 17 or Task 21.
- Search-result placement validates but may not publish. Owner: Task 17.
- Custom model/persona is metadata-only. Owner: Task 21 or explicitly non-MVP.
- AVIF omitted/flaky. Owner: Task 21. Task 13 reports `avif_skipped` when encoder unavailable; audit/demo must surface honestly.
- Lighthouse automation placeholder. Owner: Task 21. Metrics must be honest: real, seeded, or mock/manual.
- No active pg_cron due-publish job. Owner: Task 17 only if demo requires automatic due-publish. Theme-enforced dates are MVP default.
- Static frontend API adapters will exist after Task 18. Owner: future frontend migration; document it.

Also update stale ledger rows if appropriate: the row saying `Refinement requests stored but not applied | Task 15 | Task 16` is closed by Task 16 and should be marked closed during Task 21/22 docs cleanup if not already updated.

---

## 13. Implementation pitfalls discovered so far

Keep these in mind for Tasks 17-22:

1. Do not concatenate prompts, comments, copy, or Shopify data directly into HTML/Liquid. Escape for the exact context and add stored-XSS tests.
2. User-facing routes should not silently use service-role writes. Until Task 19, use fail-closed or explicit trusted-demo opt-in.
3. Regeneration must preserve old revisions and never mutate final assets silently.
4. New revisions should not reuse revision-scoped preview paths.
5. All-reviewer approval means first approval leaves campaign `needs_review`; only last required approval transitions campaign to `approved`.
6. Refinement regeneration is deterministic MVP behavior and should not claim live Gemini unless wired.
7. Shopify publishing must be idempotent and rollback/unpublish should be explicit.
8. No automated tests should make live Shopify/Gemini/Supabase network calls unless explicitly marked/integration-gated.
9. Prototype root routes must remain until frontend integration no longer depends on them.
10. Do not read or commit real `.env`, `.env.local`, Shopify access tokens, Supabase service role keys, Gemini credentials, or service account files.

---

## 14. Suggested Task 17 implementer prompt

Use this as the implementation subagent context after fresh pre-flight:

```text
You are a fresh implementation subagent for Aijolot Banner Agent. Act like a master engineer: careful, modular, reusable, concise, test-driven, and security-conscious.

You must not spawn subagents. Do the assigned work yourself.

Project root: /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
Branch: feature/backend-mvp-implementation
Active plan: docs/plans/2026-05-28-banner-creator-mvp.md

Current known state:
- Task 16 committed as 5fbb4ec.
- Full backend tests pass: 199 passed, 3 skipped, 2 pre-existing Pydantic warnings.
- Do not make live external calls in tests. Use fake/in-memory repositories and fake Shopify clients.
- Do not read or print secrets. Do not use real Shopify credentials in tests.
- Publishing must remain behind approved/scheduled state transitions.
- Until Task 19, any configured service-role/user-facing mutation path must fail closed or require explicit trusted-demo opt-in.

Task 17 from plan:
[Paste the full Task 17 text from section 5 of this handoff.]

Implementation guidance:
- Inspect existing migration schema and repository patterns before coding.
- Create strongly typed Pydantic schemas for schedule/publish requests/responses.
- Schedule service should reject non-approved campaigns for scheduling unless a clear allowed transition exists.
- Publish service should reject unapproved/unscheduled campaigns.
- Theme file and metafield clients must be injectable and fakeable.
- Shopify publisher must be idempotent: installing/updating Liquid assets multiple times should be safe.
- Publish jobs must record status/errors and no tests should hit Shopify network.
- Search-result placement must either be implemented correctly or fail with a clear unsupported error.
- Add unit/API tests for schedule create/update/cancel, publish/unpublish, job recording, idempotent theme file install, and status guards.
- Run focused tests and full backend tests.

Report back with:
- Summary of work done.
- Files changed.
- Tests/commands run and exact results.
- Any blockers or deferred gaps.
- Confirmation that this phase is complete or what remains.
```

---

## 15. Suggested review prompts

Spec review after Task 17 implementation:

```text
Project root: /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
Branch: feature/backend-mvp-implementation

Task 17 spec:
[Paste Task 17 full text.]

Review current implementation for spec compliance only:
- Are all requested files/endpoints implemented or intentionally documented as not needed?
- Are approved scheduling, idempotent theme install, publish/unpublish, and publish job recording present?
- Does search-result placement publish correctly or return a clear unsupported error?
- Are tests present for the required behaviors?

Return Critical Issues, Important Issues, Minor Issues, Verdict. Do not modify files.
```

Quality/security review after spec compliance:

```text
Project root: /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
Branch: feature/backend-mvp-implementation

Review Task 17 changed files for quality/security:
- Shopify client safety, no token leakage, no live calls in tests
- idempotent theme/metafield writes
- schedule/publish state-machine guards
- XSS/Liquid injection risks
- repository/schema alignment
- fail-closed behavior before Task 19 auth
- race/transaction concerns
- test coverage and maintainability

Return Critical Issues, Important Issues, Minor Issues, Verdict. Do not modify files.
```

---

## 16. Completion criteria for this coordinator run

The fresh coordinator session should end only after one of these is true:

1. Tasks 17-22 are completed, reviewed, committed, and the demo/doc path is ready; or
2. A real blocker requiring user decision appears, with exact options and tradeoffs; or
3. A tool/environment failure prevents further progress, with exact command/output and recovery recommendation.

If work continues across another context compression, create a new handoff file with updated commits, task status, test results, and remaining blockers.
