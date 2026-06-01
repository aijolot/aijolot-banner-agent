/* global React, Icon, GlassCard, Button, Badge, Kicker, ModelBank, LayoutDiagram, layoutCells, FoldPreview,
   SEGMENTS, HERO_STYLES, MODELS, ArtDirectionApi */
// Aijolot Banner Agent — Stage: Art direction (Concept→Product→Background→Assembly).
const { useState: useStateAR } = React;

function LayerRow({ n, icon, title, sub, done, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 9, padding: "13px 14px", borderRadius: 12, background: done ? "rgba(16,185,129,0.05)" : "rgba(248,250,252,0.7)", border: `1px solid ${done ? "rgba(16,185,129,0.18)" : "#EEF2F6"}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 26, height: 26, borderRadius: 8, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: done ? "rgba(16,185,129,0.14)" : "rgba(34,211,238,0.14)", color: done ? "#10B981" : "#0891B2" }}>
          {done ? <Icon name="check" size={15} /> : <Icon name={icon} size={15} />}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57" }}>{n}. {title}</div>
          {sub ? <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8", marginTop: 1 }}>{sub}</div> : null}
        </div>
        {done ? <Badge tone="green" icon="check">Listo</Badge> : null}
      </div>
      {children}
    </div>
  );
}

function ArtStage({ campaign, placement, onNotice, onAssemble }) {
  const seg = SEGMENTS.masculino;
  const layout = (placement && placement.layout) || { cols: [{ rows: 1, w: 1 }] };
  const cells = layoutCells(layout);
  const [createdModels, setCreated] = useStateAR([]);
  const [art, setArt] = useStateAR({ bg: "usage", heroStyle: "rocks", model: "m2", fold: 55 });
  const set = (patch) => setArt((a) => ({ ...a, ...patch }));
  const allModels = [...MODELS, ...createdModels];

  function createModel(m) {
    const id = "mc" + (createdModels.length + 1);
    const nm = { ...m, id };
    setCreated((c) => [...c, nm]);
    set({ bg: "usage", model: id });
  }

  async function assemble() {
    try {
      const r = await ArtDirectionApi.save(campaign, art, placement);
      onNotice && onNotice(r.fallback ? { tone: "amber", text: r.reason } : { tone: "green", text: "Dirección de arte guardada en backend" });
    } catch (e) {
      onNotice && onNotice({ tone: "amber", text: "No se pudo guardar arte en backend: " + (e.message || e.status || "error") });
    }
    onAssemble && onAssemble(art);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Kicker>Paso 3 de 6 · Dirección de arte</Kicker>
          <h2 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 26, color: "#002B57", margin: 0 }}>Compón el creativo</h2>
        </div>
        <Badge tone="cyan" icon="layers">Concepto → Producto → Fondo → Ensamblaje</Badge>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.5fr) minmax(320px,1fr)", gap: 16, alignItems: "start" }}>
        {/* preview */}
        <GlassCard style={{ padding: 18, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "Space Grotesk", fontSize: 12.5, color: "#94A3B8" }}>
            <Icon name="eye" size={14} /> Vista de composición · {art.bg === "hero" ? "Hero shot" : "Usage shot"}{cells > 1 ? ` · ${layout.cols.length} col / ${cells} celdas` : ""}
          </div>
          <FoldPreview art={art} layout={layout} seg={seg} allModels={allModels} />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Badge tone="slate" icon="image">{art.bg === "hero" ? "Fondo Hero generado" : "Fondo Usage + modelo"}</Badge>
            <Badge tone="slate" icon="fold-vertical">{art.fold}% sobre el pliegue</Badge>
            <Badge tone="slate" icon="layout-grid">{cells === 1 ? "1 banner" : `${layout.cols.length} col · ${cells} celdas`}</Badge>
          </div>
        </GlassCard>

        {/* ordered layers */}
        <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
          <LayerRow n="1" icon="lightbulb" title="Concepto y mensaje" sub="Definido en el brief" done>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              <Badge tone="cyan">{seg.headline.replace("\n", " ")}</Badge>
              <Badge tone="cyan">CTA · {seg.cta}</Badge>
            </div>
          </LayerRow>

          <LayerRow n="2" icon="package" title="Producto (protagonista)" sub="Asset real desde Shopify" done>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 30, height: 30, borderRadius: 7, background: seg.palette.bottle, border: "1px solid #E2E8F0" }} />
              <span style={{ fontFamily: "Inter", fontSize: 12.5, color: "#475569" }}>{seg.product.name} · PNG recortado</span>
            </div>
          </LayerRow>

          <LayerRow n="3" icon="image" title="Fondo (Hero / Usage)" sub="El contexto que abraza al producto">
            <div style={{ display: "flex", gap: 3, background: "rgba(248,250,252,0.9)", borderRadius: 10, padding: 3 }}>
              {[["hero", "Hero shot", "gem"], ["usage", "Usage shot", "users-round"]].map(([id, label, ic]) => (
                <button key={id} onClick={() => set({ bg: id })} style={{ flex: 1, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "8px 10px", borderRadius: 8, cursor: "pointer", border: "1px solid " + (art.bg === id ? "rgba(34,211,238,.5)" : "transparent"), background: art.bg === id ? "rgba(34,211,238,.14)" : "transparent", color: art.bg === id ? "#0891B2" : "#68737D", fontFamily: "Inter", fontSize: 12.5, fontWeight: 600 }}>
                  <Icon name={ic} size={14} /> {label}
                </button>
              ))}
            </div>
            {art.bg === "hero" ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {HERO_STYLES.map((h) => (
                  <button key={h.id} onClick={() => set({ heroStyle: h.id })} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 10, cursor: "pointer", textAlign: "left", border: "1.5px solid " + (art.heroStyle === h.id ? "#22D3EE" : "#EEF2F6"), background: art.heroStyle === h.id ? "rgba(34,211,238,.08)" : "#fff" }}>
                    <span style={{ width: 34, height: 24, borderRadius: 6, background: h.grad, flexShrink: 0 }} />
                    <span style={{ flex: 1 }}><span style={{ display: "block", fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#002B57" }}>{h.name}</span><span style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>{h.desc}</span></span>
                    {art.heroStyle === h.id ? <Icon name="check" size={15} color="#0891B2" /> : null}
                  </button>
                ))}
              </div>
            ) : (
              <ModelBank models={allModels} selected={art.model} onSelect={(id) => set({ model: id })} onCreate={createModel} />
            )}
          </LayerRow>

          <LayerRow n="4" icon="layout-template" title="Composición y ensamblaje" sub="Espacio sobre el pliegue + grid">
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "Inter", fontSize: 11.5, color: "#68737D" }}>
                <span>Alto del banner sobre el pliegue</span>
                <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, color: "#0891B2" }}>{art.fold}%</span>
              </div>
              <input type="range" min="30" max="80" step="5" value={art.fold} onChange={(e) => set({ fold: +e.target.value })} style={{ width: "100%", accentColor: "#22D3EE" }} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 11px", borderRadius: 10, background: "rgba(248,250,252,0.8)", border: "1px solid #EEF2F6" }}>
              <div style={{ width: 34, height: 34, flexShrink: 0 }}><LayoutDiagram layout={layout} h={34} /></div>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#002B57" }}>{layout.cols.length} col · {cells} celda{cells > 1 ? "s" : ""}</div>
                <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>Declarado en Ubicación · el arte se compone por celda</div>
              </div>
            </div>
          </LayerRow>

          <Button variant="shine" icon="wand-sparkles" onClick={assemble} style={{ justifyContent: "center" }}>Ensamblar banner</Button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ArtStage });
