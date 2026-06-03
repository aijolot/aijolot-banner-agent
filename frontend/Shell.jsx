/* global React, Icon, GlassCard, Button, Badge, Avatar, Kicker, Spinner, CAMPAIGN, CampaignApi */
// Aijolot Banner Agent — app shell (icon sidebar + topbar) and Campaigns landing.

const NAV = [
  { id: "studio", icon: "wand-sparkles", label: "Estudio de Banners" },
  { id: "brand", icon: "palette", label: "Marca" },
  { id: "dashboard", icon: "layout-dashboard", label: "Dashboard" },
  { id: "orders", icon: "shopping-cart", label: "Pedidos" },
  { id: "products", icon: "package", label: "Productos" },
  { id: "analytics", icon: "bar-chart-3", label: "Analítica" },
];

function Sidebar({ active, onNav }) {
  return (
    <aside style={{
      width: 64, flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "center",
      gap: 6, padding: "16px 0", background: "rgba(255,255,255,0.8)",
      backdropFilter: "blur(18px)", WebkitBackdropFilter: "blur(18px)",
      borderRight: "1px solid rgba(226,232,240,0.8)", zIndex: 20,
    }}>
      <div title="Aijolot" style={{
        width: 40, height: 40, borderRadius: 14, background: "linear-gradient(135deg,#22D3EE,#0891B2)",
        color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 18, marginBottom: 14,
        boxShadow: "0 8px 20px rgba(34,211,238,.35)",
      }}>A</div>
      {NAV.map((item) => {
        const on = active === item.id;
        return (
          <button key={item.id} onClick={() => onNav(item.id)} title={item.label} style={{
            width: 44, height: 44, borderRadius: 18, border: "none", cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            background: on ? "rgba(34,211,238,0.18)" : "transparent", color: on ? "#0891B2" : "#68737D",
            animation: on ? "uikBreathe 2s ease-in-out infinite" : "none", transition: "background .15s, color .15s",
          }}
            onMouseEnter={(e) => { if (!on) e.currentTarget.style.background = "rgba(34,211,238,0.08)"; }}
            onMouseLeave={(e) => { if (!on) e.currentTarget.style.background = "transparent"; }}>
            <Icon name={item.icon} size={20} />
          </button>
        );
      })}
      <div style={{ flex: 1 }} />
      <button title="Ajustes" style={{ width: 44, height: 44, borderRadius: 18, border: "none", cursor: "pointer", background: "transparent", color: "#68737D", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Icon name="settings" size={20} />
      </button>
    </aside>
  );
}

function Topbar({ crumb, onHome }) {
  return (
    <header style={{ height: 64, flexShrink: 0, display: "flex", alignItems: "center", gap: 14, padding: "0 28px", borderBottom: "1px solid rgba(226,232,240,0.7)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#68737D", fontFamily: "Inter", fontSize: 13 }}>
        <button onClick={onHome} style={{ border: "none", background: "transparent", cursor: "pointer", color: crumb ? "#68737D" : "#002B57", fontFamily: "Inter", fontSize: 13, fontWeight: crumb ? 400 : 600, padding: 0 }}>Estudio de Banners</button>
        {crumb && <><Icon name="chevron-right" size={14} color="#CBD5E1" /><span style={{ color: "#002B57", fontWeight: 600 }}>{crumb}</span></>}
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "6px 11px", borderRadius: 9999, background: "rgba(34,211,238,0.1)", border: "1px solid rgba(34,211,238,0.3)" }}>
        <span style={{ width: 7, height: 7, borderRadius: 9999, background: "#22D3EE", animation: "pulseSoft 2s ease-in-out infinite" }} />
        <span style={{ fontFamily: "Inter", fontSize: 11.5, fontWeight: 600, color: "#0891B2" }}>Agente CEOD activo</span>
      </div>
      <button style={{ position: "relative", border: "none", background: "transparent", cursor: "pointer", color: "#68737D" }}>
        <Icon name="bell" size={19} />
        <span style={{ position: "absolute", top: -2, right: -2, width: 8, height: 8, borderRadius: 9999, background: "#F72585", border: "2px solid #fff" }} />
      </button>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ textAlign: "right", lineHeight: 1.2 }}>
          <div style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#002B57" }}>Mara Voss</div>
          <div style={{ fontFamily: "Inter", fontSize: 10.5, color: "#68737D" }}>Gerente E-commerce</div>
        </div>
        <Avatar initials="MV" size={36} />
      </div>
    </header>
  );
}

// ---- Campaigns landing ----
const KPIS = [
  { icon: "rocket", label: "Campañas activas", value: "3" },
  { icon: "image", label: "Banners publicados", value: "47" },
  { icon: "mouse-pointer-click", label: "CTR promedio", value: "4.6%" },
  { icon: "feather", label: "Peso ahorrado", value: "−81%" },
];

const RECENT = [
  { id: CAMPAIGN.id, title: CAMPAIGN.title, promo: CAMPAIGN.promo, window: CAMPAIGN.window, status: "draft", tone: "amber", statusLabel: "Demo/prototipo · En revisión", action: "Continuar", source: "demo" },
  { id: "CMP-0188", title: "Calzado primavera", promo: "20% OFF", window: "12 — 19 may 2026", status: "live", tone: "green", statusLabel: "Demo/prototipo · Publicado", action: "Ver performance", source: "demo" },
  { id: "CMP-0185", title: "Skincare — Día Madre", promo: "2x1", window: "1 — 10 may 2026", status: "live", tone: "green", statusLabel: "Demo/prototipo · Publicado", action: "Ver performance", source: "demo" },
];

function isDraftish(status) {
  return ["draft", "intake", "generating", "review", "failed"].includes(status || "draft");
}

function CampaignRow({ r, index, onResume, onPerf }) {
  const draft = isDraftish(r.status);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "15px 0", borderTop: index ? "1px solid #F1F5F9" : "none" }}>
      <div style={{ width: 42, height: 42, borderRadius: 12, background: r.source === "backend" ? "rgba(34,211,238,0.1)" : "rgba(245,158,11,0.11)", display: "flex", alignItems: "center", justifyContent: "center", color: r.source === "backend" ? "#0891B2" : "#B45309", flexShrink: 0 }}>
        <Icon name={r.source === "backend" ? "database" : "flask-conical"} size={19} />
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
          <span style={{ fontFamily: "Inter", fontSize: 14, fontWeight: 600, color: "#002B57" }}>{r.title}</span>
          <Badge tone={r.source === "backend" ? "cyan" : "amber"}>{r.source === "backend" ? r.promo : "Demo/fallback"}</Badge>
        </div>
        <div style={{ fontFamily: "Space Grotesk", fontSize: 11.5, color: "#94A3B8", marginTop: 3 }}>{r.id} · {r.window}</div>
      </div>
      <Badge tone={r.tone}>{r.statusLabel}</Badge>
      <Button variant={draft ? "default" : "secondary"} icon={draft ? "arrow-right" : "bar-chart-3"}
        onClick={() => (draft ? onResume(r.campaign || r) : onPerf(r.campaign || r))}>{r.action}</Button>
    </div>
  );
}

function CampaignsView({ onNew, onResume, onPerf }) {
  const [backendCards, setBackendCards] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [apiError, setApiError] = React.useState("");

  React.useEffect(() => {
    let live = true;
    async function loadCampaigns() {
      setLoading(true);
      setApiError("");
      const result = await CampaignApi.listSafe();
      if (!live) return;
      setBackendCards((result.data || []).map((c) => CampaignApi.toRecentCard(c)));
      setApiError(result.fallback ? result.reason || "No se pudo cargar campañas del backend." : "");
      setLoading(false);
    }
    loadCampaigns();
    return () => { live = false; };
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Kicker>Agente CEOD · Content E-commerce Optimizer</Kicker>
          <h1 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 40, letterSpacing: "-0.02em", color: "#002B57", margin: 0, lineHeight: 1.04 }}>Estudio de Banners</h1>
          <p style={{ fontFamily: "Inter", fontSize: 14.5, color: "#68737D", margin: 0, maxWidth: 560 }}>Del brief al código nativo de Shopify en segundos. Banners responsivos, optimizados para SEO y de carga ultrarrápida — sin salir de marca.</p>
        </div>
        <Button variant="shine" icon="wand-sparkles" onClick={onNew} style={{ padding: "12px 20px", fontSize: 14.5 }}>Nueva campaña</Button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16 }}>
        {KPIS.map((k) => (
          <GlassCard key={k.label} style={{ padding: 18 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#68737D", fontFamily: "Inter", fontSize: 13 }}>
              <Icon name={k.icon} size={16} color="#22D3EE" /> {k.label}
            </div>
            <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 28, color: "#002B57", marginTop: 12, fontVariantNumeric: "tabular-nums" }}>{k.value}</div>
          </GlassCard>
        ))}
      </div>

      <GlassCard style={{ padding: 22 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
          <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 18, color: "#002B57" }}>Campañas recientes</div>
          <span style={{ fontFamily: "Inter", fontSize: 12.5, color: backendCards.length ? "#0891B2" : "#94A3B8" }}>{backendCards.length ? "Datos de backend /api/v1" : "Esperando campañas backend"}</span>
        </div>
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "14px 0", fontFamily: "Inter", fontSize: 13, color: "#68737D" }}><Spinner size={14} /> Cargando campañas del backend…</div>
        ) : null}
        {apiError ? (
          <div style={{ margin: "12px 0", padding: "10px 12px", borderRadius: 12, background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.35)", color: "#92400E", fontFamily: "Inter", fontSize: 12.5, display: "flex", gap: 8, alignItems: "center" }}>
            <Icon name="wifi-off" size={15} /> No se pudo cargar campañas reales: {apiError}. Mostrando Demo/fallback explícito.
          </div>
        ) : null}
        <div style={{ display: "flex", flexDirection: "column" }}>
          {backendCards.map((r, i) => <CampaignRow key={r.id} r={r} index={i} onResume={onResume} onPerf={onPerf} />)}
          {!loading && !backendCards.length && !apiError ? (
            <div style={{ padding: "18px 0 12px", fontFamily: "Inter", color: "#475569" }}>
              <div style={{ fontWeight: 600, color: "#002B57", marginBottom: 4 }}>No hay campañas creadas aún</div>
              <div style={{ fontSize: 13 }}>Crea una campaña con intake o CampaignApi.create; aparecerá aquí después de refrescar.</div>
            </div>
          ) : null}
          {!loading && !backendCards.length ? (
            <div style={{ marginTop: 10, paddingTop: 12, borderTop: "1px solid #F1F5F9" }}>
              <div style={{ fontFamily: "Inter", fontSize: 11.5, fontWeight: 700, color: "#B45309", textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 2 }}>Demo/fallback · prototipo local</div>
              {RECENT.map((r, i) => <CampaignRow key={r.id} r={r} index={i} onResume={onResume} onPerf={onPerf} />)}
            </div>
          ) : null}
        </div>
      </GlassCard>
    </div>
  );
}

function ModulePlaceholder({ label }) {
  return (
    <GlassCard radius={18} style={{ padding: 64, display: "flex", flexDirection: "column", alignItems: "center", gap: 14, color: "#94A3B8", textAlign: "center" }}>
      <Icon name="layers" size={34} color="#CBD5E1" />
      <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 17, color: "#475569" }}>{label}</div>
      <div style={{ fontFamily: "Inter", fontSize: 13, maxWidth: 320 }}>Parte del ecosistema Aijolot Admin. Este prototipo se centra en el Estudio de Banners.</div>
    </GlassCard>
  );
}

Object.assign(window, { Sidebar, Topbar, CampaignsView, ModulePlaceholder, NAV });
