/* global React, Icon, GlassCard, Button, Badge, Kicker, Chatbox */
// Aijolot Banner Agent — Stage 2: commercial brief.
// The Chatbox (GH-27) captures the idea and emits a structured Campaign; this
// stage holds that Campaign in state and shows a live summary of the brief.
// (GH-28 turns the summary into an editable Campaign-objects panel.)
const { useState: useStateB } = React;

const URGENCY_TONE = { high: "pink", medium: "amber", low: "slate" };
const URGENCY_LABEL = { high: "Alta", medium: "Media", low: "Baja" };

const BRIEF_FIELDS = [
  { key: "goal", label: "Objetivo", icon: "target" },
  { key: "audience", label: "Audiencia", icon: "users-round" },
  { key: "cta", label: "CTA", icon: "mouse-pointer-click" },
  { key: "tone", label: "Tono", icon: "message-circle" },
  { key: "urgency", label: "Urgencia", icon: "gauge" },
  { key: "placement", label: "Ubicación", icon: "map-pin" },
  { key: "deadline", label: "Fecha límite", icon: "calendar" },
];

function BriefSummary({ brief, missing }) {
  const miss = new Set(missing || []);
  return (
    <GlassCard style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14, height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Icon name="clipboard-list" size={16} color="#0891B2" />
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>Brief estructurado</span>
        <span style={{ marginLeft: "auto", fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>extraído por el agente</span>
      </div>
      <p style={{ fontFamily: "Inter", fontSize: 12.5, color: "#68737D", margin: 0, lineHeight: 1.5 }}>Se completa conforme conversas. Los campos en rosa siguen pendientes.</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
        {BRIEF_FIELDS.map((f) => {
          const raw = brief ? brief[f.key] : "";
          const val = raw == null ? "" : String(raw);
          const pending = miss.has(f.key);
          return (
            <div key={f.key} style={{ display: "flex", alignItems: "center", gap: 11, padding: "10px 12px", borderRadius: 11, background: "rgba(248,250,252,0.8)", border: `1px solid ${pending ? "rgba(247,37,133,.3)" : "#EEF2F6"}` }}>
              <div style={{ width: 30, height: 30, borderRadius: 8, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: pending ? "rgba(247,37,133,.1)" : "rgba(34,211,238,.12)", color: pending ? "#F72585" : "#0891B2" }}>
                <Icon name={f.icon} size={15} />
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, color: "#94A3B8", textTransform: "uppercase", letterSpacing: ".04em" }}>{f.label}</div>
                {f.key === "urgency" && val ? (
                  <span style={{ marginTop: 3, display: "inline-flex" }}><Badge tone={URGENCY_TONE[val] || "slate"}>{URGENCY_LABEL[val] || val}</Badge></span>
                ) : (
                  <div style={{ fontFamily: "Inter", fontSize: 13, fontWeight: 500, color: val ? "#002B57" : "#CBD5E1", marginTop: 2, lineHeight: 1.35 }}>{val || (f.key === "deadline" ? "Sin fecha (opcional)" : "Pendiente…")}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}

function BriefStage({ onGenerate, placement }) {
  const [campaign, setCampaign] = useStateB(null);
  const [complete, setComplete] = useStateB(false);
  const [missing, setMissing] = useStateB(["goal", "audience", "cta", "urgency", "placement"]);

  function onCampaign(c, isComplete, miss) {
    setCampaign(c); setComplete(!!isComplete); setMissing(miss || []);
  }

  const brief = campaign ? campaign.structured_brief : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <Kicker>Paso 2 de 6 · Brief comercial</Kicker>
        {placement && <Badge tone="slate" icon="map-pin">Ubicación: {placement.page} · {placement.name}</Badge>}
        {placement && placement.scope && <Badge tone="purple" icon="crosshair">Alcance: {placement.scope.label}</Badge>}
        {complete && <Badge tone="green" icon="check-circle-2">Brief completo</Badge>}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.35fr) minmax(0,1fr)", gap: 16, alignItems: "stretch" }}>
        <Chatbox onCampaign={onCampaign} />
        <BriefSummary brief={brief} missing={missing} />
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 12 }}>
        {!complete && <span style={{ fontFamily: "Inter", fontSize: 12, color: "#94A3B8" }}>Completa el brief en el chat para continuar.</span>}
        <Button variant={complete ? "shine" : "secondary"} icon="arrow-right" disabled={!complete} onClick={() => complete && onGenerate(campaign)}>
          Continuar a Arte
        </Button>
      </div>
    </div>
  );
}

Object.assign(window, { BriefStage, BriefSummary });
