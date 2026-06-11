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
  // Encadenado proactivo (F1): si la campaña LLEGA con el brief completo (lo
  // propuso el agente desde el calendario/catálogo), mostramos la tarjeta de
  // aceptación — aceptar tal cual y planear, o editar chips/chat primero.
  const isComplete = (c) => !!c && REQUIRED.every((k) => ((c.structured_brief || {})[k] || "").toString().trim());
  const [arrivedComplete] = useStateB(() => isComplete(normalizeCampaign(initialCampaign)));

  function onCampaign(c) { const next = normalizeCampaign(c); setCampaign(next); onCampaignReady && onCampaignReady(next); }
  function onLocalChange(c) { const next = normalizeCampaign(c); setCampaign(next); onCampaignReady && onCampaignReady(next, { localOnly: true }); }

  useEffectB(() => {
    if (initialCampaign) setCampaign(normalizeCampaign(initialCampaign));
  }, [initialCampaign]);

  const ready = isComplete(campaign);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <Kicker>{t("Paso 2 de 6 · Brief comercial")}</Kicker>
        {placement && <Badge tone="slate" icon="map-pin">Ubicación: {placement.page} · {placement.name}</Badge>}
        {placement && placement.scope && <Badge tone="purple" icon="crosshair">Alcance: {placement.scope.label}</Badge>}
        {ready && <Badge tone="green" icon="check-circle-2">{t("Brief completo")}</Badge>}
      </div>

      {arrivedComplete ? (
        <GlassCard style={{ padding: 16, display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", border: "1px solid rgba(8,145,178,0.3)", background: "rgba(34,211,238,0.06)" }}>
          <div style={{ width: 38, height: 38, borderRadius: 11, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(34,211,238,0.16)", color: "#0891B2" }}>
            <Icon name="sparkles" size={18} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57" }}>{t("El agente preparó este brief")}</div>
            <div style={{ fontFamily: "Inter", fontSize: 12, color: "#64748B", marginTop: 2 }}>
              {(campaign && campaign.raw_brief) || "Revisa los campos propuestos — puedes aceptarlos tal cual o editarlos (chips a la derecha, o pídele cambios al agente en el chat)."}
            </div>
          </div>
          <Button variant="shine" icon="arrow-right" disabled={!ready} onClick={() => ready && onGenerate(campaign)}>
            Aceptar brief y planear
          </Button>
        </GlassCard>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.35fr) minmax(0,1fr)", gap: 16, alignItems: "stretch" }}>
        <Chatbox campaign={campaign} onCampaign={onCampaign} onNotice={onNotice} />
        <CampaignChips campaign={campaign} onChange={onLocalChange} onNotice={onNotice} onAdvance={(c) => onGenerate(c)} />
      </div>
    </div>
  );
}

Object.assign(window, { BriefStage });
