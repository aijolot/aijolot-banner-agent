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
// Static prototype integration point. New backend calls use /api/v1 and default to
// http://localhost:8000 unless the hosting page defines window.AIJOLOT_API_BASE.
window.API_BASE = window.AIJOLOT_API_BASE || window.API_BASE || "http://localhost:8000";
const API_V1 = "/api/v1";
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isApiCampaign(campaign) { return !!(campaign && UUID_RE.test(campaign.id || "")); }
function localId(prefix) {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}
function fallbackResult(reason, data) { return { ok: true, fallback: true, reason: reason || "mock/local fallback", data }; }

const AijolotApi = {
  base: window.API_BASE,
  v1(path) { return API_V1 + path; },
  async request(path, options) {
    const resp = await fetch(this.base + path, {
      ...options,
      headers: { "Accept": "application/json", ...(options && options.headers ? options.headers : {}) },
    });
    const text = await resp.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch (_) { body = text; }
    if (!resp.ok) {
      const err = new Error((body && body.detail) || body || `HTTP ${resp.status}`);
      err.status = resp.status; err.body = body; throw err;
    }
    return body;
  },
  get(path) { return this.request(path); },
  post(path, body) { return this.request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }); },
  put(path, body) { return this.request(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }); },
  patch(path, body) { return this.request(path, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }); },
};

function placementPayloadFromPrototype(placement) {
  const id = placement && placement.id || "hero";
  const page = (placement && placement.page || "Inicio").toLowerCase();
  const isNew = placement && placement.layout && placement.layout.mode === "new";
  const pageTarget = page.includes("cole") ? "collection" : page.includes("producto") ? "product" : page.includes("búsqueda") || page.includes("busqueda") ? "search" : "home";
  const map = {
    announce: { key: "announcement_bar", slot: "announce", target: pageTarget === "search" ? "store" : pageTarget },
    hero: { key: "hero_main", slot: "hero", target: pageTarget === "collection" ? "collection" : "home" },
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
  const targetHandle = cfg.target === "collection" ? "fragancias" : cfg.target === "product" ? "boss-bottled-edp-100ml" : null;
  return {
    store_id: window.AIJOLOT_STORE_ID || "00000000-0000-0000-0000-000000000101",
    placement_type_key: cfg.key,
    mode: isNew ? "new_section" : "existing_section",
    target_type: cfg.target,
    target_handle: targetHandle,
    target_title: cfg.target === "collection" ? "Fragancias" : cfg.target === "product" ? "Boss Bottled EDP 100ml" : (placement && placement.page || "Inicio"),
    existing_placement_key: isNew ? null : cfg.slot,
    existing_placement_label: isNew ? null : (placement && placement.name || "Hero principal"),
    existing_placement_size: placement && placement.size || null,
    slot: isNew ? (placement.layout.dropAt || cfg.slot) : cfg.slot,
    slot_order: 0,
    scope_rule: (placement && placement.scope) || {},
    layout_json: (placement && placement.layout) || { cols: [{ rows: 1, w: 1, align: "center" }] },
  };
}

const CampaignApi = {
  async list() { return AijolotApi.get(AijolotApi.v1("/campaigns")); },
  async patch(id, fields) { return AijolotApi.patch(AijolotApi.v1(`/campaigns/${id}`), fields); },
};

const PlacementApi = {
  async save(campaign, placement) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend placement API requires a UUID campaign; local intake uses prototype ids unless Supabase is configured.", placement);
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/placement`), placementPayloadFromPrototype(placement));
    return { ok: true, fallback: false, data };
  },
};

const ArtDirectionApi = {
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
};

const ReviewApi = {
  async approveLocal(campaign, approverId, status) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend approval API requires generated revisions/reviewer UUIDs; using visible prototype approval state.", { approverId, status });
    // Full backend approval requires revision and reviewer UUIDs created by the generation pipeline.
    // The static prototype keeps the reviewer UX local until the Next.js migration owns auth/team identity.
    return fallbackResult("Static prototype approval controls are local; backend approval needs revision and reviewer UUID context.", { approverId, status });
  },
  async schedule(campaign, schedule) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend scheduling requires an approved UUID campaign; using visible prototype schedule state.", schedule);
    const startsAt = new Date(schedule.start).toISOString();
    const endsAt = schedule.auto && schedule.end ? new Date(schedule.end).toISOString() : null;
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/schedule`), { starts_at: startsAt, ends_at: endsAt, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC", auto_unpublish: !!schedule.auto });
    return { ok: true, fallback: false, data };
  },
  async publish(campaign) {
    if (!isApiCampaign(campaign)) return fallbackResult("Backend publishing requires a scheduled UUID campaign; using visible prototype publish state.", null);
    const data = await AijolotApi.post(AijolotApi.v1(`/campaigns/${campaign.id}/publish`));
    return { ok: true, fallback: false, data };
  },
};

Object.assign(window, { Icon, GlassCard, Button, Badge, BADGE_TONES, Kicker, Spinner, Avatar, AijolotApi, CampaignApi, PlacementApi, ArtDirectionApi, GenerationApi, ReviewApi, API_V1, UUID_RE, isApiCampaign });
