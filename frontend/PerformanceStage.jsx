/* global React, Icon, GlassCard, Button, Badge, Kicker, Spinner, Banner, SEGMENTS, METRICS, SEG_PERF, CTR_TREND, MEMORY,
   PerformanceApi, GenerationApi, errorText */
// Aijolot Banner Agent — Stage 4: performance loop & self-optimization (Module 8).
const { useState: useStateP, useEffect: useEffectP } = React;

function Sparkline({ data, w = 320, h = 70, color = "#22D3EE" }) {
  const min = Math.min(...data), max = Math.max(...data);
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / (max - min || 1)) * (h - 12) - 6;
    return [x, y];
  });
  const line = pts.map((p) => p.join(",")).join(" ");
  const area = `0,${h} ` + line + ` ${w},${h}`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} preserveAspectRatio="none">
      <defs>
        <linearGradient id="spk" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill="url(#spk)" />
      <polyline points={line} fill="none" stroke={color} strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="3.6" fill={color} />
    </svg>
  );
}

function fmtInt(v) {
  const n = Number(v || 0);
  return Number.isFinite(n) ? n.toLocaleString("en-US") : "—";
}

function fmtPercent(v, digits = 1) {
  if (v === null || typeof v === "undefined" || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  const pct = Math.abs(n) <= 1 ? n * 100 : n;
  return `${pct.toFixed(digits)}%`;
}

function fmtMs(v) {
  if (v === null || typeof v === "undefined") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n >= 1000 ? `${(n / 1000).toFixed(1)} s` : `${Math.round(n)} ms`;
}

function compactSourceLabel(obj) {
  if (!obj) return "manual/mock/seed/agent · no-live";
  const label = obj.data_source_label || (obj.live_analytics ? "live analytics" : "manual/mock/seed/agent · no-live");
  const lower = String(label).toLowerCase();
  return obj.live_analytics || lower.includes("not live") || lower.includes("no-live") ? label : `${label} · no-live`;
}

function extractTrendValues(trend) {
  if (Array.isArray(trend)) return trend.map(Number).filter(Number.isFinite);
  if (!trend || typeof trend !== "object") return [];
  const candidates = [trend.ctr, trend.ctr_values, trend.values, trend.points, trend.data];
  for (const c of candidates) {
    if (Array.isArray(c)) {
      const vals = c.map((p) => (typeof p === "number" ? p : Number((p && (p.ctr ?? p.value ?? p.y)) || 0))).filter(Number.isFinite);
      if (vals.length > 1) return vals.map((v) => (Math.abs(v) <= 1 ? v * 100 : v));
    }
  }
  return [];
}

function normalizeSegmentBreakdown(rows) {
  if (!Array.isArray(rows)) return [];
  const colors = ["#28C7F0", "#F6B3CE", "#E7C76B", "#8B5CF6", "#10B981"];
  return rows.map((row, i) => {
    const ctrRaw = row && (row.ctr ?? row.click_through_rate ?? row.clickRate);
    const ctrNum = Number(ctrRaw || 0);
    return {
      seg: (row && (row.seg || row.segment || row.segment_key || row.label || row.name)) || `Segmento ${i + 1}`,
      ctr: Number.isFinite(ctrNum) ? (Math.abs(ctrNum) <= 1 ? ctrNum * 100 : ctrNum) : 0,
      conv: Number((row && (row.conv ?? row.conversions ?? row.conversion_count ?? row.value)) || 0),
      color: (row && row.color) || colors[i % colors.length],
    };
  }).filter((s) => s.seg);
}

function proposalLiftLabel(lift) {
  if (!lift || typeof lift !== "object") return null;
  return lift.ctr || lift.conversion_rate || lift.conversions || lift.lift || lift.label || null;
}

function PerformanceStage({ campaign, tweaks, onBack, onNotice }) {
  const [v2, setV2] = useStateP("idle"); // idle | building | ready
  const [backendPerf, setBackendPerf] = useStateP(null);
  const [perfNotice, setPerfNotice] = useStateP("Datos demo etiquetados como manual/mock/seed/agent; no son analítica live de Shopify.");
  const [revisionId, setRevisionId] = useStateP(null);
  const [snapBusy, setSnapBusy] = useStateP(false);
  const [snapState, setSnapState] = useStateP("idle"); // idle | success | error
  const [proposalState, setProposalState] = useStateP("idle"); // idle | sending | sent | error
  const [proposalNotice, setProposalNotice] = useStateP("");

  useEffectP(() => {
    let alive = true;
    (async () => {
      try {
        const r = await PerformanceApi.get(campaign);
        if (!alive) return;
        if (r.fallback) setPerfNotice(r.reason);
        else {
          setBackendPerf(r.data);
          const label = compactSourceLabel(r.data);
          setPerfNotice(`Backend performance conectado · fuente: ${label}`);
        }
      } catch (e) {
        if (alive) setPerfNotice("Performance backend no disponible: " + (typeof errorText !== "undefined" ? errorText(e) : (e.message || e.status || "error")) + ". Se muestran métricas demo no-live.");
      }
      if (typeof GenerationApi !== "undefined") {
        const rev = await GenerationApi.latestRevision(campaign);
        if (alive && rev && !rev.fallback && rev.data) setRevisionId(rev.data.id);
      }
    })();
    return () => { alive = false; };
  }, [campaign && campaign.id]);

  // Record a manual (non-live) performance snapshot against the backend.
  async function registerSnapshot() {
    if (snapBusy) return;
    setSnapBusy(true);
    try {
      const r = await PerformanceApi.snapshot(campaign, { source: "manual", revision_id: revisionId, impressions: 12840, clicks: 591, conversions: 96 });
      if (r.fallback) {
        setSnapState("error");
        onNotice && onNotice({ tone: "amber", text: r.reason });
      }
      else {
        const label = compactSourceLabel(r.data);
        setSnapState("success");
        setBackendPerf((prev) => prev ? { ...prev, latest_snapshot: r.data, snapshots: [r.data].concat(prev.snapshots || []) } : { latest_snapshot: r.data, snapshots: [r.data], insights: [], proposals: [], live_analytics: !!(r.data && r.data.live_analytics), data_source_label: label });
        onNotice && onNotice({ tone: "green", text: `Snapshot registrado en backend · fuente: ${label}` });
        setPerfNotice(`Backend performance conectado · fuente: ${label}`);
      }
    } catch (e) {
      setSnapState("error");
      onNotice && onNotice({ tone: "amber", text: "Backend no registró el snapshot: " + (typeof errorText !== "undefined" ? errorText(e) : (e.message || e.status || "error")) });
    } finally {
      setSnapBusy(false);
    }
  }

  // V2 optimization: keep the local build animation, but send a real proposal.
  async function sendProposal() {
    if (proposalState === "sending") return;
    setProposalState("sending");
    if (!revisionId) {
      const msg = "Sin revisión backend; no se pudo enviar la propuesta V2 al backend.";
      setProposalState("error");
      setProposalNotice(msg);
      onNotice && onNotice({ tone: "amber", text: msg });
      return;
    }
    // Ground the proposal in REAL segment data: target the lowest-CTR segment from the
    // latest snapshot. No fabricated lift % — the projection is qualitative.
    const segs = normalizeSegmentBreakdown(backendPerf && backendPerf.latest_snapshot && backendPerf.latest_snapshot.segment_breakdown);
    if (!segs.length) {
      const msg = "Sin datos de segmento reales en el snapshot; no fundamento una propuesta V2 (no invento métricas).";
      setProposalState("error"); setProposalNotice(msg);
      onNotice && onNotice({ tone: "amber", text: msg });
      return;
    }
    const worst = segs.slice().sort((a, b) => (Number(a.ctr) || 0) - (Number(b.ctr) || 0))[0];
    const segName = worst.seg;
    try {
      const r = await PerformanceApi.proposal(campaign, {
        source_revision_id: revisionId,
        segment_key: segName,
        rationale: `${segName} tiene el CTR más bajo (${Number(worst.ctr || 0).toFixed(1)}%) en el snapshot actual; propongo una V2 con CTA en color de mayor contraste y layout más directo.`,
        projected_lift: { segment: segName },
        status: "sent_to_approval",
      });
      if (r.fallback) {
        setProposalState("error");
        setProposalNotice(r.reason);
        onNotice && onNotice({ tone: "amber", text: r.reason });
        return;
      }
      setBackendPerf((prev) => prev ? { ...prev, proposals: [r.data].concat(prev.proposals || []) } : prev);
      setProposalNotice("Propuesta V2 enviada a aprobación en backend");
      onNotice && onNotice({ tone: "green", text: "Propuesta V2 enviada a aprobación en backend" });
      setProposalState("sent");
    } catch (e) {
      const msg = "Backend no aceptó la propuesta V2: " + (typeof errorText !== "undefined" ? errorText(e) : (e.message || e.status || "error"));
      setProposalState("error");
      setProposalNotice(msg);
      onNotice && onNotice({ tone: "amber", text: msg });
    } finally {
      setProposalState((s) => s === "sending" ? "sent" : s);
    }
  }

  function buildV2() {
    setV2("building");
    setTimeout(() => setV2("ready"), 1700);
  }
  const latestSnapshot = backendPerf && backendPerf.latest_snapshot;
  const sourceLabel = compactSourceLabel(latestSnapshot || backendPerf);
  const isLive = !!((latestSnapshot && latestSnapshot.live_analytics) || (backendPerf && backendPerf.live_analytics));
  const kpis = latestSnapshot ? [
    { id: "impr", icon: "eye", label: "Impresiones", value: fmtInt(latestSnapshot.impressions), delta: sourceLabel, up: true, backend: true },
    { id: "ctr", icon: "mouse-pointer-click", label: "Clicks / CTR", value: `${fmtInt(latestSnapshot.clicks)} · ${fmtPercent(latestSnapshot.ctr)}`, delta: sourceLabel, up: true, backend: true },
    { id: "conv", icon: "shopping-bag", label: "Conversiones / CR", value: `${fmtInt(latestSnapshot.conversions)} · ${fmtPercent(latestSnapshot.conversion_rate)}`, delta: sourceLabel, up: true, backend: true },
    { id: "load", icon: "zap", label: "Carga / peso", value: latestSnapshot.load_p75_ms === null || typeof latestSnapshot.load_p75_ms === "undefined" ? "No informado" : fmtMs(latestSnapshot.load_p75_ms), delta: latestSnapshot.weight_saved_pct === null || typeof latestSnapshot.weight_saved_pct === "undefined" ? sourceLabel : `Peso ahorrado ${fmtPercent(latestSnapshot.weight_saved_pct)}`, up: true, backend: true },
  ] : METRICS.map((m) => ({ ...m, label: `${m.label} (demo)`, delta: `Fallback demo · ${m.delta}`, backend: false }));
  const segmentRows = normalizeSegmentBreakdown(latestSnapshot && latestSnapshot.segment_breakdown);
  const chartSegments = segmentRows.length ? segmentRows : SEG_PERF;
  // Lowest-CTR real segment (drives the V2 proposal copy); null when no real data.
  const lowCtrSeg = segmentRows.length ? segmentRows.slice().sort((a, b) => (Number(a.ctr) || 0) - (Number(b.ctr) || 0))[0].seg : null;
  const maxConv = Math.max(1, ...chartSegments.map((s) => Number(s.conv) || 0));
  const trendValues = extractTrendValues(latestSnapshot && latestSnapshot.trend);
  const chartTrend = trendValues.length > 1 ? trendValues : CTR_TREND;
  const chartFallback = !latestSnapshot || !segmentRows.length || trendValues.length <= 1;
  const insights = backendPerf && Array.isArray(backendPerf.insights) ? backendPerf.insights : [];
  const proposals = backendPerf && Array.isArray(backendPerf.proposals) ? backendPerf.proposals : [];
  const activeProposal = proposals[0];
  const v2Seg = (activeProposal && activeProposal.segment_key) || lowCtrSeg;
  const memoryCards = insights.length || proposals.length ? insights.map((m) => ({ tag: m.tag || m.segment_key || "Insight backend", text: m.insight || "Insight backend", lift: m.lift_label || "backend", source: compactSourceLabel(m) })).concat(proposals.map((p) => ({ tag: `Propuesta · ${p.status || "draft"}`, text: p.rationale, lift: proposalLiftLabel(p.projected_lift) || p.segment_key || "backend", source: compactSourceLabel(p) }))) : MEMORY.map((m) => ({ ...m, tag: `${m.tag} · demo`, source: "Fallback demo no-live" }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Kicker>Paso 6 de 6 · Performance</Kicker>
          <h2 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 26, color: "#002B57", margin: 0 }}>{isLive ? "Resultados live" : "Resultados no-live"}</h2>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Badge tone={isLive ? "green" : "slate"} icon={isLive ? "wifi" : "database-zap"}>{perfNotice}</Badge>
            {backendPerf ? <Badge tone="cyan" icon="database">{(backendPerf.snapshots || []).length} snapshots backend</Badge> : <Badge tone="amber" icon="info">Fallback demo no-live</Badge>}
            {backendPerf && backendPerf.metrics_note ? <Badge tone="slate" icon="info">{backendPerf.metrics_note}</Badge> : null}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Badge tone={isLive ? "green" : "slate"} icon={isLive ? "wifi" : "check-circle-2"}>{isLive ? "Live analytics" : "No-live visible"}</Badge>
          <Button variant="secondary" icon={snapBusy ? null : snapState === "success" ? "check-circle-2" : snapState === "error" ? "triangle-alert" : "database"} onClick={registerSnapshot} disabled={snapBusy} title="Registra un snapshot manual (no-live) en el backend">
            {snapBusy ? <><span style={{ display: "inline-flex", marginRight: 6 }}><Spinner size={13} /></span>Registrando…</> : snapState === "success" ? "Snapshot registrado" : snapState === "error" ? "Reintentar snapshot" : "Registrar snapshot"}
          </Button>
          <Button variant="outline" icon="arrow-left" onClick={onBack}>Volver al lienzo</Button>
        </div>
      </div>

      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16 }}>
        {kpis.map((m) => (
          <GlassCard key={m.id} style={{ padding: 18 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#68737D", fontFamily: "Inter", fontSize: 13 }}>
              <Icon name={m.icon} size={16} color="#22D3EE" /> {m.label}
            </div>
            <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 27, color: "#002B57", marginTop: 12, fontVariantNumeric: "tabular-nums" }}>{m.value}</div>
            <div style={{ fontFamily: "Inter", fontSize: 11.5, marginTop: 6, display: "flex", alignItems: "center", gap: 4, color: m.up ? "#10B981" : "#F72585" }}>
              <Icon name={m.up ? "trending-up" : "trending-down"} size={13} /> {m.delta}
            </div>
          </GlassCard>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.3fr) minmax(0,1fr)", gap: 16 }}>
        {/* CTR trend */}
        <GlassCard style={{ padding: 22, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 16, color: "#002B57" }}>CTR · últimos 14 días</div>
            <Badge tone={chartFallback ? "amber" : (isLive ? "green" : "cyan")} icon={chartFallback ? "info" : "trending-up"}>{chartFallback ? "Demo fallback no-live" : sourceLabel}</Badge>
          </div>
          <Sparkline data={chartTrend} />
          <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "Space Grotesk", fontSize: 10.5, color: "#94A3B8" }}>
            <span>15 may</span><span>22 may</span><span>28 may</span>
          </div>
        </GlassCard>

        {/* Segment perf */}
        <GlassCard style={{ padding: 22, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 16, color: "#002B57" }}>Conversión por segmento</div>
            <Badge tone={segmentRows.length ? (isLive ? "green" : "cyan") : "amber"} icon={segmentRows.length ? "database" : "info"}>{segmentRows.length ? sourceLabel : "Demo fallback no-live"}</Badge>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
            {chartSegments.map((s) => (
              <div key={s.seg} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "Inter", fontSize: 12.5, color: "#475569" }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><span style={{ width: 9, height: 9, borderRadius: 3, background: s.color }} /> {s.seg}</span>
                  <span style={{ fontFamily: "Space Grotesk", fontWeight: 600 }}>{fmtInt(s.conv)} · CTR {Number(s.ctr || 0).toFixed(1)}%</span>
                </div>
                <div style={{ height: 9, borderRadius: 9999, background: "#EEF2F6", overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${(s.conv / maxConv) * 100}%`, background: s.color, borderRadius: 9999 }} />
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {/* Version 2 self-optimization */}
      <GlassCard radius={18} style={{ padding: 24, background: "linear-gradient(120deg, rgba(34,211,238,0.08), rgba(139,92,246,0.06))", border: "1px solid rgba(34,211,238,0.25)" }}>
        <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ width: 44, height: 44, borderRadius: 13, background: "linear-gradient(135deg,#22D3EE,#0891B2)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", flexShrink: 0 }}><Icon name="brain-circuit" size={22} /></div>
          <div style={{ flex: 1, minWidth: 260 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 16, color: "#002B57" }}>Optimización autónoma · Versión 2</span>
              <Badge tone={activeProposal ? "cyan" : "purple"} icon="sparkles">{activeProposal ? `Backend · ${compactSourceLabel(activeProposal)}` : "Propuesta del agente demo no-live"}</Badge>
            </div>
            <p style={{ fontFamily: "Inter", fontSize: 13.5, color: "#475569", margin: "8px 0 0", lineHeight: 1.55, maxWidth: 620 }}>
              {activeProposal ? activeProposal.rationale : (v2Seg ? <>El segmento <b>{v2Seg}</b> tiene el CTR más bajo del snapshot actual. Propongo una Versión 2 con <b>CTA en color de mayor contraste</b> y layout más directo.</> : <>Registra un snapshot con desglose por segmento y el agente propondrá una Versión 2 fundamentada en datos reales (no inventa métricas).</>)}
            </p>
            {v2 === "ready" && (
              <div className="fade-up" style={{ marginTop: 16, maxWidth: 560 }}>
                <Banner seg={SEGMENTS.femenino} variant="C" ctaContrast font={tweaks.bannerFont} />
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10, fontFamily: "Inter", fontSize: 12, color: "#7C3AED", fontWeight: 600 }}>
                  <Icon name="trending-up" size={14} /> Objetivo: subir el CTR del segmento {v2Seg || "con menor desempeño"} (preview ilustrativa)
                </div>
              </div>
            )}
            <div style={{ marginTop: 16 }}>
              {v2 === "idle" && <Button variant="navy" icon="wand-sparkles" onClick={buildV2}>Generar Versión 2</Button>}
              {v2 === "building" && <Button variant="navy" disabled icon="loader"><span style={{ display: "inline-flex", marginRight: 4 }}><Spinner size={13} color="#fff" /></span>Recompilando…</Button>}
              {v2 === "ready" && <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}><Button variant="shine" icon={proposalState === "sending" ? null : proposalState === "sent" ? "check-circle-2" : proposalState === "error" ? "triangle-alert" : "git-pull-request-arrow"} onClick={sendProposal} disabled={proposalState === "sending"}>{proposalState === "sending" ? <><span style={{ display: "inline-flex", marginRight: 6 }}><Spinner size={13} color="#fff" /></span>Enviando…</> : proposalState === "sent" ? "Propuesta enviada" : proposalState === "error" ? "Reintentar aprobación" : "Enviar a aprobación"}</Button><Button variant="ghost" icon="x" onClick={() => { setV2("idle"); setProposalState("idle"); setProposalNotice(""); }}>Descartar</Button>{proposalNotice ? <Badge tone={proposalState === "error" ? "amber" : "green"} icon={proposalState === "error" ? "triangle-alert" : "check-circle-2"}>{proposalNotice}</Badge> : null}</div>}
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Evolutionary memory */}
      <GlassCard style={{ padding: 22, display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <Icon name="database-zap" size={17} color="#0891B2" />
          <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 16, color: "#002B57" }}>{insights.length || proposals.length ? "Insights y propuestas backend" : "Memoria evolutiva demo"}</span>
          <span style={{ fontFamily: "Inter", fontSize: 12, color: "#94A3B8", marginLeft: "auto" }}>{insights.length || proposals.length ? sourceLabel : "Fallback demo no-live"}</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
          {memoryCards.map((m) => (
            <div key={m.tag} style={{ padding: "14px 15px", borderRadius: 13, background: "rgba(248,250,252,0.8)", border: "1px solid #EEF2F6", display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontFamily: "Space Grotesk", fontSize: 11, color: "#94A3B8", letterSpacing: ".02em" }}>{m.tag}</span>
                <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 14, color: "#16A34A" }}>{m.lift}</span>
              </div>
              <p style={{ fontFamily: "Inter", fontSize: 12.5, color: "#475569", margin: 0, lineHeight: 1.5 }}>{m.text}</p>
              <span style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8" }}>{m.source}</span>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}

Object.assign(window, { PerformanceStage });
