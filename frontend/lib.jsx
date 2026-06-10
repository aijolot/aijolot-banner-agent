/* global React */
// Aijolot Banner Agent — shared primitives (glassmorphism)
const { useState, useEffect, useRef, useCallback } = React;

// --- Lucide icon ---
function Icon({ name, size = 16, color, style, strokeWidth = 2 }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current && window.lucide) {
      ref.current.innerHTML = "";
      const el = document.createElement("i");
      el.setAttribute("data-lucide", name);
      ref.current.appendChild(el);
      window.lucide.createIcons({
        attrs: { width: size, height: size, "stroke-width": strokeWidth },
        nameAttr: "data-lucide",
      });
    }
  }, [name, size, strokeWidth]);
  return <span ref={ref} style={{ display: "inline-flex", color: color || "currentColor", lineHeight: 0, ...style }} />;
}

// --- Glass card ---
function GlassCard({ children, style, radius = 14, className = "", onClick, id }) {
  return (
    <div
      id={id}
      onClick={onClick}
      className={className}
      style={{
        background: "rgba(255,255,255,0.8)",
        backdropFilter: "blur(18px)",
        WebkitBackdropFilter: "blur(18px)",
        border: "1px solid rgba(255,255,255,0.6)",
        borderRadius: radius,
        boxShadow: "0 10px 28px rgba(15,23,42,0.08)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// --- Button ---
function Button({ variant = "default", children, icon, iconRight, onClick, style, disabled, type = "button", title }) {
  const [hover, setHover] = useState(false);
  const base = {
    fontFamily: "Inter, sans-serif", fontWeight: 500, fontSize: 13.5,
    padding: "9px 16px", borderRadius: 8, border: "none",
    cursor: disabled ? "not-allowed" : "pointer", display: "inline-flex",
    alignItems: "center", gap: 7, position: "relative", overflow: "hidden",
    transition: "filter .15s, background .15s, box-shadow .15s, transform .05s", whiteSpace: "nowrap",
    opacity: disabled ? 0.5 : 1,
  };
  const variants = {
    default: { background: "#22D3EE", color: "#fff", boxShadow: "0 10px 30px rgba(34,211,238,.18)" },
    shine: { background: "#22D3EE", color: "#fff", boxShadow: "0 10px 30px rgba(34,211,238,.18)" },
    navy: { background: "#002B57", color: "#fff", boxShadow: "0 10px 26px rgba(0,43,87,.22)" },
    destructive: { background: "#F72585", color: "#fff", boxShadow: "0 10px 30px rgba(247,37,133,.18)" },
    outline: { background: "rgba(255,255,255,0.6)", color: "#002B57", border: "1px solid #E2E8F0" },
    ghost: { background: hover && !disabled ? "rgba(34,211,238,0.1)" : "transparent", color: "#68737D" },
    secondary: { background: "#F8FAFC", color: "#002B57", border: "1px solid #E2E8F0" },
  };
  const v = variants[variant] || variants.default;
  return (
    <button
      type={type} onClick={disabled ? undefined : onClick} disabled={disabled} title={title}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ ...base, ...v, filter: hover && !disabled && variant !== "ghost" ? "brightness(1.06)" : "none", ...style }}
    >
      {icon && <Icon name={icon} size={15} />}
      {children}
      {iconRight && <Icon name={iconRight} size={15} />}
      {(variant === "shine" || variant === "default") && hover && !disabled && (
        <span style={{ position: "absolute", inset: 0, background: "linear-gradient(110deg,transparent 35%,rgba(255,255,255,.5) 50%,transparent 65%)", animation: "uikShine 1.4s linear infinite" }} />
      )}
    </button>
  );
}

// --- Badge ---
const BADGE_TONES = {
  cyan: { bg: "rgba(34,211,238,0.12)", bd: "#22D3EE", fg: "#0891B2" },
  pink: { bg: "rgba(247,37,133,0.12)", bd: "#F72585", fg: "#F72585" },
  green: { bg: "rgba(34,197,94,0.12)", bd: "#4ADE80", fg: "#16A34A" },
  amber: { bg: "rgba(245,158,11,0.12)", bd: "#FBBF24", fg: "#B45309" },
  purple: { bg: "rgba(139,92,246,0.12)", bd: "#A78BFA", fg: "#7C3AED" },
  slate: { bg: "rgba(100,116,139,0.1)", bd: "#CBD5E1", fg: "#64748B" },
  red: { bg: "rgba(239,68,68,0.12)", bd: "#F87171", fg: "#EF4444" },
};
function Badge({ tone = "cyan", children, icon, style }) {
  const t = BADGE_TONES[tone] || BADGE_TONES.cyan;
  return (
    <span style={{
      fontFamily: "Inter, sans-serif", fontSize: 10, fontWeight: 600,
      textTransform: "uppercase", letterSpacing: "0.06em", padding: "3px 9px",
      borderRadius: 9999, border: `1px solid ${t.bd}`, background: t.bg, color: t.fg,
      display: "inline-flex", alignItems: "center", gap: 5, whiteSpace: "nowrap", ...style,
    }}>
      {icon && <Icon name={icon} size={11} />}
      {children}
    </span>
  );
}

// --- Kicker (chapter-line + uppercase label) ---
function Kicker({ children, color = "#0891B2" }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ width: 26, height: 3, borderRadius: 9999, background: color }} />
      <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, letterSpacing: "0.14em", textTransform: "uppercase", color }}>{children}</span>
    </div>
  );
}

// --- spinner ---
function Spinner({ size = 16, color = "#22D3EE" }) {
  return <span style={{ width: size, height: size, borderRadius: 9999, border: `2px solid ${color}33`, borderTopColor: color, display: "inline-block", animation: "spin .8s linear infinite" }} />;
}

// --- Avatar ---
function Avatar({ initials, gradient = "linear-gradient(135deg,#F72585,#8B5CF6)", size = 32, title }) {
  return (
    <div title={title} style={{
      width: size, height: size, borderRadius: 9999, background: gradient, color: "#fff",
      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      fontFamily: "Space Grotesk", fontWeight: 600, fontSize: size * 0.4,
    }}>{initials}</div>
  );
}

// --- Backend API client/adapters ---
// Static prototype integration point. Canonical calls use exactly one /api/v1,
// send demo auth/team context, and default to http://localhost:8000 unless the
// hosting page defines window.AIJOLOT_API_BASE.
function normalizeApiOrigin(origin) {
  return (origin || "http://localhost:8000").replace(/\/+$/, "").replace(/\/api\/v1$/i, "");
}
window.API_BASE = normalizeApiOrigin(window.AIJOLOT_API_BASE || window.API_BASE || "http://localhost:8000");
const API_V1 = "/api/v1";
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const AIJOLOT_DEMO_IDS = {
  user: window.AIJOLOT_USER_ID || "00000000-0000-0000-0000-000000000601",
  team: window.AIJOLOT_TEAM_ID || "00000000-0000-0000-0000-000000000001",
  store: window.AIJOLOT_STORE_ID || "00000000-0000-0000-0000-000000000101",
};
const AIJOLOT_DEMO_AUTH_HEADERS = {
  "X-Aijolot-User-Id": AIJOLOT_DEMO_IDS.user,
  "X-Aijolot-Team-Id": AIJOLOT_DEMO_IDS.team,
  "X-Aijolot-Store-Id": AIJOLOT_DEMO_IDS.store,
  "Authorization": `Bearer demo:${AIJOLOT_DEMO_IDS.user}:${AIJOLOT_DEMO_IDS.team}:${AIJOLOT_DEMO_IDS.store}`,
};

function isApiCampaign(campaign) { return !!(campaign && UUID_RE.test(campaign.id || "")); }
function localId(prefix) {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}
function fallbackResult(reason, data) { return { ok: true, fallback: true, reason: reason || "mock/local fallback", data }; }
function apiPath(path) { return (path || "").startsWith("/") ? path : `/${path || ""}`; }
function apiV1Path(path) {
  const normalized = apiPath(path);
  return normalized === API_V1 || normalized.startsWith(API_V1 + "/") ? normalized : API_V1 + normalized;
}
function isV1Path(path) { const normalized = apiPath(path); return normalized === API_V1 || normalized.startsWith(API_V1 + "/"); }
function errorText(e) {
  if (!e) return "error";
  if (typeof e.body === "string") return e.body;
  if (e.body && e.body.detail) return typeof e.body.detail === "string" ? e.body.detail : JSON.stringify(e.body.detail);
  return e.message || e.status || "error";
}

const AijolotApi = {
  base: window.API_BASE,
  demoAuthHeaders: AIJOLOT_DEMO_AUTH_HEADERS,
  path: apiPath,
  v1: apiV1Path,
  isV1Path,
  async request(path, options) {
    const normalizedPath = apiPath(path);
    const opts = options || {};
    const hasBody = opts.body != null;
    const authHeaders = isV1Path(normalizedPath) ? AIJOLOT_DEMO_AUTH_HEADERS : {};
    const headers = {
      Accept: "application/json",
      ...(hasBody && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      ...authHeaders,
      ...(opts.headers || {}),
    };
    const resp = await fetch(this.base + normalizedPath, { ...opts, headers });
    const text = await resp.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch (_) { body = text; }
    if (!resp.ok) {
      const err = new Error((body && body.detail) || body || `HTTP ${resp.status}`);
      err.status = resp.status; err.body = body; throw err;
    }
    return body;
  },
  async text(path, options) {
    const normalizedPath = apiPath(path);
    const opts = options || {};
    const headers = { ...(isV1Path(normalizedPath) ? AIJOLOT_DEMO_AUTH_HEADERS : {}), ...(opts.headers || {}) };
    const resp = await fetch(this.base + normalizedPath, { ...opts, headers });
    const text = await resp.text();
    if (!resp.ok) { const err = new Error(text || `HTTP ${resp.status}`); err.status = resp.status; err.body = text; throw err; }
    return text;
  },
  get(path) { return this.request(path); },
  post(path, body) { return this.request(path, { method: "POST", body: body == null ? undefined : JSON.stringify(body) }); },
  put(path, body) { return this.request(path, { method: "PUT", body: JSON.stringify(body || {}) }); },
  patch(path, body) { return this.request(path, { method: "PATCH", body: body == null ? undefined : JSON.stringify(body) }); },
  async streamIntakeEvents(message, campaignId, onEvent) {
    const resp = await fetch(this.base + this.v1("/campaigns/intake"), {
      method: "POST",
      headers: { Accept: "text/event-stream", "Content-Type": "application/json", ...AIJOLOT_DEMO_AUTH_HEADERS },
      body: JSON.stringify({ message, campaign_id: campaignId || null }),
    });
    if (!resp.ok || !resp.body) throw new Error(`intake failed: ${resp.status} ${await resp.text()}`);
    const reader = resp.body.getReader(), decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const chunk = buffer.slice(0, boundary).trim();
        buffer = buffer.slice(boundary + 2);
        const line = chunk.split("\n").find((l) => l.startsWith("data: "));
        if (line) onEvent(JSON.parse(line.slice(6)));
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    const tail = buffer.trim();
    if (tail.startsWith("data: ")) onEvent(JSON.parse(tail.slice(6)));
  },
};

function placementPayloadFromPrototype(placement) {
  const id = placement && placement.id || "hero";
  const page = (placement && placement.page || "Inicio").toLowerCase();
  const isNew = placement && placement.layout && placement.layout.mode === "new";
  const pageTarget = page.includes("cole") ? "collection" : page.includes("producto") ? "product" : page.includes("búsqueda") || page.includes("busqueda") ? "search" : page.includes("página") || page.includes("pagina") ? "page" : "home";
  const map = {
    announce: { key: "announcement_bar", slot: "announce", target: pageTarget === "search" ? "store" : pageTarget },
    hero: { key: "hero_main", slot: "hero", target: pageTarget === "collection" ? "collection" : pageTarget === "page" ? "page" : "home" },
    promo_l: { key: "promo_card", slot: "promo_l", target: pageTarget === "collection" ? "collection" : "home" },
    promo_r: { key: "promo_card", slot: "promo_r", target: pageTarget === "collection" ? "collection" : "home" },
    coll_top: { key: "collection_header", slot: "coll_top", target: "collection" },
    coll_inline: { key: "promo_card", slot: "coll_inline", target: "collection" },
    pdp_strip: { key: "pdp_strip", slot: "pdp_strip", target: "product" },
    pdp_cross: { key: "pdp_cross_sell", slot: "pdp_cross", target: "product" },
    footer: { key: "footer_cta", slot: "footer", target: pageTarget === "search" ? "store" : pageTarget },
    search_top: { key: "search_results_banner", slot: "search_top", target: "search" },
  };
  const cfg = map[id] || map.hero;
  const backend = (placement && placement.backend) || {};
  const target = backend.target_type || cfg.target;
  const targetResource = backend.target_resource || null;
  const targetHandle = backend.target_handle || (targetResource && targetResource.handle) || (target === "collection" ? "fragancias" : target === "product" ? "boss-bottled-edp-100ml" : target === "search" ? "search" : null);
  const targetTitle = backend.target_title || (targetResource && targetResource.title) || (target === "collection" ? "Fragancias" : target === "product" ? "Boss Bottled EDP 100ml" : (placement && placement.page || "Inicio"));
  return {
    store_id: backend.store_id || window.AIJOLOT_STORE_ID || "00000000-0000-0000-0000-000000000101",
    placement_type_key: backend.placement_type_key || cfg.key,
    mode: isNew ? "new_section" : "existing_section",
    target_type: target,
    target_resource_gid: backend.target_resource_gid || (targetResource && targetResource.shopify_gid) || null,
    target_handle: targetHandle,
    target_title: targetTitle,
    existing_placement_key: isNew ? null : (backend.existing_placement_key || cfg.slot),
    existing_placement_label: isNew ? null : (backend.existing_placement_label || (placement && placement.name || "Hero principal")),
    existing_placement_size: backend.existing_placement_size || (placement && placement.size) || null,
    slot: isNew ? ((placement.layout && placement.layout.dropAt) || backend.slot || cfg.slot) : (backend.slot || cfg.slot),
    slot_order: backend.slot_order || 0,
    scope_rule: (placement && placement.scope) || {},
    layout_json: (placement && placement.layout) || { cols: [{ rows: 1, w: 1, align: "center" }] },
  };
}

const CampaignApi = {
  async create(input) { return AijolotApi.post(AijolotApi.v1("/campaigns"), input || {}); },
  async list() { return AijolotApi.get(AijolotApi.v1("/campaigns")); },
  async listSafe() {
    try {
      const data = await this.list();
      return { ok: true, fallback: false, data: Array.isArray(data) ? data : [] };
    } catch (e) {
      return { ok: false, fallback: true, reason: errorText(e), data: [] };
    }
  },
  async get(id) { return AijolotApi.get(AijolotApi.v1(`/campaigns/${id}`)); },
  async patch(id, fields) { return AijolotApi.patch(AijolotApi.v1(`/campaigns/${id}`), fields); },
  toRecentCard(campaign) {
    const brief = campaign && campaign.structured_brief || {};
    const status = (campaign && campaign.status) || "draft";
    const isDraft = ["draft", "intake", "generating", "review", "failed"].includes(status);
    const tone = status === "published" || status === "live" ? "green" : status === "approved" ? "cyan" : status === "scheduled" ? "purple" : status === "failed" ? "red" : "amber";
    const labels = { draft: "Borrador backend", intake: "Brief backend", generating: "Generando", review: "En revisión", approved: "Aprobada", scheduled: "Programada", published: "Publicada", live: "Publicada", failed: "Error" };
    const promo = brief.cta || brief.urgency || "Backend";
    const windowLabel = brief.deadline ? `Deadline ${brief.deadline}` : (brief.placement || "Sin deadline");
    return {
      id: campaign && campaign.id,
      title: (campaign && campaign.title) || brief.goal || "Campaña sin título",
      promo,
      window: windowLabel,
      status,
      tone,
      statusLabel: labels[status] || status || "Backend",
      action: isDraft ? "Continuar" : "Ver performance",
      campaign,
      source: "backend",
    };
  },
};

const StoreApi = {
  async list() { return AijolotApi.get(AijolotApi.v1("/stores")); },
  async get(storeId) { return AijolotApi.get(AijolotApi.v1(`/stores/${storeId || AIJOLOT_DEMO_IDS.store}`)); },
  async resources(storeId, resourceType) { return AijolotApi.get(AijolotApi.v1(`/stores/${storeId || AIJOLOT_DEMO_IDS.store}/shopify/resources?resource_type=${encodeURIComponent(resourceType || "collection")}`)); },
  // On-demand product integration: resolve any Shopify product live by search term
  // (bypasses the bulk-sync cap) and persist it. Returns { matched, written, items }.
  async searchProducts(query, storeId, limit) {
    return AijolotApi.post(AijolotApi.v1(`/stores/${storeId || AIJOLOT_DEMO_IDS.store}/shopify/products/search`), { query, limit: limit || 8 });
  },
  async searchProductsSafe(query, storeId, limit) {
    try { return { ok: true, data: await this.searchProducts(query, storeId, limit) }; }
    catch (e) { return { ok: false, reason: errorText(e), data: { items: [] } }; }
  },
  async placementTypes(storeId) { return AijolotApi.get(AijolotApi.v1(`/stores/${storeId || AIJOLOT_DEMO_IDS.store}/placement-types`)); },
  async placementTargets(storeId, placementTypeKey) { return AijolotApi.get(AijolotApi.v1(`/stores/${storeId || AIJOLOT_DEMO_IDS.store}/placement-types/${encodeURIComponent(placementTypeKey)}/targets`)); },
  async listSafe() {
    try { return { ok: true, fallback: false, data: await this.list() }; }
    catch (e) { return { ok: false, fallback: true, reason: errorText(e), data: [] }; }
  },
  async getSafe(storeId) {
    try { return { ok: true, fallback: false, data: await this.get(storeId) }; }
    catch (e) { return { ok: false, fallback: true, reason: errorText(e), data: null }; }
  },
  async resourcesSafe(storeId, resourceType) {
    try { return { ok: true, fallback: false, data: await this.resources(storeId, resourceType) }; }
    catch (e) { return { ok: false, fallback: true, reason: errorText(e), data: [] }; }
  },
  async placementTypesSafe(storeId) {
    try { return { ok: true, fallback: false, data: await this.placementTypes(storeId) }; }
    catch (e) { return { ok: false, fallback: true, reason: errorText(e), data: [] }; }
  },
  async placementTargetsSafe(storeId, placementTypeKey) {
    try { return { ok: true, fallback: false, data: await this.placementTargets(storeId, placementTypeKey) }; }
    catch (e) { return { ok: false, fallback: true, reason: errorText(e), data: null }; }
  },
};

const PlacementApi = {
  payloadFromPrototype: placementPayloadFromPrototype,
  async validate(placement) { return AijolotApi.post(AijolotApi.v1("/placements/validate"), placement); },
  async get(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend placement lookup.", null);
    const data = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/placement`));
    return { ok: true, fallback: false, data };
  },
  async save(campaign, placement) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend placement API requires a UUID campaign; local intake uses prototype ids unless Supabase is configured.", placement);
    const payload = placementPayloadFromPrototype(placement);
    await this.validate(payload);
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/placement`), payload);
    return { ok: true, fallback: false, data };
  },
};

const CatalogApi = {
  async createSnapshot(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend catalog snapshot requires a UUID campaign.", null);
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/catalog-snapshot`), input || { store_id: AIJOLOT_DEMO_IDS.store, resource_types: ["collection", "product"], limit: 5 });
    return { ok: true, fallback: false, data };
  },
  async getSnapshot(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend catalog snapshot lookup.", null);
    const data = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/catalog-snapshot`));
    return { ok: true, fallback: false, data };
  },
};

const ArtDirectionApi = {
  // C0 — user override of the agent-recommended creative mode. Reads the stored
  // art direction (to not clobber other fields) and PUTs mode_source='user'.
  async setCreativeMode(campaign, { creative_mode, include_humans }) {
    if (!isApiCampaign(campaign)) return fallbackResult("El modo creativo requiere una campaña UUID.", null);
    try {
      let current = {};
      try { current = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/art-direction`)); } catch (e) { current = {}; }
      const payload = {
        background_mode: current.background_mode || "usage",
        hero_style_key: current.hero_style_key || null,
        model_key: current.model_key || null,
        custom_model: current.custom_model || {},
        fold_percentage: current.fold_percentage || 55,
        layout_hints: current.layout_hints || {},
        creative_mode,
        include_humans: !!include_humans,
        mode_source: "user",
      };
      const data = await AijolotApi.put(AijolotApi.v1(`/campaigns/${campaign.id}/art-direction`), payload);
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("No se pudo guardar el modo creativo (" + errorText(e) + ").", null); }
  },
  async get(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend art-direction lookup.", null);
    const data = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/art-direction`));
    return { ok: true, fallback: false, data };
  },
  async save(campaign, art, placement) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend art-direction API requires a UUID campaign; saved locally in prototype state.", art);
    const payload = {
      background_mode: art.bg || "usage",
      hero_style_key: art.heroStyle || null,
      model_key: art.model || null,
      custom_model: art.customModel || {},
      fold_percentage: art.fold || 55,
      layout_hints: { placement: placement || null },
    };
    const data = await AijolotApi.put(AijolotApi.v1(`/campaigns/${campaign.id}/art-direction`), payload);
    return { ok: true, fallback: false, data };
  },
};

const GenerationApi = {
  async start(campaign, metadata) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend generation runs require a UUID campaign; showing labeled prototype progress.", { id: localId("run"), status: "succeeded" });
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/generation-runs`), { metadata: metadata || {} });
    return { ok: true, fallback: false, data };
  },
  async latest(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend generation lookup.", null);
    const data = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/generation-runs/latest`));
    return { ok: true, fallback: false, data };
  },
  async get(runId) { return AijolotApi.get(AijolotApi.v1(`/generation-runs/${runId}`)); },
  async events(runId) { return AijolotApi.get(AijolotApi.v1(`/generation-runs/${runId}/events`)); },
  async preview(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend preview lookup.", "");
    const data = await AijolotApi.text(AijolotApi.v1(`/campaigns/${campaign.id}/preview`), { headers: { Accept: "text/html" } });
    return { ok: true, fallback: false, data };
  },
  async audit(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend audit lookup.", null);
    const data = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/audit-report`));
    return { ok: true, fallback: false, data };
  },
  async revisions(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend revision lookup.", []);
    const data = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/revisions`));
    return { ok: true, fallback: false, data };
  },
  // Resolve the most recent backend revision so canvas/performance can map
  // layout (A|B|C) + audience (segment_key) selections to real variant UUIDs.
  async latestRevision(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend revision lookup.", null);
    const list = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/revisions`));
    const rows = Array.isArray(list) ? list : [];
    if (!rows.length) return fallbackResult("Backend has no revisions yet for this campaign.", null);
    const latest = rows.reduce((a, b) => ((b.revision_number || 0) >= (a.revision_number || 0) ? b : a));
    return { ok: true, fallback: false, data: latest };
  },
  async selectVariant(campaign, variantId) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend variant selection.", null);
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/variants/${variantId}/select`));
    return { ok: true, fallback: false, data };
  },
  async regenerate(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend regeneration.", null);
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/regenerate`), input || {});
    return { ok: true, fallback: false, data };
  },
};

const ReviewApi = {
  async requestApproval(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend approval requires a UUID campaign and generated revision.", null);
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/approval/request`), input || {});
    return { ok: true, fallback: false, data };
  },
  async approval(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend approval lookup.", null);
    const data = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/approval`));
    return { ok: true, fallback: false, data };
  },
  // Lazily resolve (or create) the approval thread for a campaign revision.
  // Returns the {ok,fallback,reason,data} envelope; approval/comment services
  // fail closed with 503 in the local no-Supabase demo, surfaced as fallback.
  async ensureThread(campaign, revisionId) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend approval requires a UUID campaign and generated revision.", null);
    try {
      const state = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/approval`));
      const existing = state && (state.thread || state.approval_thread || (state.thread_id ? state : null));
      const threadId = (existing && (existing.id || existing.thread_id)) || state.thread_id || (state.thread && state.thread.id);
      if (threadId) return { ok: true, fallback: false, data: { ...state, id: threadId } };
    } catch (e) {
      if (e.status && e.status !== 404) return fallbackResult("Servicio de aprobación no disponible (" + errorText(e) + ").", null);
    }
    try {
      const thread = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/approval/request`), {
        revision_id: revisionId || null,
        requested_by: AIJOLOT_DEMO_IDS.user,
        reviewers: [{ user_id: AIJOLOT_DEMO_IDS.user, role_label: "designer" }],
      });
      return { ok: true, fallback: false, data: thread };
    } catch (e) {
      return fallbackResult("Servicio de aprobación no disponible (" + errorText(e) + ").", null);
    }
  },
  async approve(threadId, note) {
    if (!threadId) return fallbackResult("No hay hilo de aprobación de backend; aprobación local.", null);
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/approval-threads/${threadId}/approve`), { user_id: AIJOLOT_DEMO_IDS.user, note: note || null });
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Backend no registró la aprobación (" + errorText(e) + ").", null); }
  },
  async requestChangesThread(threadId, note) {
    if (!threadId) return fallbackResult("No hay hilo de aprobación de backend; cambios locales.", null);
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/approval-threads/${threadId}/request-changes`), { user_id: AIJOLOT_DEMO_IDS.user, note: note || null });
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Backend no registró la solicitud de cambios (" + errorText(e) + ").", null); }
  },
  async addComment(threadId, input) {
    if (!threadId) return fallbackResult("No hay hilo de aprobación de backend; comentario local.", null);
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/approval-threads/${threadId}/comments`), input);
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Backend no guardó el comentario (" + errorText(e) + ").", null); }
  },
  async resolveCommentSafe(commentId, input) {
    try {
      const data = await AijolotApi.patch(AijolotApi.v1(`/comments/${commentId}/resolve`), input || {});
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Backend no resolvió el comentario (" + errorText(e) + ").", null); }
  },
  // Raw passthroughs kept for callers that handle their own error envelope.
  async comment(threadId, input) { return AijolotApi.post(AijolotApi.v1(`/approval-threads/${threadId}/comments`), input); },
  async resolveComment(commentId, input) { return AijolotApi.patch(AijolotApi.v1(`/comments/${commentId}/resolve`), input || {}); },
  async approveThread(threadId, input) { return AijolotApi.post(AijolotApi.v1(`/approval-threads/${threadId}/approve`), input); },
  async requestChanges(threadId, input) { return AijolotApi.post(AijolotApi.v1(`/approval-threads/${threadId}/request-changes`), input); },
  async refinement(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend refinement requires a UUID campaign.", null);
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/refinement-requests`), input);
    return { ok: true, fallback: false, data };
  },
  async schedule(campaign, schedule) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend scheduling requires an approved UUID campaign and backend revision; local/prototype campaigns cannot be marked scheduled.", null);
    const startsAt = new Date(schedule.start).toISOString();
    const endsAt = schedule.auto && schedule.end ? new Date(schedule.end).toISOString() : null;
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/schedule`), { starts_at: startsAt, ends_at: endsAt, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC", auto_unpublish: !!schedule.auto });
    return { ok: true, fallback: false, data };
  },
  async updateSchedule(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend schedule update requires a UUID campaign.", null);
    const data = await AijolotApi.patch(AijolotApi.v1(`/campaigns/${campaign.id}/schedule`), input || {});
    return { ok: true, fallback: false, data };
  },
  async cancelSchedule(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend schedule cancel requires a UUID campaign.", null);
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/schedule/cancel`));
    return { ok: true, fallback: false, data };
  },
  async publish(campaign, dryRun) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend publishing requires a scheduled UUID campaign; local/prototype publish is unavailable/fail-closed.", null);
    const q = dryRun === undefined ? "" : `?dry_run=${dryRun ? "true" : "false"}`;
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/publish${q}`));
    return { ok: true, fallback: false, data };
  },
  async unpublish(campaign, dryRun) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend unpublish requires a UUID campaign.", null);
    const q = dryRun === undefined ? "" : `?dry_run=${dryRun ? "true" : "false"}`;
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/unpublish${q}`));
    return { ok: true, fallback: false, data };
  },
  // F10/F11 — install the Aijolot Liquid placeholder assets before first publish.
  async installThemeFiles(storeId, dryRun) {
    const sid = storeId || AIJOLOT_DEMO_IDS.store;
    const q = dryRun === undefined ? "" : `?dry_run=${dryRun ? "true" : "false"}`;
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/stores/${sid}/shopify/install-theme-files${q}`));
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Backend no instaló los placeholders del tema (" + errorText(e) + ").", null); }
  },
};

const PerformanceApi = {
  async get(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend performance lookup; showing labeled non-live prototype metrics.", null);
    const data = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/performance`));
    return { ok: true, fallback: false, data };
  },
  async snapshot(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend performance snapshot.", null);
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/performance/snapshots`), input || { source: "manual" });
    return { ok: true, fallback: false, data };
  },
  async proposal(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("No UUID campaign for backend optimization proposal.", null);
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/optimization-proposals`), input);
    return { ok: true, fallback: false, data };
  },
};

// --- F3 live catalog sync + search ---
StoreApi.sync = async function (storeId, input) {
  const sid = storeId || AIJOLOT_DEMO_IDS.store;
  try {
    const data = await AijolotApi.post(AijolotApi.v1(`/stores/${sid}/shopify/sync`), input || { dry_run: false });
    return { ok: true, fallback: false, data };
  } catch (e) { return fallbackResult("Sync en vivo no disponible (" + errorText(e) + ").", null); }
};
CatalogApi.search = async function (storeId, query, resourceType) {
  const sid = storeId || AIJOLOT_DEMO_IDS.store;
  const params = new URLSearchParams({ resource_type: resourceType || "product" });
  if (query) params.set("q", query);
  try {
    const data = await AijolotApi.get(AijolotApi.v1(`/stores/${sid}/shopify/resources?${params.toString()}`));
    return { ok: true, fallback: false, data: Array.isArray(data) ? data : (data && data.items) || [] };
  } catch (e) { return fallbackResult("Búsqueda de catálogo no disponible (" + errorText(e) + ").", []); }
};

// --- F7 AI backgrounds ---
const BackgroundApi = {
  async generate(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("Los fondos AI requieren una campaña UUID con revisión generada.", { options: [] });
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/background-options`), input || { count: 3 });
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Fondos AI no disponibles (" + errorText(e) + ").", { options: [] }); }
  },
};

// --- F8 descriptive art prompts + generation ---
const ArtApi = {
  async artPrompts(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("Las propuestas de arte requieren una campaña UUID.", { options: [] });
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/art-prompts`), input || { shot_type: "hero", count: 3 });
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Propuestas de arte no disponibles (" + errorText(e) + ").", { options: [] }); }
  },
  async modelPrompts(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("Las propuestas de modelo requieren una campaña UUID.", { options: [] });
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/model-prompts`), input || { count: 3 });
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Propuestas de modelo no disponibles (" + errorText(e) + ").", { options: [] }); }
  },
  async generateArt(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("Generar arte requiere una campaña UUID con revisión.", null);
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/generate-art`), input || {});
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Generación de arte no disponible (" + errorText(e) + ").", null); }
  },
  // Art Direction: per-variant concept proposal (+ optional feedback iteration).
  async artConcepts(campaign, input) {
    if (!isApiCampaign(campaign)) return fallbackResult("La propuesta de concepto requiere una campaña UUID.", { concepts: [] });
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/art-concepts`), input || {});
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Propuesta de concepto no disponible (" + errorText(e) + ").", { concepts: [] }); }
  },
};

// --- banner-edit: scoped, non-destructive edit (text/background/image) ---
GenerationApi.bannerEdit = async function (campaign, prompt, targetNodes, sourceRevisionId) {
  if (!isApiCampaign(campaign)) return fallbackResult("La edición de banner requiere una campaña UUID.", null);
  const input = { prompt: prompt || "Editar banner" };
  if (Array.isArray(targetNodes) && targetNodes.length) input.target_nodes = targetNodes;
  if (sourceRevisionId) input.source_revision_id = sourceRevisionId;
  try {
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/banner-edit`), input);
    return { ok: true, fallback: false, data };
  } catch (e) { return fallbackResult("Edición de banner no disponible (" + errorText(e) + ").", null); }
};

// --- F9 agentic refine (regenerate with classified target nodes) ---
GenerationApi.agenticRefine = async function (campaign, prompt, targetNodes) {
  if (!isApiCampaign(campaign)) return fallbackResult("El refinamiento agéntico requiere una campaña UUID.", null);
  const input = { prompt: prompt || "Refinar banner" };
  if (Array.isArray(targetNodes) && targetNodes.length) input.target_nodes = targetNodes;
  try {
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/regenerate`), input);
    return { ok: true, fallback: false, data };
  } catch (e) { return fallbackResult("Refinamiento agéntico no disponible (" + errorText(e) + ").", null); }
};

// --- Direct, instant banner edit (no LLM) — Phase 3 mechanism A ---
GenerationApi.applyEdits = async function (campaign, structuredChanges, sourceRevisionId) {
  if (!isApiCampaign(campaign)) return fallbackResult("La edición directa requiere una campaña UUID.", null);
  const input = { structured_changes: structuredChanges || {} };
  if (sourceRevisionId) input.source_revision_id = sourceRevisionId;
  try {
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/apply-edits`), input);
    return { ok: true, fallback: false, data };
  } catch (e) { return fallbackResult("Edición directa no disponible (" + errorText(e) + ").", null); }
};

// --- Pinned comments → agent (Phase 3 mechanism B) ---
// Creates a refinement request (server weaves in the pins' coordinates), to be run
// via GenerationApi.regenerate({ refinement_request_id }).
ReviewApi.createRefinementRequest = async function (campaign, input) {
  if (!isApiCampaign(campaign)) return fallbackResult("El refinamiento requiere una campaña UUID.", null);
  try {
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/refinement-requests`), input || {});
    return { ok: true, fallback: false, data };
  } catch (e) { return fallbackResult("No se pudo crear la solicitud de cambios (" + errorText(e) + ").", null); }
};

// --- Geometry helpers for the drag/resize editor (client-side parity with clamp_layout) ---
function pxDeltaToPct(rect, dx, dy) {
  return { dx: rect && rect.width ? (dx / rect.width) * 100 : 0, dy: rect && rect.height ? (dy / rect.height) * 100 : 0 };
}
function clampLayoutClient(layout) {
  const L = layout || {};
  const c = (v, lo, hi, d) => { const n = parseFloat(v); return Number.isFinite(n) ? Math.max(lo, Math.min(hi, n)) : d; };
  const align = ["left", "center", "right"].includes(L.textAlign) ? L.textAlign : "left";
  return {
    textX: c(L.textX, 2, 60, 6), textY: c(L.textY, 10, 90, 50), textW: c(L.textW, 24, 70, 48), textAlign: align,
    heroX: c(L.heroX, 25, 92, 74), heroY: c(L.heroY, 12, 88, 50), heroW: c(L.heroW, 24, 80, 46), heroH: c(L.heroH, 55, 90, 80),
    heroBehind: !!L.heroBehind, aspectRatio: 2.4,
  };
}

// --- Iterative campaign plan (cheap gate BEFORE the costly build) ---
const PlanApi = {
  // Kick off the plan phase (concept + wireframe, no image). Returns a poll-able run.
  async start(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("El plan de campaña requiere una campaña UUID.", null);
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/plan-runs`), {});
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("No se pudo iniciar el plan (" + errorText(e) + ").", null); }
  },
  // Fetch the latest pending plan (readable summary + deterministic wireframe spec).
  async get(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("El plan de campaña requiere una campaña UUID.", null);
    try {
      const data = await AijolotApi.get(AijolotApi.v1(`/campaigns/${campaign.id}/plan`));
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Plan no disponible en backend (" + errorText(e) + ").", null); }
  },
  // Re-draft the plan with feedback (never re-runs image work). Returns a poll-able run.
  async iterate(campaign, prompt, targetNodes) {
    if (!isApiCampaign(campaign)) return fallbackResult("Iterar el plan requiere una campaña UUID.", null);
    const input = { prompt: prompt || "Refina el plan" };
    if (Array.isArray(targetNodes) && targetNodes.length) input.target_nodes = targetNodes;
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/plan/iterate`), input);
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("No se pudo iterar el plan (" + errorText(e) + ").", null); }
  },
  // Approve the plan → starts the costly BUILD run. Returns { generation_run, revision }.
  async approve(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("Aprobar el plan requiere una campaña UUID.", null);
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/plan/approve`), {});
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("No se pudo aprobar el plan (" + errorText(e) + ").", null); }
  },
};

// --- F4 explicability: "Decisión / Razones / Fuentes" card ------------------
// Renders a DecisionTrace ({decision, reasons[], sources[{type,id,title,score}]})
// emitted by the backend in generation events / plan / revision concepts.
function DecisionTraceCard({ trace, compact }) {
  if (!trace || (!Array.isArray(trace.reasons) || !trace.reasons.length) && !trace.decision) return null;
  const sources = Array.isArray(trace.sources) ? trace.sources : [];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7, padding: compact ? "8px 10px" : "10px 12px",
      borderRadius: 10, background: "rgba(8,145,178,0.05)", border: "1px solid rgba(8,145,178,0.18)" }}>
      {trace.decision ? (
        <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 12, color: "#002B57", display: "flex", alignItems: "center", gap: 6 }}>
          <Icon name="lightbulb" size={13} color="#0891B2" /> {trace.decision}
        </div>
      ) : null}
      {(trace.reasons || []).map((r, i) => (
        <div key={i} style={{ fontFamily: "Inter", fontSize: 11.5, color: "#475569", lineHeight: 1.45, display: "flex", gap: 6 }}>
          <span style={{ color: "#0891B2" }}>·</span><span>{r}</span>
        </div>
      ))}
      {sources.length ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 2 }}>
          {sources.map((src, i) => (
            <span key={i} title={src.score != null ? `score ${Number(src.score).toFixed(2)}` : undefined} style={{
              display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 9999,
              background: src.type === "brand" ? "rgba(255,210,63,0.18)" : "rgba(34,211,238,0.12)",
              border: "1px solid rgba(8,145,178,0.2)", fontFamily: "Inter", fontSize: 10, fontWeight: 600, color: "#0E7490" }}>
              <Icon name={src.type === "brand" ? "palette" : "database"} size={10} />
              {src.title || src.type}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// Find the freshest decision_trace within a list of generation events.
function traceFromEvents(events) {
  const rows = Array.isArray(events) ? events : [];
  for (let i = rows.length - 1; i >= 0; i--) {
    const t = rows[i] && rows[i].output_summary && rows[i].output_summary.decision_trace;
    if (t) return t;
  }
  return null;
}

// --- Fase 0: proactive agent suggestions -------------------------------------
const SuggestionsApi = {
  async list(status) {
    try {
      const data = await AijolotApi.get(AijolotApi.v1(`/suggestions${status ? `?status=${status}` : ""}`));
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("Sugerencias no disponibles (" + errorText(e) + ").", null); }
  },
  async accept(id) {
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/suggestions/${id}/accept`), {});
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("No se pudo aceptar la sugerencia (" + errorText(e) + ").", null); }
  },
  async dismiss(id) {
    try {
      const data = await AijolotApi.post(AijolotApi.v1(`/suggestions/${id}/dismiss`), {});
      return { ok: true, fallback: false, data };
    } catch (e) { return fallbackResult("No se pudo descartar la sugerencia (" + errorText(e) + ").", null); }
  },
};

Object.assign(window, {
  SuggestionsApi,
  DecisionTraceCard, traceFromEvents,
  Icon, GlassCard, Button, Badge, BADGE_TONES, Kicker, Spinner, Avatar,
  AijolotApi, CampaignApi, StoreApi, PlacementApi, CatalogApi, ArtDirectionApi,
  GenerationApi, PlanApi, ReviewApi, PerformanceApi, BackgroundApi, ArtApi, API_V1, UUID_RE, isApiCampaign,
  AIJOLOT_DEMO_IDS, AIJOLOT_DEMO_AUTH_HEADERS, apiPath, apiV1Path, normalizeApiOrigin, errorText,
  pxDeltaToPct, clampLayoutClient,
});
