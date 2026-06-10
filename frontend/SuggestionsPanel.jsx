/* global React, Icon, GlassCard, Button, Badge, Spinner, SuggestionsApi, errorText */
// Aijolot Banner Agent — Fase 0: "El agente sugiere" dashboard panel.
// Renders pending agent_suggestions (calendar events, performance refreshes,
// catalog signals) with accept/dismiss actions. Accepting a calendar/catalog
// suggestion creates a draft campaign with the prefilled brief and hands it to
// the normal flow; a performance suggestion kicks a refinement run.
const { useState: useStateSP, useEffect: useEffectSP } = React;

const KIND_META = {
  calendar_event: { icon: "calendar", label: t("Fecha comercial"), tone: "cyan" },
  performance_refresh: { icon: "trending-down", label: "Performance", tone: "amber" },
  catalog_signal: { icon: "package", label: t("Catálogo"), tone: "green" },
};

function SuggestionCard({ s, onAccept, onDismiss, busy }) {
  const meta = KIND_META[s.kind] || { icon: "sparkles", label: s.kind, tone: "slate" };
  const productImg = s.payload && s.payload.product_image_url;
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: "12px 14px", borderRadius: 13,
      background: "rgba(255,255,255,0.75)", border: "1px solid rgba(8,145,178,0.16)" }}>
      {productImg ? (
        <img src={productImg} alt="" style={{ width: 44, height: 44, borderRadius: 9, objectFit: "cover", flexShrink: 0, border: "1px solid #EEF2F6" }} />
      ) : (
        <div style={{ width: 38, height: 38, borderRadius: 10, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
          background: "rgba(34,211,238,0.12)", color: "#0891B2" }}><Icon name={meta.icon} size={17} /></div>
      )}
      <div style={{ minWidth: 0, flex: 1, display: "flex", flexDirection: "column", gap: 3 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13, color: "#002B57" }}>{s.title}</span>
          <Badge tone={meta.tone} icon={meta.icon}>{meta.label}</Badge>
        </div>
        {s.rationale ? <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#64748B", lineHeight: 1.45 }}>{s.rationale}</div> : null}
        {s.expires_at ? (
          <div style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8" }}>{t("Vigente hasta")} {String(s.expires_at).slice(0, 10)}</div>
        ) : null}
      </div>
      <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
        <Button variant="ghost" icon="x" onClick={() => onDismiss(s)} disabled={busy}>{t("Descartar")}</Button>
        <Button variant="primary" icon={busy ? "loader" : (s.kind === "performance_refresh" ? "refresh-cw" : "sparkles")} onClick={() => onAccept(s)} disabled={busy}>
          {s.kind === "performance_refresh" ? t("Aplicar refresh") : t("Crear campaña")}
        </Button>
      </div>
    </div>
  );
}

function SuggestionsPanel({ onCampaignCreated, onNotice }) {
  const [rows, setRows] = useStateSP([]);
  const [status, setStatus] = useStateSP("loading"); // loading | ready | empty | unavailable
  const [busyId, setBusyId] = useStateSP(null);

  async function refresh() {
    const r = await SuggestionsApi.list();
    if (r.fallback) { setStatus("unavailable"); setRows([]); return; }
    const suggestions = (r.data && r.data.suggestions) || [];
    setRows(suggestions);
    setStatus(suggestions.length ? "ready" : "empty");
  }
  useEffectSP(() => { refresh(); }, []);

  async function accept(s) {
    setBusyId(s.id);
    const r = await SuggestionsApi.accept(s.id);
    setBusyId(null);
    if (r.fallback || !r.data) { onNotice && onNotice({ tone: "amber", text: r.reason || "No se pudo aceptar la sugerencia." }); return; }
    await refresh();
    if (r.data.campaign_id && s.kind !== "performance_refresh") {
      onNotice && onNotice({ tone: "green", text: "Campaña creada desde la sugerencia del agente." });
      onCampaignCreated && onCampaignCreated(r.data.campaign_id);
    } else {
      onNotice && onNotice({ tone: "green", text: "Refresh en marcha — el agente está regenerando." });
    }
  }
  async function dismiss(s) {
    setBusyId(s.id);
    const r = await SuggestionsApi.dismiss(s.id);
    setBusyId(null);
    if (r.fallback) { onNotice && onNotice({ tone: "amber", text: r.reason || "No se pudo descartar." }); return; }
    await refresh();
  }

  if (status === "unavailable" || status === "empty") return null; // nothing proactive → no empty chrome
  return (
    <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Icon name="sparkles" size={15} color="#0891B2" />
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 14, color: "#002B57" }}>{t("El agente sugiere")}</span>
        {status === "loading" ? <Spinner size={13} /> : <Badge tone="cyan">{rows.length}</Badge>}
      </div>
      {rows.map((s) => (
        <SuggestionCard key={s.id} s={s} busy={busyId === s.id} onAccept={accept} onDismiss={dismiss} />
      ))}
    </GlassCard>
  );
}

window.SuggestionsPanel = SuggestionsPanel;
