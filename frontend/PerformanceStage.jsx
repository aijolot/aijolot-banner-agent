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

function PerformanceStage({ campaign, tweaks, onBack, onNotice }) {
  const [v2, setV2] = useStateP("idle"); // idle | building | ready
  const [backendPerf, setBackendPerf] = useStateP(null);
  const [perfNotice, setPerfNotice] = useStateP("Datos demo etiquetados como manual/mock/seed/agent; no son analítica live de Shopify.");
  const [revisionId, setRevisionId] = useStateP(null);
  const [snapBusy, setSnapBusy] = useStateP(false);
  const [proposalState, setProposalState] = useStateP("idle"); // idle | sending | sent

  useEffectP(() => {
    let alive = true;
    (async () => {
      try {
        const r = await PerformanceApi.get(campaign);
        if (!alive) return;
        if (r.fallback) setPerfNotice(r.reason);
        else {
          setBackendPerf(r.data);
          const label = r.data && (r.data.data_source_label || (r.data.live_analytics ? "live" : "manual/mock/seed/agent"));
          setPerfNotice(`Backend performance conectado · fuente: ${label || "manual/mock/seed/agent"}`);
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
      if (r.fallback) onNotice && onNotice({ tone: "amber", text: r.reason });
      else {
        const label = r.data && (r.data.data_source_label || (r.data.live_analytics ? "live" : "manual"));
        onNotice && onNotice({ tone: "green", text: `Snapshot manual registrado en backend · fuente: ${label || "manual"}` });
        setPerfNotice(`Backend performance conectado · fuente: ${label || "manual"} (snapshot manual)`);
      }
    } catch (e) {
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
      onNotice && onNotice({ tone: "amber", text: "Sin revisión backend; la propuesta V2 queda en estado prototipo local." });
      setProposalState("sent");
      return;
    }
    try {
      const r = await PerformanceApi.proposal(campaign, {
        source_revision_id: revisionId,
        segment_key: "femenino",
        rationale: "Femenino tiene alto volumen pero CTR bajo; botón flotante contraste + layout minimal.",
        projected_lift: { ctr: "+18%", segment: "femenino" },
        status: "sent_to_approval",
      });
      onNotice && onNotice(r.fallback ? { tone: "amber", text: r.reason } : { tone: "green", text: "Propuesta V2 enviada a aprobación en backend" });
    } catch (e) {
      onNotice && onNotice({ tone: "amber", text: "Backend no aceptó la propuesta V2: " + (typeof errorText !== "undefined" ? errorText(e) : (e.message || e.status || "error")) });
    } finally {
      setProposalState("sent");
    }
  }

  function buildV2() {
    setV2("building");
    setTimeout(() => setV2("ready"), 1700);
  }
  const maxConv = Math.max(...SEG_PERF.map((s) => s.conv));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Kicker>Paso 6 de 6 · Performance</Kicker>
          <h2 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 26, color: "#002B57", margin: 0 }}>Resultados no-live</h2>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Badge tone="slate" icon="database-zap">{perfNotice}</Badge>
            {backendPerf ? <Badge tone="cyan" icon="wifi">{(backendPerf.snapshots || []).length} snapshots backend</Badge> : null}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Badge tone="slate" icon="check-circle-2">Demo no-live</Badge>
          <Button variant="secondary" icon={snapBusy ? null : "database"} onClick={registerSnapshot} disabled={snapBusy} title="Registra un snapshot manual (no-live) en el backend">
            {snapBusy ? <><span style={{ display: "inline-flex", marginRight: 6 }}><Spinner size={13} /></span>Registrando…</> : "Registrar snapshot"}
          </Button>
          <Button variant="outline" icon="arrow-left" onClick={onBack}>Volver al lienzo</Button>
        </div>
      </div>

      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16 }}>
        {METRICS.map((m) => (
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
            <Badge tone="cyan" icon="trending-up">+1.6 pts</Badge>
          </div>
          <Sparkline data={CTR_TREND} />
          <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "Space Grotesk", fontSize: 10.5, color: "#94A3B8" }}>
            <span>15 may</span><span>22 may</span><span>28 may</span>
          </div>
        </GlassCard>

        {/* Segment perf */}
        <GlassCard style={{ padding: 22, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 16, color: "#002B57" }}>Conversión por segmento</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
            {SEG_PERF.map((s) => (
              <div key={s.seg} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "Inter", fontSize: 12.5, color: "#475569" }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><span style={{ width: 9, height: 9, borderRadius: 3, background: s.color }} /> {s.seg}</span>
                  <span style={{ fontFamily: "Space Grotesk", fontWeight: 600 }}>{s.conv} · CTR {s.ctr}%</span>
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
              <Badge tone="purple" icon="sparkles">Propuesta del agente</Badge>
            </div>
            <p style={{ fontFamily: "Inter", fontSize: 13.5, color: "#475569", margin: "8px 0 0", lineHeight: 1.55, maxWidth: 620 }}>
              El segmento <b>Femenino</b> tiene muchas impresiones pero CTR por debajo del promedio. Propongo una Versión 2: <b>botón flotante en color contraste</b> y layout <b>minimal</b>, según lo que convirtió mejor en campañas pasadas.
            </p>
            {v2 === "ready" && (
              <div className="fade-up" style={{ marginTop: 16, maxWidth: 560 }}>
                <Banner seg={SEGMENTS.femenino} variant="C" ctaContrast font={tweaks.bannerFont} />
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10, fontFamily: "Inter", fontSize: 12, color: "#7C3AED", fontWeight: 600 }}>
                  <Icon name="trending-up" size={14} /> Proyección: +18% CTR en segmento Femenino
                </div>
              </div>
            )}
            <div style={{ marginTop: 16 }}>
              {v2 === "idle" && <Button variant="navy" icon="wand-sparkles" onClick={buildV2}>Generar Versión 2</Button>}
              {v2 === "building" && <Button variant="navy" disabled icon="loader"><span style={{ display: "inline-flex", marginRight: 4 }}><Spinner size={13} color="#fff" /></span>Recompilando…</Button>}
              {v2 === "ready" && <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}><Button variant="shine" icon={proposalState === "sending" ? null : "git-pull-request-arrow"} onClick={sendProposal} disabled={proposalState === "sending"}>{proposalState === "sending" ? <><span style={{ display: "inline-flex", marginRight: 6 }}><Spinner size={13} color="#fff" /></span>Enviando…</> : proposalState === "sent" ? "Reenviar a aprobación" : "Enviar a aprobación"}</Button><Button variant="ghost" icon="x" onClick={() => { setV2("idle"); setProposalState("idle"); }}>Descartar</Button></div>}
            </div>
          </div>
        </div>
      </GlassCard>

      {/* Evolutionary memory */}
      <GlassCard style={{ padding: 22, display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <Icon name="database-zap" size={17} color="#0891B2" />
          <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 16, color: "#002B57" }}>Memoria evolutiva</span>
          <span style={{ fontFamily: "Inter", fontSize: 12, color: "#94A3B8", marginLeft: "auto" }}>Aprendizajes que alimentan el próximo brief</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
          {MEMORY.map((m) => (
            <div key={m.tag} style={{ padding: "14px 15px", borderRadius: 13, background: "rgba(248,250,252,0.8)", border: "1px solid #EEF2F6", display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontFamily: "Space Grotesk", fontSize: 11, color: "#94A3B8", letterSpacing: ".02em" }}>{m.tag}</span>
                <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 14, color: "#16A34A" }}>{m.lift}</span>
              </div>
              <p style={{ fontFamily: "Inter", fontSize: 12.5, color: "#475569", margin: 0, lineHeight: 1.5 }}>{m.text}</p>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}

Object.assign(window, { PerformanceStage });
