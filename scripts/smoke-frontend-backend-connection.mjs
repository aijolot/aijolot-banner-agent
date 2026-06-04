#!/usr/bin/env node
/*
 * Smoke-test the frontend-facing /api/v1 contract against a running backend.
 *
 * Usage:
 *   node scripts/smoke-frontend-backend-connection.mjs
 *
 * Assumes FastAPI is running at AIJOLOT_API_ORIGIN (default http://localhost:8000).
 * This mirrors the static frontend client rules: exactly one /api/v1 prefix and
 * demo auth headers on every canonical request. It does not call external
 * providers; schedule/publish are expected to fail closed in the deterministic
 * local demo state.
 */

const API_ORIGIN = (process.env.AIJOLOT_API_ORIGIN || "http://localhost:8000").replace(/\/+$/, "").replace(/\/api\/v1$/i, "");
const API_BASE = `${API_ORIGIN}/api/v1`;
const REPO_ROOT = new URL("..", import.meta.url);
const DEMO_USER_ID = "00000000-0000-0000-0000-000000000601";
const DEMO_TEAM_ID = "00000000-0000-0000-0000-000000000001";
const DEMO_STORE_ID = "00000000-0000-0000-0000-000000000101";
const demoAuthHeaders = {
  "X-Aijolot-User-Id": DEMO_USER_ID,
  "X-Aijolot-Team-Id": DEMO_TEAM_ID,
  "X-Aijolot-Store-Id": DEMO_STORE_ID,
  Authorization: `Bearer demo:${DEMO_USER_ID}:${DEMO_TEAM_ID}:${DEMO_STORE_ID}`,
};
const STORE_ID = DEMO_STORE_ID;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function apiPath(path) {
  return path.startsWith("/") ? path : `/${path}`;
}

function apiUrl(path) {
  const normalized = apiPath(path);
  if (normalized === "/api/v1" || normalized.startsWith("/api/v1/")) {
    throw new Error(`path should not include /api/v1 twice: ${path}`);
  }
  return `${API_BASE}${normalized}`;
}

async function api(path, init = {}) {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...demoAuthHeaders,
      ...(init.headers || {}),
    },
  });
  const text = await response.text();
  let body = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  if (!response.ok) {
    const err = new Error(`${response.status} ${response.statusText}: ${typeof body === "string" ? body : JSON.stringify(body)}`);
    err.status = response.status;
    err.body = body;
    throw err;
  }
  return body;
}

const FAIL_CLOSED_STATUSES = new Set([404, 409, 422, 503]);

function assertFailClosed(label, err) {
  if (!FAIL_CLOSED_STATUSES.has(err.status)) {
    throw new Error(`${label} returned non-fail-closed error ${err.status || "unknown"}: ${err.message}`);
  }
}

async function expectFailure(label, fn) {
  try {
    await fn();
  } catch (err) {
    assertFailClosed(label, err);
    console.log(`ok: ${label} failed closed with ${err.status}`);
    return err;
  }
  throw new Error(`${label} unexpectedly succeeded; deterministic demo should fail closed unless real provider/state is configured`);
}

async function streamIntake(message) {
  const response = await fetch(apiUrl("/campaigns/intake"), {
    method: "POST",
    headers: { Accept: "text/event-stream", "Content-Type": "application/json", ...demoAuthHeaders },
    body: JSON.stringify({ message, campaign_id: null }),
  });
  if (!response.ok || !response.body) throw new Error(`intake failed ${response.status}: ${await response.text()}`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const events = [];
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const chunk = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 2);
      const line = chunk.split("\n").find((item) => item.startsWith("data: "));
      if (line) events.push(JSON.parse(line.slice(6)));
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
  const doneEvent = events.find((event) => event.type === "done");
  if (!doneEvent?.campaign?.id) throw new Error("intake did not return campaign id");
  return { events, campaign: doneEvent.campaign };
}

async function main() {
  const health = await fetch(`${API_ORIGIN}/health`).then((r) => r.json());
  if (health.status !== "ok") throw new Error(`health not ok: ${JSON.stringify(health)}`);
  console.log("ok: backend health");

  const brands = await api("/brands");
  if (!Array.isArray(brands) || brands.length === 0) throw new Error("brand list empty");
  await api(`/brands/${brands[0].id}`);
  console.log(`ok: brands loaded (${brands.length})`);

  const { events: intakeEvents, campaign } = await streamIntake("Banner de Black Friday, 50% off perfumes Hugo Boss, para clientes VIP, CTA Comprar ahora, urgencia alta, en home hero");
  if (!UUID_RE.test(campaign.id)) throw new Error(`campaign id is not UUID: ${campaign.id}`);
  console.log(`ok: intake streamed ${intakeEvents.length} events and returned campaign ${campaign.id}`);

  await api(`/campaigns/${campaign.id}`, { method: "PATCH", body: JSON.stringify({ cta: "Comprar ahora", placement: "Home · Hero" }) });
  const placement = {
    store_id: STORE_ID,
    placement_type_key: "hero_main",
    mode: "existing_section",
    target_type: "home",
    target_handle: null,
    target_title: "Inicio",
    existing_placement_key: "hero",
    existing_placement_label: "Hero principal",
    existing_placement_size: "1440 × 420",
    slot: "hero",
    slot_order: 0,
    scope_rule: { source: "frontend-smoke" },
    layout_json: { cols: [{ rows: 1, w: 1, align: "center" }] },
  };
  await api("/placements/validate", { method: "POST", body: JSON.stringify(placement) });
  await api(`/campaigns/${campaign.id}/placement`, { method: "POST", body: JSON.stringify(placement) });
  await api(`/campaigns/${campaign.id}/placement`);
  console.log("ok: placement validate/save/load");

  await api(`/campaigns/${campaign.id}/catalog-snapshot`, { method: "POST", body: JSON.stringify({ store_id: STORE_ID, resource_types: ["collection", "product"], limit: 5 }) });
  await api(`/campaigns/${campaign.id}/catalog-snapshot`);
  await api(`/campaigns/${campaign.id}/art-direction`, { method: "PUT", body: JSON.stringify({ background_mode: "usage", model_key: "m2", fold_percentage: 55, layout_hints: { source: "frontend-smoke" } }) });
  await api(`/campaigns/${campaign.id}/art-direction`);
  console.log("ok: catalog snapshot and art direction");

  let revisions = [];
  const run = await api(`/campaigns/${campaign.id}/generation-runs`, { method: "POST", body: JSON.stringify({ metadata: { source: "frontend-smoke" } }) });
  if (!run || !UUID_RE.test(run.id) || !["queued", "running", "succeeded", "completed"].includes(run.status)) {
    throw new Error(`generation did not return a valid run: ${JSON.stringify(run)}`);
  }
  await api(`/campaigns/${campaign.id}/generation-runs/latest`);
  await api(`/generation-runs/${run.id}`);
  const generationEvents = await api(`/generation-runs/${run.id}/events`);
  const eventKeys = generationEvents.map((event) => event.node_key || "");
  if (!generationEvents.length) throw new Error("generation events empty");
  if (!eventKeys.some((key) => /research|kg|knowledge|context/i.test(key))) throw new Error(`KG/research event missing: ${eventKeys.join(", ")}`);
  let previewOk = false;
  let previewHtml = "";
  try {
    const response = await fetch(apiUrl(`/campaigns/${campaign.id}/preview`), { headers: { ...demoAuthHeaders, Accept: "text/html" } });
    if (!response.ok) {
      const err = Object.assign(new Error(`preview failed ${response.status}`), { status: response.status });
      throw err;
    }
    previewHtml = await response.text();
    if (!/<[a-z][\s\S]*>/i.test(previewHtml) || !previewHtml.includes("aijolot-banner")) throw new Error("preview returned non-banner HTML from a 200 response");
    previewOk = true;
  } catch (err) {
    if (!err.status) throw err;
    assertFailClosed("preview", err);
    console.log(`ok: preview unavailable/fail-closed in local fallback: ${err.status}`);
  }
  let auditOk = false;
  let audit = null;
  try {
    audit = await api(`/campaigns/${campaign.id}/audit-report`);
    if (!audit || typeof audit !== "object" || !(audit.status || audit.runtime_status || audit.schema_report)) throw new Error("audit returned invalid report from a 200 response");
    auditOk = true;
  } catch (err) {
    if (!err.status) throw err;
    assertFailClosed("audit", err);
    console.log(`ok: audit unavailable/fail-closed in local fallback: ${err.status}`);
  }
  try {
    revisions = await api(`/campaigns/${campaign.id}/revisions`);
  } catch (err) {
    assertFailClosed("revisions", err);
    console.log(`ok: revisions unavailable/fail-closed in local fallback: ${err.status}`);
  }
  if (revisions.length) {
    if (!previewOk) throw new Error("backend revisions exist but preview route did not return HTML");
    if (!auditOk) throw new Error("backend revisions exist but audit route did not return a report");
    if (!revisions.some((revision) => revision.html_preview || revision.preview_storage_path)) throw new Error("backend revisions exist but no preview artifact is exposed");
  } else if (previewOk || auditOk) {
    throw new Error("preview/audit loaded but revisions endpoint returned no persisted revisions; persistence contract is inconsistent");
  }
  console.log(`ok: generation/events/KG/preview/audit/revisions (${generationEvents.length} events, preview=${previewOk}, audit=${auditOk}, ${revisions.length} revisions)`);

  // Newly-wired stage interactions. Each of these is best-effort in the local
  // no-Supabase demo: they either succeed against the request-scoped fallback or
  // fail closed with 404/409/422/503. The frontend surfaces both honestly, so
  // the smoke script accepts either outcome but rejects auth/server regressions.
  async function attempt(label, fn) {
    try {
      await fn();
      console.log(`ok: ${label} succeeded against backend`);
    } catch (err) {
      assertFailClosed(label, err);
      console.log(`ok: ${label} failed closed with ${err.status}`);
    }
  }

  if (revisions.length) {
    const rev = revisions.reduce((a, b) => ((b.revision_number || 0) >= (a.revision_number || 0) ? b : a));
    const variant = (rev.variants && rev.variants[0]) || (rev.layout_variants && rev.layout_variants[0]);
    if (variant && variant.id) {
      await attempt("select variant", () => api(`/campaigns/${campaign.id}/variants/${variant.id}/select`, { method: "POST" }));
    }
  } else {
    console.log("ok: no revisions to select variants from (fail-closed local demo)");
  }

  const canvasSource = await import("node:fs/promises").then((fs) => fs.readFile(new URL("frontend/CanvasStage.jsx", REPO_ROOT), "utf8"));
  if (!canvasSource.includes("srcDoc={iframeSafePreviewHtml(backendCreativeHtml)}") || !canvasSource.includes("Backend-backed creative") || !canvasSource.includes("Content-Security-Policy")) {
    throw new Error("Canvas smoke failed: backend HTML preview is not rendered as primary creative");
  }
  if (!canvasSource.includes("Fallback local/prototipo")) {
    throw new Error("Canvas smoke failed: local Banner fallback is not visibly labeled");
  }
  console.log("ok: Canvas source renders backend creative before local fallback");

  await attempt("regenerate (refinement)", () => api(`/campaigns/${campaign.id}/regenerate`, { method: "POST", body: JSON.stringify({ prompt: "haz el fondo más brillante", requested_by: DEMO_USER_ID }) }));
  await attempt("refinement request", () => api(`/campaigns/${campaign.id}/refinement-requests`, { method: "POST", body: JSON.stringify({ prompt: "subir contraste del CTA", requested_by: DEMO_USER_ID }) }));

  // Approval thread + comments (503 in local no-Supabase demo).
  let threadId = null;
  await attempt("request approval", async () => {
    const thread = await api(`/campaigns/${campaign.id}/approval/request`, { method: "POST", body: JSON.stringify({ requested_by: DEMO_USER_ID, reviewers: [DEMO_USER_ID] }) });
    threadId = thread && thread.id;
  });
  if (threadId) {
    await attempt("add comment", () => api(`/approval-threads/${threadId}/comments`, { method: "POST", body: JSON.stringify({ author_id: DEMO_USER_ID, body: "Se ve premium", pin_x: 40, pin_y: 30, device_key: "desktop" }) }));
    await attempt("approve thread", () => api(`/approval-threads/${threadId}/approve`, { method: "POST", body: JSON.stringify({ user_id: DEMO_USER_ID }) }));
  } else {
    console.log("ok: approval thread unavailable (fail-closed local demo)");
  }

  await expectFailure("schedule before approval", () => api(`/campaigns/${campaign.id}/schedule`, { method: "POST", body: JSON.stringify({ starts_at: new Date().toISOString(), timezone: "UTC", auto_unpublish: true }) }));
  await expectFailure("publish before eligible state", () => api(`/campaigns/${campaign.id}/publish`, { method: "POST" }));

  // Performance snapshot + V2 optimization proposal.
  await attempt("performance snapshot", () => api(`/campaigns/${campaign.id}/performance/snapshots`, { method: "POST", body: JSON.stringify({ source: "manual", impressions: 12840, clicks: 591, conversions: 96 }) }));
  if (revisions.length) {
    const rev = revisions.reduce((a, b) => ((b.revision_number || 0) >= (a.revision_number || 0) ? b : a));
    await attempt("optimization proposal", () => api(`/campaigns/${campaign.id}/optimization-proposals`, { method: "POST", body: JSON.stringify({ source_revision_id: rev.id, rationale: "Femenino CTR bajo", projected_lift: { ctr: "+18%" }, status: "sent_to_approval" }) }));
  } else {
    console.log("ok: no revision for optimization proposal (fail-closed local demo)");
  }

  try {
    const perf = await api(`/campaigns/${campaign.id}/performance`);
    const label = perf.data_source_label || (perf.live_analytics ? "live" : "manual/mock/seed/agent");
    if (perf.live_analytics) throw new Error("deterministic demo unexpectedly reported live analytics");
    console.log(`ok: performance loaded with non-live label: ${label}`);
  } catch (err) {
    assertFailClosed("performance", err);
    console.log(`ok: performance unavailable/fail-closed in local fallback: ${err.status}`);
  }

  console.log("frontend-backend connection smoke passed");
}

main().catch((err) => {
  console.error(err.stack || err.message || err);
  process.exit(1);
});
