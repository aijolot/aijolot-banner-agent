/* global React, Icon */
// Aijolot Banner Agent — store-template mock pages for the placement stage.

const Block = ({ h, children, style }) => (
  <div style={{ background: "#F1F5F9", borderRadius: 6, height: h, display: "flex", alignItems: "center", justifyContent: "center", ...style }}>{children}</div>
);

function Slot({ id, sel, hov, onSel, onHov, children, style, label }) {
  const active = sel === id, hovd = hov === id;
  return (
    <div onClick={(e) => { e.stopPropagation(); onSel(id); }} onMouseEnter={() => onHov(id)} onMouseLeave={() => onHov(null)}
      style={{ position: "relative", cursor: "pointer", borderRadius: 8, ...style }}>
      {children}
      <div style={{
        position: "absolute", inset: 0, borderRadius: 8, transition: "all .12s",
        border: active ? "2px solid #22D3EE" : hovd ? "2px dashed rgba(34,211,238,.65)" : "2px dashed transparent",
        background: active ? "rgba(34,211,238,.14)" : hovd ? "rgba(34,211,238,.06)" : "transparent",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        {(active || hovd) && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "Inter", fontSize: 11, fontWeight: 600, color: "#0891B2", background: "rgba(255,255,255,.92)", padding: "4px 10px", borderRadius: 9999, boxShadow: "0 4px 12px rgba(15,23,42,.12)" }}>
            <Icon name={active ? "check" : "plus"} size={12} /> {active ? "Banner aquí" : label}
          </span>
        )}
      </div>
    </div>
  );
}

// New-section drop target — only renders while embedding a new space.
function InsertZone({ id, ins }) {
  if (!ins || !ins.active) return null;
  if (ins.dropAt === id) {
    const cols = (ins.layout && ins.layout.cols) || [{ rows: 1, w: 1 }];
    const cells = cols.reduce((s, c) => s + c.rows, 0);
    return (
      <div style={{ padding: "0 16px 14px" }}>
        <div style={{ position: "relative", borderRadius: 10, border: "2px solid #22D3EE", background: "rgba(34,211,238,.08)", padding: "10px 10px 12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 8 }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "Inter", fontSize: 10.5, fontWeight: 700, color: "#0891B2", background: "#fff", padding: "3px 9px", borderRadius: 9999, boxShadow: "0 3px 10px rgba(15,23,42,.1)" }}><Icon name="sparkles" size={11} /> Nuevo espacio · {cols.length} col</span>
            <button onClick={(e) => { e.stopPropagation(); ins.onClear(); }} title="Quitar" style={{ marginLeft: "auto", width: 22, height: 22, borderRadius: 6, border: "none", background: "#fff", cursor: "pointer", color: "#94A3B8", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 3px 10px rgba(15,23,42,.08)" }}><Icon name="x" size={13} /></button>
          </div>
          <LayoutDiagram layout={ins.layout} h={Math.min(120, 32 + cells * 22)} />
        </div>
      </div>
    );
  }
  const over = ins.overZone === id;
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); if (ins.overZone !== id) ins.onOver(id); }}
      onDragLeave={() => { if (ins.overZone === id) ins.onOver(null); }}
      onDrop={(e) => { e.preventDefault(); ins.onDrop(id); }}
      style={{ padding: "0 16px", marginBottom: 12 }}>
      <div style={{ height: over ? 42 : 24, borderRadius: 8, border: "2px dashed " + (over ? "#22D3EE" : "#CBD5E1"), background: over ? "rgba(34,211,238,.1)" : "rgba(248,250,252,.7)", display: "flex", alignItems: "center", justifyContent: "center", gap: 6, transition: "all .12s", color: over ? "#0891B2" : "#94A3B8", fontFamily: "Inter", fontSize: 11, fontWeight: 600 }}>
        <Icon name="plus" size={13} /> {over ? "Soltar aquí" : "Soltar nuevo espacio"}
      </div>
    </div>
  );
}

function StoreHeader({ pageId, onNav, store, resources }) {
  const storeName = (store && (store.name || store.shop_domain)) || "Maison";
  const navCollection = ((resources && resources.collection) || [])[0];
  const NAV = [["Inicio", "home"], [(navCollection && (navCollection.title || navCollection.handle)) || "Fragancias", "collection"], ["Hombre", "collection"], ["Mujer", "collection"]];
  return (
    <div style={{ height: 52, display: "flex", alignItems: "center", gap: 16, padding: "0 22px", borderBottom: "1px solid #EEF2F6", flexShrink: 0 }}>
      <span onClick={() => onNav("home")} style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 16, color: "#0F172A", letterSpacing: ".02em", cursor: "pointer" }}>{String(storeName).toUpperCase()}</span>
      <div style={{ display: "flex", gap: 16, marginLeft: 8 }}>
        {NAV.map(([n, pg], i) => {
          const on = (pg === "collection" && pageId === "collection") || (pg === "home" && pageId === "home");
          return <span key={i} onClick={() => onNav(pg)} style={{ fontSize: 11.5, color: on ? "#0F172A" : "#64748B", fontWeight: on ? 600 : 400, cursor: "pointer", borderBottom: on ? "2px solid #0F172A" : "2px solid transparent", paddingBottom: 2 }}>{n}</span>;
        })}
      </div>
      <div style={{ flex: 1 }} />
      <Icon name="search" size={15} color="#94A3B8" />
      <Icon name="shopping-bag" size={15} color="#94A3B8" />
    </div>
  );
}

const Announce = (sp) => (
  <Slot id="announce" label="Colocar aquí" {...sp}>
    <div style={{ height: 30, background: "#0F172A", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <span style={{ fontSize: 10.5, color: "#CBD5E1", letterSpacing: ".04em" }}>Envío gratis en pedidos +$50 · Devoluciones 30 días</span>
    </div>
  </Slot>
);
const Footer = (sp) => (
  <div style={{ padding: "0 16px 18px" }}>
    <Slot id="footer" label="Colocar CTA" {...sp}>
      <div style={{ height: 70, borderRadius: 8, background: "#F8FAFC", border: "1px solid #EEF2F6", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontSize: 12, color: "#64748B" }}>Suscríbete y recibe 10% en tu primera compra</span>
      </div>
    </Slot>
  </div>
);

function HomeMock({ sp, onNav, ins, store, resources }) {
  const collection = ((resources && resources.collection) || [])[0];
  return (
    <div style={{ fontFamily: "Inter", background: "#fff" }}>
      {Announce(sp)}
      <StoreHeader pageId="home" onNav={onNav} store={store} resources={resources} />
      <InsertZone id="top" ins={ins} />
      <div style={{ padding: 16 }}>
        <Slot id="hero" label="Colocar hero" {...sp}>
          <div style={{ height: 150, borderRadius: 8, background: "linear-gradient(120deg,#1E293B,#334155)", display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 26px", gap: 9 }}>
            <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 22, color: "#fff" }}>Nueva colección</span>
            <span style={{ fontSize: 12, color: "rgba(255,255,255,.7)", maxWidth: 230 }}>Descubre {(collection && (collection.title || collection.handle)) || "las fragancias"} de la temporada.</span>
            <span style={{ marginTop: 4, alignSelf: "flex-start", fontSize: 11, fontWeight: 600, color: "#0F172A", background: "#fff", padding: "7px 14px", borderRadius: 9999 }}>Comprar</span>
          </div>
        </Slot>
      </div>
      <div style={{ padding: "0 16px 16px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, height: 78 }}>
          <Slot id="promo_l" label="Promo izq." {...sp}>
            <Block h="100%"><span style={{ fontSize: 11, color: "#94A3B8" }}>Promo izquierda</span></Block>
          </Slot>
          <Slot id="promo_r" label="Promo der." {...sp}>
            <Block h="100%"><span style={{ fontSize: 11, color: "#94A3B8" }}>Promo derecha</span></Block>
          </Slot>
        </div>
      </div>
      <InsertZone id="mid" ins={ins} />
      <div style={{ padding: "0 16px 18px" }}>
        <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13, color: "#0F172A", marginBottom: 10 }}>Más vendidos</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10 }}>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} onClick={() => onNav("product")} style={{ display: "flex", flexDirection: "column", gap: 6, cursor: "pointer" }}>
              <Block h={86} />
              <div style={{ height: 7, width: "70%", background: "#E2E8F0", borderRadius: 4 }} />
              <div style={{ height: 7, width: "40%", background: "#EEF2F6", borderRadius: 4 }} />
            </div>
          ))}
        </div>
      </div>
      <InsertZone id="bottom" ins={ins} />
      {Footer(sp)}
    </div>
  );
}

function CollectionMock({ sp, onNav, ins, store, resources }) {
  const collection = ((resources && resources.collection) || [])[0];
  const products = ((resources && resources.product) || []);
  return (
    <div style={{ fontFamily: "Inter", background: "#fff" }}>
      {Announce(sp)}
      <StoreHeader pageId="collection" onNav={onNav} store={store} resources={resources} />
      <InsertZone id="top" ins={ins} />
      <div style={{ padding: "12px 16px 8px", fontSize: 10.5, color: "#94A3B8" }}>Inicio › {(collection && (collection.title || collection.handle)) || "Fragancias"}</div>
      <div style={{ padding: "0 16px 14px" }}>
        <Slot id="coll_top" label="Colocar cabecera" {...sp}>
          <div style={{ height: 96, borderRadius: 8, background: "linear-gradient(120deg,#0F172A,#475569)", display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 24px", gap: 6 }}>
            <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 19, color: "#fff" }}>{(collection && (collection.title || collection.handle)) || "Fragancias"}</span>
            <span style={{ fontSize: 11, color: "rgba(255,255,255,.7)" }}>{products.length || 42} productos</span>
          </div>
        </Slot>
      </div>
      <InsertZone id="mid" ins={ins} />
      <div style={{ padding: "0 16px 18px", display: "grid", gridTemplateColumns: "92px 1fr", gap: 14 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 11, color: "#0F172A" }}>Filtros</div>
          {["Marca", "Precio", "Familia", "Tamaño"].map((f) => (
            <div key={f} style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              <div style={{ height: 6, width: "70%", background: "#E2E8F0", borderRadius: 4 }} />
              <div style={{ height: 6, width: "50%", background: "#EEF2F6", borderRadius: 4 }} />
            </div>
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10 }}>
          {[0, 1].map((i) => (
            <div key={i} onClick={() => onNav("product")} style={{ display: "flex", flexDirection: "column", gap: 6, cursor: "pointer" }}>
              <Block h={84} /><div style={{ height: 6, width: "70%", background: "#E2E8F0", borderRadius: 4 }} /><div style={{ height: 6, width: "40%", background: "#EEF2F6", borderRadius: 4 }} />
            </div>
          ))}
          <Slot id="coll_inline" label="Colocar bloque" {...sp} style={{ gridRow: "span 1" }}>
            <Block h={108} style={{ height: "100%", minHeight: 108 }}><span style={{ fontSize: 10.5, color: "#94A3B8" }}>Bloque promo</span></Block>
          </Slot>
          {[2, 3, 4].map((i) => (
            <div key={i} onClick={() => onNav("product")} style={{ display: "flex", flexDirection: "column", gap: 6, cursor: "pointer" }}>
              <Block h={84} /><div style={{ height: 6, width: "70%", background: "#E2E8F0", borderRadius: 4 }} /><div style={{ height: 6, width: "40%", background: "#EEF2F6", borderRadius: 4 }} />
            </div>
          ))}
        </div>
      </div>
      <InsertZone id="bottom" ins={ins} />
      {Footer(sp)}
    </div>
  );
}

function ProductMock({ sp, onNav, ins, store, resources }) {
  const product = ((resources && resources.product) || [])[0];
  const productTitle = (product && (product.title || product.handle)) || "Boss Bottled EDP";
  return (
    <div style={{ fontFamily: "Inter", background: "#fff" }}>
      {Announce(sp)}
      <StoreHeader pageId="product" onNav={onNav} store={store} resources={resources} />
      <InsertZone id="top" ins={ins} />
      <div style={{ padding: "12px 16px 8px", fontSize: 10.5, color: "#94A3B8" }}>Inicio › Producto › {productTitle}</div>
      <div style={{ padding: "0 16px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Block h={196}><Icon name="image" size={26} color="#CBD5E1" /></Block>
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 17, color: "#0F172A" }}>{productTitle}</span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 18, color: "#0F172A" }}>$124.20</span>
            <span style={{ fontSize: 11, color: "#CBD5E1", textDecoration: "line-through" }}>$138.00</span>
          </div>
          <Slot id="pdp_strip" label="Colocar oferta" {...sp}>
            <div style={{ height: 44, borderRadius: 8, background: "linear-gradient(120deg,#1E293B,#334155)", display: "flex", alignItems: "center", padding: "0 14px" }}>
              <span style={{ fontSize: 11.5, color: "#fff", fontWeight: 600 }}>10% OFF · termina pronto</span>
            </div>
          </Slot>
          <div style={{ height: 36, borderRadius: 8, background: "#0F172A", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 12, fontWeight: 600 }}>Añadir al carrito</div>
          {[0, 1, 2].map((i) => <div key={i} style={{ height: 6, width: `${80 - i * 16}%`, background: "#EEF2F6", borderRadius: 4 }} />)}
        </div>
      </div>
      <InsertZone id="mid" ins={ins} />
      <div style={{ padding: "0 16px 16px" }}>
        <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 12.5, color: "#0F172A", marginBottom: 9 }}>También te puede gustar</div>
        <Slot id="pdp_cross" label="Colocar cross-sell" {...sp}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, padding: 4 }}>
            {[0, 1, 2, 3].map((i) => <div key={i} style={{ display: "flex", flexDirection: "column", gap: 5 }}><Block h={64} /><div style={{ height: 6, width: "70%", background: "#E2E8F0", borderRadius: 4 }} /></div>)}
          </div>
        </Slot>
      </div>
      <InsertZone id="bottom" ins={ins} />
      {Footer(sp)}
    </div>
  );
}

function SearchMock({ sp, onNav, ins, store, resources }) {
  const search = ((resources && resources.search) || [])[0];
  const searchLabel = (search && (search.title || search.handle)) || "hugo boss";
  const products = ((resources && resources.product) || []);
  return (
    <div style={{ fontFamily: "Inter", background: "#fff" }}>
      {Announce(sp)}
      <StoreHeader pageId="search" onNav={onNav} store={store} resources={resources} />
      <InsertZone id="top" ins={ins} />
      <div style={{ padding: "14px 16px 6px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, height: 36, border: "1px solid #E2E8F0", borderRadius: 9999, padding: "0 14px", background: "#F8FAFC" }}>
          <Icon name="search" size={14} color="#94A3B8" />
          <span style={{ fontSize: 12.5, color: "#0F172A", fontWeight: 500 }}>{searchLabel}</span>
          <span style={{ marginLeft: "auto", fontSize: 10.5, color: "#94A3B8" }}>{products.length || 24} resultados</span>
        </div>
      </div>
      <div style={{ padding: "8px 16px 14px" }}>
        <Slot id="search_top" label="Colocar banner" {...sp}>
          <div style={{ height: 72, borderRadius: 8, background: "linear-gradient(120deg,#1E293B,#334155)", display: "flex", alignItems: "center", padding: "0 22px" }}>
            <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 15, color: "#fff" }}>Resultados para “{searchLabel}”</span>
          </div>
        </Slot>
      </div>
      <InsertZone id="mid" ins={ins} />
      <div style={{ padding: "0 16px 18px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10 }}>
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <div key={i} onClick={() => onNav("product")} style={{ display: "flex", flexDirection: "column", gap: 6, cursor: "pointer" }}>
              <Block h={72} /><div style={{ height: 6, width: "70%", background: "#E2E8F0", borderRadius: 4 }} /><div style={{ height: 6, width: "40%", background: "#EEF2F6", borderRadius: 4 }} />
            </div>
          ))}
        </div>
      </div>
      <InsertZone id="bottom" ins={ins} />
      {Footer(sp)}
    </div>
  );
}

Object.assign(window, { Block, Slot, InsertZone, StoreHeader, HomeMock, CollectionMock, ProductMock, SearchMock });
