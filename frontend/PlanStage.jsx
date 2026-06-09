/* global React, Icon, GlassCard, Button, Badge, Spinner, Kicker, Banner, SEGMENTS, PlanApi, GenerationApi, CatalogApi, AIJOLOT_DEMO_IDS, errorText, isApiCampaign */
// Aijolot Banner Agent — Stage 3: iterative CAMPAIGN PLAN gate.
// Shows a cheap, readable plan (typography, color classes, product/theme intent)
// plus a DETERMINISTIC wireframe (no generated image) so the user can iterate the
// idea and approve BEFORE the costly build (image + render + audit) runs.
const { useState: useStateP, useEffect: useEffectP, useRef: useRefP } = React;

const PLAN_TERMINAL = ["succeeded", "failed", "escalated"];

function planErrText(e) {
  return typeof errorText !== "undefined" ? errorText(e) : (e && (e.message || e.status)) || "error";
}

function PlanCard({ icon, title, children }) {
  return (
    <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(34,211,238,0.12)", color: "#0891B2" }}>
          <Icon name={icon} size={15} />
        </span>
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57" }}>{title}</span>
      </div>
      <div style={{ fontFamily: "Inter", fontSize: 12.5, color: "#475569", lineHeight: 1.55 }}>{children}</div>
    </GlassCard>
  );
}

function Swatch({ label, value }) {
  if (!value) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 18, height: 18, borderRadius: 5, background: value, border: "1px solid rgba(0,0,0,0.08)" }} />
      <span style={{ fontFamily: "Space Grotesk", fontSize: 10.5, color: "#94A3B8" }}>{label}</span>
    </div>
  );
}

function PlanStage({ campaign, placement, onNotice, onApprove, onBack }) {
  const [status, setStatus] = useStateP("starting"); // starting | running | ready | failed | prototype
  const [plan, setPlan] = useStateP(null);
  const [error, setError] = useStateP(null);
  const [feedback, setFeedback] = useStateP("");
  const [iterating, setIterating] = useStateP(false);
  const [approveBusy, setApproveBusy] = useStateP(false);
  const aliveRef = useRefP(true);

  async function pollAndLoad(run) {
    setStatus("running");
    let cur = run;
    for (let i = 0; aliveRef.current && cur && !PLAN_TERMINAL.includes(cur.status) && i < 120; i += 1) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        cur = (await GenerationApi.get(cur.id)) || cur;
      } catch (e) {
        if (!aliveRef.current) return;
        setStatus("failed");
        setError("No se pudo refrescar el plan: " + planErrText(e));
        return;
      }
    }
    if (!aliveRef.current) return;
    if (!cur || cur.status !== "succeeded") {
      const msg = (cur && (cur.error_message || `El plan finalizó con estado ${cur.status}`)) || "El backend no confirmó el plan.";
      setStatus("failed");
      setError(msg);
      onNotice && onNotice({ tone: "red", text: "Plan no completado: " + msg });
      return;
    }
    const p = await PlanApi.get(campaign);
    if (!aliveRef.current) return;
    if (p.fallback || !p.data) {
      setStatus("failed");
      setError(p.reason || "Plan no disponible en backend.");
      return;
    }
    setPlan(p.data);
    setStatus("ready");
    onNotice && onNotice({ tone: "green", text: "Plan listo para revisar · sin costo de imagen hasta que apruebes" });
  }

  useEffectP(() => {
    aliveRef.current = true;
    (async () => {
      if (!isApiCampaign(campaign)) {
        setStatus("prototype");
        onNotice && onNotice({ tone: "amber", text: "Plan en modo prototipo (campaña sin UUID backend)." });
        return;
      }
      // Best-effort catalog snapshot so the plan grounds on the real store catalog
      // + the products picked in Brief. Never blocks the plan.
      try {
        const storeId = (placement && placement.backend && placement.backend.store_id) || (AIJOLOT_DEMO_IDS && AIJOLOT_DEMO_IDS.store);
        await CatalogApi.createSnapshot(campaign, { store_id: storeId, resource_types: ["product", "collection"], limit: 24 });
      } catch (e) { /* grounding is best-effort */ }
      const started = await PlanApi.start(campaign);
      if (!aliveRef.current) return;
      if (started.fallback || !started.data) {
        setStatus("failed");
        setError(started.reason || "No se pudo iniciar el plan.");
        onNotice && onNotice({ tone: "amber", text: started.reason || "No se pudo iniciar el plan." });
        return;
      }
      await pollAndLoad(started.data);
    })();
    return () => { aliveRef.current = false; };
  }, []);

  async function iterate() {
    const prompt = feedback.trim();
    if (!prompt || iterating) return;
    setIterating(true);
    const r = await PlanApi.iterate(campaign, prompt);
    if (r.fallback || !r.data) {
      setIterating(false);
      onNotice && onNotice({ tone: "amber", text: r.reason || "No se pudo iterar el plan." });
      return;
    }
    setFeedback("");
    await pollAndLoad(r.data);
    setIterating(false);
  }

  async function approve() {
    if (approveBusy) return;
    setApproveBusy(true);
    const r = await PlanApi.approve(campaign);
    if (r.fallback || !r.data) {
      setApproveBusy(false);
      onNotice && onNotice({ tone: "amber", text: r.reason || "No se pudo aprobar el plan." });
      return;
    }
    onNotice && onNotice({ tone: "green", text: "Plan aprobado · generando el banner final…" });
    onApprove(r.data.generation_run || null);
  }

  const seg = SEGMENTS.masculino;
  const busy = status === "starting" || status === "running";
  const typo = (plan && plan.typography) || {};
  const colors = (plan && plan.color_guidance) || {};
  const palette = colors.palette_usage || {};
  const copyPreview = (plan && plan.copy_preview) || {};
  const products = (plan && plan.product_intent) || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Kicker>Paso 3 de 6 · Plan de campaña</Kicker>
          <h2 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 26, color: "#002B57", margin: 0 }}>Revisa el plan antes de generar</h2>
          <p style={{ fontFamily: "Inter", fontSize: 13, color: "#68737D", margin: 0, maxWidth: 620 }}>
            Una vista de baja fidelidad de lo que el agente va a crear — tipografías, paleta y tema del producto. Itera la idea; la imagen y el render finales se generan solo al aprobar.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button variant="ghost" icon="chevron-left" onClick={onBack}>Volver al brief</Button>
          <Button variant="primary" icon="sparkles" onClick={approve} disabled={status !== "ready" || approveBusy}>
            {approveBusy ? "Generando…" : "Aprobar y generar"}
          </Button>
        </div>
      </div>

      <GlassCard style={{ padding: 12, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        {busy ? <Badge tone="cyan" icon="loader"><span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Spinner size={12} /> Armando el plan…</span></Badge>
          : status === "ready" ? <Badge tone="green" icon="check">Plan listo · sin costo de imagen</Badge>
          : status === "prototype" ? <Badge tone="amber" icon="flask-conical">Prototipo local</Badge>
          : <Badge tone="red" icon="circle-alert">Plan no disponible</Badge>}
        {plan && plan.estimated_image_cost_note ? <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>{plan.estimated_image_cost_note}</span> : null}
      </GlassCard>

      {error ? (
        <GlassCard style={{ padding: 14, border: "1px solid rgba(239,68,68,0.25)" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start", fontFamily: "Inter", fontSize: 12.5, color: "#EF4444", lineHeight: 1.45 }}>
            <Icon name="circle-alert" size={15} color="#EF4444" /><span><b>Error visible:</b> {error}</span>
          </div>
        </GlassCard>
      ) : null}

      {busy ? (
        <GlassCard style={{ padding: 40, display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
          <Spinner size={28} />
          <div style={{ fontFamily: "Inter", fontSize: 13, color: "#68737D" }}>El agente está planeando el concepto, la tipografía y la paleta…</div>
        </GlassCard>
      ) : null}

      {status === "ready" && plan ? (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.15fr) minmax(0,1fr)", gap: 16, alignItems: "start" }}>
          {/* Wireframe + iterate */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57" }}>Wireframe (baja fidelidad)</span>
                <Badge tone="slate" icon="image-off">Sin imagen</Badge>
              </div>
              <div style={{ width: "100%", borderRadius: 12, overflow: "hidden", border: "1px dashed rgba(148,163,184,0.5)" }}>
                <Banner seg={seg} live={plan.wireframe} idSuffix="plan" breakpoint="desktop" />
              </div>
              <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>El recuadro del producto es un marcador; la imagen real se genera al aprobar.</div>
            </GlassCard>

            <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57" }}>Itera la idea</span>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="p. ej. 'fondo más vibrante', 'headline más corto y urgente', 'mueve el copy a la derecha'"
                rows={3}
                style={{ width: "100%", resize: "vertical", borderRadius: 10, border: "1px solid #E2E8F0", padding: "10px 12px", fontFamily: "Inter", fontSize: 12.5, color: "#0F172A", outline: "none" }}
              />
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button variant="secondary" icon={iterating ? "loader" : "refresh-cw"} onClick={iterate} disabled={iterating || !feedback.trim()}>
                  {iterating ? "Replaneando…" : "Aplicar al plan"}
                </Button>
              </div>
            </GlassCard>
          </div>

          {/* Readable summary */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <PlanCard icon="type" title="Tipografía">
              <div><b>Display:</b> {typo.display || "—"}</div>
              <div><b>Texto:</b> {typo.body || "—"}</div>
              {typo.rationale ? <div style={{ marginTop: 4, color: "#64748B" }}>{typo.rationale}</div> : null}
            </PlanCard>

            <PlanCard icon="palette" title="Paleta y color">
              {colors.background_name ? <div><b>Fondo:</b> {colors.background_name}</div> : null}
              {colors.background_description ? <div style={{ color: "#64748B" }}>{colors.background_description}</div> : null}
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 6 }}>
                <Swatch label="Fondo" value={palette.background} />
                <Swatch label="Texto" value={palette.text || colors.text_ink} />
                <Swatch label="CTA" value={palette.cta_background} />
              </div>
            </PlanCard>

            <PlanCard icon="package" title="Producto y tema">
              {plan.theme ? <div style={{ marginBottom: 6 }}>{plan.theme}</div> : null}
              {products.map((p, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
                  <Icon name={p.has_hero_planned ? "image" : "circle-dashed"} size={12} color={p.has_hero_planned ? "#0891B2" : "#CBD5E1"} />
                  <span><b>{p.segment_label || "Audiencia"}:</b> {p.product_title || p.audience || "—"}</span>
                </div>
              ))}
            </PlanCard>

            <PlanCard icon="text-cursor" title="Copy propuesto">
              {copyPreview.eyebrow ? <div style={{ fontSize: 11, letterSpacing: ".04em", color: "#94A3B8" }}>{copyPreview.eyebrow}</div> : null}
              <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>{copyPreview.headline || "—"}</div>
              {copyPreview.subheadline ? <div style={{ color: "#64748B" }}>{copyPreview.subheadline}</div> : null}
              {copyPreview.cta ? <div style={{ marginTop: 4, display: "inline-block", padding: "4px 10px", borderRadius: 8, background: "rgba(34,211,238,0.12)", color: "#0891B2", fontWeight: 600, fontSize: 11.5 }}>{copyPreview.cta}</div> : null}
            </PlanCard>

            {plan.layout_note ? (
              <PlanCard icon="layout-template" title="Layout">
                {plan.layout_note}
              </PlanCard>
            ) : null}
          </div>
        </div>
      ) : null}

      {status === "prototype" ? (
        <GlassCard style={{ padding: 24, display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-start" }}>
          <div style={{ fontFamily: "Inter", fontSize: 13, color: "#68737D" }}>
            El plan iterativo requiere una campaña backend (UUID). Puedes continuar a la generación en modo prototipo.
          </div>
          <Button variant="primary" icon="chevron-right" onClick={() => onApprove(null)}>Continuar a generación</Button>
        </GlassCard>
      ) : null}
    </div>
  );
}

Object.assign(window, { PlanStage });
