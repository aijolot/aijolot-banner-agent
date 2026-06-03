/* global React, Icon, GlassCard, Button, Badge, Spinner, Kicker, Banner, PIPELINE, CODE_LINES, BRAND, CATALOG, SEGMENTS, GenerationApi, errorText, isApiCampaign */
// Aijolot Banner Agent — Stage 2: backend event-driven generation pipeline.
const { useState: useStateG, useEffect: useEffectG, useRef: useRefG } = React;

const DUR = [1300, 1250, 1650, 1700, 1750]; // prototype fallback timing only
const BACKEND_STEP_KEYS = ["intake_context", "concept", "image", "render_audit", "review_publish"];
const STEP_TO_PIPELINE = { intake_context: 0, concept: 1, image: 2, render_audit: 3, review_publish: 4 };
const TERMINAL_RUN_STATUSES = ["succeeded", "failed", "escalated"];
const FAILED_STATUSES = ["failed", "escalated"];
const RUNNING_STATUSES = ["queued", "running", "started", "retried"];

function textFromError(e) {
  return typeof errorText !== "undefined" ? errorText(e) : (e && (e.message || e.status)) || "error";
}

function eventSummary(event) {
  if (!event) return null;
  const summary = event.output_summary || event.input_summary;
  if (!summary) return null;
  if (typeof summary === "string") return summary;
  if (summary.summary) return summary.summary;
  if (summary.value) return typeof summary.value === "string" ? summary.value : JSON.stringify(summary.value);
  return JSON.stringify(summary);
}

function normalizeArtifact(settled) {
  if (!settled || settled.status !== "fulfilled") return { ok: false, reason: settled && settled.reason ? textFromError(settled.reason) : "No disponible" };
  const value = settled.value;
  if (!value || value.fallback) return { ok: false, reason: (value && value.reason) || "No disponible en backend" };
  return { ok: true, data: value.data };
}

function stepsFromBackend(run, events) {
  const backendProgress = run && Array.isArray(run.progress) ? run.progress : [];
  const byKey = {};
  backendProgress.forEach((step) => {
    if (step && step.key) byKey[step.key] = step;
  });
  (events || []).forEach((event) => {
    const key = event && event.frontend_step;
    if (!key) return;
    if (!byKey[key]) byKey[key] = { key, node_keys: [] };
    byKey[key].events = [...(byKey[key].events || []), event];
  });
  return BACKEND_STEP_KEYS.map((key, i) => {
    const fallback = PIPELINE[i] || PIPELINE[0];
    const step = byKey[key] || {};
    const stepEvents = step.events || [];
    const failedEvent = stepEvents.find((event) => FAILED_STATUSES.includes(event.status));
    const succeededNodes = new Set(stepEvents.filter((event) => event.status === "succeeded").map((event) => event.node_key));
    const startedEvent = stepEvents.find((event) => RUNNING_STATUSES.includes(event.status));
    let status = step.status || "queued";
    if (failedEvent) status = failedEvent.status;
    else if (stepEvents.length && step.node_keys && step.node_keys.length && succeededNodes.size >= step.node_keys.length) status = "succeeded";
    else if (startedEvent) status = "running";
    const latest = stepEvents[stepEvents.length - 1];
    return {
      key,
      id: fallback.id,
      icon: fallback.icon,
      title: fallback.title,
      backendLabel: step.label || key.replace(/_/g, " "),
      sub: latest ? `${latest.node_key || key} · ${latest.status || "evento"}` : fallback.sub,
      done: latest ? (eventSummary(latest) || `${succeededNodes.size || stepEvents.length} eventos backend`) : fallback.done,
      status,
      events: stepEvents,
      failedEvent,
    };
  });
}

function phaseFromBackend(run, events, steps, status) {
  if (status === "prototype") return null;
  if (!run && !(events && events.length)) return 0;
  if (run && run.status === "succeeded") return 5;
  const failedIdx = steps.findIndex((step) => FAILED_STATUSES.includes(step.status));
  if (failedIdx >= 0) return failedIdx;
  const currentKey = (run && run.frontend_step) || (events && events.length ? events[events.length - 1].frontend_step : null);
  const currentIdx = currentKey && STEP_TO_PIPELINE[currentKey] != null ? STEP_TO_PIPELINE[currentKey] : 0;
  if (run && FAILED_STATUSES.includes(run.status)) return currentIdx;
  const runningIdx = steps.findIndex((step) => RUNNING_STATUSES.includes(step.status));
  if (runningIdx >= 0) return runningIdx;
  const firstOpen = steps.findIndex((step) => step.status !== "succeeded");
  return firstOpen >= 0 ? firstOpen : Math.min(currentIdx, 4);
}

function progressPct(run, steps, phase, status) {
  if (status === "failed") return Math.max(4, Math.round((Math.min(phase, 4) / 5) * 100));
  if (status === "succeeded" || (run && run.status === "succeeded")) return 100;
  if (run && Array.isArray(run.progress) && run.progress.length) {
    const succeeded = run.progress.filter((step) => step.status === "succeeded").length;
    const partial = run.status === "running" || run.status === "queued" ? 0.35 : 0;
    return Math.min(99, Math.round(((succeeded + partial) / run.progress.length) * 100));
  }
  const succeeded = (steps || []).filter((step) => step.status === "succeeded").length;
  if (succeeded) return Math.min(99, Math.round((succeeded / 5) * 100));
  return Math.min(100, Math.round((phase / 5) * 100));
}

function StepRail({ steps, phase, status }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {steps.map((s, i) => {
        const failed = FAILED_STATUSES.includes(s.status);
        const done = !failed && (s.status === "succeeded" || phase > i);
        const running = !failed && phase === i && status !== "succeeded";
        return (
          <div key={s.key || s.id} style={{
            display: "flex", alignItems: "center", gap: 13, padding: "13px 15px", borderRadius: 13,
            background: failed ? "rgba(239,68,68,0.08)" : running ? "rgba(34,211,238,0.1)" : done ? "rgba(16,185,129,0.06)" : "rgba(248,250,252,0.7)",
            border: `1px solid ${failed ? "rgba(239,68,68,0.28)" : running ? "rgba(34,211,238,0.35)" : done ? "rgba(16,185,129,0.2)" : "#EEF2F6"}`,
            transition: "background .3s, border .3s", opacity: phase < i && !failed ? 0.55 : 1,
          }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
              background: failed ? "rgba(239,68,68,0.12)" : done ? "rgba(16,185,129,0.14)" : running ? "rgba(34,211,238,0.16)" : "#fff",
              color: failed ? "#EF4444" : done ? "#10B981" : running ? "#0891B2" : "#CBD5E1", border: running ? "none" : "1px solid #EEF2F6" }}>
              {failed ? <Icon name="circle-alert" size={18} /> : done ? <Icon name="check" size={18} /> : running ? <Spinner size={17} /> : <Icon name={s.icon} size={17} />}
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57" }}>{s.title}</div>
              <div style={{ fontFamily: "Inter", fontSize: 11.5, color: failed ? "#EF4444" : done ? "#16A34A" : running ? "#0891B2" : "#94A3B8", marginTop: 2, transition: "color .3s" }}>
                {failed ? `Error backend · ${(s.failedEvent && s.failedEvent.node_key) || s.backendLabel}` : done ? s.done : running ? s.sub : "En espera"}
              </div>
              <div style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8", marginTop: 3 }}>
                Backend: {s.backendLabel}{s.events && s.events.length ? ` · ${s.events.length} eventos` : ""}
              </div>
            </div>
            {failed ? <Badge tone="red" icon="circle-alert">Error</Badge> : done && <Badge tone="green" icon="check">OK</Badge>}
            <span style={{ fontFamily: "Space Grotesk", fontSize: 10.5, color: "#CBD5E1" }}>{i + 1}/5</span>
          </div>
        );
      })}
    </div>
  );
}

function Gauge({ label, value, target, color, unit }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "Inter", fontSize: 11.5, color: "#68737D" }}>
        <span>{label}</span>
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, color }}>{value}{unit}</span>
      </div>
      <div style={{ height: 7, borderRadius: 9999, background: "#EEF2F6", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${target}%`, background: color, borderRadius: 9999, transition: "width 1.1s cubic-bezier(.4,0,.2,1)" }} />
      </div>
    </div>
  );
}

function Viewport({ phase, typed, shieldOn, generationStatus, backendError }) {
  // phase 0 query | 1 brand | 2 image | 3 code | 4 shield | 5 done
  if (generationStatus === "failed") {
    return (
      <div className="fade-up" style={{ display: "flex", flexDirection: "column", gap: 14, alignItems: "center", justifyContent: "center", height: "100%", textAlign: "center" }}>
        <Badge tone="red" icon="circle-alert">Generación detenida</Badge>
        <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 18, color: "#002B57" }}>El backend no confirmó la generación.</div>
        <div style={{ fontFamily: "Inter", fontSize: 12.5, color: "#EF4444", lineHeight: 1.5, maxWidth: 520 }}>{backendError || "Revisa el detalle de eventos/backend antes de continuar."}</div>
      </div>
    );
  }
  const seg = SEGMENTS.masculino;
  if (phase >= 5) {
    return (
      <div className="fade-up" style={{ display: "flex", flexDirection: "column", gap: 14, alignItems: "center", justifyContent: "center", height: "100%" }}>
        <Badge tone="green" icon="sparkles">Banner generado por backend</Badge>
        <div style={{ width: "100%" }}><Banner seg={seg} variant="A" /></div>
        <div style={{ fontFamily: "Inter", fontSize: 12, color: "#94A3B8" }}>Generación confirmada · abriendo el lienzo…</div>
      </div>
    );
  }
  if (phase === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
        <div style={{ fontFamily: "Space Grotesk", fontSize: 12, color: "#94A3B8", letterSpacing: ".04em" }}>QUERY · catálogo Shopify</div>
        {CATALOG.map((c, i) => (
          <div key={c.sku} className="fade-up" style={{ animationDelay: `${i * 0.18}s`, display: "flex", alignItems: "center", gap: 10, fontFamily: "Space Grotesk", fontSize: 12.5, color: "#002B57", padding: "8px 12px", borderRadius: 9, background: "rgba(248,250,252,0.8)", border: "1px solid #EEF2F6" }}>
            <Icon name="check" size={13} color="#10B981" />
            <span style={{ flex: 1 }}>{c.sku}</span>
            <span style={{ color: "#94A3B8" }}>stock {c.stock}</span>
            <span style={{ color: "#0891B2", fontWeight: 600 }}>${c.sale.toFixed(2)}</span>
          </div>
        ))}
      </div>
    );
  }
  if (phase === 1) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ fontFamily: "Space Grotesk", fontSize: 12, color: "#94A3B8", letterSpacing: ".04em" }}>IDENTIDAD · bloqueando marca</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {BRAND.palette.map((p, i) => (
            <div key={p.hex} className="fade-up" style={{ animationDelay: `${i * 0.12}s`, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <div style={{ width: 52, height: 52, borderRadius: 12, background: p.hex, border: "1px solid rgba(0,0,0,.06)", boxShadow: "0 6px 16px rgba(15,23,42,.12)" }} />
              <span style={{ fontFamily: "Space Grotesk", fontSize: 9.5, color: "#94A3B8" }}>{p.hex}</span>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 9, flexWrap: "wrap" }}>
          {BRAND.fonts.map((f) => <span key={f} style={{ fontFamily: "Inter", fontSize: 11.5, padding: "6px 12px", borderRadius: 9999, background: "rgba(34,211,238,.1)", color: "#0891B2", border: "1px solid rgba(34,211,238,.25)" }}>{f}</span>)}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {BRAND.rules.map((r, i) => (
            <div key={r} className="fade-up" style={{ animationDelay: `${0.3 + i * 0.1}s`, display: "flex", alignItems: "center", gap: 8, fontFamily: "Inter", fontSize: 12, color: "#68737D" }}>
              <Icon name="lock" size={12} color="#0891B2" /> {r}
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (phase === 2) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 12, height: "100%" }}>
        <div style={{ fontFamily: "Space Grotesk", fontSize: 12, color: "#94A3B8", letterSpacing: ".04em" }}>IMAGEN IA · fondo + producto aislado</div>
        <div style={{ position: "relative", flex: 1, minHeight: 220, borderRadius: 14, overflow: "hidden", background: "linear-gradient(120deg,#0A1420,#16314a)" }}>
          <div style={{ position: "absolute", inset: 0, background: "linear-gradient(100deg,transparent 20%,rgba(255,255,255,.18) 45%,transparent 70%)", backgroundSize: "460px 100%", animation: "shimmer 1.3s linear infinite" }} />
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", gap: 18 }}>
            <div style={{ width: 70, height: 135, borderRadius: 12, background: "linear-gradient(160deg,#1b2c43,#0b1622)", border: "1px solid rgba(255,255,255,.14)", boxShadow: "0 0 50px rgba(40,199,240,.4)" }} />
          </div>
          <div style={{ position: "absolute", bottom: 12, left: 14, display: "flex", alignItems: "center", gap: 8, color: "#bcd9ff", fontFamily: "Inter", fontSize: 11.5 }}>
            <Spinner size={13} color="#28C7F0" /> Aislando frasco · sin texto incrustado (capa ligera)
          </div>
        </div>
      </div>
    );
  }
  if (phase === 3) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10, height: "100%" }}>
        <div style={{ fontFamily: "Space Grotesk", fontSize: 12, color: "#94A3B8", letterSpacing: ".04em" }}>COMPILANDO · HTML / Liquid</div>
        <div style={{ flex: 1, borderRadius: 12, background: "#0B1622", padding: "16px 18px", fontFamily: "'Space Grotesk',monospace", fontSize: 12.5, lineHeight: 1.7, color: "#9FE9FB", overflow: "hidden" }}>
          {CODE_LINES.slice(0, typed).map((l, i) => (
            <div key={i} style={{ whiteSpace: "pre", color: l.includes("{{") ? "#E7C76B" : l.match(/<\/?\w/) ? "#9FE9FB" : "#cdd9e3" }}>
              {l}{i === typed - 1 && <span style={{ display: "inline-block", width: 7, height: 14, background: "#28C7F0", marginLeft: 2, verticalAlign: "middle", animation: "caret 1s step-end infinite" }} />}
            </div>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ fontFamily: "Space Grotesk", fontSize: 12, color: "#94A3B8", letterSpacing: ".04em" }}>CORE WEB VITALS · SEO · A11y</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Gauge label="PageSpeed" value={shieldOn ? 98 : 0} target={shieldOn ? 98 : 0} color="#10B981" unit="" />
        <Gauge label="Reducción de peso" value={shieldOn ? 82 : 0} target={shieldOn ? 82 : 0} color="#22D3EE" unit="%" />
        <Gauge label="Contraste WCAG AA" value={shieldOn ? 100 : 0} target={shieldOn ? 100 : 0} color="#8B5CF6" unit="%" />
        <Gauge label="Texto rastreable (SEO)" value={shieldOn ? 100 : 0} target={shieldOn ? 100 : 0} color="#F59E0B" unit="%" />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 12px", borderRadius: 10, background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)" }}>
        <Icon name="shield-check" size={15} color="#10B981" />
        <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#16A34A", fontWeight: 500 }}>alt semántico generado · lazy-load activo · texto vivo en HTML</span>
      </div>
    </div>
  );
}

function GenerateStage({ campaign, placement, art, onNotice, onDone }) {
  const [prototypePhase, setPrototypePhase] = useStateG(0);
  const [typed, setTyped] = useStateG(0);
  const [shieldOn, setShieldOn] = useStateG(false);
  const [backendRun, setBackendRun] = useStateG(null);
  const [backendEvents, setBackendEvents] = useStateG([]);
  const [generationStatus, setGenerationStatus] = useStateG("starting");
  const [backendError, setBackendError] = useStateG(null);
  const [kgContext, setKgContext] = useStateG(null);
  const [artifactStatus, setArtifactStatus] = useStateG(null);
  const [artifactNotice, setArtifactNotice] = useStateG(null);
  const completed = useRefG(false);

  useEffectG(() => {
    let alive = true;
    (async () => {
      setGenerationStatus("starting");
      setBackendError(null);
      setArtifactStatus(null);
      setArtifactNotice(null);
      try {
        const r = await GenerationApi.start(campaign, { placement, art, source: "frontend-generate-stage" });
        if (!alive) return;
        if (r.fallback) {
          setGenerationStatus("prototype");
          onNotice && onNotice({ tone: "amber", text: r.reason || "Generación en modo prototipo local." });
          return;
        }
        let run = r.data;
        setBackendRun(run);
        setGenerationStatus(run && run.status === "succeeded" ? "succeeded" : run && FAILED_STATUSES.includes(run.status) ? "failed" : "running");
        onNotice && onNotice({ tone: "green", text: "Generación iniciada en backend" });

        for (let attempt = 0; alive && attempt < 20; attempt += 1) {
          try {
            const events = await GenerationApi.events(run.id);
            if (!alive) return;
            const rows = Array.isArray(events) ? events : [];
            setBackendEvents(rows);
            const kg = rows.find((event) => event.node_key === "research_best_practices" && event.status === "succeeded");
            setKgContext(kg ? eventSummary(kg) : null);
          } catch (e) {
            if (!alive) return;
            const msg = "No se pudieron cargar eventos de generación: " + textFromError(e);
            setBackendError(msg);
            setGenerationStatus("failed");
            onNotice && onNotice({ tone: "red", text: msg });
            return;
          }

          try {
            const fresh = await GenerationApi.get(run.id);
            if (!alive) return;
            run = fresh || run;
            setBackendRun(run);
          } catch (e) {
            if (!alive) return;
            const msg = "No se pudo refrescar el run de generación: " + textFromError(e);
            setBackendError(msg);
            setGenerationStatus("failed");
            onNotice && onNotice({ tone: "red", text: msg });
            return;
          }

          if (run && TERMINAL_RUN_STATUSES.includes(run.status)) break;
          await new Promise((resolve) => setTimeout(resolve, 1500));
        }

        if (!alive) return;
        if (!run || run.status !== "succeeded") {
          const msg = (run && (run.error_message || `Run finalizó con estado ${run.status}`)) || "El backend no confirmó éxito de generación.";
          setBackendError(msg);
          setGenerationStatus("failed");
          onNotice && onNotice({ tone: "red", text: "Generación backend no completada: " + msg });
          return;
        }

        setGenerationStatus("succeeded");
        const [preview, audit, revisions] = await Promise.allSettled([
          GenerationApi.preview(campaign),
          GenerationApi.audit(campaign),
          GenerationApi.revisions(campaign),
        ]);
        if (!alive) return;
        const normalized = {
          preview: normalizeArtifact(preview),
          audit: normalizeArtifact(audit),
          revisions: normalizeArtifact(revisions),
        };
        if (normalized.revisions.ok && !Array.isArray(normalized.revisions.data)) normalized.revisions = { ok: false, reason: "Respuesta de revisiones inválida" };
        setArtifactStatus({
          preview: normalized.preview.ok,
          previewReason: normalized.preview.reason,
          audit: normalized.audit.ok,
          auditReason: normalized.audit.reason,
          revisions: normalized.revisions.ok ? normalized.revisions.data.length : null,
          revisionsReason: normalized.revisions.reason,
        });
        const failures = [
          normalized.preview.ok ? null : `Preview: ${normalized.preview.reason}`,
          normalized.audit.ok ? null : `Audit: ${normalized.audit.reason}`,
          normalized.revisions.ok ? null : `Revisiones: ${normalized.revisions.reason}`,
        ].filter(Boolean);
        if (failures.length) {
          const notice = "Artefactos fail-closed/no disponibles · " + failures.join(" · ");
          setArtifactNotice(notice);
          onNotice && onNotice({ tone: "amber", text: notice });
        } else {
          onNotice && onNotice({ tone: "green", text: "Generación backend completada con preview, audit y revisiones disponibles" });
        }
      } catch (e) {
        if (!alive) return;
        const msg = "No se pudo iniciar generación backend: " + textFromError(e);
        setBackendError(msg);
        setGenerationStatus("failed");
        onNotice && onNotice({ tone: "red", text: msg });
      }
    })();
    return () => { alive = false; };
  }, []);

  useEffectG(() => {
    if (generationStatus !== "prototype") return undefined;
    if (prototypePhase >= 5) {
      const t = setTimeout(() => { if (!completed.current) { completed.current = true; onDone(); } }, 1500);
      return () => clearTimeout(t);
    }
    let dur = DUR[prototypePhase];
    if (prototypePhase === 3) dur = CODE_LINES.length * 95 + 500;
    const t = setTimeout(() => setPrototypePhase((p) => p + 1), dur);
    return () => clearTimeout(t);
  }, [generationStatus, prototypePhase]);

  const backendSteps = stepsFromBackend(backendRun, backendEvents);
  const backendPhase = phaseFromBackend(backendRun, backendEvents, backendSteps, generationStatus);
  const phase = generationStatus === "prototype" ? prototypePhase : backendPhase;

  useEffectG(() => {
    if (phase === 4) { const s = setTimeout(() => setShieldOn(true), 120); return () => clearTimeout(s); }
    if (phase < 4) setShieldOn(false);
    return undefined;
  }, [phase]);

  useEffectG(() => {
    if (generationStatus !== "succeeded" || phase < 5 || completed.current) return undefined;
    const t = setTimeout(() => { completed.current = true; onDone(); }, 1500);
    return () => clearTimeout(t);
  }, [generationStatus, phase]);

  useEffectG(() => {
    if (phase !== 3) { if (phase < 3) setTyped(0); return undefined; }
    setTyped(0);
    const iv = setInterval(() => setTyped((n) => { if (n >= CODE_LINES.length) { clearInterval(iv); return n; } return n + 1; }), 95);
    return () => clearInterval(iv);
  }, [phase]);

  function continueIfReady() {
    if (generationStatus === "succeeded" || generationStatus === "prototype") {
      completed.current = true;
      onDone();
    }
  }

  const pct = progressPct(backendRun, backendSteps, phase, generationStatus);
  const canContinue = generationStatus === "succeeded" || generationStatus === "prototype";
  const isUuid = typeof isApiCampaign !== "undefined" ? isApiCampaign(campaign) : !!(campaign && campaign.id);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Kicker>Paso 4 de 6 · Generación</Kicker>
          <h2 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 26, color: "#002B57", margin: 0 }}>Construyendo tu banner</h2>
        </div>
        <Button variant="ghost" icon="chevron-right" iconRight="chevron-right" onClick={continueIfReady} disabled={!canContinue} style={{ color: canContinue ? "#68737D" : "#94A3B8" }}>
          {canContinue ? "Continuar al lienzo" : generationStatus === "failed" ? "Backend requerido" : "Esperando backend"}
        </Button>
      </div>

      <div style={{ height: 6, borderRadius: 9999, background: "#EEF2F6", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: generationStatus === "failed" ? "linear-gradient(90deg,#EF4444,#F97316)" : "linear-gradient(90deg,#22D3EE,#0891B2)", borderRadius: 9999, transition: "width .5s ease" }} />
      </div>

      <GlassCard style={{ padding: 14, display: "flex", flexDirection: "column", gap: 9, border: generationStatus === "failed" ? "1px solid rgba(239,68,68,.25)" : "1px solid rgba(34,211,238,.25)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {generationStatus === "failed" ? <Badge tone="red" icon="circle-alert">Backend error</Badge> : generationStatus === "prototype" ? <Badge tone="amber" icon="flask-conical">Prototipo local</Badge> : <Badge tone="green" icon="wifi">Backend conectado</Badge>}
          {backendRun ? <Badge tone="cyan" icon="git-branch">Run {backendRun.id.slice(0, 8)} · {backendRun.status}</Badge> : null}
          {backendEvents.length ? <Badge tone="purple" icon="activity">{backendEvents.length} eventos</Badge> : null}
          {artifactStatus ? <Badge tone="slate" icon="file-check">Preview {artifactStatus.preview ? "OK" : "—"} · Audit {artifactStatus.audit ? "OK" : "—"} · Revs {artifactStatus.revisions == null ? "—" : artifactStatus.revisions}</Badge> : null}
          {!isUuid ? <Badge tone="amber" icon="flask-conical">Campaña no UUID</Badge> : null}
        </div>
        {backendError ? (
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start", fontFamily: "Inter", fontSize: 12, color: "#EF4444", lineHeight: 1.45 }}>
            <Icon name="circle-alert" size={14} color="#EF4444" />
            <span><b>Error visible:</b> {backendError}</span>
          </div>
        ) : null}
        {kgContext ? (
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start", fontFamily: "Inter", fontSize: 12, color: "#475569", lineHeight: 1.45 }}>
            <Icon name="brain-circuit" size={14} color="#7C3AED" />
            <span><b>Contexto usado:</b> {kgContext}</span>
          </div>
        ) : null}
        {artifactNotice ? (
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start", fontFamily: "Inter", fontSize: 12, color: "#B45309", lineHeight: 1.45 }}>
            <Icon name="triangle-alert" size={14} color="#B45309" />
            <span><b>Fail-closed:</b> {artifactNotice}</span>
          </div>
        ) : null}
      </GlassCard>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1.1fr)", gap: 16, alignItems: "stretch" }}>
        <GlassCard style={{ padding: 18 }}><StepRail steps={generationStatus === "prototype" ? PIPELINE.map((step, i) => ({ ...step, key: step.id, backendLabel: "Fallback local", status: prototypePhase > i ? "succeeded" : prototypePhase === i ? "running" : "queued", events: [] })) : backendSteps} phase={phase} status={generationStatus} /></GlassCard>
        <GlassCard style={{ padding: 20, minHeight: 360, display: "flex", flexDirection: "column" }}>
          <Viewport phase={phase} typed={typed} shieldOn={shieldOn} generationStatus={generationStatus} backendError={backendError} />
        </GlassCard>
      </div>
    </div>
  );
}

Object.assign(window, { GenerateStage });
