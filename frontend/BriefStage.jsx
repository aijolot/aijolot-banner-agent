/* global React, Icon, GlassCard, Button, Badge, Avatar, Kicker, Spinner, CAMPAIGN, CATALOG, SEGMENTS */
// Aijolot Banner Agent — Stage 1: the commercial brief (chat) + synced catalog.
const { useState: useStateB, useRef: useRefB, useEffect: useEffectB } = React;

function BotBubble({ children }) {
  return (
    <div className="fade-up" style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
      <div style={{ width: 34, height: 34, borderRadius: 9999, background: "#22D3EE", color: "#06121f", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, boxShadow: "0 6px 16px rgba(34,211,238,.3)" }}>
        <Icon name="bot" size={18} />
      </div>
      <div style={{ maxWidth: "82%", fontFamily: "Inter", fontSize: 14, lineHeight: 1.5, padding: "12px 15px", borderRadius: 16, borderBottomLeftRadius: 5, background: "#fff", color: "#002B57", border: "1px solid #E2E8F0", boxShadow: "0 8px 20px rgba(15,23,42,.05)" }}>
        {children}
      </div>
    </div>
  );
}
function UserBubble({ children }) {
  return (
    <div className="fade-up" style={{ display: "flex", justifyContent: "flex-end" }}>
      <div style={{ maxWidth: "82%", fontFamily: "Inter", fontSize: 14, lineHeight: 1.5, padding: "12px 15px", borderRadius: 16, borderBottomRightRadius: 5, background: "#22D3EE", color: "#06121f", boxShadow: "0 8px 20px rgba(34,211,238,.18)" }}>
        {children}
      </div>
    </div>
  );
}
function Typing() {
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
      <div style={{ width: 34, height: 34, borderRadius: 9999, background: "#22D3EE", color: "#06121f", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><Icon name="bot" size={18} /></div>
      <div style={{ background: "#fff", border: "1px solid #E2E8F0", borderRadius: 16, borderBottomLeftRadius: 5, padding: "14px 16px", display: "flex", gap: 5 }}>
        {[0, 1, 2].map((i) => <span key={i} style={{ width: 7, height: 7, borderRadius: 9999, background: "#94A3B8", animation: `chatBounce 1.2s ${i * 0.18}s infinite ease-in-out` }} />)}
      </div>
    </div>
  );
}

const SUGGEST = [
  "Banner 10% OFF perfumes Hugo Boss para la home",
  "Personalizar por género del cliente",
  "Que destaque el frasco y se vea premium",
];

function BriefStage({ onGenerate, placement }) {
  const [msgs, setMsgs] = useStateB([{ role: "bot", text: "Hola Mara. Cuéntame qué campaña quieres lanzar y yo construyo el banner — consulto tu catálogo de Shopify, respeto la marca y entrego código nativo listo para publicar." }]);
  const [val, setVal] = useStateB("");
  const [typing, setTyping] = useStateB(false);
  const [sent, setSent] = useStateB(false);
  const scroller = useRefB(null);

  useEffectB(() => { if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight; }, [msgs, typing]);

  function send(text) {
    const t = (text != null ? text : val).trim();
    if (!t || sent) return;
    setSent(true);
    setMsgs((m) => [...m, { role: "user", text: t }]);
    setVal("");
    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      setMsgs((m) => [...m, { role: "bot", text: "Entendido. Encontré 5 SKUs de Hugo Boss con stock y apliqué el 10% de descuento. Voy a diseñar el banner ahora.", generating: true }]);
      setTimeout(() => onGenerate(), 1400);
    }, 1600);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <Kicker>Paso 2 de 6 · Brief comercial</Kicker>
        {placement && <Badge tone="slate" icon="map-pin">Ubicación: {placement.page} · {placement.name}</Badge>}
        {placement && placement.scope && <Badge tone="purple" icon="crosshair">Alcance: {placement.scope.label}</Badge>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.35fr) minmax(0,1fr)", gap: 16, alignItems: "stretch" }}>
        {/* Chat */}
        <GlassCard style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 460 }}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid #EEF2F6", display: "flex", alignItems: "center", gap: 11 }}>
            <div style={{ width: 36, height: 36, borderRadius: 11, background: "linear-gradient(135deg,#22D3EE,#0891B2)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff" }}><Icon name="wand-sparkles" size={18} /></div>
            <div>
              <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>Brief con el agente</div>
              <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>Describe la campaña en lenguaje natural</div>
            </div>
          </div>
          <div ref={scroller} style={{ flex: 1, overflowY: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 14, maxHeight: 420 }}>
            {msgs.map((m, i) => m.role === "bot"
              ? <BotBubble key={i}>{m.text}{m.generating && <span style={{ display: "inline-flex", marginLeft: 8, verticalAlign: "middle" }}><Spinner size={13} /></span>}</BotBubble>
              : <UserBubble key={i}>{m.text}</UserBubble>)}
            {typing && <Typing />}
          </div>
          {!sent && (
            <div style={{ padding: "0 20px 12px", display: "flex", flexWrap: "wrap", gap: 8 }}>
              {SUGGEST.map((s) => (
                <button key={s} onClick={() => setVal((v) => (v ? v + " " + s : s))} style={{ fontFamily: "Inter", fontSize: 12, padding: "7px 13px", borderRadius: 9999, border: "1px solid #E2E8F0", background: "#fff", color: "#0891B2", cursor: "pointer" }}>
                  + {s}
                </button>
              ))}
              <button onClick={() => setVal(CAMPAIGN.brief)} style={{ fontFamily: "Inter", fontSize: 12, padding: "7px 13px", borderRadius: 9999, border: "1px solid rgba(34,211,238,.4)", background: "rgba(34,211,238,.1)", color: "#0891B2", cursor: "pointer", fontWeight: 600 }}>
                Usar brief de ejemplo
              </button>
            </div>
          )}
          <div style={{ padding: "12px 16px 16px", borderTop: "1px solid #EEF2F6" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "flex-end", background: "rgba(241,245,249,0.6)", border: "1px solid #E2E8F0", borderRadius: 14, padding: 8 }}>
              <textarea value={val} onChange={(e) => setVal(e.target.value)} disabled={sent} rows={2}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                placeholder="Ej: Banner de 10% OFF en perfumes Hugo Boss para la home, del 2 al 9 de junio…"
                style={{ flex: 1, border: "none", outline: "none", background: "transparent", resize: "none", fontFamily: "Inter", fontSize: 13.5, color: "#002B57", lineHeight: 1.45, padding: "6px 8px" }} />
              <Button variant="default" icon="send" onClick={() => send()} disabled={sent || !val.trim()} style={{ padding: "10px 14px" }} />
            </div>
            <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8", marginTop: 9, textAlign: "center" }}>El agente consulta el catálogo, valida stock y aplica precios automáticamente.</div>
          </div>
        </GlassCard>

        {/* Synced catalog */}
        <GlassCard style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="database" size={16} color="#0891B2" />
            <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>Catálogo sincronizado</span>
            <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "Inter", fontSize: 11, color: "#16A34A", fontWeight: 600 }}>
              <span style={{ width: 6, height: 6, borderRadius: 9999, background: "#10B981" }} /> en vivo
            </span>
          </div>
          <p style={{ fontFamily: "Inter", fontSize: 12.5, color: "#68737D", margin: 0, lineHeight: 1.5 }}>El agente tiene embebida tu base de productos y promociones. No necesitas pasar SKUs a mano.</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {CATALOG.map((c) => (
              <div key={c.sku} style={{ display: "flex", alignItems: "center", gap: 11, padding: "10px 12px", borderRadius: 11, background: "rgba(248,250,252,0.8)", border: "1px solid #EEF2F6" }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: "linear-gradient(160deg," + SEGMENTS[c.seg].palette.bgB + "," + SEGMENTS[c.seg].palette.bgA + ")", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Icon name="spray-can" size={15} color={SEGMENTS[c.seg].palette.cap} />
                </div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#002B57", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.name}</div>
                  <div style={{ fontFamily: "Space Grotesk", fontSize: 10.5, color: "#94A3B8" }}>{c.sku} · stock {c.stock}</div>
                </div>
                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  <div style={{ fontFamily: "Space Grotesk", fontSize: 13, fontWeight: 600, color: "#0891B2", fontVariantNumeric: "tabular-nums" }}>${c.sale.toFixed(2)}</div>
                  <div style={{ fontFamily: "Space Grotesk", fontSize: 10, color: "#CBD5E1", textDecoration: "line-through" }}>${c.price.toFixed(2)}</div>
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: "auto", display: "flex", alignItems: "center", gap: 7, padding: "10px 12px", borderRadius: 10, background: "rgba(34,211,238,0.08)", border: "1px solid rgba(34,211,238,0.2)" }}>
            <Icon name="check-circle-2" size={14} color="#0891B2" />
            <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#0891B2", fontWeight: 500 }}>5 productos con stock · 10% aplicado · promoción validada</span>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}

Object.assign(window, { BriefStage });
