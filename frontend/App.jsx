/* global React, useTweaks, TweaksPanel, TweakSection, TweakSelect, TweakRadio,
   Sidebar, Topbar, CampaignsView, ModulePlaceholder, BrandContextView, BriefStage, PlanStage, GenerateStage,
   CanvasStage, PerformanceStage, Icon, Badge, PlacementApi, CampaignApi, isApiCampaign */
// Aijolot Banner Agent — app orchestrator.
const { useState: useStateA, useRef: useRefA } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "bannerFont": "Space Grotesk",
  "lockLayout": "auto",
  "bannerAccent": "auto"
}/*EDITMODE-END*/;

const STEPS = [
  { id: "placement", label: "Ubicación", icon: "store" },
  { id: "brief", label: "Brief", icon: "message-square" },
  { id: "plan", label: "Plan", icon: "clipboard-list" },
  { id: "generate", label: "Generación", icon: "wand-sparkles" },
  { id: "canvas", label: "Lienzo", icon: "layout-template" },
  { id: "performance", label: "Performance", icon: "bar-chart-3" },
];
const STAGE_CRUMB = { campaigns: "", placement: "Ubicación", brief: "Brief comercial", plan: "Plan de campaña", generate: "Generación", canvas: "Lienzo colaborativo", performance: "Performance" };

function Stepper({ stage, goTo }) {
  const cur = STEPS.findIndex((s) => s.id === stage);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "10px 14px", borderRadius: 14, background: "rgba(255,255,255,0.7)", border: "1px solid rgba(255,255,255,0.6)", boxShadow: "0 10px 28px rgba(15,23,42,0.06)", marginBottom: 20, flexWrap: "wrap" }}>
      {STEPS.map((s, i) => {
        const done = i < cur, active = i === cur;
        const clickable = s.id !== "generate" && s.id !== "plan" && i <= cur;
        return (
          <React.Fragment key={s.id}>
            <button onClick={() => clickable && goTo(s.id)} style={{
              display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 12px", borderRadius: 10, border: "none",
              background: active ? "rgba(34,211,238,0.14)" : "transparent", cursor: clickable ? "pointer" : "default",
            }}>
              <span style={{ width: 22, height: 22, borderRadius: 9999, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                background: active ? "#22D3EE" : done ? "rgba(16,185,129,0.16)" : "#EEF2F6",
                color: active ? "#06121f" : done ? "#10B981" : "#94A3B8", fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 11 }}>
                {done ? <Icon name="check" size={13} /> : i + 1}
              </span>
              <span style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: active ? 600 : 500, color: active ? "#0891B2" : done ? "#475569" : "#94A3B8" }}>{s.label}</span>
            </button>
            {i < STEPS.length - 1 && <span style={{ width: 18, height: 1, background: "#E2E8F0" }} />}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [nav, setNav] = useStateA("studio");
  const [stage, setStage] = useStateA("campaigns");
  const [placement, setPlacement] = useStateA(() => ({ id: "hero", name: "Hero principal", size: "1440 × 420", page: "Inicio", layout: { cols: [{ rows: 1, w: 1 }] } }));
  // Art direction is computed by the generation agent (concept → background → hero →
  // typography → self-review); the designer iterates in the Canvas. This is just the
  // canvas fold/preview default (no standalone "Arte" step).
  const [art] = useStateA(() => ({ bg: "usage", fold: 60 }));
  const [campaign, setCampaign] = useStateA(null);
  const [apiNotice, setApiNotice] = useStateA(null);
  // The BUILD run started when the user approves the plan; GenerateStage polls it
  // instead of starting a fresh generation run.
  const [buildRun, setBuildRun] = useStateA(null);
  // Dedupe placement persistence: placement→brief advance AND campaign-ready (when a
  // prototype becomes a backend UUID during intake) both used to save, racing. Save
  // once per (campaign, placement) pair.
  const placementSavedKey = useRefA("");

  async function persistPlacement(camp, plc) {
    if (!isApiCampaign(camp) || !plc) return;
    const key = camp.id + "::" + (plc.id || plc.name || "");
    if (placementSavedKey.current === key) return;
    placementSavedKey.current = key;
    try {
      const r = await PlacementApi.save(camp, plc);
      if (!r.fallback && PlacementApi.get) await PlacementApi.get(camp);
      setApiNotice(r.fallback ? { tone: "amber", text: r.reason } : { tone: "green", text: "Ubicación guardada y recuperable en backend" });
    } catch (e) {
      placementSavedKey.current = "";  // allow a retry on a later trigger
      setApiNotice({ tone: "amber", text: "No se pudo guardar ubicación en backend: " + (e.message || e.status || "error") });
    }
  }

  function onNav(id) { setNav(id); }
  async function handleNewCampaign() {
    setApiNotice(null);
    try {
      const c = await CampaignApi.create({ title: "Nueva campaña", raw_brief: "" });
      setCampaign(c);
      setApiNotice({ tone: "green", text: "Campaña creada: " + c.id });
      setStage("placement");
    } catch (e) {
      // Producción: sin backend NO hay campaña — error visible, sin modo prototipo.
      setCampaign(null);
      setApiNotice({ tone: "red", text: "No se pudo crear la campaña: " + (e.message || e.status || "error") + ". Verifica que el backend (:8000) y Supabase estén arriba." });
    }
  }
  async function handlePlacementNext(p) {
    setPlacement(p);
    await persistPlacement(campaign, p);
    setStage("brief");
  }
  function hydrateCampaignSelection(c, nextStage) {
    if (!c || !isApiCampaign(c)) {
      // Producción: no se navega con campañas sin UUID backend.
      setApiNotice({ tone: "red", text: "La campaña no tiene ID de backend; no se puede continuar." });
      return;
    }
    setCampaign({ ...c, structured_brief: c.structured_brief || {} });
    setApiNotice({ tone: "green", text: "Campaña activa: " + c.id });
    setStage(nextStage);
  }
  async function onCampaignReady(c, opts) {
    if (!isApiCampaign(c)) {
      setApiNotice({ tone: "red", text: "El intake no devolvió una campaña de backend; revisa la conexión e inténtalo de nuevo." });
      return;
    }
    setCampaign(c);
    if (opts && opts.localOnly) return;
    if (!placement) return;
    await persistPlacement(c, placement);
  }

  let body;
  if (nav === "brand") {
    body = <BrandContextView />;
  } else if (nav !== "studio") {
    const labels = { dashboard: "Dashboard", orders: "Pedidos", products: "Productos", analytics: "Analítica" };
    body = <ModulePlaceholder label={labels[nav]} />;
  } else if (stage === "campaigns") {
    body = <>
      {apiNotice ? <div style={{ marginBottom: 12 }}><Badge tone={apiNotice.tone || "slate"} icon={apiNotice.tone === "green" ? "wifi" : "wifi-off"}>{apiNotice.text}</Badge></div> : null}
      <CampaignsView onNew={handleNewCampaign} onResume={(c) => hydrateCampaignSelection(c, "canvas")} onPerf={(c) => hydrateCampaignSelection(c, "performance")} />
    </>;
  } else {
    let view;
    if (stage === "placement") view = <PlacementStage onNotice={setApiNotice} onNext={handlePlacementNext} />;
    else if (stage === "brief") view = <BriefStage campaign={campaign} onGenerate={(c) => { setCampaign(c); setBuildRun(null); setStage("plan"); }} onCampaignReady={onCampaignReady} onNotice={setApiNotice} placement={placement} />;
    else if (stage === "plan") view = <PlanStage campaign={campaign} placement={placement} onNotice={setApiNotice} onApprove={(run) => { setBuildRun(run); setStage("generate"); }} onBack={() => setStage("brief")} />;
    else if (stage === "generate") view = <GenerateStage campaign={campaign} placement={placement} art={art} initialRun={buildRun} onNotice={setApiNotice} onDone={() => setStage("canvas")} />;
    else if (stage === "canvas") view = <CanvasStage campaign={campaign} tweaks={t} placement={placement} art={art} onNotice={setApiNotice} onPublish={() => setStage("performance")} />;
    else view = <PerformanceStage campaign={campaign} tweaks={t} onNotice={setApiNotice} onBack={() => setStage("canvas")} />;
    body = <><Stepper stage={stage} goTo={setStage} />{apiNotice ? <div style={{ marginBottom: 12 }}><Badge tone={apiNotice.tone || "slate"} icon={apiNotice.tone === "green" ? "wifi" : "wifi-off"}>{apiNotice.text}</Badge></div> : null}{view}</>;
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar active={nav} onNav={onNav} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Topbar crumb={nav === "studio" ? STAGE_CRUMB[stage] : undefined} onHome={() => { setNav("studio"); setStage("campaigns"); }} />
        <main style={{ flex: 1, overflowY: "auto", padding: "28px 34px 60px" }}>
          <div style={{ maxWidth: 1240, margin: "0 auto" }}>{body}</div>
        </main>
      </div>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Creativo del banner" />
        <TweakSelect label="Tipografía display" value={t.bannerFont} options={["Space Grotesk", "Georgia", "Inter"]} onChange={(v) => setTweak("bannerFont", v)} />
        <TweakSelect label="Acento del banner" value={t.bannerAccent} options={["auto", "cyan", "gold", "rose"]} onChange={(v) => setTweak("bannerAccent", v)} />
        <TweakSection label="Lienzo" />
        <TweakSelect label="Layout por defecto" value={t.lockLayout} options={["auto", "A", "B", "C"]} onChange={(v) => setTweak("lockLayout", v)} />
      </TweaksPanel>
    </div>
  );
}

function mountApp() {
  if (window.lucide) ReactDOM.createRoot(document.getElementById("root")).render(<App />);
  else setTimeout(mountApp, 50);
}
mountApp();

Object.assign(window, { App });
