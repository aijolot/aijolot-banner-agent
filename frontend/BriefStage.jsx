/* global React, Icon, GlassCard, Button, Badge, Kicker, Chatbox, CampaignChips */
// Aijolot Banner Agent — Stage 2: commercial brief.
// The Chatbox (GH-27) captures the idea and emits a structured Campaign, held in
// this stage's state. CampaignChips (GH-28) renders it as editable fields and
// advances to Art once the brief is complete and valid.
const { useState: useStateB, useEffect: useEffectB } = React;

const REQUIRED = ["goal", "audience", "cta", "urgency", "placement"];

function BriefStage({ campaign: initialCampaign, onGenerate, onCampaignReady, onNotice, placement }) {
  const normalizeCampaign = (c) => c ? { ...c, structured_brief: c.structured_brief || {} } : null;
  const [campaign, setCampaign] = useStateB(() => normalizeCampaign(initialCampaign));

  function onCampaign(c) { const next = normalizeCampaign(c); setCampaign(next); onCampaignReady && onCampaignReady(next); }
  function onLocalChange(c) { const next = normalizeCampaign(c); setCampaign(next); onCampaignReady && onCampaignReady(next, { localOnly: true }); }

  useEffectB(() => {
    if (initialCampaign) setCampaign(normalizeCampaign(initialCampaign));
  }, [initialCampaign]);

  const ready = !!campaign && REQUIRED.every((k) => ((campaign.structured_brief || {})[k] || "").toString().trim());

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <Kicker>Paso 2 de 6 · Brief comercial</Kicker>
        {placement && <Badge tone="slate" icon="map-pin">Ubicación: {placement.page} · {placement.name}</Badge>}
        {placement && placement.scope && <Badge tone="purple" icon="crosshair">Alcance: {placement.scope.label}</Badge>}
        {ready && <Badge tone="green" icon="check-circle-2">Brief completo</Badge>}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.35fr) minmax(0,1fr)", gap: 16, alignItems: "stretch" }}>
        <Chatbox campaign={campaign} onCampaign={onCampaign} onNotice={onNotice} />
        <CampaignChips campaign={campaign} onChange={onLocalChange} onNotice={onNotice} onAdvance={(c) => onGenerate(c)} />
      </div>
    </div>
  );
}

Object.assign(window, { BriefStage });
