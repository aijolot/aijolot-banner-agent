#!/usr/bin/env node
/*
 * Source-level frontend smoke for the static MVP UI.
 *
 * This intentionally does not launch a browser or call external services. It
 * verifies that demo-critical guardrail labels/routes remain present in the
 * static React prototype so old ambiguous UI states do not silently return.
 */

import { readFile } from "node:fs/promises";

const ROOT = new URL("..", import.meta.url);

async function source(path) {
  return readFile(new URL(path, ROOT), "utf8");
}

function includesAll(label, text, needles) {
  const missing = needles.filter((needle) => !text.includes(needle));
  if (missing.length) {
    throw new Error(`${label} missing expected UI/static markers:\n- ${missing.join("\n- ")}`);
  }
  console.log(`ok: ${label}`);
}

function matchesAll(label, text, patterns) {
  const missing = patterns.filter((pattern) => !pattern.test(text)).map(String);
  if (missing.length) {
    throw new Error(`${label} missing expected UI/static patterns:\n- ${missing.join("\n- ")}`);
  }
  console.log(`ok: ${label}`);
}

const [shell, app, lib, brief, chatbox, chips, placement, generate, canvas, canvasPanels, performance] = await Promise.all([
  source("frontend/Shell.jsx"),
  source("frontend/App.jsx"),
  source("frontend/lib.jsx"),
  source("frontend/BriefStage.jsx"),
  source("frontend/components/Chatbox.jsx"),
  source("frontend/components/CampaignChips.jsx"),
  source("frontend/PlacementStage.jsx"),
  source("frontend/GenerateStage.jsx"),
  source("frontend/CanvasStage.jsx"),
  source("frontend/CanvasPanels.jsx"),
  source("frontend/PerformanceStage.jsx"),
]);

includesAll("API path/auth contract markers", lib, [
  "AIJOLOT_DEMO_AUTH_HEADERS",
  "Bearer demo:${AIJOLOT_DEMO_IDS.user}:${AIJOLOT_DEMO_IDS.team}:${AIJOLOT_DEMO_IDS.store}",
  "apiV1Path(path)",
  "return normalized === API_V1 || normalized.startsWith(API_V1 + \"/\") ? normalized : API_V1 + normalized",
  "streamIntakeEvents(message, campaignId, onEvent)",
  "fallbackResult(reason, data)",
  "async latestRevision(campaign)",
  "async ensureThread(campaign, revisionId)",
  "async publish(campaign)",
]);

includesAll("resume/create routing stays backend-aware", app + shell + lib, [
  "onNew={handleNewCampaign}",
  "hydrateCampaignSelection(c, \"canvas\")",
  "hydrateCampaignSelection(c, \"performance\")",
  "Revisando progreso backend para retomar en el paso correcto",
  "Campaña backend activa",
  "Borrador backend",
  "Demo/fallback · prototipo local",
  "No se pudo cargar campañas reales",
  "Derivado de /api/v1",
]);
matchesAll("resume/create routing helper shape", app + shell, [
  /async\s+function\s+handleNewCampaign\s*\(\)/,
  /async\s+function\s+hydrateCampaignSelection\s*\(c,\s*nextStage\)/,
  /CampaignRow\([\s\S]*onResume\(r\.campaign \|\| r\)/,
]);

includesAll("brief fallback and persistence labels", brief + chatbox + chips + lib, [
  "Backend no disponible; usando extractor local solo como fallback offline.",
  "localOnly: true",
  "isApiCampaign",
  "PATCH /api/v1/campaigns/{id}",
  "Brief guardado en backend.",
]);

includesAll("placement backend/fallback guardrails", placement, [
  "Ubicación validada por el backend",
  "No se pudo validar la ubicación en backend",
  "Fallback STORE_PAGES",
  "fallback STORE_PAGES",
  "Los títulos/handles visibles provienen de STORE_PAGES/semillas estáticas solo como fallback.",
]);

includesAll("generation happy path/fail-closed labels", generate + canvas, [
  "GenerationApi.start",
  "GenerationApi.events",
  "GenerationApi.preview",
  "GenerationApi.audit",
  "GenerationApi.revisions",
  "No se pudo iniciar generación backend",
  "Generación backend completada",
  "Lienzo usando preview HTML backend.",
  "Sin revisiones backend; lienzo en modo prototipo local.",
]);

includesAll("canvas preview/revision/audit source labels", canvas, [
  "srcDoc={iframeSafePreviewHtml(backendCreativeHtml)}",
  "Content-Security-Policy",
  "Backend-backed creative",
  "Fallback local/prototipo",
  "preview/revisión backend",
  "fallback local/prototipo",
  "auditStatusLabel",
  "Refinamiento enviado al backend",
  "(local, sin backend)",
]);

includesAll("approval, schedule, publish guardrails", canvas + canvasPanels, [
  "Aprobaciones locales/prototipo",
  "Programación backend no disponible: la campaña local/prototipo no tiene UUID.",
  "Programación bloqueada: no hay revisión backend seleccionada.",
  "Programación bloqueada: las aprobaciones son locales/prototipo; backend no confirmó el hilo.",
  "Publicación fail-closed: backend requiere campaña scheduled",
  "Simular publicación / dry-run",
  "Dry-run",
  "sin mutación live Shopify",
  "Acción fail-closed: no se marcará como programada/publicada localmente.",
]);

includesAll("performance non-live labels and V2 backend hooks", performance, [
  "manual/mock/seed/agent · no-live",
  "Datos demo etiquetados como manual/mock/seed/agent; no son analítica live de Shopify.",
  "Resultados no-live",
  "No-live visible",
  "Fallback demo no-live",
  "Registrar snapshot",
  "PerformanceApi.snapshot",
  "PerformanceApi.proposal",
  "Propuesta V2 enviada a aprobación en backend",
]);

console.log("frontend UI/static smoke passed");
