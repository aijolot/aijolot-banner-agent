/* global React, Icon, GlassCard, Button, Badge, Kicker, ChromeWindow, STORE_PAGES,
   SCOPE_OPTS, HomeMock, CollectionMock, ProductMock, SearchMock,
   PlacementApi, StoreApi, LayoutDiagram, errorText, AIJOLOT_DEMO_IDS */
// Aijolot Banner Agent — Stage 0: navigate the store template & choose a placement + scope.
const { useState: useStatePL, useEffect: useEffectPL } = React;

const PL_RESOURCE_TYPES = ["collection", "product", "page", "search"];
const PL_SLOT_ICON = { announce: "megaphone", hero: "panel-top", promo_l: "panel-left", promo_r: "panel-right", coll_top: "gallery-horizontal-end", coll_inline: "layout-grid", pdp_strip: "tag", pdp_cross: "layers", footer: "panel-bottom", search_top: "search" };
const PL_PAGE_LABEL = { home: "Inicio", collection: "Colección", product: "Producto", page: "Página", search: "Búsqueda" };
const PL_PAGE_ICON = { home: "house", collection: "layout-grid", product: "package", page: "file-text", search: "search" };
const PL_PREFERRED_SLOT = { home: "hero", collection: "coll_top", product: "pdp_strip", search: "search_top" };
const PL_TYPE_PAGE_SLOT = {
  announcement_bar: { home: ["announce"], collection: ["announce"], product: ["announce"], search: ["announce"], page: ["announce"] },
  hero_main: { home: ["hero"], collection: ["coll_top"], page: ["hero"] },
  promo_card: { home: ["promo_l", "promo_r"], collection: ["coll_inline"] },
  collection_header: { collection: ["coll_top"] },
  pdp_strip: { product: ["pdp_strip"] },
  pdp_cross_sell: { product: ["pdp_cross"] },
  footer_cta: { home: ["footer"], collection: ["footer"], product: ["footer"], search: ["footer"], page: ["footer"] },
  search_results_banner: { search: ["search_top"] },
};

function plDefaultResource(resources, type) { return ((resources && resources[type]) || [])[0] || null; }
function plSizeFromType(t) {
  const d = t && t.default_dimensions && t.default_dimensions.desktop;
  return d && d.width && d.height ? `${d.width} × ${d.height}` : "responsivo";
}
function plResourceUrl(store, type, resource) {
  const domain = (store && (store.shop_domain || store.domain)) || "maison-store.myshopify.com";
  const handle = resource && resource.handle;
  if (type === "collection") return `${domain}/collections/${handle || "fragancias"}`;
  if (type === "product") return `${domain}/products/${handle || "boss-bottled"}`;
  if (type === "page") return `${domain}/pages/${handle || "landing"}`;
  if (type === "search") return `${domain}/search?q=${encodeURIComponent((resource && (resource.handle || resource.title)) || "hugo boss")}`;
  return domain;
}
function plTargetResource(resources, pageId) {
  if (pageId === "collection") return plDefaultResource(resources, "collection");
  if (pageId === "product") return plDefaultResource(resources, "product");
  if (pageId === "page") return plDefaultResource(resources, "page");
  if (pageId === "search") return plDefaultResource(resources, "search");
  return null;
}
function plBuildPages(store, resources, placementTypes, fallbackPages) {
  const byId = Object.fromEntries((fallbackPages || []).map((p) => [p.id, p]));
  if (!Array.isArray(placementTypes) || !placementTypes.length) return (fallbackPages || []).map((p) => ({ ...p, source: "fallback" }));
  const ids = ["home", "collection", "product", "search"];
  return ids.map((pageId) => {
    const targetRes = plTargetResource(resources, pageId);
    const placements = [];
    placementTypes.filter((t) => t && t.is_active !== false).forEach((t) => {
      const supported = t.supported_targets || [];
      if (!supported.includes(pageId) && !(pageId === "search" && supported.includes("store"))) return;
      const slots = (PL_TYPE_PAGE_SLOT[t.key] && PL_TYPE_PAGE_SLOT[t.key][pageId]) || (t.supported_slots || []).map((s) => s.key).filter((k) => PL_SLOT_ICON[k]);
      slots.forEach((slotKey) => {
        const targetType = pageId === "search" && !supported.includes("search") && supported.includes("store") ? "store" : (pageId === "home" ? "home" : pageId);
        placements.push({
        id: slotKey,
        name: ((t.supported_slots || []).find((s) => s.key === slotKey) || {}).label || t.label,
        size: plSizeFromType(t),
        icon: PL_SLOT_ICON[slotKey] || "layout-template",
        rec: slotKey === (PL_PREFERRED_SLOT[pageId] || slots[0]),
        source: "backend",
        backend: {
          store_id: store && store.id,
          placement_type_id: t.id,
          placement_type_key: t.key,
          target_type: targetType,
          target_resource: targetRes,
          target_resource_gid: targetRes && targetRes.shopify_gid,
          target_handle: targetRes && targetRes.handle,
          target_title: targetRes && targetRes.title,
          existing_placement_key: slotKey,
          existing_placement_label: ((t.supported_slots || []).find((s) => s.key === slotKey) || {}).label || t.label,
          existing_placement_size: plSizeFromType(t),
          slot: slotKey,
        },
        });
      });
    });
    const fallback = byId[pageId] || byId.home;
    return {
      id: pageId,
      label: PL_PAGE_LABEL[pageId] || (fallback && fallback.label) || pageId,
      url: plResourceUrl(store, pageId, targetRes),
      resource: targetRes,
      source: placements.length ? "backend" : "fallback",
      placements: placements.length ? placements : ((fallback && fallback.placements) || []).map((p) => ({ ...p, source: "fallback" })),
    };
  });
}

function PlacementStage({ onNext, onNotice }) {
  const [pageId, setPageId] = useStatePL("home");
  const [sel, setSel] = useStatePL("hero");
  const [hov, setHov] = useStatePL(null);
  const [scopeKind, setScopeKind] = useStatePL("home");
  const [brand, setBrand] = useStatePL("Hugo Boss");
  const [tag, setTag] = useStatePL("fragancia");
  const [colls, setColls] = useStatePL(["Fragancias"]);
  const [query, setQuery] = useStatePL("hugo boss");
  const [layout, setLayout] = useStatePL({ cols: [{ rows: 1, w: 1, align: "center" }] });
  const [storeState, setStoreState] = useStatePL({ loading: true, source: "fallback", store: null, resources: {}, placementTypes: [], error: null });
  const [mode, setMode] = useStatePL("existing"); // "existing" = update section · "new" = inject new section
  const [dragging, setDragging] = useStatePL(false);
  const [overZone, setOverZone] = useStatePL(null);
  const [dropAt, setDropAt] = useStatePL(null);
  const ZONE_LABELS = { top: "Parte superior", mid: "Zona media", bottom: "Antes del footer" };
  const pages = plBuildPages(storeState.store, storeState.resources, storeState.placementTypes, STORE_PAGES);
  const page = pages.find((p) => p.id === pageId) || pages[0];
  const rec = (pg) => ((pg && pg.placements || []).find((x) => x.rec) || (pg && pg.placements || [])[0] || {}).id || "hero";
  const defScope = (id) => ((SCOPE_OPTS[id] || SCOPE_OPTS.home || [])[0] || {}).id || "home";
  const collectionChoices = (storeState.resources.collection || []).map((r) => r.title || r.handle).filter(Boolean);
  const productChoices = storeState.resources.product || [];
  const brandChoices = [...new Set(productChoices.map((r) => r.vendor).filter(Boolean))];
  const tagChoices = [...new Set(productChoices.flatMap((r) => r.tags || []).filter(Boolean))];
  const resourceCounts = PL_RESOURCE_TYPES.reduce((acc, t) => ({ ...acc, [t]: (storeState.resources[t] || []).length }), {});
  const storeName = (storeState.store && (storeState.store.name || storeState.store.shop_domain)) || "Maison";
  const storeDomain = (storeState.store && storeState.store.shop_domain) || page.url || "maison-store.myshopify.com";

  useEffectPL(() => {
    let alive = true;
    async function hydrate() {
      if (typeof StoreApi === "undefined") {
        if (alive) setStoreState((s) => ({ ...s, loading: false, source: "fallback", error: "StoreApi no disponible; usando STORE_PAGES estático como fallback." }));
        return;
      }
      try {
        const list = StoreApi.listSafe ? await StoreApi.listSafe() : { ok: true, data: await StoreApi.list() };
        const first = (list.data || []).find((s) => s.id === (AIJOLOT_DEMO_IDS && AIJOLOT_DEMO_IDS.store)) || (list.data || [])[0];
        const store = first ? (StoreApi.getSafe ? (await StoreApi.getSafe(first.id)).data || first : await StoreApi.get(first.id)) : null;
        const storeId = store && store.id;
        const resources = {};
        const failures = [];
        await Promise.all(PL_RESOURCE_TYPES.map(async (type) => {
          const r = StoreApi.resourcesSafe ? await StoreApi.resourcesSafe(storeId, type) : { ok: true, data: await StoreApi.resources(storeId, type) };
          resources[type] = Array.isArray(r.data) ? r.data : [];
          if (r.fallback || r.ok === false) failures.push(`${type}: ${r.reason || "error"}`);
        }));
        const pt = StoreApi.placementTypesSafe ? await StoreApi.placementTypesSafe(storeId) : { ok: true, data: await StoreApi.placementTypes(storeId) };
        if (pt.fallback || pt.ok === false) failures.push(`placements: ${pt.reason || "error"}`);
        if (!alive) return;
        const placementTypes = Array.isArray(pt.data) ? pt.data : [];
        setStoreState({ loading: false, source: store && placementTypes.length ? "backend" : "fallback", store, resources, placementTypes, error: failures.length ? failures.join(" · ") : null });
        const hydratedPages = plBuildPages(store, resources, placementTypes, STORE_PAGES);
        const hydratedPage = hydratedPages.find((p) => p.id === pageId) || hydratedPages[0];
        if (hydratedPage) { setSel(rec(hydratedPage)); setScopeKind(defScope(hydratedPage.id)); }
        if (failures.length) onNotice && onNotice({ tone: "amber", text: "Recursos/placements parciales; STORE_PAGES estático queda etiquetado como fallback: " + failures.join(" · ") });
      } catch (e) {
        if (!alive) return;
        const msg = typeof errorText !== "undefined" ? errorText(e) : (e.message || e.status || "error");
        setStoreState({ loading: false, source: "fallback", store: null, resources: {}, placementTypes: [], error: msg });
        onNotice && onNotice({ tone: "amber", text: "No se pudo hidratar tienda/recursos; usando STORE_PAGES estático como fallback: " + msg });
      }
    }
    hydrate();
    return () => { alive = false; };
  }, []);

  const cells = layout.cols.reduce((s, c) => s + c.rows, 0);
  const totalW = layout.cols.reduce((s, c) => s + c.w, 0) || 1;
  const editCol = (ci, patch) => setLayout((L) => ({ cols: L.cols.map((c, i) => i === ci ? { ...c, ...patch } : c) }));
  const addCol = () => setLayout((L) => L.cols.length >= 4 ? L : ({ cols: [...L.cols, { rows: 1, w: 1, align: "center" }] }));
  const removeCol = (ci) => setLayout((L) => L.cols.length <= 1 ? L : ({ cols: L.cols.filter((_, i) => i !== ci) }));

  function goPage(id) {
    if (id === pageId) return;
    const pg = pages.find((p) => p.id === id) || pages[0];
    setPageId(id); setSel(rec(pg)); setHov(null); setScopeKind(defScope(id)); setDropAt(null);
  }
  function toggleColl(c) {
    setColls((cur) => cur.includes(c) ? cur.filter((x) => x !== c) : (cur.length >= 3 ? cur : [...cur, c]));
  }
  function buildScope() {
    const pageResource = page && page.resource;
    if (pageId === "search") return { label: "Búsqueda: " + query, reach: (pageResource && (pageResource.title || pageResource.handle)) || "disparador", resource: pageResource };
    if (pageId === "home") return scopeKind === "store" ? { label: "Toda la tienda", reach: "todas las páginas" } : { label: "Solo Home", reach: "1 página" };
    if (pageId === "collection") {
      if (scopeKind === "all") return { label: "Todas las colecciones", reach: collectionChoices.length ? `≈ ${collectionChoices.length} colecciones backend` : "colecciones fallback" };
      if (scopeKind === "multi") return { label: colls.length + " colecciones", reach: colls.join(" · ") || "—" };
      return { label: "Solo esta colección", reach: (pageResource && (pageResource.title || pageResource.handle)) || "Fragancias", resource: pageResource };
    }
    if (pageId === "product") {
      if (scopeKind === "brand") return { label: "PDP · marca " + brand, reach: brandChoices.length ? `${brandChoices.length} marcas backend` : "marca fallback" };
      if (scopeKind === "ptag") return { label: "PDP con tag " + tag, reach: tagChoices.length ? `${tagChoices.length} tags backend` : "tags fallback" };
      return { label: "Solo este producto", reach: (pageResource && (pageResource.title || pageResource.handle)) || "1 PDP", resource: pageResource };
    }
    return { label: "Página: " + ((pageResource && (pageResource.title || pageResource.handle)) || "Landing"), reach: "1 página", resource: pageResource };
  }
  const scope = buildScope();

  const mockSp = {
    sel: mode === "new" ? null : sel,
    hov,
    onSel: (id) => { setSel(id); setMode("existing"); setDropAt(null); },
    onHov: setHov,
  };
  const ins = {
    active: mode === "new", dragging, overZone, dropAt, layout,
    onOver: setOverZone,
    onDrop: (id) => { setDropAt(id); setDragging(false); setOverZone(null); },
    onClear: () => setDropAt(null),
  };
  const canContinue = mode === "new" ? !!dropAt : !!sel;
  const selObj = page.placements.find((p) => p.id === sel) || page.placements[0];

  function buildPlacement() {
    const backend = selObj && selObj.backend ? { ...selObj.backend, target_resource: (scope && scope.resource) || selObj.backend.target_resource } : null;
    return mode === "new"
      ? { id: "custom", name: "Nuevo espacio", size: "responsivo", page: page.label, scope, layout: { ...layout, mode: "new", dropAt }, dropLabel: ZONE_LABELS[dropAt], backend: backend || { store_id: storeState.store && storeState.store.id, target_type: pageId === "home" ? "home" : pageId, target_resource: scope && scope.resource } }
      : { ...selObj, page: page.label, scope, layout: { cols: [{ rows: 1, w: 1, align: "center" }], mode: "existing" }, backend };
  }
  // Validate the chosen placement against the backend before advancing. This is a
  // stateless check (no campaign UUID needed) so it works in the local demo. On a
  // 422 we surface an honest amber badge but still advance with the local choice.
  async function handleContinue() {
    if (!canContinue) return;
    const p = buildPlacement();
    if (typeof PlacementApi !== "undefined" && PlacementApi.validate) {
      try {
        await PlacementApi.validate(PlacementApi.payloadFromPrototype(p));
        onNotice && onNotice({ tone: "green", text: "Ubicación validada por el backend" });
      } catch (e) {
        if (e && e.status === 422) onNotice && onNotice({ tone: "amber", text: "El backend marcó la ubicación como inválida; se continúa con la selección local." });
        else onNotice && onNotice({ tone: "amber", text: "No se pudo validar la ubicación en backend: " + (typeof errorText !== "undefined" ? errorText(e) : (e.message || e.status || "error")) });
      }
    }
    onNext(p);
  }
  const Mock = pageId === "home" ? HomeMock : pageId === "collection" ? CollectionMock : pageId === "product" ? ProductMock : SearchMock;

  const radioDot = (on) => (
    <span style={{ width: 16, height: 16, borderRadius: 9999, flexShrink: 0, border: "2px solid " + (on ? "#22D3EE" : "#CBD5E1"), background: on ? "#22D3EE" : "transparent", display: "flex", alignItems: "center", justifyContent: "center" }}>{on ? <Icon name="check" size={10} color="#fff" /> : null}</span>
  );
  const chip = (on) => ({ fontFamily: "Inter", fontSize: 11.5, fontWeight: 600, padding: "6px 12px", borderRadius: 9999, cursor: "pointer", border: "1px solid " + (on ? "#22D3EE" : "#E2E8F0"), background: on ? "rgba(34,211,238,.12)" : "#fff", color: on ? "#0891B2" : "#64748B", display: "inline-flex", alignItems: "center", gap: 5 });
  const fieldWrap = { display: "flex", alignItems: "center", gap: 7, flex: 1, border: "1px solid #E2E8F0", borderRadius: 9, padding: "8px 11px", background: "#fff" };
  const inputStyle = { flex: 1, border: "none", outline: "none", background: "transparent", fontFamily: "Inter", fontSize: 12.5, color: "#002B57" };
  const stepBtnStyle = { width: 20, height: 20, borderRadius: 5, border: "none", background: "rgba(248,250,252,0.9)", cursor: "pointer", color: "#0891B2", display: "flex", alignItems: "center", justifyContent: "center" };
  const alignBtnStyle = (on) => ({ width: 24, height: 24, borderRadius: 6, border: "1px solid " + (on ? "#22D3EE" : "#E2E8F0"), background: on ? "rgba(34,211,238,.14)" : "#fff", color: on ? "#0891B2" : "#94A3B8", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" });
  const Step = ({ label, val, onMinus, onPlus, icon }) => (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }} title={label}>
      <Icon name={icon} size={12} color="#94A3B8" />
      <div style={{ display: "flex", alignItems: "center", gap: 5, border: "1px solid #E2E8F0", borderRadius: 8, padding: "3px 5px", background: "#fff" }}>
        <button onClick={onMinus} style={stepBtnStyle}><Icon name="minus" size={12} /></button>
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 13, color: "#002B57", minWidth: 12, textAlign: "center" }}>{val}</span>
        <button onClick={onPlus} style={stepBtnStyle}><Icon name="plus" size={12} /></button>
      </div>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Kicker>Paso 1 de 6 · Ubicación</Kicker>
          <h2 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 26, color: "#002B57", margin: 0 }}>¿Dónde irá el banner?</h2>
        </div>
        <Badge tone={storeState.source === "backend" ? "cyan" : "amber"} icon="store">{storeState.source === "backend" ? "Backend" : "Fallback STORE_PAGES"} · {storeName} · {storeDomain}</Badge>
      </div>

      {/* page navigation tabs */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontFamily: "Inter", fontSize: 12, color: "#94A3B8", display: "inline-flex", alignItems: "center", gap: 6 }}><Icon name="compass" size={14} /> Navega la tienda:</span>
        <div style={{ display: "flex", gap: 3, background: "rgba(255,255,255,0.7)", border: "1px solid rgba(255,255,255,0.6)", borderRadius: 11, padding: 3, boxShadow: "0 6px 18px rgba(15,23,42,.05)" }}>
          {pages.map((p) => {
            const on = pageId === p.id;
            const ic = PL_PAGE_ICON[p.id] || "file-text";
            return (
              <button key={p.id} onClick={() => goPage(p.id)} style={{
                display: "inline-flex", alignItems: "center", gap: 7, padding: "7px 13px", borderRadius: 9, cursor: "pointer",
                border: "1px solid " + (on ? "rgba(34,211,238,.5)" : "transparent"), background: on ? "rgba(34,211,238,.14)" : "transparent",
                color: on ? "#0891B2" : "#68737D", fontFamily: "Inter", fontSize: 12.5, fontWeight: 600,
              }}>
                <Icon name={ic} size={14} /> {p.label}
                <span style={{ fontFamily: "Inter", fontSize: 10, fontWeight: 600, color: on ? "#0891B2" : "#CBD5E1", background: on ? "rgba(34,211,238,.18)" : "#F1F5F9", borderRadius: 9999, padding: "1px 6px" }}>{p.placements.length}</span>
                {p.source === "fallback" ? <span style={{ fontFamily: "Inter", fontSize: 9.5, color: "#B45309" }}>fallback</span> : null}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.55fr) minmax(290px,1fr)", gap: 16, alignItems: "start" }}>
        {/* template preview */}
        <GlassCard style={{ padding: 16, display: "flex", justifyContent: "center", background: "rgba(255,255,255,0.55)", backgroundImage: "radial-gradient(rgba(148,163,184,.18) 1px, transparent 1px)", backgroundSize: "18px 18px" }}>
          <div style={{ width: "100%", maxWidth: 620 }}>
            <ChromeWindow width="100%" height={560} url={page.url} tabs={[{ title: storeName + " · " + page.label }]}>
              <Mock sp={mockSp} ins={ins} onNav={goPage} store={storeState.store} resources={storeState.resources} page={page} />
            </ChromeWindow>
          </div>
        </GlassCard>

        {/* right column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <GlassCard style={{ padding: 18, display: "flex", flexDirection: "column", gap: 11 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Icon name="layout-template" size={16} color="#0891B2" />
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>Espacios en {page.label}</span>
            </div>
            <p style={{ fontFamily: "Inter", fontSize: 12, color: "#68737D", margin: 0, lineHeight: 1.5 }}>Elige un espacio existente del tema, o incrusta uno nuevo y arrástralo a la página.</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 9, marginTop: 2 }}>
              {page.placements.map((p) => {
                const on = mode === "existing" && sel === p.id;
                return (
                  <button key={p.id} onClick={() => { setSel(p.id); setMode("existing"); setDropAt(null); }} onMouseEnter={() => setHov(p.id)} onMouseLeave={() => setHov(null)} style={{
                    display: "flex", alignItems: "center", gap: 12, padding: "11px 13px", borderRadius: 12, cursor: "pointer", textAlign: "left",
                    border: "1.5px solid " + (on ? "#22D3EE" : "#EEF2F6"), background: on ? "rgba(34,211,238,.08)" : "rgba(248,250,252,0.7)",
                  }}>
                    <div style={{ width: 34, height: 34, borderRadius: 9, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: on ? "rgba(34,211,238,.16)" : "#fff", color: on ? "#0891B2" : "#94A3B8", border: on ? "none" : "1px solid #EEF2F6" }}>
                      <Icon name={p.icon} size={17} />
                    </div>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                        <span style={{ fontFamily: "Inter", fontSize: 13, fontWeight: 600, color: "#002B57" }}>{p.name}</span>
                        {p.rec ? <Badge tone="cyan">Recomendado</Badge> : null}
                        <Badge tone={p.source === "backend" ? "green" : "amber"}>{p.source === "backend" ? "Backend" : "Fallback STORE_PAGES"}</Badge>
                      </div>
                      <div style={{ fontFamily: "Space Grotesk", fontSize: 10.5, color: "#94A3B8", marginTop: 2 }}>{page.label} · {p.size}px</div>
                    </div>
                    {radioDot(on)}
                  </button>
                );
              })}

              {/* embed a brand-new section */}
              {(() => {
                const on = mode === "new";
                return (
                  <button onClick={() => { setMode("new"); setHov(null); }} style={{
                    display: "flex", alignItems: "center", gap: 12, padding: "11px 13px", borderRadius: 12, cursor: "pointer", textAlign: "left",
                    border: "1.5px dashed " + (on ? "#22D3EE" : "#CBD5E1"), background: on ? "rgba(34,211,238,.08)" : "transparent",
                  }}>
                    <div style={{ width: 34, height: 34, borderRadius: 9, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: on ? "rgba(34,211,238,.16)" : "#fff", color: on ? "#0891B2" : "#94A3B8", border: on ? "none" : "1px solid #EEF2F6" }}>
                      <Icon name="square-plus" size={17} />
                    </div>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                        <span style={{ fontFamily: "Inter", fontSize: 13, fontWeight: 600, color: "#002B57" }}>Incrustar nuevo espacio</span>
                        <Badge tone="purple">Sección nueva</Badge>
                      </div>
                      <div style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8", marginTop: 2 }}>Arma el layout y arrástralo a la página</div>
                    </div>
                    {radioDot(on)}
                  </button>
                );
              })()}
            </div>
          </GlassCard>

          <GlassCard style={{ padding: 18, display: "flex", flexDirection: "column", gap: 11 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Icon name="crosshair" size={16} color="#0891B2" />
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>Alcance</span>
              <span style={{ marginLeft: "auto" }}><Badge tone="purple" icon="target">{scope.reach}</Badge></span>
            </div>
            <p style={{ fontFamily: "Inter", fontSize: 12, color: "#68737D", margin: 0, lineHeight: 1.5 }}>Una regla define en qué páginas aparece el banner — no solo en esta.</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {SCOPE_OPTS[pageId].map((o) => {
                const on = scopeKind === o.id;
                return (
                  <div key={o.id}>
                    <button onClick={() => setScopeKind(o.id)} style={{
                      width: "100%", display: "flex", alignItems: "center", gap: 11, padding: "10px 12px", borderRadius: 11, cursor: "pointer", textAlign: "left",
                      border: "1.5px solid " + (on ? "#22D3EE" : "#EEF2F6"), background: on ? "rgba(34,211,238,.08)" : "rgba(248,250,252,0.7)",
                    }}>
                      <Icon name={o.icon} size={15} color={on ? "#0891B2" : "#94A3B8"} />
                      <span style={{ flex: 1, fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#002B57" }}>{o.label}</span>
                      {radioDot(on)}
                    </button>
                    {on && o.param === "brand" ? (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, padding: "9px 2px 2px" }}>
                        {brandChoices.map((b) => <button key={b} onClick={() => setBrand(b)} style={chip(brand === b)}>{b}</button>)}
                        {brandChoices.length ? <Badge tone="green">vendors backend</Badge> : <Badge tone="red" icon="circle-alert">Sin vendors del backend — sincroniza la tienda</Badge>}
                      </div>
                    ) : null}
                    {on && o.param === "tag" ? (
                      <div style={{ display: "flex", padding: "9px 2px 2px" }}>
                        <div style={fieldWrap}>
                          <Icon name="hash" size={13} color="#94A3B8" />
                          <input value={tag} onChange={(e) => setTag(e.target.value)} placeholder="ej. fragancia, premium" style={inputStyle} />
                        </div>
                      </div>
                    ) : null}
                    {on && o.param === "collections" ? (
                      <div style={{ padding: "9px 2px 2px", display: "flex", flexDirection: "column", gap: 7 }}>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                          {collectionChoices.length ? collectionChoices.map((c) => <button key={c} onClick={() => toggleColl(c)} style={chip(colls.includes(c))}>{colls.includes(c) ? <Icon name="check" size={11} /> : null}{c}</button>) : <Badge tone="red" icon="circle-alert">Sin colecciones del backend — sincroniza la tienda</Badge>}
                          {collectionChoices.length ? <Badge tone="green">colecciones backend</Badge> : <Badge tone="amber">colecciones fallback</Badge>}
                        </div>
                        <span style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8" }}>{colls.length}/3 seleccionadas</span>
                      </div>
                    ) : null}
                    {on && o.param === "query" ? (
                      <div style={{ display: "flex", padding: "9px 2px 2px" }}>
                        <div style={fieldWrap}>
                          <Icon name="search" size={13} color="#94A3B8" />
                          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="término que dispara el banner" style={inputStyle} />
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </GlassCard>

          <GlassCard style={{ padding: 14, display: "flex", flexDirection: "column", gap: 9 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Icon name="database" size={15} color="#0891B2" />
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 14, color: "#002B57" }}>Recursos de tienda</span>
              <span style={{ marginLeft: "auto" }}><Badge tone={storeState.source === "backend" ? "green" : "amber"}>{storeState.loading ? "cargando" : storeState.source === "backend" ? "backend" : "fallback STORE_PAGES"}</Badge></span>
            </div>
            {storeState.error ? <div style={{ fontFamily: "Inter", fontSize: 11, color: "#B45309", lineHeight: 1.45 }}>Fallback estático etiquetado: {storeState.error}</div> : null}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {PL_RESOURCE_TYPES.map((type) => <Badge key={type} tone={resourceCounts[type] ? "cyan" : "slate"}>{type}: {resourceCounts[type] || 0}</Badge>)}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {PL_RESOURCE_TYPES.flatMap((type) => (storeState.resources[type] || []).slice(0, 2).map((r) => ({ type, r }))).slice(0, 6).map(({ type, r }) => (
                <div key={type + ":" + (r.id || r.handle || r.title)} style={{ fontFamily: "Inter", fontSize: 11.5, color: "#475569", display: "flex", gap: 6, alignItems: "center" }}>
                  <Badge tone="slate">{type}</Badge><span style={{ color: "#002B57", fontWeight: 600 }}>{r.title || r.handle}</span><span style={{ color: "#94A3B8" }}>/{r.handle || "sin-handle"}</span>
                </div>
              ))}
              {storeState.source !== "backend" ? <div style={{ fontFamily: "Inter", fontSize: 11, color: "#B45309" }}>Los títulos/handles visibles provienen de STORE_PAGES/semillas estáticas solo como fallback.</div> : null}
            </div>
          </GlassCard>

          {mode === "new" ? (
          <GlassCard style={{ padding: 18, display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Icon name="layout-grid" size={16} color="#0891B2" />
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>Arma el espacio</span>
              <span style={{ marginLeft: "auto" }}><Badge tone="cyan">{layout.cols.length} col · {cells} celda{cells > 1 ? "s" : ""}</Badge></span>
            </div>
            <p style={{ fontFamily: "Inter", fontSize: 12, color: "#68737D", margin: 0, lineHeight: 1.5 }}>Define columnas, filas, ancho % y alineación. Luego arrástralo a la página.</p>

            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {layout.cols.map((c, ci) => {
                const pct = Math.round((c.w / totalW) * 100);
                return (
                  <div key={ci} style={{ display: "flex", flexDirection: "column", gap: 8, padding: "9px 10px", borderRadius: 10, background: "rgba(248,250,252,0.8)", border: "1px solid #EEF2F6" }}>
                    <div style={{ display: "flex", alignItems: "center" }}>
                      <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 11, color: "#0891B2" }}>Columna {ci + 1}</span>
                      <button onClick={() => removeCol(ci)} disabled={layout.cols.length <= 1} title="Quitar columna" style={{ marginLeft: "auto", width: 22, height: 22, borderRadius: 6, border: "none", background: "transparent", cursor: layout.cols.length <= 1 ? "default" : "pointer", color: layout.cols.length <= 1 ? "#CBD5E1" : "#94A3B8", display: "flex", alignItems: "center", justifyContent: "center" }}><Icon name="x" size={13} /></button>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                      <Step label="Filas" icon="rows-3" val={c.rows} onMinus={() => editCol(ci, { rows: Math.max(1, c.rows - 1) })} onPlus={() => editCol(ci, { rows: Math.min(4, c.rows + 1) })} />
                      <Step label="Ancho %" icon="move-horizontal" val={pct + "%"} onMinus={() => editCol(ci, { w: Math.max(1, c.w - 1) })} onPlus={() => editCol(ci, { w: Math.min(8, c.w + 1) })} />
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }} title="Alineación">
                        <Icon name="align-center" size={12} color="#94A3B8" />
                        <div style={{ display: "flex", gap: 4 }}>
                          {[["align-left", "left"], ["align-center", "center"], ["align-right", "right"]].map(([ic, a]) => (
                            <button key={a} onClick={() => editCol(ci, { align: a })} style={alignBtnStyle(c.align === a)}><Icon name={ic} size={12} /></button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
              {layout.cols.length < 4 ? (
                <button onClick={addCol} style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "8px 0", borderRadius: 9, cursor: "pointer", border: "1.5px dashed #CBD5E1", background: "transparent", color: "#0891B2", fontFamily: "Inter", fontSize: 12, fontWeight: 600 }}><Icon name="plus" size={13} /> Añadir columna</button>
              ) : null}
            </div>
            <LayoutDiagram layout={layout} h={70} />

            {/* draggable handle — drop onto the store preview */}
            <div
              draggable
              onDragStart={(e) => { try { e.dataTransfer.setData("text/plain", "ns"); e.dataTransfer.effectAllowed = "copy"; } catch (_) {} setDragging(true); }}
              onDragEnd={() => { setDragging(false); setOverZone(null); }}
              style={{ display: "flex", alignItems: "center", gap: 11, padding: "11px 12px", borderRadius: 11, cursor: dropAt ? "default" : "grab", border: "1.5px dashed " + (dropAt ? "#10B981" : "#22D3EE"), background: dropAt ? "rgba(16,185,129,.07)" : "rgba(34,211,238,.07)", userSelect: "none" }}>
              <Icon name="grip-vertical" size={16} color={dropAt ? "#10B981" : "#0891B2"} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#002B57" }}>{dropAt ? "Espacio colocado" : "Arrastra a la página"}</div>
                <div style={{ fontFamily: "Inter", fontSize: 11, color: "#68737D", marginTop: 2 }}>{dropAt ? ZONE_LABELS[dropAt] : "Suéltalo en la visualización ←"}</div>
              </div>
              <Icon name={dropAt ? "circle-check-big" : "move"} size={18} color={dropAt ? "#10B981" : "#0891B2"} />
            </div>
          </GlassCard>
          ) : null}

          <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, fontFamily: "Inter", fontSize: 12.5, color: "#475569" }}>
              <Icon name="map-pin" size={15} color="#0891B2" />
              {mode === "new"
                ? <span>Nuevo espacio en <b style={{ color: "#002B57" }}>{page.label}</b> · {dropAt ? ZONE_LABELS[dropAt] : <span style={{ color: "#94A3B8" }}>arrástralo a la página</span>}</span>
                : <span>Incrustar en <b style={{ color: "#002B57" }}>{page.label} · {selObj.name}</b> · {selObj.size}px</span>}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "Inter", fontSize: 12.5, color: "#475569" }}>
              <Icon name="crosshair" size={15} color="#7C3AED" />
              Alcance: <b style={{ color: "#002B57" }}>{scope.label}</b> · {mode === "new" && cells > 1 ? `${cells} celdas` : "1 banner"}
            </div>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8, fontFamily: "Inter", fontSize: 12.5, color: "#475569", lineHeight: 1.45 }}>
              <Icon name="code-2" size={15} color="#0891B2" style={{ marginTop: 1, flexShrink: 0 }} />
              <span>Liquid: <b style={{ color: "#002B57" }}>{mode === "new" ? "crea una sección nueva" : `actualiza la sección «${selObj.name}»`}</b>{mode === "new" ? " e inyecta el banner" : ""}</span>
            </div>
            <Button variant="shine" icon="arrow-right" disabled={!canContinue}
              onClick={handleContinue}
              title={canContinue ? undefined : (mode === "new" ? "Arrastra el espacio a la página para continuar" : "Selecciona un espacio")}
              style={{ justifyContent: "center", marginTop: 2 }}>{mode === "new" && !dropAt ? "Arrastra a la página" : "Continuar al brief"}</Button>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { PlacementStage });
