/* global React, Icon, GlassCard, Button, Badge, Kicker, Chatbox, CampaignChips */
// Aijolot Banner Agent — Stage 2: commercial brief.
// The Chatbox (GH-27) captures the idea and emits a structured Campaign, held in
// this stage's state. CampaignChips (GH-28) renders it as editable fields and
// advances to Art once the brief is complete and valid.
const { useState: useStateB } = React;

const REQUIRED = ["goal", "audience", "cta", "urgency", "placement"];

function BriefStage({ onGenerate, onCampaignReady, placement }) {
  const [campaign, setCampaign] = useStateB(null);

  function onCampaign(c) { setCampaign(c); onCampaignReady && onCampaignReady(c); }

  const ready = !!campaign && REQUIRED.every((k) => (campaign.structured_brief[k] || "").toString().trim());

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <Kicker>Paso 2 de 6 · Brief comercial</Kicker>
        {placement && <Badge tone="slate" icon="map-pin">Ubicación: {placement.page} · {placement.name}</Badge>}
        {placement && placement.scope && <Badge tone="purple" icon="crosshair">Alcance: {placement.scope.label}</Badge>}
        {ready && <Badge tone="green" icon="check-circle-2">Brief completo</Badge>}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.35fr) minmax(0,1fr)", gap: 16, alignItems: "stretch" }}>
        <Chatbox onCampaign={onCampaign} />
        <CampaignChips campaign={campaign} onChange={setCampaign} onAdvance={(c) => onGenerate(c)} />
      </div>
    </div>
  );
}

Object.assign(window, { BriefStage });
