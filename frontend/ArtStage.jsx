/* global React, Icon, GlassCard, Button, Badge, Kicker, ModelBank, LayoutDiagram, layoutCells, FoldPreview,
   SEGMENTS, CATALOG, HERO_STYLES, MODELS, CatalogApi, ArtDirectionApi, BackgroundApi, ArtApi, isApiCampaign, AIJOLOT_DEMO_IDS, errorText */
// Aijolot Banner Agent — Stage: Art direction (Concept→Product→Background→Assembly).
const { useState: useStateAR, useEffect: useEffectAR } = React;

const DEFAULT_ART_DIRECTION = { bg: "usage", heroStyle: "rocks", model: "m2", fold: 55 };

function catalogFallbackItems() {
  return (CATALOG || []).map((p, idx) => ({
    id: p.sku || `fallback-${idx}`,
    resource_type: "product",
    title: p.name,
    sku: p.sku,
    price: p.price,
    sale_price: p.sale,
    stock: p.stock,
    segment_key: p.seg,
    handle: p.sku ? p.sku.toLowerCase() : null,
    source: "fallback",
  }));
}

function normalizeCatalogItems(snapshot) {
  const items = snapshot && Array.isArray(snapshot.items) ? snapshot.items : [];
  return items.map((item, idx) => ({
    id: item.id || item.shopify_gid || item.shopify_product_gid || item.handle || `snapshot-${idx}`,
    resource_type: item.resource_type || "product",
    title: item.title || item.handle || "Recurso sin título",
    vendor: item.vendor || null,
    sku: item.sku || null,
    handle: item.handle || null,
    tags: Array.isArray(item.tags) ? item.tags : [],
    price: item.price,
    sale_price: item.sale_price,
    stock: item.stock,
    segment_key: item.segment_key || null,
    image_url: item.image_url || null,
    raw: item.raw || {},
  }));
}

function artFromBackend(row) {
  return {
    bg: row && row.background_mode || DEFAULT_ART_DIRECTION.bg,
    heroStyle: row && row.hero_style_key || DEFAULT_ART_DIRECTION.heroStyle,
    model: row && row.model_key || DEFAULT_ART_DIRECTION.model,
    customModel: row && row.custom_model || {},
    fold: row && Number.isFinite(Number(row.fold_percentage)) ? Number(row.fold_percentage) : DEFAULT_ART_DIRECTION.fold,
  };
}

function money(v) {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? `$${n.toFixed(n % 1 ? 2 : 0)}` : String(v);
}

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
  const [art, setArt] = useStateAR(DEFAULT_ART_DIRECTION);
  const [catalog, setCatalog] = useStateAR({ loading: true, fallback: false, source: "local_fallback", reason: "", snapshot: null, items: catalogFallbackItems() });
  const [catalogSelect, setCatalogSelect] = useStateAR(null);
  const [hydrateNotice, setHydrateNotice] = useStateAR(null);
  const [saveState, setSaveState] = useStateAR("idle");
  const [aiBg, setAiBg] = useStateAR({ loading: false, options: [], source: "", selected: null, error: "" });
  const [artGen, setArtGen] = useStateAR({ loading: false, asset: null, source: "", prompt: "", error: "" });
  const set = (patch) => { setSaveState("dirty"); setArt((a) => ({ ...a, ...patch })); };
  const canArtApi = typeof isApiCampaign === "function" && isApiCampaign(campaign) && typeof ArtApi !== "undefined";

  async function generateBackgrounds() {
    if (aiBg.loading) return;
    if (!canArtApi || typeof BackgroundApi === "undefined") {
      setAiBg((s) => ({ ...s, error: "Requiere campaña backend con revisión generada." }));
      onNotice && onNotice({ tone: "amber", text: "Fondos AI requieren una campaña backend con revisión generada (corré Generar primero)." });
      return;
    }
    setAiBg((s) => ({ ...s, loading: true, error: "" }));
    const res = await BackgroundApi.generate(campaign, { count: 3 });
    const options = (res && res.data && res.data.options) || [];
    if (res && res.ok && !res.fallback && options.length) {
      setAiBg({ loading: false, options, source: res.data.source || "deterministic", selected: options[0].name, error: "" });
      onNotice && onNotice({ tone: "green", text: "Fondos AI generados (" + (res.data.source || "deterministic") + ")" });
    } else {
      setAiBg({ loading: false, options, source: "", selected: null, error: (res && res.reason) || "Sin opciones." });
      onNotice && onNotice({ tone: "amber", text: (res && res.reason) || "No se pudieron generar fondos AI." });
    }
  }

  async function generateArtImage() {
    if (artGen.loading) return;
    if (!canArtApi) {
      onNotice && onNotice({ tone: "amber", text: "Generar imagen requiere una campaña backend con revisión generada." });
      return;
    }
    setArtGen((s) => ({ ...s, loading: true, error: "" }));
    const bgOption = aiBg.options.find((o) => o.name === aiBg.selected);
    const shotType = art.bg === "hero" ? "hero" : "usage";
    const subject = selectedItem ? `${selectedItem.title}${productMeta ? ", " + productMeta : ""}` : (campaign && campaign.title) || "producto destacado";
    const res = await ArtApi.generateArt(campaign, {
      prompt: subject,
      shot_type: shotType,
      background_ref: bgOption ? bgOption.name : null,
      background_css: bgOption ? bgOption.css : null,
    });
    if (res && res.ok && !res.fallback && res.data) {
      const asset = res.data.asset || (res.data.assets && res.data.assets[0]) || null;
      setArtGen({ loading: false, asset, source: res.data.provider || "", prompt: res.data.prompt || subject, error: "" });
      onNotice && onNotice({ tone: "green", text: "Imagen generada (" + (res.data.provider || "provider") + ") y adjunta a la revisión" });
    } else {
      setArtGen({ loading: false, asset: null, source: "", prompt: "", error: (res && res.reason) || "Falló." });
      onNotice && onNotice({ tone: "amber", text: (res && res.reason) || "No se pudo generar la imagen." });
    }
  }
  const allModels = [...MODELS, ...createdModels];
  const selectedItem = catalog.items.find((item) => item.id === catalogSelect) || catalog.items[0] || catalogFallbackItems()[0];
  const previewSeg = selectedItem ? { ...seg, product: { ...seg.product, name: selectedItem.title, sku: selectedItem.sku || selectedItem.handle || selectedItem.id } } : seg;
  const productMeta = selectedItem ? [selectedItem.sku, selectedItem.vendor, selectedItem.handle].filter(Boolean).join(" · ") : "";

  useEffectAR(() => {
    let cancelled = false;
    async function load() {
      setCatalog((c) => ({ ...c, loading: true }));
      setCatalogSelect(null);
      setHydrateNotice(null);
      setSaveState("idle");
      if (!(typeof isApiCampaign === "function" && isApiCampaign(campaign))) {
        const reason = "Sin campaña UUID backend: usando catálogo demo local y dirección de arte no durable.";
        if (!cancelled) {
          setCatalog({ loading: false, fallback: true, source: "local_fallback", reason, snapshot: null, items: catalogFallbackItems() });
          setHydrateNotice({ tone: "amber", text: reason });
          onNotice && onNotice({ tone: "amber", text: reason });
        }
        return;
      }

      let snapshotEnvelope = null;
      try {
        try {
          snapshotEnvelope = await CatalogApi.getSnapshot(campaign);
        } catch (e) {
          if (e && e.status === 404) {
            snapshotEnvelope = await CatalogApi.createSnapshot(campaign, {
              store_id: (placement && placement.backend && placement.backend.store_id) || (AIJOLOT_DEMO_IDS && AIJOLOT_DEMO_IDS.store) || window.AIJOLOT_STORE_ID || "00000000-0000-0000-0000-000000000101",
              resource_types: ["product", "collection", "page"],
              limit: 12,
              query_summary: campaign && (campaign.title || campaign.promo || campaign.brief) || null,
            });
          } else {
            throw e;
          }
        }
        const snapshot = snapshotEnvelope && snapshotEnvelope.data;
        const items = normalizeCatalogItems(snapshot);
        if (!cancelled) {
          if (items.length) {
            setCatalog({ loading: false, fallback: false, source: snapshot.source || "shopify_resource_cache", reason: "", snapshot, items });
            setCatalogSelect((current) => current || (items[0] && items[0].id));
          } else {
            const reason = "El snapshot backend no trajo recursos visibles; usando catálogo demo local como fallback.";
            setCatalog({ loading: false, fallback: true, source: "local_fallback", reason, snapshot, items: catalogFallbackItems() });
            setHydrateNotice({ tone: "amber", text: reason });
            onNotice && onNotice({ tone: "amber", text: reason });
          }
        }
      } catch (e) {
        const reason = "No se pudo hidratar catálogo desde backend: " + (typeof errorText !== "undefined" ? errorText(e) : (e.message || e.status || "error")) + ". Usando fallback demo local.";
        if (!cancelled) {
          setCatalog({ loading: false, fallback: true, source: "local_fallback", reason, snapshot: null, items: catalogFallbackItems() });
          setHydrateNotice({ tone: "amber", text: reason });
          onNotice && onNotice({ tone: "amber", text: reason });
        }
      }

      try {
        const saved = await ArtDirectionApi.get(campaign);
        if (!cancelled && saved && !saved.fallback && saved.data) {
          setArt(artFromBackend(saved.data));
          setSaveState("saved");
          onNotice && onNotice({ tone: "green", text: "Dirección de arte restaurada desde backend" });
        }
      } catch (e) {
        if (!cancelled && e && e.status !== 404) {
          const reason = "No se pudo restaurar dirección de arte: " + (typeof errorText !== "undefined" ? errorText(e) : (e.message || e.status || "error"));
          setHydrateNotice({ tone: "amber", text: reason });
          onNotice && onNotice({ tone: "amber", text: reason });
        }
      }
    }
    load();
    return () => { cancelled = true; };
  }, [campaign && campaign.id]);

  function createModel(m) {
    const id = "mc" + (createdModels.length + 1);
    const nm = { ...m, id };
    setCreated((c) => [...c, nm]);
    set({ bg: "usage", model: id, customModel: { name: m.name, tag: m.tag, desc: m.desc || "" } });
  }

  async function assemble() {
    setSaveState("saving");
    try {
      let snapshot = null;
      if (typeof isApiCampaign === "function" && isApiCampaign(campaign)) {
        snapshot = await CatalogApi.createSnapshot(campaign, {
          store_id: (placement && placement.backend && placement.backend.store_id) || (AIJOLOT_DEMO_IDS && AIJOLOT_DEMO_IDS.store) || window.AIJOLOT_STORE_ID || "00000000-0000-0000-0000-000000000101",
          resource_types: ["product", "collection", "page"],
          limit: 12,
          query_summary: campaign && (campaign.title || campaign.promo || campaign.brief) || null,
        });
        if (snapshot && !snapshot.fallback && snapshot.data) {
          const items = normalizeCatalogItems(snapshot.data);
          if (items.length) setCatalog({ loading: false, fallback: false, source: snapshot.data.source || "shopify_resource_cache", reason: "", snapshot: snapshot.data, items });
        }
      }
      if (snapshot && snapshot.fallback) onNotice && onNotice({ tone: "amber", text: snapshot.reason });
      const r = await ArtDirectionApi.save(campaign, art, placement);
      setSaveState(r.fallback ? "fallback" : "saved");
      onNotice && onNotice(r.fallback ? { tone: "amber", text: r.reason } : { tone: "green", text: "Catálogo y dirección de arte guardados en backend" });
    } catch (e) {
      setSaveState("failed");
      onNotice && onNotice({ tone: "amber", text: "No se pudo guardar catálogo/arte en backend: " + (typeof errorText !== "undefined" ? errorText(e) : (e.message || e.status || "error")) });
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
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <Badge tone={catalog.fallback ? "amber" : catalog.loading ? "slate" : "green"} icon={catalog.fallback ? "triangle-alert" : "database"}>
            {catalog.loading ? "Cargando snapshot" : catalog.fallback ? "Catálogo fallback local" : "Snapshot backend"}
          </Badge>
          <Badge tone={saveState === "failed" ? "red" : saveState === "saved" ? "green" : saveState === "saving" ? "amber" : saveState === "dirty" ? "amber" : "cyan"} icon={saveState === "saved" ? "check" : "palette"}>
            {saveState === "saving" ? "Guardando arte" : saveState === "saved" ? "Arte backend guardado" : saveState === "failed" ? "Arte no guardado" : saveState === "dirty" ? "Cambios sin guardar" : "Arte local listo"}
          </Badge>
          <Badge tone="cyan" icon="layers">Concepto → Producto → Fondo → Ensamblaje</Badge>
        </div>
      </div>

      {hydrateNotice ? (
        <div style={{ display: "flex", alignItems: "flex-start", gap: 9, padding: "10px 12px", borderRadius: 12, border: "1px solid rgba(245,158,11,0.28)", background: "rgba(245,158,11,0.10)", color: "#92400E", fontFamily: "Inter", fontSize: 12.5 }}>
          <Icon name="triangle-alert" size={15} />
          <span>{hydrateNotice.text}</span>
        </div>
      ) : null}

      <GlassCard style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "Space Grotesk", fontSize: 13, fontWeight: 600, color: "#002B57" }}>
            <Icon name="database" size={15} /> Recursos de catálogo
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <Badge tone={catalog.fallback ? "amber" : "green"}>{catalog.fallback ? "Fallback demo local" : catalog.source}</Badge>
            {catalog.snapshot ? <Badge tone="slate">{catalog.snapshot.item_count || catalog.items.length} items</Badge> : <Badge tone="slate">{catalog.items.length} items UI</Badge>}
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 8 }}>
          {catalog.items.slice(0, 6).map((item) => {
            const price = money(item.sale_price || item.price);
            const active = selectedItem && selectedItem.id === item.id;
            return (
              <button key={item.id} onClick={() => setCatalogSelect(item.id)} style={{ display: "flex", alignItems: "center", gap: 9, padding: "9px 10px", borderRadius: 11, cursor: "pointer", border: "1.5px solid " + (active ? "#22D3EE" : "#EEF2F6"), background: active ? "rgba(34,211,238,0.08)" : "rgba(255,255,255,0.85)", textAlign: "left" }}>
                <span style={{ width: 34, height: 34, borderRadius: 8, flexShrink: 0, background: item.image_url ? `url(${item.image_url}) center/cover` : (item.resource_type === "collection" ? "linear-gradient(135deg,#ECFEFF,#CFFAFE)" : "linear-gradient(160deg,#1b2c43,#0b1622)"), border: "1px solid #E2E8F0", display: "flex", alignItems: "center", justifyContent: "center", color: item.image_url ? "transparent" : "#0891B2" }}>
                  {!item.image_url ? <Icon name={item.resource_type === "collection" ? "layout-grid" : item.resource_type === "page" ? "file-text" : "package"} size={15} /> : null}
                </span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ display: "block", fontFamily: "Inter", fontSize: 12.2, fontWeight: 700, color: "#002B57", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.title}</span>
                  <span style={{ display: "block", fontFamily: "Space Grotesk", fontSize: 10, color: "#94A3B8", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.resource_type}{price ? ` · ${price}` : ""}{item.stock != null ? ` · stock ${item.stock}` : ""}</span>
                </span>
              </button>
            );
          })}
        </div>
      </GlassCard>

      {/* F7/F8 — AI Studio: backgrounds + image generation against the backend */}
      <GlassCard style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "Space Grotesk", fontSize: 13, fontWeight: 600, color: "#002B57" }}>
            <Icon name="wand-sparkles" size={15} /> Estudio AI · Fondos y arte
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {aiBg.source ? <Badge tone={aiBg.source === "gemini" ? "purple" : "slate"}>Fondos {aiBg.source}</Badge> : null}
            {artGen.source ? <Badge tone="green" icon="image">Imagen {artGen.source}</Badge> : null}
            {!canArtApi ? <Badge tone="amber" icon="triangle-alert">Requiere revisión backend</Badge> : null}
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button variant="secondary" icon="palette" onClick={generateBackgrounds} disabled={aiBg.loading}>
            {aiBg.loading ? "Generando fondos…" : "Generar 3 fondos AI"}
          </Button>
          <Button variant="default" icon="sparkles" onClick={generateArtImage} disabled={artGen.loading}>
            {artGen.loading ? "Generando imagen…" : `Generar imagen (${art.bg === "hero" ? "hero" : "usage"})`}
          </Button>
        </div>

        {aiBg.options.length ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 8 }}>
            {aiBg.options.map((o, i) => {
              const scoped = String(o.css || "").split(".aijolot-banner").join(`.aijolot-bg-${i}`);
              const on = aiBg.selected === o.name;
              return (
                <button key={i} onClick={() => setAiBg((s) => ({ ...s, selected: o.name }))} style={{ textAlign: "left", padding: 0, borderRadius: 11, overflow: "hidden", cursor: "pointer", border: "2px solid " + (on ? "#22D3EE" : "#EEF2F6"), background: "#fff" }}>
                  <style dangerouslySetInnerHTML={{ __html: scoped }} />
                  <div className={`aijolot-bg-${i}`} style={{ height: 56, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "Inter", fontSize: 10, color: "rgba(255,255,255,.85)" }}>preview</div>
                  <div style={{ padding: "7px 9px" }}>
                    <div style={{ fontFamily: "Inter", fontSize: 12, fontWeight: 700, color: "#002B57", display: "flex", alignItems: "center", gap: 5 }}>{on ? <Icon name="check" size={12} color="#0891B2" /> : null}{o.name}</div>
                    <div style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8" }}>{o.description}</div>
                  </div>
                </button>
              );
            })}
          </div>
        ) : null}

        {artGen.asset && (artGen.asset.public_url || artGen.asset.storage_path) ? (
          <div style={{ display: "flex", gap: 12, alignItems: "center", padding: 10, borderRadius: 11, background: "rgba(248,250,252,0.8)", border: "1px solid #EEF2F6" }}>
            <img src={artGen.asset.public_url || ""} alt="" style={{ width: 120, height: 68, objectFit: "cover", borderRadius: 8, background: "#0b1622", flexShrink: 0 }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontFamily: "Inter", fontSize: 12, fontWeight: 600, color: "#002B57" }}>Imagen generada · {artGen.asset.format || "webp"} {artGen.asset.size_key || ""}px</div>
              <div style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8", wordBreak: "break-all" }}>{artGen.prompt}</div>
            </div>
          </div>
        ) : null}
      </GlassCard>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.5fr) minmax(320px,1fr)", gap: 16, alignItems: "start" }}>
        {/* preview */}
        <GlassCard style={{ padding: 18, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "Space Grotesk", fontSize: 12.5, color: "#94A3B8" }}>
            <Icon name="eye" size={14} /> Vista de composición · {art.bg === "hero" ? "Hero shot" : "Usage shot"}{cells > 1 ? ` · ${layout.cols.length} col / ${cells} celdas` : ""}
          </div>
          <FoldPreview art={art} layout={layout} seg={previewSeg} allModels={allModels} />
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

          <LayerRow n="2" icon="package" title="Producto / recurso protagonista" sub={catalog.fallback ? "Fallback demo local visible" : "Snapshot backend desde resource cache"} done>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ width: 30, height: 30, borderRadius: 7, background: selectedItem && selectedItem.image_url ? `url(${selectedItem.image_url}) center/cover` : seg.palette.bottle, border: "1px solid #E2E8F0" }} />
              <span style={{ fontFamily: "Inter", fontSize: 12.5, color: "#475569" }}>
                {selectedItem ? selectedItem.title : "Producto no disponible"}{productMeta ? ` · ${productMeta}` : ""}
              </span>
            </div>
            {selectedItem ? (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <Badge tone={catalog.fallback ? "amber" : "green"}>{catalog.fallback ? "Dato fallback" : "Dato backend"}</Badge>
                <Badge tone="slate">{selectedItem.resource_type}</Badge>
                {money(selectedItem.sale_price || selectedItem.price) ? <Badge tone="slate">{money(selectedItem.sale_price || selectedItem.price)}</Badge> : null}
                {selectedItem.stock != null ? <Badge tone="slate">Stock {selectedItem.stock}</Badge> : null}
              </div>
            ) : null}
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
                <div style={{ display: "flex", alignItems: "center", gap: 7, fontFamily: "Inter", fontSize: 11.5, color: "#B45309", background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.20)", borderRadius: 9, padding: "7px 9px" }}>
                  <Icon name="info" size={13} /> Estilos hero: presets locales de UI (sin endpoint backend de listado)
                </div>
                {HERO_STYLES.map((h) => (
                  <button key={h.id} onClick={() => set({ heroStyle: h.id })} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 10, cursor: "pointer", textAlign: "left", border: "1.5px solid " + (art.heroStyle === h.id ? "#22D3EE" : "#EEF2F6"), background: art.heroStyle === h.id ? "rgba(34,211,238,.08)" : "#fff" }}>
                    <span style={{ width: 34, height: 24, borderRadius: 6, background: h.grad, flexShrink: 0 }} />
                    <span style={{ flex: 1 }}><span style={{ display: "block", fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#002B57" }}>{h.name}</span><span style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>{h.desc}</span></span>
                    {art.heroStyle === h.id ? <Icon name="check" size={15} color="#0891B2" /> : null}
                  </button>
                ))}
              </div>
            ) : (
              <ModelBank models={allModels} selected={art.model} onSelect={(id) => set({ model: id })} onCreate={createModel} campaign={campaign} onNotice={onNotice} />
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

          <Button variant="shine" icon="wand-sparkles" onClick={assemble} disabled={saveState === "saving"} style={{ justifyContent: "center" }}>
            {saveState === "saving" ? "Guardando dirección de arte…" : "Ensamblar banner"}
          </Button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ArtStage });
