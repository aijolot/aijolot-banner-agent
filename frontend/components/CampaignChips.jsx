/* global React, Icon, GlassCard, Button, Badge, CampaignApi, isApiCampaign */
// Aijolot Banner Agent — editable Campaign objects (GH-28).
// Renders the structured brief from GH-27 as inline-editable fields, validates
// client-side, persists edits via PATCH /api/v1/campaigns/{id}, and advances to Art.
// Controlled component: the Campaign lives in BriefStage; this edits via onChange
// so live chat updates and manual edits never clobber each other.
const { useState: useStateCC } = React;

const REQUIRED = ["goal", "audience", "cta", "urgency", "placement"];
const URGENCIES = [["low", "Baja"], ["medium", "Media"], ["high", "Alta"]];

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

  async function persist(k, value) {
    if (!isBackendCampaign) {
      setSaveState("failed");
      const text = "Modo prototipo: este brief local no tiene UUID backend y no puede persistirse ni avanzar.";
      onNotice && onNotice({ tone: "amber", text });
      return;
    }
    try {
      setSaveState("saving");
      const updated = await CampaignApi.patch(campaign.id, { [k]: value });
      setSaveState("saved");
      onChange && onChange({ ...updated, structured_brief: updated.structured_brief || {} });
      onNotice && onNotice({ tone: "green", text: "Brief guardado en backend." });
    } catch (e) {
      const msg = e && (e.message || e.status) || "error";
      setSaveState("failed");
      onNotice && onNotice({ tone: "amber", text: "No se pudo guardar brief en backend: " + msg });
    }
  }

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
      </div>

      <Button variant={canAdvance ? "shine" : "secondary"} icon="arrow-right" disabled={!canAdvance} onClick={() => canAdvance && onAdvance && onAdvance(campaign)} style={{ justifyContent: "center", marginTop: 2 }}>
        {prototypeOnly ? "Requiere campaña backend" : canAdvance ? "Avanzar a Arte" : `Completa ${missing.length} campo${missing.length === 1 ? "" : "s"}`}
      </Button>
    </GlassCard>
  );
}

Object.assign(window, { CampaignChips });
