/* global React, Icon, GlassCard, Button, Badge, CampaignApi, StoreApi, isApiCampaign */
// Aijolot Banner Agent — editable Campaign objects (GH-28).
// Renders the structured brief from GH-27 as inline-editable fields, validates
// client-side, persists edits via PATCH /api/v1/campaigns/{id}, and advances to Art.
// Controlled component: the Campaign lives in BriefStage; this edits via onChange
// so live chat updates and manual edits never clobber each other.
const { useState: useStateCC } = React;

const REQUIRED = ["goal", "audience", "cta", "urgency", "placement"];
const URGENCIES = [["low", "Baja"], ["medium", "Media"], ["high", "Alta"]];

// Personalization dimensions (1 campaign, N variants served by customer tag).
const DIMENSIONS = [["", "Ninguna"], ["gender", "Género"], ["value_tier", "Tier de valor"]];
const VARIANT_PRESETS = {
  gender: [
    { key: "male", label: "Hombre", audience: "hombres", customer_tag: "gender:male" },
    { key: "female", label: "Mujer", audience: "mujeres", customer_tag: "gender:female" },
  ],
  value_tier: [
    { key: "vip", label: "Cliente VIP", audience: "clientes VIP", customer_tag: "vip:true" },
    { key: "regular", label: "Cliente", audience: "clientes regulares", customer_tag: "vip:false" },
  ],
};

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function validate(brief) {
  const errs = {};
  if (!(brief.cta || "").trim()) errs.cta = "El CTA no puede estar vacío.";
  if (brief.deadline && /^\d{4}-\d{2}-\d{2}$/.test(brief.deadline) && brief.deadline < todayISO()) {
    errs.deadline = "La fecha debe ser futura.";
  }
  return errs;
}

function Row({ icon, label, error, children }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 11, padding: "10px 12px", borderRadius: 11, background: "rgba(248,250,252,0.8)", border: `1px solid ${error ? "rgba(248,113,113,.5)" : "#EEF2F6"}` }}>
      <div style={{ width: 30, height: 30, borderRadius: 8, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: error ? "rgba(248,113,113,.1)" : "rgba(34,211,238,.12)", color: error ? "#EF4444" : "#0891B2", marginTop: 2 }}>
        <Icon name={icon} size={15} />
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, color: "#94A3B8", textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 4 }}>{label}</div>
        {children}
        {error ? <div style={{ fontFamily: "Inter", fontSize: 10.5, color: "#EF4444", marginTop: 4 }}>{error}</div> : null}
      </div>
    </div>
  );
}

const inputStyle = { width: "100%", border: "1px solid #E2E8F0", borderRadius: 8, padding: "7px 10px", fontFamily: "Inter", fontSize: 13, color: "#002B57", outline: "none", background: "#fff" };

// Per-variant featured product picker. Resolves products LIVE from Shopify by
// search term (StoreApi.searchProducts → on-demand integration that also persists
// them), so any product is selectable even beyond the bulk-sync window.
function VariantProductPicker({ variant, onPick, onNotice }) {
  const [q, setQ] = useStateCC("");
  const [busy, setBusy] = useStateCC(false);
  const [results, setResults] = useStateCC([]);
  const [open, setOpen] = useStateCC(false);
  async function search() {
    const term = q.trim();
    if (!term) return;
    setBusy(true);
    const res = await StoreApi.searchProductsSafe(term);
    setBusy(false);
    if (!res.ok) { onNotice && onNotice({ tone: "amber", text: "Búsqueda de productos no disponible: " + res.reason }); return; }
    setResults((res.data && res.data.items) || []);
    setOpen(true);
  }
  function pick(p) {
    onPick({ product_gid: p.shopify_gid || null, product_title: p.title || "", product_image_url: p.image_url || null });
    setOpen(false); setResults([]); setQ("");
  }
  const chosen = variant.product_title;
  return (
    <div style={{ position: "relative", display: "flex", flexDirection: "column", gap: 5 }}>
      {chosen ? (
        <div style={{ display: "flex", alignItems: "center", gap: 8, background: "rgba(16,185,129,.08)", border: "1px solid rgba(16,185,129,.3)", borderRadius: 8, padding: "5px 8px" }}>
          {variant.product_image_url ? <img src={variant.product_image_url} alt="" style={{ width: 26, height: 26, borderRadius: 5, objectFit: "cover", flexShrink: 0 }} /> : <Icon name="package" size={14} color="#10B981" />}
          <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#047857", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{chosen}</span>
          <button onClick={() => onPick({ product_gid: null, product_title: "", product_image_url: null })} title="Quitar producto" style={{ border: "none", background: "transparent", color: "#94A3B8", cursor: "pointer", padding: 2, display: "flex" }}><Icon name="x" size={13} /></button>
        </div>
      ) : (
        <div style={{ display: "flex", gap: 6 }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); search(); } }} placeholder="Buscar producto Shopify (ej. Mandarin Sky)" style={{ ...inputStyle, fontSize: 11.5, padding: "5px 8px" }} />
          <button onClick={search} disabled={busy || !q.trim()} style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, padding: "5px 10px", borderRadius: 8, border: "1px solid #E2E8F0", background: "#fff", color: "#0891B2", cursor: busy ? "default" : "pointer", whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 4 }}>
            <Icon name={busy ? "loader" : "search"} size={12} />{busy ? "…" : "Buscar"}
          </button>
        </div>
      )}
      {open && !chosen ? (
        <div style={{ background: "#fff", border: "1px solid #E2E8F0", borderRadius: 8, boxShadow: "0 8px 20px rgba(15,23,42,.12)", overflow: "hidden", maxHeight: 180, overflowY: "auto" }}>
          {results.length ? results.map((p) => (
            <button key={p.shopify_gid || p.id} onClick={() => pick(p)} style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", textAlign: "left", border: "none", borderBottom: "1px solid #F1F5F9", background: "#fff", padding: "6px 8px", cursor: "pointer" }}>
              {p.image_url ? <img src={p.image_url} alt="" style={{ width: 28, height: 28, borderRadius: 5, objectFit: "cover", flexShrink: 0 }} /> : <Icon name="package" size={14} color="#94A3B8" />}
              <span style={{ minWidth: 0, flex: 1 }}>
                <span style={{ display: "block", fontFamily: "Inter", fontSize: 11.5, color: "#002B57", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.title}</span>
                <span style={{ display: "block", fontFamily: "Inter", fontSize: 10, color: "#94A3B8" }}>{p.vendor || ""}{p.metadata && p.metadata.price ? ` · ${p.metadata.price} ${p.metadata.currency || ""}` : ""}</span>
              </span>
            </button>
          )) : <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8", padding: "8px 10px" }}>Sin resultados para “{q}”.</div>}
        </div>
      ) : null}
    </div>
  );
}

function CampaignChips({ campaign, onChange, onAdvance, onNotice }) {
  const [saveState, setSaveState] = useStateCC("saved");

  if (!campaign) {
    return (
      <GlassCard style={{ padding: 24, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10, height: "100%", color: "#94A3B8", textAlign: "center" }}>
        <Icon name="clipboard-list" size={30} color="#CBD5E1" />
        <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 14, color: "#475569" }}>Brief estructurado</div>
        <div style={{ fontFamily: "Inter", fontSize: 12.5, maxWidth: 280 }}>Conversa con el agente para generar el brief. Aparecerá aquí, editable, antes de avanzar a Arte.</div>
      </GlassCard>
    );
  }

  const brief = campaign.structured_brief || {};
  const errors = validate(brief);
  const missing = REQUIRED.filter((f) => !(brief[f] || "").trim());
  const isBackendCampaign = typeof isApiCampaign === "function" && isApiCampaign(campaign);
  const prototypeOnly = !isBackendCampaign;
  const canAdvance = !prototypeOnly && missing.length === 0 && Object.keys(errors).length === 0;

  const setField = (k, v) => onChange && onChange({ ...campaign, structured_brief: { ...brief, [k]: v } });
  const setFields = (patch) => onChange && onChange({ ...campaign, structured_brief: { ...brief, ...patch } });

  async function persistFields(fields) {
    if (!isBackendCampaign) {
      setSaveState("failed");
      onNotice && onNotice({ tone: "amber", text: "Modo prototipo: este brief local no tiene UUID backend y no puede persistirse ni avanzar." });
      return;
    }
    try {
      setSaveState("saving");
      const updated = await CampaignApi.patch(campaign.id, fields);
      setSaveState("saved");
      onChange && onChange({ ...updated, structured_brief: updated.structured_brief || {} });
      onNotice && onNotice({ tone: "green", text: "Brief guardado en backend." });
    } catch (e) {
      const msg = e && (e.message || e.status) || "error";
      setSaveState("failed");
      onNotice && onNotice({ tone: "amber", text: "No se pudo guardar brief en backend: " + msg });
    }
  }
  const persist = (k, value) => persistFields({ [k]: value });

  // --- personalization variants (1 campaign, N served by tag) ---
  const pVariants = Array.isArray(brief.personalization_variants) ? brief.personalization_variants : [];
  const pDimension = brief.personalization_dimension || "";
  function chooseDimension(dim) {
    const variants = dim ? (VARIANT_PRESETS[dim] || []).map((v) => ({ ...v })) : [];
    setFields({ personalization_dimension: dim, personalization_variants: variants });
    persistFields({ personalization_dimension: dim, personalization_variants: variants });
  }
  function setVariantAudience(i, value) {
    const next = pVariants.map((v, idx) => (idx === i ? { ...v, audience: value } : v));
    setField("personalization_variants", next);
  }
  function setVariantProduct(i, product) {
    const next = pVariants.map((v, idx) => (idx === i ? { ...v, ...product } : v));
    setField("personalization_variants", next);
    persistFields({ personalization_variants: next });
  }
  function persistVariants() { persistFields({ personalization_variants: pVariants }); }

  return (
    <GlassCard style={{ padding: 20, display: "flex", flexDirection: "column", gap: 13, height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Icon name="clipboard-list" size={16} color="#0891B2" />
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>Brief estructurado</span>
        <span style={{ fontFamily: "Inter", fontSize: 10.5, color: saveState === "failed" ? "#DC2626" : saveState === "saving" ? "#0891B2" : "#10B981" }}>
          {saveState === "saving" ? "guardando…" : saveState === "failed" ? "guardado falló" : "guardado"}
        </span>
        <span style={{ marginLeft: "auto" }}>{canAdvance ? <Badge tone="green" icon="check">Completo</Badge> : <Badge tone="amber" icon="pencil">{missing.length} pendiente{missing.length === 1 ? "" : "s"}</Badge>}</span>
      </div>
      <p style={{ fontFamily: "Inter", fontSize: 12, color: "#68737D", margin: 0, lineHeight: 1.5 }}>Edita cualquier campo antes de avanzar. Se sincroniza con el agente.</p>
      {prototypeOnly ? (
        <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#B45309", background: "rgba(251,191,36,.14)", border: "1px solid rgba(251,191,36,.35)", borderRadius: 10, padding: "8px 10px" }}>
          Modo prototipo solamente: esta campaña no tiene UUID backend. Crea/recupera una campaña backend para guardar y avanzar.
        </div>
      ) : null}

      <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
        <Row icon="target" label="Objetivo">
          <textarea value={brief.goal || ""} onChange={(e) => setField("goal", e.target.value)} onBlur={(e) => persist("goal", e.target.value)} rows={2} style={{ ...inputStyle, resize: "vertical", lineHeight: 1.4 }} placeholder="Qué quieres lograr con la campaña" />
        </Row>
        <Row icon="users-round" label="Audiencia">
          <input value={brief.audience || ""} onChange={(e) => setField("audience", e.target.value)} onBlur={(e) => persist("audience", e.target.value)} style={inputStyle} placeholder="ej. mujeres 25-40" />
        </Row>
        <Row icon="mouse-pointer-click" label="CTA" error={errors.cta}>
          <input value={brief.cta || ""} onChange={(e) => setField("cta", e.target.value)} onBlur={(e) => persist("cta", e.target.value)} style={inputStyle} placeholder="ej. Comprar ahora" />
        </Row>
        <Row icon="message-circle" label="Tono">
          <input value={brief.tone || ""} onChange={(e) => setField("tone", e.target.value)} onBlur={(e) => persist("tone", e.target.value)} style={inputStyle} placeholder="ej. Premium, Directo" />
        </Row>
        <Row icon="gauge" label="Urgencia">
          <div style={{ display: "flex", gap: 6 }}>
            {URGENCIES.map(([id, lbl]) => {
              const on = brief.urgency === id;
              return (
                <button key={id} onClick={() => { setField("urgency", id); persist("urgency", id); }} style={{
                  flex: 1, fontFamily: "Inter", fontSize: 12, fontWeight: 600, padding: "7px 0", borderRadius: 8, cursor: "pointer",
                  border: "1px solid " + (on ? "#22D3EE" : "#E2E8F0"), background: on ? "rgba(34,211,238,.12)" : "#fff", color: on ? "#0891B2" : "#64748B",
                }}>{lbl}</button>
              );
            })}
          </div>
        </Row>
        <Row icon="map-pin" label="Ubicación">
          <input value={brief.placement || ""} onChange={(e) => setField("placement", e.target.value)} onBlur={(e) => persist("placement", e.target.value)} style={inputStyle} placeholder="ej. Home · Hero" />
        </Row>
        <Row icon="calendar" label="Fecha límite (opcional)" error={errors.deadline}>
          <input type="date" value={/^\d{4}-\d{2}-\d{2}$/.test(brief.deadline || "") ? brief.deadline : ""} onChange={(e) => { setField("deadline", e.target.value || null); persist("deadline", e.target.value || null); }} style={inputStyle} />
        </Row>
        <Row icon="users" label="Personalización (1 campaña · N variantes por tag)">
          <div style={{ display: "flex", gap: 6, marginBottom: pVariants.length ? 9 : 0 }}>
            {DIMENSIONS.map(([id, lbl]) => {
              const on = pDimension === id || (id === "" && !pDimension);
              return (
                <button key={id || "none"} onClick={() => chooseDimension(id)} style={{
                  flex: 1, fontFamily: "Inter", fontSize: 11.5, fontWeight: 600, padding: "7px 0", borderRadius: 8, cursor: "pointer",
                  border: "1px solid " + (on ? "#22D3EE" : "#E2E8F0"), background: on ? "rgba(34,211,238,.12)" : "#fff", color: on ? "#0891B2" : "#64748B",
                }}>{lbl}</button>
              );
            })}
          </div>
          {pVariants.length ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              {pVariants.map((v, i) => (
                <div key={v.key || i} style={{ display: "flex", flexDirection: "column", gap: 5, padding: "7px 8px", borderRadius: 9, background: "#fff", border: "1px solid #EEF2F6" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontFamily: "Inter", fontSize: 10.5, fontWeight: 700, color: "#0891B2", background: "rgba(34,211,238,.1)", border: "1px solid rgba(34,211,238,.3)", borderRadius: 9999, padding: "3px 9px", whiteSpace: "nowrap" }}>{v.label || v.key}</span>
                    <input value={v.audience || ""} onChange={(e) => setVariantAudience(i, e.target.value)} onBlur={persistVariants} style={{ ...inputStyle, fontSize: 12 }} placeholder={`Audiencia para ${v.label || v.key}`} />
                    <span style={{ fontFamily: "Space Grotesk", fontSize: 9.5, color: "#94A3B8", whiteSpace: "nowrap" }}>{v.customer_tag}</span>
                  </div>
                  <VariantProductPicker variant={v} onPick={(p) => setVariantProduct(i, p)} onNotice={onNotice} />
                </div>
              ))}
              <div style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8" }}>El agente genera un banner por variante (con su producto destacado) y lo sirve según el tag del cliente.</div>
            </div>
          ) : (
            <div style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8" }}>Sin personalización: una sola audiencia. Elige una dimensión para segmentar (ej. Género → Hombre / Mujer).</div>
          )}
        </Row>
      </div>

      <Button variant={canAdvance ? "shine" : "secondary"} icon="arrow-right" disabled={!canAdvance} onClick={() => canAdvance && onAdvance && onAdvance(campaign)} style={{ justifyContent: "center", marginTop: 2 }}>
        {prototypeOnly ? "Requiere campaña backend" : canAdvance ? "Avanzar a Arte" : `Completa ${missing.length} campo${missing.length === 1 ? "" : "s"}`}
      </Button>
    </GlassCard>
  );
}

Object.assign(window, { CampaignChips });
