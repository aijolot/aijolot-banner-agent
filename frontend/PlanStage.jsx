/* global React, Icon, GlassCard, Button, Badge, Spinner, Kicker, Banner, SEGMENTS, PlanApi, GenerationApi, CatalogApi, PlacementApi, CampaignApi, ArtDirectionApi, AIJOLOT_DEMO_IDS, errorText, isApiCampaign, DecisionTraceCard */
// Aijolot Banner Agent — Stage 3: iterative CAMPAIGN PLAN gate.
// Shows a cheap, readable plan (typography, color classes, product/theme intent)
// plus a DETERMINISTIC wireframe (no generated image) so the user can iterate the
// idea and approve BEFORE the costly build (image + render + audit) runs.
const { useState: useStateP, useEffect: useEffectP, useRef: useRefP } = React;

const PLAN_TERMINAL = ["succeeded", "failed", "escalated"];

function planErrText(e) {
  return typeof errorText !== "undefined" ? errorText(e) : (e && (e.message || e.status)) || "error";
}

function PlanCard({ icon, title, children, updated }) {
  return (
    <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8,
      ...(updated ? { border: "1px solid rgba(8,145,178,0.45)", boxShadow: "0 0 0 3px rgba(34,211,238,0.12)" } : {}) }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(34,211,238,0.12)", color: "#0891B2" }}>
          <Icon name={icon} size={15} />
        </span>
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57" }}>{title}</span>
        {updated ? <Badge tone="cyan" icon="sparkles">{t("Ajustado")}</Badge> : null}
      </div>
      <div style={{ fontFamily: "Inter", fontSize: 12.5, color: "#475569", lineHeight: 1.55 }}>{children}</div>
    </GlassCard>
  );
}

// Etiquetas legibles para las ops que el intérprete de refinamiento detectó —
// le muestran al usuario QUÉ entendió el agente de su feedback (W0.1 + F4).
const OP_LABELS = {
  set_ink: "Color del texto",
  change_background: "Fondo",
  change_decor: "Elemento decorativo",
  edit_copy: "Copy",
  adjust_layout: "Layout",
  redraft_concept: "Concepto",
};

// Secciones del plan cuyas tarjetas se resaltan cuando cambian entre iteraciones.
const PLAN_SECTIONS = {
  typography: (p) => p.typography,
  palette: (p) => p.color_guidance,
  copy: (p) => p.copy_preview,
  theme: (p) => [p.theme, p.product_intent],
  layout: (p) => p.layout_note,
  wireframe: (p) => p.wireframe,
  placement: (p) => p.placement_plan,
  mode: (p) => [p.creative_mode, p.include_humans],
};

function diffPlanSections(prev, next) {
  if (!prev || !next) return {};
  const changed = {};
  Object.keys(PLAN_SECTIONS).forEach((key) => {
    try {
      if (JSON.stringify(PLAN_SECTIONS[key](prev) || null) !== JSON.stringify(PLAN_SECTIONS[key](next) || null)) changed[key] = true;
    } catch (e) { /* sección ilegible → sin resaltado */ }
  });
  return changed;
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
  const [agentOps, setAgentOps] = useStateP(null); // ops que el agente entendió del feedback (run.metadata)
  const [changedKeys, setChangedKeys] = useStateP({}); // secciones ajustadas en la última iteración
  const [approveBusy, setApproveBusy] = useStateP(false);
  const aliveRef = useRefP(true);
  const planRef = useRefP(null);

  // preserve=true (iteración): el plan actual SIGUE visible mientras el agente
  // lo ajusta — nada de pantalla de carga total; al terminar se resalta lo que
  // cambió para que se lea como tuning del mismo plan, no un plan nuevo.
  async function pollAndLoad(run, { preserve = false } = {}) {
    const keepVisible = preserve && planRef.current;
    if (!keepVisible) setStatus("running");
    let cur = run;
    for (let i = 0; aliveRef.current && cur && !PLAN_TERMINAL.includes(cur.status) && i < 120; i += 1) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        cur = (await GenerationApi.get(cur.id)) || cur;
      } catch (e) {
        if (!aliveRef.current) return;
        if (keepVisible) { onNotice && onNotice({ tone: "red", text: t("No se pudo refrescar el plan") + ": " + planErrText(e) }); return; }
        setStatus("failed");
        setError("No se pudo refrescar el plan: " + planErrText(e));
        return;
      }
      // En cuanto el backend interpreta el feedback, muéstralo (acompañamiento).
      const ops = cur && cur.metadata && cur.metadata.interpreted_ops;
      if (keepVisible && Array.isArray(ops) && ops.length) setAgentOps(ops);
    }
    if (!aliveRef.current) return;
    if (!cur || cur.status !== "succeeded") {
      const msg = (cur && (cur.error_message || `El plan finalizó con estado ${cur.status}`)) || "El backend no confirmó el plan.";
      if (keepVisible) { onNotice && onNotice({ tone: "red", text: t("No se pudo ajustar el plan") + ": " + msg }); return; }
      setStatus("failed");
      setError(msg);
      onNotice && onNotice({ tone: "red", text: "Plan no completado: " + msg });
      return;
    }
    const p = await PlanApi.get(campaign);
    if (!aliveRef.current) return;
    if (p.fallback || !p.data) {
      if (keepVisible) { onNotice && onNotice({ tone: "red", text: p.reason || t("Plan no disponible en backend.") }); return; }
      setStatus("failed");
      setError(p.reason || "Plan no disponible en backend.");
      return;
    }
    if (keepVisible) {
      const changed = diffPlanSections(planRef.current, p.data);
      setChangedKeys(changed);
      const labels = Object.keys(changed).map((k) => ({
        typography: t("Tipografía"), palette: t("Paleta y color"), copy: t("Copy propuesto"), theme: t("Producto y tema"),
        layout: t("Layout"), wireframe: t("Wireframe (baja fidelidad)"), placement: t("Piezas y ubicaciones propuestas"), mode: t("Modo creativo"),
      })[k]).filter(Boolean);
      onNotice && onNotice({ tone: "green", text: labels.length
        ? t("El agente ajustó") + ": " + labels.join(" · ") + ". " + t("El resto del plan se mantuvo.")
        : t("Plan ajustado — sin cambios visibles en las tarjetas.") });
    } else {
      onNotice && onNotice({ tone: "green", text: "Plan listo para revisar · sin costo de imagen hasta que apruebes" });
    }
    planRef.current = p.data;
    setPlan(p.data);
    setStatus("ready");
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

  const [modeBusy, setModeBusy] = React.useState(false);
  const [pieceBusy, setPieceBusy] = React.useState(null);
  const [appliedPiece, setAppliedPiece] = React.useState(null);
  // El agente propuso el set de piezas; aplicar una la convierte en la
  // ubicación de la campaña (y actualiza el brief para consistencia).
  async function applyPiece(piece) {
    if (pieceBusy) return;
    setPieceBusy(piece.placement_key);
    const r = await PlacementApi.applySuggested(campaign, piece);
    if (r.fallback) {
      onNotice && onNotice({ tone: "red", text: r.reason || "No se pudo aplicar la ubicación." });
    } else {
      setAppliedPiece(piece.placement_key);
      onNotice && onNotice({ tone: "green", text: `Ubicación aplicada: ${piece.label}.` });
      try { await CampaignApi.patch(campaign.id, { placement: piece.label }); } catch (e) { /* best-effort */ }
    }
    setPieceBusy(null);
  }
  // C0 — user override: persist mode_source='user' then re-plan so the wireframe
  // and downstream build respect the chosen mode.
  async function overrideMode(creative_mode, include_humans) {
    if (modeBusy) return;
    setModeBusy(true);
    const saved = await ArtDirectionApi.setCreativeMode(campaign, { creative_mode, include_humans });
    if (saved.fallback) { setModeBusy(false); setError(saved.reason || "No se pudo guardar el modo."); return; }
    const r = await PlanApi.iterate(campaign, "Aplica el modo creativo seleccionado", ["concept"]);
    if (!r.fallback && r.data) await pollAndLoad(r.data, { preserve: true });
    setModeBusy(false);
  }

  async function iterate() {
    const prompt = feedback.trim();
    if (!prompt || iterating) return;
    setIterating(true);
    setAgentOps(null);
    setChangedKeys({});
    const r = await PlanApi.iterate(campaign, prompt);
    if (r.fallback || !r.data) {
      setIterating(false);
      onNotice && onNotice({ tone: "amber", text: r.reason || "No se pudo iterar el plan." });
      return;
    }
    setFeedback("");
    await pollAndLoad(r.data, { preserve: true });
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
          <Kicker>{t("Paso 3 de 6 · Plan de campaña")}</Kicker>
          <h2 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 26, color: "#002B57", margin: 0 }}>{t("Revisa el plan antes de generar")}</h2>
          <p style={{ fontFamily: "Inter", fontSize: 13, color: "#68737D", margin: 0, maxWidth: 620 }}>
            Una vista de baja fidelidad de lo que el agente va a crear — tipografías, paleta y tema del producto. Itera la idea; la imagen y el render finales se generan solo al aprobar.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button variant="ghost" icon="chevron-left" onClick={onBack}>{t("Volver al brief")}</Button>
          <Button variant="primary" icon="sparkles" onClick={approve} disabled={status !== "ready" || approveBusy}>
            {approveBusy ? t("Generando…") : t("Aprobar y generar")}
          </Button>
        </div>
      </div>

      <GlassCard style={{ padding: 12, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        {busy ? <Badge tone="cyan" icon="loader"><span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Spinner size={12} /> {t("Armando el plan…")}</span></Badge>
          : iterating || modeBusy ? <Badge tone="cyan" icon="loader"><span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><Spinner size={12} /> {t("Ajustando el plan — el resto se mantiene")}</span></Badge>
          : status === "ready" ? <Badge tone="green" icon="check">{t("Plan listo · sin costo de imagen")}</Badge>
          : status === "prototype" ? <Badge tone="amber" icon="flask-conical">Prototipo local</Badge>
          : <Badge tone="red" icon="circle-alert">Plan no disponible</Badge>}
        {(iterating || modeBusy) && agentOps && agentOps.length ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, flexWrap: "wrap", fontFamily: "Inter", fontSize: 11.5, color: "#0891B2" }}>
            {t("El agente entendió")}: {agentOps.map((op) => (
              <span key={op} style={{ padding: "2px 8px", borderRadius: 9999, background: "rgba(34,211,238,0.12)", fontWeight: 600 }}>{t(OP_LABELS[op] || op)}</span>
            ))}
          </span>
        ) : null}
        {!iterating && !modeBusy && plan && plan.estimated_image_cost_note ? <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>{plan.estimated_image_cost_note}</span> : null}
      </GlassCard>

      {error ? (
        <GlassCard style={{ padding: 14, border: "1px solid rgba(239,68,68,0.25)" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start", fontFamily: "Inter", fontSize: 12.5, color: "#EF4444", lineHeight: 1.45 }}>
            <Icon name="circle-alert" size={15} color="#EF4444" /><span><b>Error visible:</b> {error}</span>
          </div>
        </GlassCard>
      ) : null}

      {busy && !plan ? (
        <GlassCard style={{ padding: 40, display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
          <Spinner size={28} />
          <div style={{ fontFamily: "Inter", fontSize: 13, color: "#68737D" }}>{t("El agente está planeando el concepto, la tipografía y la paleta…")}</div>
        </GlassCard>
      ) : null}

      {status === "ready" && plan ? (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.15fr) minmax(0,1fr)", gap: 16, alignItems: "start",
          opacity: iterating || modeBusy ? 0.72 : 1, transition: "opacity .25s ease" }}>
          {/* Wireframe + iterate */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10,
              ...(changedKeys.wireframe ? { border: "1px solid rgba(8,145,178,0.45)", boxShadow: "0 0 0 3px rgba(34,211,238,0.12)" } : {}) }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57", display: "inline-flex", alignItems: "center", gap: 8 }}>
                  {t("Wireframe (baja fidelidad)")}{changedKeys.wireframe ? <Badge tone="cyan" icon="sparkles">{t("Ajustado")}</Badge> : null}
                </span>
                <Badge tone="slate" icon="image-off">{t("Sin imagen")}</Badge>
              </div>
              <div style={{ width: "100%", borderRadius: 12, overflow: "hidden", border: "1px dashed rgba(148,163,184,0.5)" }}>
                <Banner seg={seg} live={plan.wireframe} idSuffix="plan" breakpoint="desktop" />
              </div>
              <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>El recuadro del producto es un marcador; la imagen real se genera al aprobar.</div>
            </GlassCard>

            {plan.placement_plan && (plan.placement_plan.pieces || []).length ? (
              <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10,
                ...(changedKeys.placement ? { border: "1px solid rgba(8,145,178,0.45)", boxShadow: "0 0 0 3px rgba(34,211,238,0.12)" } : {}) }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57" }}>{t("Piezas y ubicaciones propuestas")}</span>
                  {changedKeys.placement ? <Badge tone="cyan" icon="sparkles">{t("Ajustado")}</Badge> : null}
                  <Badge tone="cyan" icon="layout-grid">{plan.placement_plan.pieces.length} pieza{plan.placement_plan.pieces.length === 1 ? "" : "s"}</Badge>
                </div>
                {plan.placement_plan.rationale ? (
                  <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#64748B" }}>{plan.placement_plan.rationale}</div>
                ) : null}
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {plan.placement_plan.pieces.map((piece) => (
                    <div key={piece.placement_key} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 11px", borderRadius: 11,
                      background: piece.priority === 1 ? "rgba(34,211,238,0.07)" : "rgba(248,250,252,0.8)",
                      border: `1px solid ${piece.priority === 1 ? "rgba(8,145,178,0.3)" : "#EEF2F6"}` }}>
                      <span style={{ width: 22, height: 22, borderRadius: 7, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
                        background: piece.priority === 1 ? "#0891B2" : "#E2E8F0", color: piece.priority === 1 ? "#fff" : "#64748B",
                        fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 11.5 }}>{piece.priority}</span>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap" }}>
                          <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 12.5, color: "#002B57" }}>{piece.label}</span>
                          {piece.format ? <span style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8" }}>{piece.format}</span> : null}
                          <Badge tone="slate">{piece.creative_mode === "full_picture" ? t("Escena completa") : piece.creative_mode === "video" ? t("Video") : t("Producto recortado")}</Badge>
                          {piece.priority === 1 ? <Badge tone="cyan" icon="sparkles">{t("Se genera al aprobar")}</Badge> : null}
                        </div>
                        {piece.rationale ? <div style={{ fontFamily: "Inter", fontSize: 11, color: "#64748B", marginTop: 2 }}>{piece.rationale}</div> : null}
                      </div>
                      {appliedPiece === piece.placement_key ? (
                        <Badge tone="green" icon="check">{t("Aplicada")}</Badge>
                      ) : (
                        <Button variant={piece.priority === 1 ? "primary" : "ghost"} icon={pieceBusy === piece.placement_key ? "loader" : "map-pin"}
                          onClick={() => applyPiece(piece)} disabled={!!pieceBusy}>
                          Usar ubicación
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
                <div style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8" }}>
                  La pieza 1 es la que se genera al aprobar este plan; las demás quedan como backlog de la campaña.
                </div>
              </GlassCard>
            ) : null}

            <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10,
              ...(changedKeys.mode ? { border: "1px solid rgba(8,145,178,0.45)", boxShadow: "0 0 0 3px rgba(34,211,238,0.12)" } : {}) }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57" }}>{t("Modo creativo")}</span>
                {changedKeys.mode ? <Badge tone="cyan" icon="sparkles">{t("Ajustado")}</Badge> : null}
                <Badge tone={plan.mode_source === "user" ? "amber" : "cyan"} icon={plan.mode_source === "user" ? "user" : "sparkles"}>
                  {plan.mode_source === "user" ? t("Definido por ti") : t("Recomendado por el agente")}
                </Badge>
              </div>
              {plan.mode_rationale ? <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#64748B" }}>{plan.mode_rationale}</div> : null}
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                {[["composite", t("Producto recortado"), "scissors"], ["full_picture", t("Escena completa"), "image"], ["video", t("Video"), "clapperboard"]].map(([key, label, icon]) => (
                  <button key={key} onClick={() => overrideMode(key, plan.include_humans)} disabled={modeBusy} style={{
                    display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 9999, cursor: "pointer",
                    border: `1px solid ${plan.creative_mode === key ? "rgba(8,145,178,0.5)" : "#E2E8F0"}`,
                    background: plan.creative_mode === key ? "rgba(34,211,238,0.14)" : "#fff",
                    fontFamily: "Inter", fontSize: 11.5, fontWeight: 600, color: plan.creative_mode === key ? "#0891B2" : "#64748B" }}>
                    <Icon name={icon} size={12} /> {label}
                  </button>
                ))}
                <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "Inter", fontSize: 11.5, color: "#64748B", marginLeft: 6 }}>
                  <input type="checkbox" checked={!!plan.include_humans} disabled={modeBusy} onChange={(e) => overrideMode(plan.creative_mode, e.target.checked)} />
                  Incluir personas
                </label>
                {modeBusy ? <Spinner size={13} /> : null}
              </div>
            </GlassCard>

            <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57" }}>{t("Itera la idea")}</span>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="p. ej. 'fondo más vibrante', 'headline más corto y urgente', 'mueve el copy a la derecha'"
                rows={3}
                style={{ width: "100%", resize: "vertical", borderRadius: 10, border: "1px solid #E2E8F0", padding: "10px 12px", fontFamily: "Inter", fontSize: 12.5, color: "#0F172A", outline: "none" }}
              />
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button variant="secondary" icon={iterating ? "loader" : "refresh-cw"} onClick={iterate} disabled={iterating || !feedback.trim()}>
                  {iterating ? t("Replaneando…") : t("Aplicar al plan")}
                </Button>
              </div>
            </GlassCard>
          </div>

          {/* Readable summary */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {plan.decision_trace && (plan.decision_trace.reasons || []).length ? (
              <PlanCard icon="lightbulb" title={t("¿Por qué este plan?")}>
                <DecisionTraceCard trace={plan.decision_trace} compact />
              </PlanCard>
            ) : null}
            <PlanCard icon="type" title={t("Tipografía")} updated={changedKeys.typography}>
              <div><b>Display:</b> {typo.display || "—"}</div>
              <div><b>{t("Texto")}:</b> {typo.body || "—"}</div>
              {typo.rationale ? <div style={{ marginTop: 4, color: "#64748B" }}>{typo.rationale}</div> : null}
            </PlanCard>

            <PlanCard icon="palette" title={t("Paleta y color")} updated={changedKeys.palette}>
              {colors.background_name ? <div><b>Fondo:</b> {colors.background_name}</div> : null}
              {colors.background_description ? <div style={{ color: "#64748B" }}>{colors.background_description}</div> : null}
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 6 }}>
                <Swatch label="Fondo" value={palette.background} />
                <Swatch label="Texto" value={palette.text || colors.text_ink} />
                <Swatch label="CTA" value={palette.cta_background} />
              </div>
            </PlanCard>

            <PlanCard icon="package" title={t("Producto y tema")} updated={changedKeys.theme}>
              {plan.theme ? <div style={{ marginBottom: 6 }}>{plan.theme}</div> : null}
              {products.map((p, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
                  <Icon name={p.has_hero_planned ? "image" : "circle-dashed"} size={12} color={p.has_hero_planned ? "#0891B2" : "#CBD5E1"} />
                  <span><b>{p.segment_label || "Audiencia"}:</b> {p.product_title || p.audience || "—"}</span>
                </div>
              ))}
            </PlanCard>

            <PlanCard icon="text-cursor" title={t("Copy propuesto")} updated={changedKeys.copy}>
              {copyPreview.eyebrow ? <div style={{ fontSize: 11, letterSpacing: ".04em", color: "#94A3B8" }}>{copyPreview.eyebrow}</div> : null}
              <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>{copyPreview.headline || "—"}</div>
              {copyPreview.subheadline ? <div style={{ color: "#64748B" }}>{copyPreview.subheadline}</div> : null}
              {copyPreview.cta ? <div style={{ marginTop: 4, display: "inline-block", padding: "4px 10px", borderRadius: 8, background: "rgba(34,211,238,0.12)", color: "#0891B2", fontWeight: 600, fontSize: 11.5 }}>{copyPreview.cta}</div> : null}
            </PlanCard>

            {plan.layout_note ? (
              <PlanCard icon="layout-template" title={t("Layout")} updated={changedKeys.layout}>
                {plan.layout_note}
              </PlanCard>
            ) : null}
          </div>
        </div>
      ) : null}

      {status === "prototype" ? (
        <GlassCard style={{ padding: 24, display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-start", border: "1px solid rgba(239,68,68,0.3)" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", fontFamily: "Inter", fontSize: 13, color: "#991B1B" }}>
            <Icon name="circle-alert" size={16} color="#EF4444" />
            La campaña no tiene ID de backend — no se puede planear ni generar. Regresa al brief y verifica la conexión con el backend.
          </div>
          <Button variant="ghost" icon="chevron-left" onClick={onBack}>{t("Volver al brief")}</Button>
        </GlassCard>
      ) : null}
    </div>
  );
}

Object.assign(window, { PlanStage });
