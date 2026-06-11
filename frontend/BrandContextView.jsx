/* global React, Icon, GlassCard, Button, Badge, Kicker, Spinner, Banner, BrandAPI, SEGMENTS */
// Aijolot Banner Agent — Brand Context (GH-26).
// Multi-brand CRUD wired to the FastAPI bridge (GET/PUT /brands), with a live
// banner preview driven by the selected brand. Falls back to in-memory seeds
// when the bridge is unreachable (BrandAPI handles that transparently).
// Brand Discovery + Tipografía (Task 9): Shopify evidence review, Gemini color-role
// recommendations and the font candidate workflow accumulate into the SAME local
// draft as manual edits — nothing persists until "Guardar cambios" (PUT /brands/{id}).
const { useState: useStateBC, useEffect: useEffectBC, useRef: useRefBC, useMemo: useMemoBC } = React;

const HEX_RE = /^#[0-9a-fA-F]{6}$/;
const FONTS = ["Space Grotesk", "Inter", "Georgia", "Helvetica", "Playfair Display"];

// ---- color helpers (for the live preview mapping) ----
function _hx(hex, i) { return parseInt(hex.replace("#", "").slice(i, i + 2), 16); }
function hexLum(hex) {
  const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(_hx(hex, 0)) + 0.7152 * f(_hx(hex, 2)) + 0.0722 * f(_hx(hex, 4));
}
function hexSat(hex) {
  const r = _hx(hex, 0) / 255, g = _hx(hex, 2) / 255, b = _hx(hex, 4) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
  return mx === 0 ? 0 : (mx - mn) / mx;
}
function hexRgba(hex, a) { return `rgba(${_hx(hex, 0)},${_hx(hex, 2)},${_hx(hex, 4)},${a})`; }

const ROLE_KEYS = ["primary", "secondary", "tertiary"];
const ROLE_COPY = {
  primary: { title: "Primario", fallbackLabel: "Primary", usage_hint: "Main brand color for dominant identity moments, headline emphasis, and major visual anchors.", agent_hint: "Prefer for main brand identity, key text/visual anchors, and high-recognition surfaces." },
  secondary: { title: "Secundario", fallbackLabel: "Secondary", usage_hint: "Support color for backgrounds, secondary surfaces, and balance around the primary color.", agent_hint: "Use for background fields, supporting surfaces, and composition balance." },
  tertiary: { title: "Terciario / Acento", fallbackLabel: "Tertiary / Accent", usage_hint: "Accent color for CTA, highlights, badges, and small high-attention elements.", agent_hint: "Use sparingly for CTA, promotional badges, urgency marks, and highlights." },
};

function paletteColorAt(palette, idx, fallback) {
  const c = (palette || [])[idx] || (palette || [])[0] || {};
  return { name: c.name || fallback.name, hex: HEX_RE.test(c.hex || "") ? c.hex : fallback.hex };
}
function ensureColorSystem(brand) {
  const palette = brand.palette || [];
  const fallbacks = [
    paletteColorAt(palette, 0, { name: "Primary", hex: "#0B1622" }),
    paletteColorAt(palette, 1, { name: "Secondary", hex: "#1E3A52" }),
    paletteColorAt(palette, 2, { name: "Accent", hex: "#C9A24B" }),
  ];
  const current = brand.color_system || {};
  const out = {};
  ROLE_KEYS.forEach((key, i) => {
    const r = current[key] || {};
    out[key] = {
      key,
      label: r.label || fallbacks[i].name || ROLE_COPY[key].fallbackLabel,
      hex: r.hex || fallbacks[i].hex,
      usage_hint: r.usage_hint || ROLE_COPY[key].usage_hint,
      agent_hint: r.agent_hint || ROLE_COPY[key].agent_hint,
      variants: Array.isArray(r.variants) ? r.variants : [],
    };
  });
  return out;
}
function syncPaletteFromColorSystem(brand, colorSystem) {
  const old = brand.palette || [];
  const roleColors = ROLE_KEYS.map((key, i) => {
    const r = colorSystem[key];
    return { name: r.label || ROLE_COPY[key].fallbackLabel || `Color ${i + 1}`, hex: r.hex };
  });
  const extra = old.slice(3);
  return roleColors.concat(extra);
}

// ---- typography helpers (Task 9 font system) ----
// Mirrors the backend whitelist (app/schemas/brand.py): a single family allows
// letters/digits/spaces/hyphens; a role value/stack additionally allows commas
// and quotes. NOTHING else (no parentheses, slashes, braces) so PUT never 422s.
const FONT_FAMILY_RE = /^[A-Za-z0-9][A-Za-z0-9 -]*$/;
const FONT_STACK_RE = /^[A-Za-z0-9 ,'"-]+$/;
const FONT_CATEGORIES = ["sans", "serif", "display", "mono", "handwritten"];

function fontValueOk(value, required) {
  const s = (value == null ? "" : String(value)).trim();
  if (!s) return !required;
  return FONT_STACK_RE.test(s);
}

// `"Family", generic` fallback stack. Only whitelist-safe characters (the backend
// css_stack rule allows letters/digits/spaces/hyphens/commas/quotes — no parens).
function buildFontStack(family, category) {
  const fam = (family || "").trim().replace(/\s+/g, " ");
  const quoted = fam.includes(" ") ? `"${fam}"` : fam;
  const generic = category === "serif" ? "Georgia, serif" : category === "mono" ? "monospace" : "Arial, sans-serif";
  return `${quoted}, ${generic}`;
}

// Light client-side mirror of the backend category heuristic (font_discovery.py).
function guessFontCategory(family) {
  const n = ` ${(family || "").toLowerCase()} `;
  if (/(mono|code|courier|consol)/.test(n)) return "mono";
  if (/(playfair|merriweather|lora|georgia|garamond|times|baskerville)/.test(n) || (n.includes("serif") && !n.includes("sans"))) return "serif";
  if (/(script|hand|caveat|brush|cursive)/.test(n)) return "handwritten";
  if (/(display|bebas|oswald|impact)/.test(n)) return "display";
  if (/(grotesk|grotesque|helvetica|arial|inter|roboto|lato|futura|sans)/.test(n)) return "sans";
  return "unknown";
}

// Map raw discovery evidence (DiscoveredFont) onto a strict FontCandidate shape so
// approving it later survives the backend PUT validation.
function discoveredFontToCandidate(font) {
  const family = ((font && font.family) || "").trim().replace(/\s+/g, " ");
  if (!family) return null;
  const category = guessFontCategory(family);
  const source = String((font && font.source) || "").toLowerCase().startsWith("css") ? "storefront_css" : "shopify_theme";
  return {
    family,
    css_stack: (font && font.css_stack) || buildFontStack(family, category),
    category,
    source,
    status: "candidate",
    recommended_roles: [],
    rationale: font && font.sample_usage ? `Descubierta en ${font.source} (${font.sample_usage})` : `Descubierta en ${(font && font.source) || "Shopify"}`,
    evidence_refs: font && font.source ? [font.source] : [],
  };
}

// Normalize typography for legacy payloads/seeds: optional roles -> null when empty,
// approved/discarded font lists always arrays so the UI never crashes.
function ensureTypography(brand) {
  const t = (brand && brand.typography) || {};
  const opt = (v) => { const s = (v == null ? "" : String(v)).trim(); return s ? s : null; };
  return {
    ...t,
    display: t.display || "Space Grotesk",
    body: t.body || "Inter",
    headline: opt(t.headline),
    accent: opt(t.accent),
    approved_fonts: Array.isArray(t.approved_fonts) ? t.approved_fonts : [],
    discarded_fonts: Array.isArray(t.discarded_fonts) ? t.discarded_fonts : [],
  };
}

function apiErrorMessage(e, fallback) {
  if (!e) return fallback;
  if (typeof e.body === "string") return e.body;
  if (e.body && e.body.detail) return typeof e.body.detail === "string" ? e.body.detail : JSON.stringify(e.body.detail);
  if (e.message) return e.message;
  if (e.status) return `HTTP ${e.status}`;
  return fallback;
}

// Map brand color roles (preferred) or arbitrary legacy palette → the Banner's palette variables.
function paletteToVars(palette, colorSystem) {
  if (colorSystem && colorSystem.primary && colorSystem.secondary && colorSystem.tertiary) {
    const p = colorSystem.primary.hex, s = colorSystem.secondary.hex, t = colorSystem.tertiary.hex;
    if (HEX_RE.test(p) && HEX_RE.test(s) && HEX_RE.test(t)) {
      const bgA = hexLum(p) <= hexLum(s) ? p : s;
      const bgB = hexLum(p) <= hexLum(s) ? s : p;
      const ink = hexLum(bgA) < 0.45 ? "#FFFFFF" : p;
      return { bgA, bgB, ink, sub: hexRgba(ink, 0.72), accent: t, chip: t, glow: hexRgba(t, 0.32), bottle: `linear-gradient(160deg,${bgB},${bgA})`, cap: t };
    }
  }
  const valid = (palette || []).filter((c) => HEX_RE.test(c.hex));
  if (!valid.length) return SEGMENTS.masculino.palette;
  const byLum = [...valid].sort((a, b) => hexLum(a.hex) - hexLum(b.hex));
  const bgA = byLum[0].hex, bgB = (byLum[1] || byLum[0]).hex, ink = byLum[byLum.length - 1].hex;
  const accent = [...valid].sort((a, b) => hexSat(b.hex) - hexSat(a.hex))[0].hex;
  return { bgA, bgB, ink, sub: hexRgba(ink, 0.72), accent, chip: accent, glow: hexRgba(accent, 0.32), bottle: `linear-gradient(160deg,${bgB},${bgA})`, cap: accent };
}

function brandToSeg(brand) {
  const phrases = (brand.voice && brand.voice.required_phrases) || [];
  return {
    id: brand.id || "preview",
    eyebrow: (brand.name || "Marca").toUpperCase(),
    headline: "Tu estilo,\ntu momento.",
    sub: phrases[0] || "Descubre la nueva colección esta semana.",
    cta: "Comprar ahora",
    product: { name: brand.name || "Producto" },
    palette: paletteToVars(brand.palette, brand.color_system),
  };
}

// ---- small editors ----
function Field({ label, value, onChange, placeholder, error, mono }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5, flex: 1, minWidth: 0 }}>
      <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, color: "#68737D" }}>{label}</span>
      <input value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={{
        border: `1px solid ${error ? "#F87171" : "#E2E8F0"}`, borderRadius: 9, padding: "8px 11px", outline: "none",
        fontFamily: mono ? "Space Grotesk" : "Inter", fontSize: 12.5, color: "#002B57", background: "#fff",
      }} />
      {error ? <span style={{ fontFamily: "Inter", fontSize: 10.5, color: "#EF4444" }}>{error}</span> : null}
    </div>
  );
}

function ChipList({ items, onChange, placeholder, tone = "cyan", emptyHint }) {
  const [val, setVal] = useStateBC("");
  const TONE = { cyan: ["#22D3EE", "rgba(34,211,238,.12)", "#0891B2"], pink: ["#F72585", "rgba(247,37,133,.1)", "#F72585"], green: ["#10B981", "rgba(16,185,129,.1)", "#16A34A"] }[tone];
  const add = () => { const v = val.trim(); if (!v) return; if (!items.includes(v)) onChange([...items, v]); setVal(""); };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
        {items.length === 0 && emptyHint ? <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>{emptyHint}</span> : null}
        {items.map((t) => (
          <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "Inter", fontSize: 11, fontWeight: 600, padding: "4px 10px", borderRadius: 9999, border: `1px solid ${TONE[0]}`, background: TONE[1], color: TONE[2] }}>
            {t}
            <button onClick={() => onChange(items.filter((x) => x !== t))} style={{ border: "none", background: "transparent", cursor: "pointer", color: TONE[2], padding: 0, display: "inline-flex" }}><Icon name="x" size={11} /></button>
          </span>
        ))}
      </div>
      <div style={{ display: "flex", gap: 7 }}>
        <input value={val} onChange={(e) => setVal(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} placeholder={placeholder} style={{ flex: 1, border: "1px solid #E2E8F0", borderRadius: 8, padding: "7px 10px", fontFamily: "Inter", fontSize: 12, color: "#002B57", outline: "none" }} />
        <Button variant="secondary" icon="plus" onClick={add}>Añadir</Button>
      </div>
    </div>
  );
}

function TextAreaField({ label, value, onChange, placeholder, rows = 2 }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5, flex: 1, minWidth: 0 }}>
      <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, color: "#68737D" }}>{label}</span>
      <textarea value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={rows} style={{
        border: "1px solid #E2E8F0", borderRadius: 9, padding: "8px 11px", outline: "none", resize: "vertical",
        fontFamily: "Inter", fontSize: 12.5, color: "#002B57", background: "#fff", lineHeight: 1.35,
      }} />
    </div>
  );
}

// Collapsible evidence/system group with a compact uppercase header.
function ToggleSection({ title, count, defaultOpen = false, tone = "#0891B2", children }) {
  const [open, setOpen] = useStateBC(defaultOpen);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
      <button onClick={() => setOpen((o) => !o)} style={{ display: "inline-flex", alignItems: "center", gap: 6, alignSelf: "flex-start", border: "none", background: "transparent", cursor: "pointer", padding: 0, color: tone, fontFamily: "Inter", fontSize: 11, fontWeight: 800, letterSpacing: ".06em", textTransform: "uppercase" }}>
        <Icon name={open ? "chevron-down" : "chevron-right"} size={13} />
        {title}{count != null ? ` · ${count}` : ""}
      </button>
      {open ? children : null}
    </div>
  );
}

function ColorRoleEditor({ roleKey, role, draft, online, onRoleChange, onOnlineChange }) {
  const [suggestState, setSuggestState] = useStateBC({ loading: false, error: "", suggestions: [] });
  const copy = ROLE_COPY[roleKey];
  const baseBad = !HEX_RE.test(role.hex || "");
  const variants = role.variants || [];
  const setRole = (patch) => onRoleChange(roleKey, { ...role, ...patch });
  const setVariant = (i, patch) => setRole({ variants: variants.map((v, j) => j === i ? { ...v, ...patch } : v) });
  const addVariant = () => setRole({ variants: variants.concat([{ name: "Nueva variante", hex: role.hex || "#22D3EE", usage_hint: "", source: "manual" }]) });
  const removeVariant = (i) => setRole({ variants: variants.filter((_, j) => j !== i) });
  const acceptedHexes = new Set(variants.map((v) => (v.hex || "").toUpperCase()));
  const acceptSuggestion = (s) => {
    const hex = (s.hex || "").toUpperCase();
    if (!HEX_RE.test(hex) || acceptedHexes.has(hex)) return;
    setRole({ variants: variants.concat([{ name: s.name || "AI suggestion", hex, usage_hint: s.usage_hint || "", source: "ai_suggested" }]) });
  };
  const acceptAll = () => {
    const next = variants.slice();
    const seen = new Set(next.map((v) => (v.hex || "").toUpperCase()));
    (suggestState.suggestions || []).forEach((s) => {
      const hex = (s.hex || "").toUpperCase();
      if (HEX_RE.test(hex) && !seen.has(hex)) {
        next.push({ name: s.name || "AI suggestion", hex, usage_hint: s.usage_hint || "", source: "ai_suggested" });
        seen.add(hex);
      }
    });
    setRole({ variants: next });
  };
  const requestSuggestions = async () => {
    setSuggestState({ loading: true, error: "", suggestions: [] });
    try {
      const res = await BrandAPI.paletteSuggestions(draft.id, {
        role_key: roleKey,
        base_hex: role.hex,
        count: 8,
        intent: role.usage_hint || "",
        draft_brand_context: draft,
      });
      setSuggestState({ loading: false, error: "", suggestions: (res && res.suggestions) || [] });
      onOnlineChange(BrandAPI.online);
    } catch (e) {
      onOnlineChange(BrandAPI.online);
      setSuggestState({ loading: false, error: apiErrorMessage(e, "AI Palette Suggestions unavailable"), suggestions: [] });
    }
  };
  return (
    <GlassCard style={{ padding: 17, display: "flex", flexDirection: "column", gap: 13, border: "1px solid rgba(34,211,238,.18)", background: "rgba(255,255,255,.72)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <label style={{ width: 42, height: 42, borderRadius: 12, flexShrink: 0, border: "1px solid rgba(0,0,0,.08)", background: baseBad ? "#F1F5F9" : role.hex, cursor: "pointer", boxShadow: "0 8px 18px rgba(15,23,42,.12)" }}>
            <input type="color" value={baseBad ? "#000000" : role.hex} onChange={(e) => setRole({ hex: e.target.value.toUpperCase() })} style={{ opacity: 0, width: "100%", height: "100%", cursor: "pointer" }} />
          </label>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 15, color: "#002B57" }}>{copy.title}</span>
            <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>{role.label || copy.fallbackLabel}</span>
          </div>
        </div>
        <Button variant="secondary" icon="sparkles" disabled={suggestState.loading || !HEX_RE.test(role.hex || "")} onClick={requestSuggestions}>AI Palette Suggestions</Button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 130px", gap: 10 }}>
        <Field label="Nombre visible" value={role.label} onChange={(v) => setRole({ label: v })} placeholder={copy.fallbackLabel} />
        <Field label="Base hex" value={role.hex} onChange={(v) => setRole({ hex: v })} placeholder="#RRGGBB" mono error={baseBad ? "Hex inválido" : ""} />
      </div>
      <TextAreaField label="Uso / helper copy" value={role.usage_hint} onChange={(v) => setRole({ usage_hint: v })} placeholder={copy.usage_hint} />
      <TextAreaField label="Agent guidance · avanzado" value={role.agent_hint} onChange={(v) => setRole({ agent_hint: v })} placeholder={copy.agent_hint} rows={2} />

      <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 800, letterSpacing: ".06em", textTransform: "uppercase", color: "#0891B2" }}>Variantes permitidas</span>
          <button onClick={addVariant} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 10px", borderRadius: 8, cursor: "pointer", border: "1.5px dashed #CBD5E1", background: "transparent", color: "#0891B2", fontFamily: "Inter", fontSize: 11.5, fontWeight: 700 }}><Icon name="plus" size={12} /> Variante manual</button>
        </div>
        {variants.length === 0 ? <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>Sin variantes aún. Añade manualmente o acepta sugerencias de IA.</span> : null}
        {variants.map((v, i) => {
          const bad = !HEX_RE.test(v.hex || "");
          return (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "34px 1fr 112px 1.4fr 30px", gap: 8, alignItems: "center" }}>
              <label style={{ width: 32, height: 32, borderRadius: 9, border: "1px solid rgba(0,0,0,.08)", background: bad ? "#F1F5F9" : v.hex, cursor: "pointer" }}>
                <input type="color" value={bad ? "#000000" : v.hex} onChange={(e) => setVariant(i, { hex: e.target.value.toUpperCase() })} style={{ opacity: 0, width: "100%", height: "100%", cursor: "pointer" }} />
              </label>
              <input value={v.name || ""} onChange={(e) => setVariant(i, { name: e.target.value })} placeholder="Nombre" style={{ minWidth: 0, border: "1px solid #E2E8F0", borderRadius: 8, padding: "7px 9px", fontFamily: "Inter", fontSize: 12, color: "#002B57", outline: "none" }} />
              <input value={v.hex || ""} onChange={(e) => setVariant(i, { hex: e.target.value })} placeholder="#RRGGBB" style={{ border: `1px solid ${bad ? "#F87171" : "#E2E8F0"}`, borderRadius: 8, padding: "7px 9px", fontFamily: "Space Grotesk", fontSize: 12, color: bad ? "#EF4444" : "#002B57", outline: "none" }} />
              <input value={v.usage_hint || ""} onChange={(e) => setVariant(i, { usage_hint: e.target.value })} placeholder="Uso sugerido" style={{ minWidth: 0, border: "1px solid #E2E8F0", borderRadius: 8, padding: "7px 9px", fontFamily: "Inter", fontSize: 12, color: "#002B57", outline: "none" }} />
              <button onClick={() => removeVariant(i)} title="Eliminar variante" style={{ width: 30, height: 30, borderRadius: 8, border: "none", background: "transparent", cursor: "pointer", color: "#94A3B8", display: "flex", alignItems: "center", justifyContent: "center" }}><Icon name="trash-2" size={14} /></button>
            </div>
          );
        })}
      </div>

      {suggestState.loading || suggestState.error || suggestState.suggestions.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 9, padding: 12, borderRadius: 12, background: "rgba(34,211,238,.06)", border: "1px solid rgba(34,211,238,.18)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 800, letterSpacing: ".06em", textTransform: "uppercase", color: "#0891B2" }}>Gemini suggestions</span>
            {suggestState.suggestions.length ? <Button variant="secondary" icon="check" onClick={acceptAll}>Aceptar todo</Button> : null}
          </div>
          {suggestState.loading ? <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontFamily: "Inter", fontSize: 12.5, color: "#0891B2" }}><Spinner size={14} /> Consultando Gemini…</span> : null}
          {suggestState.error ? <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontFamily: "Inter", fontSize: 12, color: "#EF4444", fontWeight: 600 }}><Icon name="triangle-alert" size={14} /> {suggestState.error}</span> : null}
          {suggestState.suggestions.map((s, i) => {
            const hex = (s.hex || "").toUpperCase();
            const bad = !HEX_RE.test(hex);
            const accepted = acceptedHexes.has(hex);
            return (
              <div key={`${hex}-${i}`} style={{ display: "grid", gridTemplateColumns: "32px 1fr auto", gap: 9, alignItems: "center", padding: 9, borderRadius: 10, background: "rgba(255,255,255,.78)", border: "1px solid rgba(226,232,240,.9)" }}>
                <span style={{ width: 30, height: 30, borderRadius: 9, background: bad ? "#F1F5F9" : hex, border: "1px solid rgba(0,0,0,.08)" }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: "flex", gap: 7, alignItems: "baseline", flexWrap: "wrap" }}><span style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: 800, color: "#002B57" }}>{s.name || "Suggestion"}</span><span style={{ fontFamily: "Space Grotesk", fontSize: 12, color: bad ? "#EF4444" : "#68737D" }}>{hex}</span></div>
                  <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#68737D" }}>{s.usage_hint || ""}{s.rationale ? ` · ${s.rationale}` : ""}</div>
                </div>
                <Button variant={accepted ? "secondary" : "shine"} icon={accepted ? "check" : "plus"} disabled={bad || accepted} onClick={() => acceptSuggestion(s)}>{accepted ? "Aceptada" : "Aceptar"}</Button>
              </div>
            );
          })}
        </div>
      ) : online === false ? <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#B45309" }}>Modo offline: las sugerencias de Gemini requieren backend conectado.</span> : null}
    </GlassCard>
  );
}

function BCard({ icon, title, children }) {
  return (
    <GlassCard style={{ padding: 20, display: "flex", flexDirection: "column", gap: 13 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <div style={{ width: 30, height: 30, borderRadius: 9, background: "rgba(34,211,238,0.12)", display: "flex", alignItems: "center", justifyContent: "center", color: "#0891B2" }}><Icon name={icon} size={16} /></div>
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>{title}</span>
      </div>
      {children}
    </GlassCard>
  );
}

// ============================================================================
// Brand Discovery card (Task 9) — Shopify evidence review + AI recommendations.
// Everything accepted here only mutates the LOCAL draft; "Guardar cambios" persists.
// ============================================================================

const DISCOVERY_STATUS_BADGE = {
  succeeded: { tone: "green", icon: "check-circle-2", label: "Completado" },
  partial: { tone: "amber", icon: "triangle-alert", label: "Parcial" },
  failed: { tone: "red", icon: "x-circle", label: "Fallido" },
  running: { tone: "cyan", icon: "loader", label: "En curso" },
  pending: { tone: "slate", icon: "clock", label: "Pendiente" },
};
const ROLE_SHORT = { primary: "P", secondary: "S", tertiary: "T" };

function DiscoveredColorRow({ color, draft, onAddVariant }) {
  const hex = (color.hex || "").toUpperCase();
  const bad = !HEX_RE.test(hex);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9, padding: 8, borderRadius: 10, background: "rgba(255,255,255,.78)", border: "1px solid rgba(226,232,240,.9)" }}>
      <span style={{ width: 30, height: 30, borderRadius: 9, flexShrink: 0, background: bad ? "#F1F5F9" : hex, border: "1px solid rgba(0,0,0,.08)" }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", gap: 7, alignItems: "baseline", flexWrap: "wrap" }}>
          <span style={{ fontFamily: "Inter", fontSize: 12, fontWeight: 800, color: "#002B57" }}>{color.name || hex}</span>
          <span style={{ fontFamily: "Space Grotesk", fontSize: 11, color: "#68737D" }}>{hex}</span>
          <Badge tone="slate" style={{ textTransform: "none" }}>{Math.round((color.confidence || 0) * 100)}%</Badge>
        </div>
        <div title={`${color.source}${color.usage_hint ? ` · ${color.usage_hint}` : ""}`} style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{color.source}{color.usage_hint ? ` · ${color.usage_hint}` : ""}</div>
      </div>
      <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
        {ROLE_KEYS.map((rk) => {
          const role = (draft.color_system || {})[rk] || {};
          const added = (role.variants || []).some((v) => (v.hex || "").toUpperCase() === hex);
          return (
            <button key={rk} disabled={bad || added} onClick={() => onAddVariant(rk, color)}
              title={added ? `Ya es variante de ${ROLE_COPY[rk].title}` : `Añadir como variante · ${ROLE_COPY[rk].title}`}
              style={{ width: 26, height: 26, borderRadius: 7, cursor: bad || added ? "default" : "pointer", border: `1px solid ${added ? "#4ADE80" : "#CBD5E1"}`, background: added ? "rgba(34,197,94,.12)" : "#fff", color: added ? "#16A34A" : "#0891B2", fontFamily: "Inter", fontSize: 10.5, fontWeight: 800, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
              {added ? <Icon name="check" size={12} /> : ROLE_SHORT[rk]}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function DiscoveredFontRow({ font, state, onAdd }) {
  // family/css_stack are backend whitelist-validated (letters/digits/spaces/hyphens,
  // stacks + commas/quotes), so using them as inline font-family preview is safe.
  const preview = font.css_stack || buildFontStack(font.family, guessFontCategory(font.family));
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: 9, borderRadius: 10, background: "rgba(255,255,255,.78)", border: "1px solid rgba(226,232,240,.9)" }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
          <span style={{ fontFamily: preview, fontSize: 15, fontWeight: 700, color: "#002B57" }}>{font.family}</span>
          <Badge tone="slate" style={{ textTransform: "none" }}>{Math.round((font.confidence || 0) * 100)}%</Badge>
        </div>
        <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>{font.source}{font.sample_usage ? ` · ${font.sample_usage}` : ""}</div>
      </div>
      {state === "approved" ? <Badge tone="green" icon="check">Aprobada</Badge>
        : state === "discarded" ? <Badge tone="red" icon="x">Descartada</Badge>
          : state === "candidate" ? <Badge tone="cyan" icon="list-plus">En candidatas</Badge>
            : <Button variant="secondary" icon="list-plus" style={{ padding: "6px 11px", fontSize: 12 }} onClick={() => onAdd(font)}>Añadir a candidatas</Button>}
    </div>
  );
}

function AssetTile({ asset, draft, onPatch }) {
  const isLogo = asset.kind === "logo";
  const inUse = isLogo && asset.url && draft.logo_url === asset.url;
  return (
    <div style={{ width: 140, display: "flex", flexDirection: "column", gap: 6, padding: 8, borderRadius: 10, background: "rgba(255,255,255,.78)", border: "1px solid rgba(226,232,240,.9)" }}>
      <img src={asset.url} alt={asset.kind} onError={(e) => { e.currentTarget.style.display = "none"; }} style={{ width: "100%", height: 70, objectFit: "contain", borderRadius: 7, background: "#F8FAFC", border: "1px solid #EEF2F7" }} />
      <div style={{ display: "flex", gap: 5, flexWrap: "wrap", alignItems: "center" }}>
        <Badge tone={isLogo ? "purple" : "slate"} style={{ textTransform: "none" }}>{asset.kind}</Badge>
      </div>
      <span title={asset.source} style={{ fontFamily: "Inter", fontSize: 10, color: "#94A3B8", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{asset.source}</span>
      {isLogo && asset.url ? (
        <Button variant={inUse ? "secondary" : "outline"} icon={inUse ? "check" : "image"} disabled={inUse} onClick={() => onPatch({ logo_url: asset.url })} style={{ padding: "5px 9px", fontSize: 11 }}>
          {inUse ? "Logo en uso" : "Usar como logo"}
        </Button>
      ) : null}
    </div>
  );
}

function RecommendationRoleCard({ rec, applied, onApply }) {
  const hex = (rec.base_hex || "").toUpperCase();
  const copy = ROLE_COPY[rec.role_key] || {};
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: 10, borderRadius: 10, background: "rgba(255,255,255,.78)", border: "1px solid rgba(226,232,240,.9)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 34, height: 34, borderRadius: 10, flexShrink: 0, background: HEX_RE.test(hex) ? hex : "#F1F5F9", border: "1px solid rgba(0,0,0,.08)" }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", gap: 7, alignItems: "baseline", flexWrap: "wrap" }}>
            <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 13.5, color: "#002B57" }}>{copy.title || rec.role_key}</span>
            <span style={{ fontFamily: "Inter", fontSize: 12, fontWeight: 600, color: "#0891B2" }}>{rec.label}</span>
            <span style={{ fontFamily: "Space Grotesk", fontSize: 11.5, color: "#68737D" }}>{hex}</span>
          </div>
          {rec.usage_hint ? <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#68737D" }}>{rec.usage_hint}</div> : null}
        </div>
        <Button variant={applied ? "secondary" : "shine"} icon={applied ? "check" : "arrow-down-to-line"} onClick={onApply} style={{ padding: "7px 12px", fontSize: 12.5 }}>{applied ? "Aplicado" : "Aplicar a borrador"}</Button>
      </div>
      {rec.rationale ? <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#68737D", fontStyle: "italic" }}>{rec.rationale}</div> : null}
      {(rec.variants || []).length ? (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {rec.variants.map((v, i) => {
            const vh = (v.hex || "").toUpperCase();
            return (
              <span key={`${vh}-${i}`} title={v.usage_hint || ""} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 8px", borderRadius: 9999, border: "1px solid #E2E8F0", background: "#fff", fontFamily: "Inter", fontSize: 10.5, fontWeight: 600, color: "#334155" }}>
                <span style={{ width: 11, height: 11, borderRadius: 4, background: HEX_RE.test(vh) ? vh : "#F1F5F9", border: "1px solid rgba(0,0,0,.08)" }} />
                {v.name}<span style={{ fontFamily: "Space Grotesk", color: "#94A3B8" }}>{vh}</span>
              </span>
            );
          })}
        </div>
      ) : null}
      {(rec.evidence_refs || []).length ? (
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontFamily: "Inter", fontSize: 10, color: "#94A3B8", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em" }}>Evidencia:</span>
          {rec.evidence_refs.map((ref, i) => <Badge key={i} tone="slate" style={{ textTransform: "none" }}>{ref}</Badge>)}
        </div>
      ) : null}
    </div>
  );
}

function BrandDiscoveryCard({ draft, online, onOnlineChange, onPatch, onAddVariant, onApplyRecommendations, onAddFontCandidate, fontStateFor }) {
  const [phase, setPhase] = useStateBC("idle"); // idle | running | done | error
  const [run, setRun] = useStateBC(null);
  const [error, setError] = useStateBC("");
  const [recState, setRecState] = useStateBC({ loading: false, error: "" });
  const [appliedRoles, setAppliedRoles] = useStateBC({});

  const snapshot = (run && run.snapshot) || null;
  const recommendation = (run && run.recommendation) || {};
  const recColors = Array.isArray(recommendation.colors) ? recommendation.colors : [];
  const meta = (snapshot && snapshot.theme_metadata) || {};
  const colors = (snapshot && snapshot.colors) || [];
  const fonts = (snapshot && snapshot.fonts) || [];
  const assets = (snapshot && snapshot.assets) || [];
  const runErrors = (snapshot && snapshot.errors) || [];
  const assetsWithUrl = assets.filter((a) => a.url);
  const assetsWithoutUrl = assets.filter((a) => !a.url);
  const statusBadge = run ? DISCOVERY_STATUS_BADGE[run.status] || DISCOVERY_STATUS_BADGE.pending : null;

  const startRun = async () => {
    setPhase("running"); setError(""); setRun(null); setRecState({ loading: false, error: "" }); setAppliedRoles({});
    try {
      const r = await BrandAPI.startDiscovery(draft.id, {});
      onOnlineChange(BrandAPI.online);
      setRun(r); setPhase("done");
    } catch (e) {
      onOnlineChange(BrandAPI.online);
      setError(apiErrorMessage(e, "No se pudo ejecutar el descubrimiento de marca."));
      setPhase("error");
    }
  };

  const requestRecommendations = async () => {
    if (!run || !run.id) return;
    setRecState({ loading: true, error: "" });
    try {
      const r = await BrandAPI.discoveryRecommendations(draft.id, run.id);
      onOnlineChange(BrandAPI.online);
      setRun(r); setRecState({ loading: false, error: "" }); setAppliedRoles({});
    } catch (e) {
      onOnlineChange(BrandAPI.online);
      setRecState({ loading: false, error: apiErrorMessage(e, "Recomendaciones IA no disponibles.") });
    }
  };

  const applyOne = (rc) => { onApplyRecommendations([rc]); setAppliedRoles((a) => ({ ...a, [rc.role_key]: true })); };
  const applyAll = () => {
    onApplyRecommendations(recColors);
    const next = {};
    recColors.forEach((rc) => { next[rc.role_key] = true; });
    setAppliedRoles(next);
  };

  return (
    <BCard icon="scan-search" title="Brand Discovery">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ fontFamily: "Inter", fontSize: 12.5, color: "#68737D", lineHeight: 1.45, flex: 1, minWidth: 240 }}>
          Importa colores, fuentes y assets desde tu tienda Shopify. Lo descubierto es evidencia con procedencia: nada se aplica a la marca hasta que lo aceptes aquí y pulses “Guardar cambios”.
        </div>
        <Button variant={run ? "secondary" : "shine"} icon={phase === "running" ? null : "scan-search"} disabled={phase === "running"} onClick={startRun}>
          {phase === "running" ? <><span style={{ display: "inline-flex", marginRight: 6 }}><Spinner size={13} color={run ? "#22D3EE" : "#fff"} /></span>Analizando tu tienda…</> : run ? "Re-descubrir desde Shopify" : "Descubrir desde Shopify"}
        </Button>
      </div>

      {online === false && !run && phase !== "error" ? (
        <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#B45309", display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Icon name="wifi-off" size={13} /> El descubrimiento requiere el backend y Shopify conectados. No se puede simular.
        </span>
      ) : null}

      {phase === "running" ? (
        <div style={{ display: "flex", alignItems: "center", gap: 9, padding: 12, borderRadius: 12, background: "rgba(34,211,238,.06)", border: "1px solid rgba(34,211,238,.18)", fontFamily: "Inter", fontSize: 12.5, color: "#0891B2" }}>
          <Spinner size={15} /> Analizando tu tienda… leyendo tema publicado, settings y CSS.
        </div>
      ) : null}

      {phase === "error" ? (
        <div style={{ display: "flex", alignItems: "flex-start", gap: 9, padding: 12, borderRadius: 12, background: "rgba(248,113,113,.06)", border: "1px solid rgba(248,113,113,.4)" }}>
          <Icon name="triangle-alert" size={15} color="#EF4444" />
          <span style={{ fontFamily: "Inter", fontSize: 12.5, color: "#EF4444", fontWeight: 500 }}>{error}</span>
        </div>
      ) : null}

      {run ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
          {/* result header: status + shop/theme metadata + source summary */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {statusBadge ? <Badge tone={statusBadge.tone} icon={statusBadge.icon}>{statusBadge.label}</Badge> : null}
            {meta.shop_name ? <Badge tone="cyan" icon="store" style={{ textTransform: "none" }}>{meta.shop_name}</Badge> : null}
            {meta.theme_name ? <Badge tone="purple" icon="layout-template" style={{ textTransform: "none" }}>{meta.theme_name}</Badge> : null}
            {snapshot && snapshot.shop_domain ? <span style={{ fontFamily: "Space Grotesk", fontSize: 11.5, color: "#94A3B8" }}>{snapshot.shop_domain}</span> : null}
          </div>
          {meta.brand_slogan ? <div style={{ fontFamily: "Inter", fontSize: 12, color: "#68737D", fontStyle: "italic" }}>“{meta.brand_slogan}”</div> : null}
          {snapshot && snapshot.source_summary ? <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>{snapshot.source_summary}</div> : null}
          {!snapshot ? <span style={{ fontFamily: "Inter", fontSize: 12, color: "#EF4444" }}>El run no produjo snapshot de evidencias.</span> : null}

          {runErrors.length ? (
            <ToggleSection title="Errores del run" count={runErrors.length} tone="#EF4444">
              <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 4 }}>
                {runErrors.map((err, i) => <li key={i} style={{ fontFamily: "Inter", fontSize: 11.5, color: "#B91C1C" }}>{err}</li>)}
              </ul>
            </ToggleSection>
          ) : null}

          {snapshot && !colors.length && !fonts.length && !assets.length ? (
            <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>El run no encontró colores, fuentes ni assets en la tienda.</span>
          ) : null}

          {colors.length ? (
            <ToggleSection title="Colores descubiertos" count={colors.length} defaultOpen>
              <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>
                P = Primario · S = Secundario · T = Terciario — añade el color como variante de ese rol (solo en el borrador).
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 8 }}>
                {colors.slice(0, 24).map((c, i) => <DiscoveredColorRow key={`${c.hex}-${i}`} color={c} draft={draft} onAddVariant={onAddVariant} />)}
              </div>
              {colors.length > 24 ? <span style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>+{colors.length - 24} colores más en el snapshot.</span> : null}
            </ToggleSection>
          ) : null}

          {fonts.length ? (
            <ToggleSection title="Fuentes descubiertas" count={fonts.length} defaultOpen>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {fonts.map((f, i) => <DiscoveredFontRow key={`${f.family}-${i}`} font={f} state={fontStateFor(f.family)} onAdd={onAddFontCandidate} />)}
              </div>
            </ToggleSection>
          ) : null}

          {assets.length ? (
            <ToggleSection title="Assets" count={assets.length} defaultOpen>
              {assetsWithUrl.length ? (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {assetsWithUrl.slice(0, 8).map((a, i) => <AssetTile key={`${a.url}-${i}`} asset={a} draft={draft} onPatch={onPatch} />)}
                </div>
              ) : null}
              {assetsWithUrl.length > 8 ? <span style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>+{assetsWithUrl.length - 8} assets más con URL.</span> : null}
              {assetsWithoutUrl.length ? (
                <div style={{ display: "flex", gap: 5, flexWrap: "wrap", alignItems: "center" }}>
                  {assetsWithoutUrl.slice(0, 8).map((a, i) => (
                    <Badge key={i} tone="slate" style={{ textTransform: "none" }}>{a.kind} · {a.theme_asset_key || a.source}</Badge>
                  ))}
                  {assetsWithoutUrl.length > 8 ? <span style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>+{assetsWithoutUrl.length - 8} más</span> : null}
                </div>
              ) : null}
            </ToggleSection>
          ) : null}

          {snapshot ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: 12, borderRadius: 12, background: "rgba(34,211,238,.06)", border: "1px solid rgba(34,211,238,.18)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 800, letterSpacing: ".06em", textTransform: "uppercase", color: "#0891B2" }}>Roles de color recomendados · Gemini</span>
                <div style={{ display: "flex", gap: 8 }}>
                  {recColors.length ? <Button variant="secondary" icon="check-check" onClick={applyAll}>Aplicar los {recColors.length} roles</Button> : null}
                  <Button variant="secondary" icon="sparkles" disabled={recState.loading} onClick={requestRecommendations}>
                    {recColors.length ? "Regenerar (IA)" : "Recomendar roles de color (IA)"}
                  </Button>
                </div>
              </div>
              {recState.loading ? <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontFamily: "Inter", fontSize: 12.5, color: "#0891B2" }}><Spinner size={14} /> Consultando Gemini…</span> : null}
              {recState.error ? <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontFamily: "Inter", fontSize: 12, color: "#EF4444", fontWeight: 600 }}><Icon name="triangle-alert" size={14} /> {recState.error}</span> : null}
              {recommendation.summary ? <div style={{ fontFamily: "Inter", fontSize: 12, color: "#68737D" }}>{recommendation.summary}</div> : null}
              {recColors.map((rc) => (
                <RecommendationRoleCard key={rc.role_key} rec={rc} applied={!!appliedRoles[rc.role_key]} onApply={() => applyOne(rc)} />
              ))}
              {!recState.loading && !recState.error && !recColors.length ? (
                <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>Pide a Gemini un borrador de roles primario/secundario/terciario basado en la evidencia del run. “Aplicar a borrador” reemplaza el rol en el editor; nada se guarda sin “Guardar cambios”.</span>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </BCard>
  );
}

// ============================================================================
// Tipografía card (Task 9) — role assignment + approved/discarded/candidates.
// ============================================================================

const FONT_ROLE_FIELDS = [
  { key: "display", label: "Display", required: true, placeholder: "Space Grotesk" },
  { key: "body", label: "Texto / Body", required: true, placeholder: "Inter" },
  { key: "headline", label: "Headline", required: false, placeholder: "— opcional —" },
  { key: "accent", label: "Accent", required: false, placeholder: "— opcional —" },
];

function FontCandidateRow({ candidate, state, onApprove, onDiscard }) {
  const roles = candidate.recommended_roles || [];
  const terminal = state === "approved" || state === "discarded";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: 9, borderRadius: 10, background: "rgba(255,255,255,.78)", border: "1px solid rgba(226,232,240,.9)" }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", gap: 7, alignItems: "baseline", flexWrap: "wrap" }}>
          <span style={{ fontFamily: candidate.css_stack || "Inter", fontSize: 15, fontWeight: 700, color: "#002B57" }}>{candidate.family}</span>
          <Badge tone="slate" style={{ textTransform: "none" }}>{candidate.category || "unknown"}</Badge>
          {roles.map((r) => <Badge key={r} tone="cyan" style={{ textTransform: "none" }}>{r}</Badge>)}
        </div>
        {candidate.rationale ? <div style={{ fontFamily: "Inter", fontSize: 11, color: "#68737D", marginTop: 3 }}>{candidate.rationale}</div> : null}
      </div>
      {terminal ? (
        state === "approved" ? <Badge tone="green" icon="check">Aprobada</Badge> : <Badge tone="red" icon="x">Descartada</Badge>
      ) : (
        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          <Button variant="secondary" icon="check" style={{ padding: "6px 11px", fontSize: 12 }} onClick={() => onApprove(candidate)}>Aprobar</Button>
          <Button variant="ghost" icon="x" style={{ padding: "6px 9px", fontSize: 12 }} onClick={() => onDiscard(candidate)}>Descartar</Button>
        </div>
      )}
    </div>
  );
}

function FontCandidateGroup({ title, badgeLabel, badgeTone, fonts, fontStateFor, onApprove, onDiscard }) {
  if (!fonts || !fonts.length) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 800, letterSpacing: ".06em", textTransform: "uppercase", color: "#0891B2" }}>{title}</span>
        {badgeLabel ? <Badge tone={badgeTone || "slate"} style={{ textTransform: "none" }}>{badgeLabel}</Badge> : null}
      </div>
      {fonts.map((c, i) => <FontCandidateRow key={`${c.family}-${i}`} candidate={c} state={fontStateFor(c.family)} onApprove={onApprove} onDiscard={onDiscard} />)}
    </div>
  );
}

function TypographyCard({ draft, online, onOnlineChange, onPatchTypography, candidates, fontStateFor, onApprove, onDiscard }) {
  const t = draft.typography;
  const approved = t.approved_fonts || [];
  const discarded = t.discarded_fonts || [];
  const [intent, setIntent] = useStateBC("");
  const [sugState, setSugState] = useStateBC({ loading: false, error: "", res: null });
  const [manual, setManual] = useStateBC({ family: "", category: "sans", error: "" });

  const fontOptions = (current) => {
    const out = [];
    approved.forEach((f) => { if (f.family && !out.includes(f.family)) out.push(f.family); });
    FONTS.forEach((f) => { if (!out.includes(f)) out.push(f); });
    const cur = (current || "").trim();
    if (cur && !out.includes(cur)) out.push(cur);
    return out;
  };

  const requestSuggestions = async () => {
    setSugState({ loading: true, error: "", res: null });
    try {
      const res = await BrandAPI.fontSuggestions(draft.id, { count: 8, intent: intent || "", draft_brand_context: draft });
      onOnlineChange(BrandAPI.online);
      setSugState({ loading: false, error: "", res });
    } catch (e) {
      onOnlineChange(BrandAPI.online);
      setSugState({ loading: false, error: apiErrorMessage(e, "Sugerencias de fuentes no disponibles."), res: null });
    }
  };

  const addManual = () => {
    const fam = manual.family.trim().replace(/\s+/g, " ");
    if (!FONT_FAMILY_RE.test(fam)) {
      setManual({ ...manual, error: "Nombre inválido: solo letras, números, espacios y guiones (debe empezar por letra o número)." });
      return;
    }
    onApprove({
      family: fam,
      css_stack: buildFontStack(fam, manual.category),
      category: manual.category,
      source: "manual",
      status: "approved",
      recommended_roles: [],
      rationale: "Añadida manualmente",
      evidence_refs: [],
    });
    setManual({ family: "", category: manual.category, error: "" });
  };

  const typoValid = FONT_ROLE_FIELDS.every((f) => fontValueOk(t[f.key], f.required));
  const res = sugState.res;

  return (
    <BCard icon="type" title="Tipografía">
      <div style={{ fontFamily: "Inter", fontSize: 12.5, color: "#68737D", lineHeight: 1.45 }}>
        Asigna fuentes por rol y gestiona la lista aprobada que usa el agente. Aprobados, descartes y asignaciones son borrador: no se guardan hasta pulsar “Guardar cambios”.
      </div>

      {/* role assignment */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
        {FONT_ROLE_FIELDS.map(({ key, label, required, placeholder }) => {
          const value = t[key] == null ? "" : t[key];
          const ok = fontValueOk(value, required);
          const setValue = (v) => onPatchTypography({ [key]: required ? v : (v || null) });
          return (
            <div key={key} style={{ display: "flex", flexDirection: "column", gap: 5, minWidth: 0 }}>
              <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, color: "#68737D" }}>{label}{required ? "" : " · opcional"}</span>
              <select value={value} onChange={(e) => setValue(e.target.value)} style={{ border: `1px solid ${ok ? "#E2E8F0" : "#F87171"}`, borderRadius: 9, padding: "8px 10px", fontFamily: "Inter", fontSize: 12.5, color: "#002B57", background: "#fff", outline: "none" }}>
                {!required ? <option value="">— Sin asignar —</option> : null}
                {fontOptions(value).map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
              <input value={value} onChange={(e) => setValue(e.target.value)} placeholder={placeholder} style={{ border: `1px solid ${ok ? "#E2E8F0" : "#F87171"}`, borderRadius: 8, padding: "6px 9px", fontFamily: "Inter", fontSize: 11.5, color: "#002B57", outline: "none" }} />
              {!ok ? <span style={{ fontFamily: "Inter", fontSize: 10.5, color: "#EF4444" }}>{(value || "").trim() ? "Solo letras, números, espacios, guiones, comas y comillas." : "Requerido."}</span> : null}
            </div>
          );
        })}
      </div>

      {/* approved fonts */}
      <ToggleSection title="Fuentes aprobadas" count={approved.length} defaultOpen tone="#16A34A">
        {approved.length === 0 ? <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>Aún no hay fuentes aprobadas. Aprueba candidatas abajo o añade una manual.</span> : null}
        <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
          {approved.map((f, i) => (
            <div key={`${f.family}-${i}`} style={{ display: "flex", alignItems: "center", gap: 9, padding: 9, borderRadius: 10, background: "rgba(255,255,255,.78)", border: "1px solid rgba(226,232,240,.9)" }}>
              <div style={{ flex: 1, minWidth: 0, display: "flex", gap: 7, alignItems: "baseline", flexWrap: "wrap" }}>
                <span style={{ fontFamily: f.css_stack || "Inter", fontSize: 15, fontWeight: 700, color: "#002B57" }}>{f.family}</span>
                <Badge tone="slate" style={{ textTransform: "none" }}>{f.category || "unknown"}</Badge>
                {(f.recommended_roles || []).map((r) => <Badge key={r} tone="cyan" style={{ textTransform: "none" }}>{r}</Badge>)}
                <Badge tone={f.source === "gemini_suggested" ? "purple" : "slate"} style={{ textTransform: "none" }}>{f.source}</Badge>
              </div>
              <Button variant="ghost" icon="trash-2" style={{ padding: "6px 9px", fontSize: 12 }} onClick={() => onDiscard(f)}>Quitar</Button>
            </div>
          ))}
        </div>
      </ToggleSection>

      {/* discarded fonts */}
      {discarded.length ? (
        <ToggleSection title="Fuentes descartadas" count={discarded.length} tone="#94A3B8">
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            {discarded.map((f, i) => (
              <div key={`${f.family}-${i}`} style={{ display: "flex", alignItems: "center", gap: 9, padding: "7px 9px", borderRadius: 10, background: "rgba(248,250,252,.9)", border: "1px solid rgba(226,232,240,.9)" }}>
                <span style={{ flex: 1, fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#94A3B8", textDecoration: "line-through" }}>{f.family}</span>
                <Button variant="secondary" icon="rotate-ccw" style={{ padding: "5px 10px", fontSize: 11.5 }} onClick={() => onApprove(f)}>Restaurar</Button>
              </div>
            ))}
          </div>
        </ToggleSection>
      ) : null}

      {/* candidates added from Brand Discovery */}
      {candidates.length ? (
        <ToggleSection title="Candidatas desde discovery" count={candidates.length} defaultOpen>
          <FontCandidateGroup title="Descubiertas" badgeLabel="Shopify · no-IA" badgeTone="slate" fonts={candidates} fontStateFor={fontStateFor} onApprove={onApprove} onDiscard={onDiscard} />
        </ToggleSection>
      ) : null}

      {/* AI font suggestions */}
      <div style={{ display: "flex", flexDirection: "column", gap: 9, padding: 12, borderRadius: 12, background: "rgba(34,211,238,.06)", border: "1px solid rgba(34,211,238,.18)" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input value={intent} onChange={(e) => setIntent(e.target.value)} placeholder="Intención (ej. premium minimalista, streetwear)…" style={{ flex: 1, minWidth: 180, border: "1px solid #E2E8F0", borderRadius: 8, padding: "7px 10px", fontFamily: "Inter", fontSize: 12, color: "#002B57", outline: "none", background: "#fff" }} />
          <Button variant="secondary" icon="sparkles" disabled={sugState.loading} onClick={requestSuggestions}>Sugerencias de fuentes (IA)</Button>
        </div>
        {sugState.loading ? <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontFamily: "Inter", fontSize: 12.5, color: "#0891B2" }}><Spinner size={14} /> Consultando Gemini…</span> : null}
        {sugState.error ? <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontFamily: "Inter", fontSize: 12, color: "#EF4444", fontWeight: 600 }}><Icon name="triangle-alert" size={14} /> {sugState.error}</span> : null}
        {!sugState.loading && !sugState.error && !res && online === false ? (
          <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#B45309" }}>Modo offline: solo puedes añadir fuentes manuales. Las sugerencias requieren backend conectado.</span>
        ) : null}
        {res ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
            {!res.ai_available ? (
              <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: 10, borderRadius: 10, background: "rgba(245,158,11,.08)", border: "1px solid rgba(251,191,36,.5)" }}>
                <Icon name="triangle-alert" size={14} color="#B45309" />
                <span style={{ fontFamily: "Inter", fontSize: 12, color: "#B45309", fontWeight: 500 }}>{res.message || "IA no disponible: mostrando solo candidatas no-IA."}</span>
              </div>
            ) : null}
            {res.ai_available ? <FontCandidateGroup title="Sugerencias IA" badgeLabel="Gemini" badgeTone="cyan" fonts={res.suggestions} fontStateFor={fontStateFor} onApprove={onApprove} onDiscard={onDiscard} /> : null}
            <FontCandidateGroup title="Descubiertas" badgeLabel="Shopify · no-IA" badgeTone="slate" fonts={res.discovered} fontStateFor={fontStateFor} onApprove={onApprove} onDiscard={onDiscard} />
            <FontCandidateGroup title="Seeds curados" badgeLabel="No-IA / curado" badgeTone="slate" fonts={res.seeds} fontStateFor={fontStateFor} onApprove={onApprove} onDiscard={onDiscard} />
          </div>
        ) : null}
      </div>

      {/* manual addition */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 150px auto", gap: 8, alignItems: "start" }}>
        <Field label="Añadir fuente manual" value={manual.family} onChange={(v) => setManual({ ...manual, family: v, error: "" })} placeholder="ej. Outfit" error={manual.error} />
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, color: "#68737D" }}>Categoría</span>
          <select value={manual.category} onChange={(e) => setManual({ ...manual, category: e.target.value })} style={{ border: "1px solid #E2E8F0", borderRadius: 9, padding: "8px 10px", fontFamily: "Inter", fontSize: 12.5, color: "#002B57", background: "#fff", outline: "none" }}>
            {FONT_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, color: "transparent", userSelect: "none" }}>·</span>
          <Button variant="secondary" icon="plus" onClick={addManual}>Aprobar manual</Button>
        </div>
      </div>

      {!typoValid ? (
        <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#EF4444", display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Icon name="triangle-alert" size={13} /> Display y Texto son obligatorios; los valores solo admiten letras, números, espacios, guiones, comas y comillas.
        </span>
      ) : null}
    </BCard>
  );
}

function BrandContextView() {
  const [brands, setBrands] = useStateBC([]);
  const [selId, setSelId] = useStateBC(null);
  const [draft, setDraft] = useStateBC(null);
  const [loading, setLoading] = useStateBC(true);
  const [loadErr, setLoadErr] = useStateBC("");
  const [saveState, setSaveState] = useStateBC("idle"); // idle | saving | saved | error
  const [saveErr, setSaveErr] = useStateBC("");
  const [online, setOnline] = useStateBC(null);
  const [fontCandidates, setFontCandidates] = useStateBC([]); // discovery → typography candidates (UI-only)
  const original = useRefBC(null);

  // initial load
  useEffectBC(() => {
    let alive = true;
    (async () => {
      try {
        const list = await BrandAPI.list();
        if (!alive) return;
        setBrands(list); setOnline(BrandAPI.online);
        if (list.length) await select(list[0].id);
      } catch (e) {
        if (alive) setLoadErr(apiErrorMessage(e, "No se pudo cargar la lista de marcas"));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  async function select(id) {
    setSelId(id); setSaveState("idle"); setSaveErr(""); setFontCandidates([]);
    try {
      const b = await BrandAPI.get(id);
      const normalized = { ...b, palette: b.palette || [], color_system: ensureColorSystem(b), typography: ensureTypography(b) };
      original.current = JSON.stringify(normalized);
      setDraft(normalized); setOnline(BrandAPI.online);
    } catch (e) {
      setLoadErr(apiErrorMessage(e, "No se pudo cargar la marca"));
    }
  }

  const patch = (p) => { setDraft((d) => ({ ...d, ...p })); setSaveState("idle"); };
  const patchVoice = (p) => patch({ voice: { ...draft.voice, ...p } });
  const patchShopify = (p) => patch({ shopify: { ...draft.shopify, ...p } });
  const patchTypography = (p) => patch({ typography: { ...draft.typography, ...p } });
  const patchColorRole = (roleKey, role) => {
    const colorSystem = { ...draft.color_system, [roleKey]: role };
    patch({ color_system: colorSystem, palette: syncPaletteFromColorSystem(draft, colorSystem) });
  };

  // Discovery → draft accumulation (same contract as the AI palette accept flow:
  // local-only until "Guardar cambios").
  const addDiscoveredVariant = (roleKey, color) => {
    const role = (draft.color_system || {})[roleKey];
    const hex = (color.hex || "").toUpperCase();
    if (!role || !HEX_RE.test(hex)) return;
    if ((role.variants || []).some((v) => (v.hex || "").toUpperCase() === hex)) return;
    patchColorRole(roleKey, { ...role, variants: (role.variants || []).concat([{ name: color.name || hex, hex, usage_hint: color.usage_hint || "", source: "shopify_discovery" }]) });
  };

  const applyRecommendations = (recs) => {
    const colorSystem = { ...draft.color_system };
    let touched = false;
    (recs || []).forEach((rec) => {
      if (!ROLE_KEYS.includes(rec.role_key)) return;
      const hex = (rec.base_hex || "").toUpperCase();
      if (!HEX_RE.test(hex)) return;
      colorSystem[rec.role_key] = {
        key: rec.role_key,
        label: rec.label || ROLE_COPY[rec.role_key].fallbackLabel,
        hex,
        usage_hint: rec.usage_hint || ROLE_COPY[rec.role_key].usage_hint,
        agent_hint: rec.agent_hint || ROLE_COPY[rec.role_key].agent_hint,
        variants: (rec.variants || [])
          .filter((v) => HEX_RE.test((v.hex || "").toUpperCase()))
          .map((v) => ({ name: v.name || "AI variant", hex: (v.hex || "").toUpperCase(), usage_hint: v.usage_hint || "", source: "ai_suggested" })),
      };
      touched = true;
    });
    if (touched) patch({ color_system: colorSystem, palette: syncPaletteFromColorSystem(draft, colorSystem) });
  };

  // Font candidate lifecycle (dedupe by family, case-insensitive).
  const approveFont = (candidate) => {
    const fam = ((candidate && candidate.family) || "").toLowerCase();
    if (!fam) return;
    const t = draft.typography;
    patch({
      typography: {
        ...t,
        approved_fonts: (t.approved_fonts || []).filter((f) => (f.family || "").toLowerCase() !== fam).concat([{ ...candidate, status: "approved" }]),
        discarded_fonts: (t.discarded_fonts || []).filter((f) => (f.family || "").toLowerCase() !== fam),
      },
    });
  };
  const discardFont = (candidate) => {
    const fam = ((candidate && candidate.family) || "").toLowerCase();
    if (!fam) return;
    const t = draft.typography;
    patch({
      typography: {
        ...t,
        approved_fonts: (t.approved_fonts || []).filter((f) => (f.family || "").toLowerCase() !== fam),
        discarded_fonts: (t.discarded_fonts || []).filter((f) => (f.family || "").toLowerCase() !== fam).concat([{ ...candidate, status: "discarded" }]),
      },
    });
  };
  const fontStateFor = (family) => {
    const fam = (family || "").toLowerCase();
    const t = draft && draft.typography;
    if (!t) return null;
    if ((t.approved_fonts || []).some((f) => (f.family || "").toLowerCase() === fam)) return "approved";
    if ((t.discarded_fonts || []).some((f) => (f.family || "").toLowerCase() === fam)) return "discarded";
    if (fontCandidates.some((f) => (f.family || "").toLowerCase() === fam)) return "candidate";
    return null;
  };
  const addFontCandidate = (discoveredFont) => {
    const candidate = discoveredFontToCandidate(discoveredFont);
    if (!candidate) return;
    const fam = candidate.family.toLowerCase();
    setFontCandidates((cs) => cs.some((c) => (c.family || "").toLowerCase() === fam) ? cs : cs.concat([candidate]));
  };

  const seg = useMemoBC(() => (draft ? brandToSeg(draft) : null), [draft]);

  const roleValid = draft && draft.color_system && ROLE_KEYS.every((key) => {
    const r = draft.color_system[key];
    return r && HEX_RE.test(r.hex || "") && (r.variants || []).every((v) => HEX_RE.test(v.hex || ""));
  });
  const paletteValid = draft && draft.palette.length > 0 && draft.palette.every((c) => HEX_RE.test(c.hex));
  const domainValid = draft && (draft.shopify.store_domain || "").trim().length > 0;
  const typographyValid = draft && draft.typography
    && fontValueOk(draft.typography.display, true)
    && fontValueOk(draft.typography.body, true)
    && fontValueOk(draft.typography.headline, false)
    && fontValueOk(draft.typography.accent, false);
  const valid = paletteValid && roleValid && domainValid && typographyValid;
  const dirty = draft && original.current !== JSON.stringify(draft);

  async function save() {
    if (!valid || !draft) return;
    setSaveState("saving"); setSaveErr("");
    try {
      // ensureTypography also nulls empty optional roles so the PUT payload is canonical.
      const saved = await BrandAPI.put(draft.id, { ...draft, typography: ensureTypography(draft) });
      const normalized = { ...saved, palette: saved.palette || [], color_system: ensureColorSystem(saved), typography: ensureTypography(saved) };
      original.current = JSON.stringify(normalized);
      setDraft(normalized); setOnline(BrandAPI.online); setSaveState("saved");
      setBrands((bs) => bs.map((b) => b.id === normalized.id ? { id: normalized.id, name: normalized.name, palette: normalized.palette } : b));
    } catch (e) {
      setSaveState("error");
      setSaveErr(e.status === 422 ? "El backend rechazó los datos (validación). Revisa los campos." : apiErrorMessage(e, "Error al guardar"));
    }
  }

  if (loading) {
    return <GlassCard style={{ padding: 48, display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}><Spinner size={18} /><span style={{ fontFamily: "Inter", fontSize: 14, color: "#0891B2" }}>Cargando marcas…</span></GlassCard>;
  }
  if (loadErr) {
    return <GlassCard style={{ padding: 32, display: "flex", alignItems: "center", gap: 12, border: "1px solid rgba(248,113,113,.4)" }}><Icon name="triangle-alert" size={20} color="#EF4444" /><span style={{ fontFamily: "Inter", fontSize: 13.5, color: "#EF4444" }}>{loadErr}</span></GlassCard>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      {/* header */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Kicker>Guardián de identidad</Kicker>
          <h1 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 38, letterSpacing: "-0.02em", color: "#002B57", margin: 0, lineHeight: 1.05 }}>Contexto de marca</h1>
          <p style={{ fontFamily: "Inter", fontSize: 14.5, color: "#68737D", margin: 0, maxWidth: 560 }}>El filtro que el agente aplica antes de diseñar. Selecciona una tienda, edita sus tokens y guárdalos — se persisten en <span style={{ fontFamily: "Space Grotesk" }}>brands/{(draft && draft.id) || "{id}"}.md</span>.</p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
          {online === true ? <Badge tone="green" icon="wifi">Bridge conectado</Badge>
            : online === false ? <Badge tone="amber" icon="wifi-off">Modo offline · mock</Badge> : null}
          <div style={{ display: "flex", gap: 9 }}>
            {saveState === "saved" && !dirty ? <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "Inter", fontSize: 12, color: "#16A34A", fontWeight: 600 }}><Icon name="check-circle-2" size={15} /> Guardado</span> : null}
            <Button variant={valid && dirty ? "shine" : "secondary"} icon={saveState === "saving" ? null : "save"} disabled={!valid || !dirty || saveState === "saving"} onClick={save}>
              {saveState === "saving" ? <><span style={{ display: "inline-flex", marginRight: 6 }}><Spinner size={13} color="#fff" /></span>Guardando…</> : "Guardar cambios"}
            </Button>
          </div>
        </div>
      </div>

      {saveState === "error" ? (
        <GlassCard style={{ padding: "13px 16px", display: "flex", alignItems: "center", gap: 11, border: "1px solid rgba(248,113,113,.4)", background: "rgba(248,113,113,.06)" }}>
          <Icon name="triangle-alert" size={17} color="#EF4444" /><span style={{ fontFamily: "Inter", fontSize: 13, color: "#EF4444", fontWeight: 500 }}>{saveErr}</span>
        </GlassCard>
      ) : null}

      {/* brand selector */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontFamily: "Inter", fontSize: 12, color: "#94A3B8", display: "inline-flex", alignItems: "center", gap: 6 }}><Icon name="store" size={14} /> Tienda:</span>
        <div style={{ display: "flex", gap: 3, background: "rgba(255,255,255,0.7)", border: "1px solid rgba(255,255,255,0.6)", borderRadius: 11, padding: 3, boxShadow: "0 6px 18px rgba(15,23,42,.05)", flexWrap: "wrap" }}>
          {brands.map((b) => {
            const on = selId === b.id;
            return (
              <button key={b.id} onClick={() => select(b.id)} style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "7px 13px", borderRadius: 9, cursor: "pointer", border: "1px solid " + (on ? "rgba(34,211,238,.5)" : "transparent"), background: on ? "rgba(34,211,238,.14)" : "transparent", color: on ? "#0891B2" : "#68737D", fontFamily: "Inter", fontSize: 12.5, fontWeight: 600 }}>
                <span style={{ display: "inline-flex", gap: 2 }}>{(b.palette || []).slice(0, 3).map((c, i) => <span key={i} style={{ width: 10, height: 10, borderRadius: 3, background: c.hex, border: "1px solid rgba(0,0,0,.06)" }} />)}</span>
                {b.name}
              </button>
            );
          })}
        </div>
      </div>

      {draft ? (
        <>
          {/* live preview */}
          <GlassCard style={{ padding: 18, display: "flex", flexDirection: "column", gap: 10, background: "rgba(255,255,255,0.55)", backgroundImage: "radial-gradient(rgba(148,163,184,.18) 1px, transparent 1px)", backgroundSize: "18px 18px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "Space Grotesk", fontSize: 12, color: "#94A3B8" }}>
              <Icon name="eye" size={14} /> Preview en vivo · refleja la paleta y tipografía de la marca
            </div>
            <Banner seg={seg} variant="A" font={draft.typography.display} />
          </GlassCard>

          {/* Brand Discovery — top of the editor column (key resets run state per brand) */}
          <BrandDiscoveryCard
            key={`discovery-${draft.id}`}
            draft={draft}
            online={online}
            onOnlineChange={setOnline}
            onPatch={patch}
            onAddVariant={addDiscoveredVariant}
            onApplyRecommendations={applyRecommendations}
            onAddFontCandidate={addFontCandidate}
            fontStateFor={fontStateFor}
          />

          {/* editable cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 16 }}>
            <Field label="Nombre de la marca" value={draft.name} onChange={(v) => patch({ name: v })} placeholder="Avocado Store" error={!draft.name.trim() ? "Requerido" : ""} />
            <Field label="Logo URL" value={draft.logo_url} onChange={(v) => patch({ logo_url: v })} placeholder="https://…/logo.svg" />
          </div>

          <BCard icon="palette" title="Sistema de color por roles">
            <div style={{ fontFamily: "Inter", fontSize: 12.5, color: "#68737D", lineHeight: 1.45 }}>
              Edita los colores base que usa el agente para identidad, soporte y acentos. Las variantes aceptadas amplían la paleta permitida, pero no se guardan hasta pulsar “Guardar cambios”.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 13 }}>
              {ROLE_KEYS.map((key) => (
                <ColorRoleEditor key={key} roleKey={key} role={draft.color_system[key]} draft={draft} online={online} onRoleChange={patchColorRole} onOnlineChange={setOnline} />
              ))}
            </div>
            {!roleValid || !paletteValid ? <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#EF4444", display: "inline-flex", alignItems: "center", gap: 6 }}><Icon name="triangle-alert" size={13} /> Cada color base y variante debe ser un hex válido (#RRGGBB).</span> : null}
          </BCard>

          {/* Tipografía — full font role/candidate system (key resets suggestion state per brand) */}
          <TypographyCard
            key={`typography-${draft.id}`}
            draft={draft}
            online={online}
            onOnlineChange={setOnline}
            onPatchTypography={patchTypography}
            candidates={fontCandidates}
            fontStateFor={fontStateFor}
            onApprove={approveFont}
            onDiscard={discardFont}
          />

          <BCard icon="shopping-bag" title="Shopify">
            <Field label="Store domain" value={draft.shopify.store_domain} onChange={(v) => patchShopify({ store_domain: v })} placeholder="tienda.myshopify.com" mono error={!domainValid ? "Requerido" : ""} />
            <div style={{ display: "flex", gap: 12 }}>
              <Field label="Theme ID" value={draft.shopify.theme_id} onChange={(v) => patchShopify({ theme_id: v })} placeholder="128934771" mono />
              <Field label="Placement por defecto" value={draft.shopify.default_placement} onChange={(v) => patchShopify({ default_placement: v })} placeholder="hero" mono />
            </div>
          </BCard>

          <BCard icon="message-circle" title="Tono y voz">
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "#0891B2" }}>Tono</span>
                <ChipList items={draft.voice.tone} onChange={(v) => patchVoice({ tone: v })} placeholder="ej. Premium, Directo…" tone="cyan" emptyHint="Sin atributos de tono aún." />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "#F72585" }}>Palabras prohibidas</span>
                  <ChipList items={draft.voice.prohibited_words} onChange={(v) => patchVoice({ prohibited_words: v })} placeholder="ej. barato…" tone="pink" emptyHint="Ninguna." />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "#16A34A" }}>Frases obligatorias</span>
                  <ChipList items={draft.voice.required_phrases} onChange={(v) => patchVoice({ required_phrases: v })} placeholder="ej. envío gratis +$50…" tone="green" emptyHint="Ninguna." />
                </div>
              </div>
            </div>
          </BCard>

          <BCard icon="image" title="Directivas de estilo de imagen">
            <ChipList items={draft.image_style_directives} onChange={(v) => patch({ image_style_directives: v })} placeholder="ej. luz natural, sombras suaves…" tone="cyan" emptyHint="Sin directivas aún." />
          </BCard>

          <GlassCard style={{ padding: 18, display: "flex", alignItems: "center", gap: 12, background: "linear-gradient(120deg, rgba(34,211,238,0.08), rgba(139,92,246,0.05))", border: "1px solid rgba(34,211,238,0.22)" }}>
            <div style={{ width: 36, height: 36, borderRadius: 11, background: "linear-gradient(135deg,#22D3EE,#0891B2)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", flexShrink: 0 }}><Icon name="wand-sparkles" size={18} /></div>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 14, color: "#002B57" }}>El agente aplica este contexto en cada generación</div>
              <div style={{ fontFamily: "Inter", fontSize: 12.5, color: "#68737D" }}>Paleta, tipografía, voz y reglas se inyectan al nodo <span style={{ fontFamily: "Space Grotesk" }}>load_brand_context</span> antes de diseñar.</div>
            </div>
            <Badge tone="purple" icon="lock">Bloqueado por marca</Badge>
          </GlassCard>
        </>
      ) : null}
    </div>
  );
}

Object.assign(window, { BrandContextView });
