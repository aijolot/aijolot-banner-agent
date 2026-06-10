/* global React, Icon, GlassCard, Button, Badge, Spinner, CalendarApi, SuggestionsApi, CampaignApi */
// Aijolot Banner Agent — F1 UI: "Calendario comercial" en el dashboard.
// Lista las próximas fechas (seed MX/global + nicho inferido + manuales) con
// countdown, permite ajustar la anticipación, inferir fechas del nicho de la
// tienda, y ARRANCAR la campaña de una fecha desde aquí (accept → brief
// prellenado → flujo normal placement/brief/plan).
const { useState: useStateCP, useEffect: useEffectCP } = React;

// Próxima ocurrencia de un evento (espejo de _next_occurrence del backend):
// recurrentes (month/day) ruedan al siguiente año; one-shot usan starts_on.
function nextOccurrence(event, today) {
  const dur = Math.max(1, parseInt(event.duration_days, 10) || 7);
  if (event.starts_on) {
    const start = new Date(event.starts_on + "T00:00:00Z");
    if (isNaN(start)) return null;
    const end = new Date(start); end.setUTCDate(end.getUTCDate() + dur);
    return end >= today ? { start, end } : null;
  }
  if (!event.month || !event.day) return null;
  for (const year of [today.getUTCFullYear(), today.getUTCFullYear() + 1]) {
    const start = new Date(Date.UTC(year, event.month - 1, event.day));
    const end = new Date(start); end.setUTCDate(end.getUTCDate() + dur);
    if (end >= today) return { start, end };
  }
  return null;
}

const SOURCE_META = {
  seed: { label: t("Retail MX/Global"), tone: "cyan", icon: "calendar" },
  niche_inferred: { label: t("Nicho (agente)"), tone: "green", icon: "sparkles" },
  manual: { label: t("Manual"), tone: "slate", icon: "user" },
};

function fmtDate(d) {
  return d.toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

function CalendarPanel({ onStartBrief, onNotice }) {
  const [events, setEvents] = useStateCP([]);
  const [settings, setSettings] = useStateCP({ lead_time_days: 14, enabled: true });
  const [scanRows, setScanRows] = useStateCP([]); // suggestion rows del último scan (slug → {id,status})
  const [status, setStatus] = useStateCP("loading"); // loading | ready | unavailable
  const [busy, setBusy] = useStateCP(null); // slug en acción | "infer" | "lead"

  async function refresh({ rescan = true } = {}) {
    const [ev, st] = await Promise.all([CalendarApi.events(), CalendarApi.settings()]);
    if (ev.fallback) { setStatus("unavailable"); return; }
    setEvents((ev.data && ev.data.events) || []);
    if (!st.fallback && st.data) setSettings(st.data);
    if (rescan) {
      // Materializa las sugerencias de la ventana actual sin esperar al cron diario.
      const scan = await CalendarApi.scan();
      if (!scan.fallback && scan.data) setScanRows(scan.data.suggestion_rows || []);
    }
    setStatus("ready");
  }
  useEffectCP(() => { refresh(); }, []);

  async function changeLead(delta) {
    const next = Math.max(1, Math.min(90, (parseInt(settings.lead_time_days, 10) || 14) + delta));
    setBusy("lead");
    const r = await CalendarApi.saveSettings({ lead_time_days: next });
    if (!r.fallback && r.data) setSettings(r.data);
    await refresh();
    setBusy(null);
  }

  async function inferNiche() {
    setBusy("infer");
    const r = await CalendarApi.infer();
    setBusy(null);
    if (r.fallback) { onNotice && onNotice({ tone: "red", text: r.reason }); return; }
    const inferred = (r.data && r.data.inferred) || [];
    onNotice && onNotice(inferred.length
      ? { tone: "green", text: `El agente encontró ${inferred.length} fecha(s) de tu nicho.` }
      : { tone: "amber", text: "Sin fechas nuevas de nicho (requiere GOOGLE_API_KEY en el backend o no encontró fechas relevantes)." });
    await refresh();
  }

  async function startCampaign(slug) {
    const row = scanRows.find((r) => r.slug === slug);
    if (!row || row.status !== "pending") return;
    setBusy(slug);
    const r = await SuggestionsApi.accept(row.id);
    setBusy(null);
    if (r.fallback || !r.data || !r.data.campaign_id) {
      onNotice && onNotice({ tone: "red", text: (r && r.reason) || "No se pudo crear la campaña desde el calendario." });
      return;
    }
    onNotice && onNotice({ tone: "green", text: "Campaña creada con el brief de la fecha — revisa y planéala." });
    await refresh();
    // Trae la campaña real (con el brief prellenado por el agente) — un stub
    // vacío dejaría el BriefStage sin la propuesta.
    let full = { id: r.data.campaign_id, status: "draft", structured_brief: {} };
    try { full = await CampaignApi.get(r.data.campaign_id); } catch (e) { /* el brief se recarga en el stage */ }
    onStartBrief && onStartBrief(full);
  }

  if (status === "unavailable") return null;

  const today = new Date();
  const lead = parseInt(settings.lead_time_days, 10) || 14;
  const rows = events
    .map((e) => ({ event: e, occ: nextOccurrence(e, today) }))
    .filter((r) => r.occ)
    .map((r) => ({ ...r, days: Math.ceil((r.occ.start - today) / 86400000) }))
    .sort((a, b) => a.occ.start - b.occ.start)
    .slice(0, 8);

  return (
    <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <Icon name="calendar-days" size={16} color="#0891B2" />
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 14, color: "#002B57" }}>{t("Calendario comercial")}</span>
        {status === "loading" ? <Spinner size={13} /> : null}
        <div style={{ flex: 1 }} />
        <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#64748B", display: "inline-flex", alignItems: "center", gap: 6 }}>
          {t("Anticipación")}
          <button onClick={() => changeLead(-7)} disabled={busy === "lead"} style={{ width: 20, height: 20, borderRadius: 6, border: "1px solid #E2E8F0", background: "#fff", cursor: "pointer", fontWeight: 700 }}>−</button>
          <b style={{ color: "#0891B2", minWidth: 46, textAlign: "center" }}>{lead} {t("días")}</b>
          <button onClick={() => changeLead(7)} disabled={busy === "lead"} style={{ width: 20, height: 20, borderRadius: 6, border: "1px solid #E2E8F0", background: "#fff", cursor: "pointer", fontWeight: 700 }}>+</button>
        </span>
        <Button variant="secondary" icon={busy === "infer" ? "loader" : "sparkles"} onClick={inferNiche} disabled={!!busy}>
          {busy === "infer" ? t("Buscando…") : t("Fechas de mi nicho")}
        </Button>
      </div>

      {status === "ready" && !rows.length ? (
        <div style={{ fontFamily: "Inter", fontSize: 12.5, color: "#64748B" }}>{t("Sin fechas próximas en el calendario.")}</div>
      ) : null}

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {rows.map(({ event, occ, days }) => {
          const meta = SOURCE_META[event.source] || SOURCE_META.manual;
          const inWindow = days <= lead;
          const scanRow = scanRows.find((r) => r.slug === event.slug);
          const accepted = scanRow && scanRow.status === "accepted";
          return (
            <div key={(event.team_id || "g") + ":" + event.slug} style={{
              display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: 12,
              background: inWindow ? "rgba(34,211,238,0.07)" : "rgba(248,250,252,0.8)",
              border: `1px solid ${inWindow ? "rgba(8,145,178,0.25)" : "#EEF2F6"}`,
            }}>
              <div style={{ width: 52, flexShrink: 0, textAlign: "center" }}>
                <div style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 17, color: days <= 7 ? "#DC2626" : inWindow ? "#0891B2" : "#475569", lineHeight: 1 }}>{days <= 0 ? "HOY" : days}</div>
                {days > 0 ? <div style={{ fontFamily: "Inter", fontSize: 9.5, color: "#94A3B8" }}>{days === 1 ? t("día") : t("días")}</div> : null}
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13, color: "#002B57" }}>{event.name}</span>
                  <Badge tone={meta.tone} icon={meta.icon}>{meta.label}</Badge>
                </div>
                <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8", marginTop: 2 }}>
                  {fmtDate(occ.start)}{event.relevance_note ? ` · ${event.relevance_note}` : ""}
                </div>
              </div>
              {accepted ? (
                <Badge tone="green" icon="check">{t("Campaña creada")}</Badge>
              ) : inWindow && scanRow ? (
                <Button variant="primary" icon={busy === event.slug ? "loader" : "wand-sparkles"} onClick={() => startCampaign(event.slug)} disabled={!!busy}>
                  Preparar campaña
                </Button>
              ) : (
                <span style={{ fontFamily: "Inter", fontSize: 10.5, color: "#CBD5E1", whiteSpace: "nowrap" }}>{t("fuera de ventana")}</span>
              )}
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}

window.CalendarPanel = CalendarPanel;
