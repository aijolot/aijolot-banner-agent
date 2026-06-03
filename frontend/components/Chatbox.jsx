/* global React, Icon, GlassCard, Button, Spinner, AijolotApi */
// Aijolot Banner Agent — intake Chatbox (GH-27).
// Conversational capture of the campaign idea → ADK node 2 intake_campaign_idea.
// Streams the agent reply over SSE from POST /api/v1/campaigns/intake and surfaces the
// structured Campaign to the parent via onCampaign(). Falls back to a local
// rule-based intake when the bridge is unreachable.
const { useState: useStateCB, useRef: useRefCB, useEffect: useEffectCB } = React;

const SUGGEST = [
  "Banner de Black Friday, 50% off audífonos, a mujeres 25-40, urgencia alta, en la home hero",
  "Promo 10% en perfumes para clientes VIP, tono premium",
  'CTA: "Comprar ahora"',
];

// ---- offline fallback: a compact mirror of the backend extractor ----
function localExtract(brief, text) {
  const b = { ...brief };
  const t = text.toLowerCase();
  const promo = (text.match(/(\d{1,3})\s*%\s*(?:off|de\s+descuento|descuento|dto)/i) || [])[1];
  if (/urgenc\w*\s*(alta|máxima)|black\s*friday|hoy|cuanto antes|urgent/.test(t)) b.urgency = "high";
  else if (/urgenc\w*\s*media|pronto|esta semana|soon/.test(t)) b.urgency = "medium";
  else if (/urgenc\w*\s*baja|sin prisa|no rush/.test(t)) b.urgency = "low";
  const aud = text.match(/\b(?:a|para)\s+((?:mujeres|hombres|clientes|jóvenes|adultos|vip)[^.,;\n]*)/i);
  if (aud) b.audience = aud[1].trim();
  if (/\bhero\b|\b(home|inicio)\b/.test(t)) b.placement = "Home · Hero";
  else if (/colecci[oó]n|collection/.test(t)) b.placement = "Colección · Cabecera";
  else if (/producto|product|pdp/.test(t)) b.placement = "Producto · Franja";
  const cta = text.match(/\bcta[:\s]+["“]?([^"”.\n]{2,40})/i) || text.match(/bot[oó]n[:\s]+["“]?([^"”.\n]{2,40})/i);
  if (cta) b.cta = cta[1].trim();
  if (!b.goal) b.goal = (promo ? `${text.trim()} (${promo}% OFF)` : text.trim()).slice(0, 160);
  return b;
}
const REQUIRED = ["goal", "audience", "cta", "urgency", "placement"];
const missingOf = (b) => REQUIRED.filter((f) => !(b[f] || "").trim());

function Bubble({ role, children }) {
  const bot = role !== "user";
  return (
    <div className="fade-up" style={{ display: "flex", justifyContent: bot ? "flex-start" : "flex-end", gap: 10, alignItems: "flex-end" }}>
      {bot && <div style={{ width: 32, height: 32, borderRadius: 9999, background: "#22D3EE", color: "#06121f", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><Icon name="bot" size={17} /></div>}
      <div style={{ maxWidth: "82%", fontFamily: "Inter", fontSize: 14, lineHeight: 1.5, padding: "11px 14px", borderRadius: 16,
        borderBottomLeftRadius: bot ? 5 : 16, borderBottomRightRadius: bot ? 16 : 5,
        background: bot ? "#fff" : "#22D3EE", color: bot ? "#002B57" : "#06121f",
        border: bot ? "1px solid #E2E8F0" : "none", boxShadow: "0 8px 20px rgba(15,23,42,.05)" }}>
        {children}
      </div>
    </div>
  );
}

function Chatbox({ campaign, onCampaign, onNotice }) {
  const [msgs, setMsgs] = useStateCB([{ role: "agent", text: "Hola. Cuéntame la campaña que quieres lanzar — promo, producto, audiencia y dónde irá. Yo armo el brief." }]);
  const [val, setVal] = useStateCB("");
  const [streaming, setStreaming] = useStateCB(false);
  const [error, setError] = useStateCB("");
  const campaignId = useRefCB(null);
  const brief = useRefCB({ goal: "", audience: "", cta: "", tone: "", urgency: "", placement: "", deadline: null });
  const scroller = useRefCB(null);

  useEffectCB(() => { if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight; }, [msgs, streaming]);
  useEffectCB(() => {
    if (!campaign) return;
    if (campaign.id) campaignId.current = campaign.id;
    if (campaign.structured_brief) brief.current = campaign.structured_brief;
  }, [campaign]);

  function pushAgentToken(text) {
    setMsgs((m) => {
      const last = m[m.length - 1];
      if (last && last.role === "agent" && last.streaming) return [...m.slice(0, -1), { ...last, text: last.text + text }];
      return [...m, { role: "agent", text, streaming: true }];
    });
  }
  const sealAgent = () => setMsgs((m) => m.map((x) => x.streaming ? { ...x, streaming: false } : x));

  function finish(campaign, complete, missing) {
    campaignId.current = campaign.id;
    brief.current = campaign.structured_brief;
    sealAgent();
    onCampaign && onCampaign(campaign, complete, missing);
  }

  async function streamFromBridge(text) {
    if (typeof AijolotApi === "undefined" || !AijolotApi.streamIntakeEvents) throw new Error("api client unavailable");
    await AijolotApi.streamIntakeEvents(text, campaignId.current, (evt) => {
      if (evt.type === "token") pushAgentToken(evt.text);
      else if (evt.type === "done") finish(evt.campaign, evt.complete, evt.missing);
    });
  }

  function isOfflineFallbackError(e) {
    const msg = (e && (e.message || String(e))) || "";
    return /api client unavailable|failed to fetch|networkerror|load failed|could not connect|connection refused/i.test(msg);
  }

  async function fallbackLocal(text) {
    const updated = localExtract(brief.current, text);
    const missing = missingOf(updated);
    const reply = missing.length
      ? `Para cerrar el brief me falta: ${missing.join(", ")}. ¿Me lo confirmas? (modo offline)`
      : "Listo — brief completo (modo offline). Revisa los campos y avanza a Arte.";
    // simulate streaming
    const words = reply.split(" ");
    for (let i = 0; i < words.length; i++) { pushAgentToken((i ? " " : "") + words[i]); await new Promise((r) => setTimeout(r, 18)); }
    const campaign = { id: campaignId.current || "local", title: updated.goal.slice(0, 40), raw_brief: text, structured_brief: updated, status: "draft", messages: [] };
    finish(campaign, missing.length === 0, missing);
  }

  async function send(text) {
    const t = (text != null ? text : val).trim();
    if (!t || streaming) return;
    setMsgs((m) => [...m, { role: "user", text: t }]);
    setVal(""); setStreaming(true); setError("");
    try { await streamFromBridge(t); }
    catch (e) {
      const msg = e && (e.message || e.status) || "error";
      if (!isOfflineFallbackError(e)) {
        sealAgent();
        setError("Intake backend falló: " + msg);
        onNotice && onNotice({ tone: "amber", text: "No se pudo guardar intake en backend: " + msg });
        return;
      }
      setError("Bridge no disponible — usando modo offline explícito.");
      onNotice && onNotice({ tone: "amber", text: "Backend no disponible; usando extractor local solo como fallback offline." });
      await fallbackLocal(t);
    }
    finally { setStreaming(false); }
  }

  return (
    <GlassCard style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 460, height: "100%" }}>
      <div style={{ padding: "14px 18px", borderBottom: "1px solid #EEF2F6", display: "flex", alignItems: "center", gap: 11 }}>
        <div style={{ width: 34, height: 34, borderRadius: 11, background: "linear-gradient(135deg,#22D3EE,#0891B2)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff" }}><Icon name="wand-sparkles" size={17} /></div>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>Brief con el agente</div>
          <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>Describe la campaña en lenguaje natural</div>
        </div>
        {error ? <span title={error} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "Inter", fontSize: 11, color: "#B45309" }}><Icon name="wifi-off" size={13} /> {error.includes("offline") ? "offline" : "error backend"}</span> : null}
      </div>

      <div ref={scroller} style={{ flex: 1, overflowY: "auto", padding: 18, display: "flex", flexDirection: "column", gap: 13, maxHeight: 380 }}>
        {msgs.map((m, i) => (
          <Bubble key={i} role={m.role}>
            {m.text}
            {m.streaming && streaming ? <span style={{ display: "inline-block", width: 7, height: 13, background: "#22D3EE", marginLeft: 3, verticalAlign: "middle", animation: "caret 1s step-end infinite" }} /> : null}
          </Bubble>
        ))}
      </div>

      <div style={{ padding: "0 18px 10px", display: "flex", flexWrap: "wrap", gap: 7 }}>
        {SUGGEST.map((s) => (
          <button key={s} onClick={() => send(s)} disabled={streaming} title={s} style={{ fontFamily: "Inter", fontSize: 11.5, padding: "6px 11px", borderRadius: 9999, border: "1px solid #E2E8F0", background: "#fff", color: "#0891B2", cursor: streaming ? "default" : "pointer", maxWidth: 240, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            + {s}
          </button>
        ))}
      </div>

      <div style={{ padding: "10px 16px 16px", borderTop: "1px solid #EEF2F6" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", background: "rgba(241,245,249,0.6)", border: "1px solid #E2E8F0", borderRadius: 14, padding: 8 }}>
          <textarea value={val} onChange={(e) => setVal(e.target.value)} disabled={streaming} rows={2}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder="Ej: Banner 10% OFF en perfumes para la home, a clientes VIP, urgencia media…"
            style={{ flex: 1, border: "none", outline: "none", background: "transparent", resize: "none", fontFamily: "Inter", fontSize: 13.5, color: "#002B57", lineHeight: 1.45, padding: "6px 8px" }} />
          <Button variant="default" icon={streaming ? null : "send"} onClick={() => send()} disabled={streaming || !val.trim()} style={{ padding: "10px 14px" }}>
            {streaming ? <Spinner size={14} color="#fff" /> : null}
          </Button>
        </div>
        <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8", marginTop: 8, textAlign: "center" }}>El agente extrae objetivo, audiencia, CTA, urgencia y ubicación, y pregunta lo que falte.</div>
      </div>
    </GlassCard>
  );
}

Object.assign(window, { Chatbox });
