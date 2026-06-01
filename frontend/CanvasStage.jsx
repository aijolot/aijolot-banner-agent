/* global React, Icon, GlassCard, Button, Badge, Avatar, Kicker, Spinner, Banner,
   ApprovalPanel, CommentsPanel, SEGMENTS, SEGMENT_ORDER, VARIANTS, COMMENTS_SEED, APPROVERS_SEED, ReviewApi */
// Aijolot Banner Agent — Stage 3: collaborative canvas (Modules 4, 6, 7).
const { useState: useStateCV, useRef: useRefCV } = React;

const DEVICES = [
  { id: "desktop", icon: "monitor", w: "100%", label: "1440px" },
  { id: "tablet", icon: "tablet", w: 680, label: "768px" },
  { id: "mobile", icon: "smartphone", w: 360, label: "390px" },
];

let CID = 100;
const ACCENT_MAP = { cyan: "#28C7F0", gold: "#E7C76B", rose: "#F6B3CE" };

function CanvasStage({ campaign, tweaks, placement, art, onNotice, onPublish }) {
  const [variant, setVariant] = useStateCV("A");
  const [segId, setSegId] = useStateCV("masculino");
  const [device, setDevice] = useStateCV("desktop");
  const [comments, setComments] = useStateCV(() => COMMENTS_SEED.map((c) => ({ ...c })));
  const [approvers, setApprovers] = useStateCV(() => APPROVERS_SEED.map((a) => ({ ...a })));
  const [commentMode, setCommentMode] = useStateCV(false);
  const [editingId, setEditingId] = useStateCV(null);
  const [applied, setApplied] = useStateCV({ brighter: false, ctaContrast: false });
  const [refining, setRefining] = useStateCV(false);
  const [refineMsg, setRefineMsg] = useStateCV("");
  const [refineInput, setRefineInput] = useStateCV("");
  const [published, setPublished] = useStateCV(false);
  const [scheduled, setScheduled] = useStateCV(false);
  const stageRef = useRefCV(null);

  const seg = SEGMENTS[segId];
  const approvedCount = approvers.filter((a) => a.status === "approved").length;
  const allApproved = approvedCount === approvers.length;
  const missing = approvers.length - approvedCount;
  const dev = DEVICES.find((d) => d.id === device);
  const gridLayout = (placement && placement.layout) || { cols: [{ rows: 1, w: 1 }] };
  const cellCount = layoutCells(gridLayout);
  const locked = tweaks.lockLayout && tweaks.lockLayout !== "auto";
  const layoutVariant = locked ? tweaks.lockLayout : variant;
  const bannerAccent = tweaks.bannerAccent && tweaks.bannerAccent !== "auto" ? ACCENT_MAP[tweaks.bannerAccent] : undefined;

  async function setApprover(id, status) {
    setApprovers((arr) => arr.map((a) => a.id === id ? { ...a, status, note: status === "approved" ? "Aprobado." : "Solicita ajustes." } : a));
    try {
      const r = await ReviewApi.approveLocal(campaign, id, status);
      onNotice && onNotice(r.fallback ? { tone: "amber", text: r.reason } : { tone: "green", text: "Aprobación guardada en backend" });
    } catch (e) {
      onNotice && onNotice({ tone: "amber", text: "No se pudo sincronizar aprobación: " + (e.message || e.status || "error") });
    }
  }
  function resolveComment(id) { setComments((arr) => arr.map((c) => c.id === id ? { ...c, resolved: true } : c)); }

  function addComment(e) {
    if (!commentMode || !stageRef.current) return;
    const r = stageRef.current.getBoundingClientRect();
    const x = Math.round(((e.clientX - r.left) / r.width) * 100);
    const y = Math.round(((e.clientY - r.top) / r.height) * 100);
    const id = "c" + (CID++);
    setComments((arr) => [...arr, { id, x, y, author: "Mara Voss", initials: "MV", grad: "linear-gradient(135deg,#F72585,#8B5CF6)", text: "", resolved: false, time: "ahora", _new: true }]);
    setEditingId(id);
    setCommentMode(false);
  }
  function saveDraft(id, text) {
    setComments((arr) => arr.map((c) => c.id === id ? { ...c, text, _new: false } : c));
    setEditingId(null);
  }
  function cancelDraft(id) {
    setComments((arr) => arr.filter((c) => !(c.id === id && c._new)));
    setEditingId(null);
  }

  function refine(text) {
    if (refining) return;
    const t = text.toLowerCase();
    setRefining(true);
    setRefineInput("");
    setTimeout(() => {
      const next = { ...applied };
      const acks = [];
      if (/bril|luz|clar|ilumin/.test(t)) { next.brighter = true; acks.push("subí el brillo del fondo"); }
      if (/bot|cta|contrast|resalt/.test(t)) { next.ctaContrast = true; acks.push("cambié el botón a color contraste"); }
      if (/oscur|sobrio/.test(t)) { next.brighter = false; acks.push("oscurecí el fondo"); }
      setApplied(next);
      // resolve any comment the instruction addresses
      setComments((arr) => arr.map((c) => {
        const ct = c.text.toLowerCase();
        if (!c.resolved && ((/bril|luz/.test(t) && /bril|luz/.test(ct)) || (/bot|cta|contrast|resalt/.test(t) && /bot|cta|contrast|resalt/.test(ct)))) return { ...c, resolved: true };
        return c;
      }));
      setRefineMsg(acks.length ? "Listo: " + acks.join(" y ") + "." : "Apliqué el ajuste y recompilé el banner.");
      setRefining(false);
    }, 1500);
  }

  async function publish() {
    let canAdvance = false;
    try {
      const r = await ReviewApi.publish(campaign);
      onNotice && onNotice(r.fallback ? { tone: "amber", text: r.reason } : { tone: "green", text: "Publicación enviada al backend" });
      canAdvance = true;
    } catch (e) {
      onNotice && onNotice({ tone: "amber", text: "Backend no publicó aún: " + (e.message || e.status || "error") });
    }
    if (canAdvance) { setScheduled(false); setPublished(true); setTimeout(() => onPublish && onPublish(), 950); }
  }
  async function schedule(s) {
    let accepted = false;
    try {
      const r = await ReviewApi.schedule(campaign, s);
      onNotice && onNotice(r.fallback ? { tone: "amber", text: r.reason } : { tone: "green", text: "Agenda guardada en backend" });
      accepted = true;
    } catch (e) {
      onNotice && onNotice({ tone: "amber", text: "Backend no aceptó la agenda: " + (e.message || e.status || "error") });
    }
    if (accepted) setScheduled(true);
  }

  const TabBtn = ({ active, onClick, children, title }) => (
    <button onClick={onClick} title={title} style={{
      display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "Inter", fontSize: 12.5, fontWeight: 600,
      padding: "7px 12px", borderRadius: 9, cursor: "pointer", whiteSpace: "nowrap",
      border: `1px solid ${active ? "rgba(34,211,238,.5)" : "transparent"}`,
      background: active ? "rgba(34,211,238,.14)" : "transparent", color: active ? "#0891B2" : "#68737D",
      transition: "background .15s",
    }}>{children}</button>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Kicker>Paso 5 de 6 · Lienzo colaborativo</Kicker>
          <h2 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 26, color: "#002B57", margin: 0 }}>Revisa, comenta y aprueba</h2>
        </div>
        <Badge tone="cyan" icon="git-branch">3 variantes · 3 segmentos</Badge>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.7fr) minmax(300px,1fr)", gap: 16, alignItems: "start" }}>
        {/* MAIN */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* toolbar */}
          <GlassCard style={{ padding: 10, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <div style={{ display: "flex", gap: 2, background: "rgba(248,250,252,0.8)", borderRadius: 11, padding: 3 }}>
              {VARIANTS.map((v) => (
                <TabBtn key={v.id} active={layoutVariant === v.id} onClick={() => !locked && setVariant(v.id)} title={locked ? "Layout fijado en Tweaks" : v.desc}>
                  {v.id === "A" ? "Spotlight" : v.id === "B" ? "Split" : "Minimal"}
                  {v.recommended && layoutVariant === v.id && <Icon name="sparkles" size={12} />}
                </TabBtn>
              ))}
            </div>
            <div style={{ flex: 1 }} />
            <div style={{ display: "flex", gap: 2, background: "rgba(248,250,252,0.8)", borderRadius: 11, padding: 3 }}>
              {DEVICES.map((d) => (
                <TabBtn key={d.id} active={device === d.id} onClick={() => setDevice(d.id)} title={d.label}><Icon name={d.icon} size={15} /></TabBtn>
              ))}
            </div>
          </GlassCard>

          {/* banner stage */}
          <GlassCard style={{ padding: 22, display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
            background: "rgba(255,255,255,0.55)",
            backgroundImage: "radial-gradient(rgba(148,163,184,.18) 1px, transparent 1px)", backgroundSize: "18px 18px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, alignSelf: "stretch", justifyContent: "center", fontFamily: "Space Grotesk", fontSize: 11, color: "#94A3B8" }}>
              <Icon name={dev.icon} size={13} /> {dev.label} · {VARIANTS.find((v) => v.id === layoutVariant).name}{placement ? ` · ${placement.name}` : ""}{cellCount > 1 ? ` · ${gridLayout.cols.length} col / ${cellCount} celdas` : ""}{art ? ` · ${art.fold}% sobre el pliegue` : ""}
            </div>
            <div style={{ width: dev.w, maxWidth: "100%", transition: "width .35s ease" }}>
              <div ref={stageRef} onClick={addComment} style={{ position: "relative", cursor: commentMode ? "crosshair" : "default" }}>
                {cellCount > 1 ? (
                  <BannerLayout layout={gridLayout} gap={12} cell={(i) => (
                    <Banner key={i} seg={seg} variant={layoutVariant} slot={i === 0} font={tweaks.bannerFont} accent={bannerAccent}
                      brighter={applied.brighter} ctaContrast={applied.ctaContrast} idSuffix={"-cv" + i} />
                  )} />
                ) : (
                  <Banner seg={seg} variant={layoutVariant} slot font={tweaks.bannerFont} accent={bannerAccent}
                    brighter={applied.brighter} ctaContrast={applied.ctaContrast} idSuffix={"-cv"} />
                )}

                {/* refine shimmer overlay */}
                {refining && (
                  <div style={{ position: "absolute", inset: 0, borderRadius: 18, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(10,20,32,.35)", backdropFilter: "blur(2px)", zIndex: 20 }}>
                    <div style={{ position: "absolute", inset: 0, background: "linear-gradient(100deg,transparent 30%,rgba(40,199,240,.25) 50%,transparent 70%)", backgroundSize: "500px 100%", animation: "shimmer 1.2s linear infinite" }} />
                    <div style={{ display: "flex", alignItems: "center", gap: 9, background: "rgba(255,255,255,.92)", borderRadius: 9999, padding: "9px 16px", zIndex: 2 }}>
                      <Spinner size={15} /><span style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#0891B2" }}>El agente está refinando…</span>
                    </div>
                  </div>
                )}

                {/* comment pins */}
                {comments.map((c, i) => (
                  <div key={c.id} title={c.text} style={{ position: "absolute", left: `${c.x}%`, top: `${c.y}%`, transform: "translate(-50%,-50%)", zIndex: 15 }}>
                    <div style={{ position: "relative", width: 26, height: 26, borderRadius: "50% 50% 50% 2px", background: c.resolved ? "#94A3B8" : "#fff", border: `2px solid ${c.resolved ? "#CBD5E1" : "#22D3EE"}`, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 6px 14px rgba(15,23,42,.25)", cursor: "pointer" }}>
                      <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 12, color: c.resolved ? "#fff" : "#0891B2" }}>{i + 1}</span>
                      {c.id === editingId && <span style={{ position: "absolute", inset: -6, borderRadius: "50%", border: "2px solid #22D3EE", animation: "ringGrow 1.4s ease-out infinite" }} />}
                    </div>
                  </div>
                ))}
                {commentMode && (
                  <div style={{ position: "absolute", top: 10, left: "50%", transform: "translateX(-50%)", zIndex: 16, background: "rgba(0,43,87,.9)", color: "#fff", fontFamily: "Inter", fontSize: 11.5, padding: "5px 12px", borderRadius: 9999 }}>
                    Toca el banner para anclar un comentario
                  </div>
                )}
              </div>
            </div>
          </GlassCard>

          {/* segment personalization */}
          <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Icon name="users-round" size={15} color="#0891B2" />
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 14, color: "#002B57" }}>Hiper-personalización · Customer Tags</span>
              <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8", marginLeft: "auto" }}>{seg.audience}</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10 }}>
              {SEGMENT_ORDER.map((id) => {
                const s = SEGMENTS[id]; const on = segId === id;
                return (
                  <button key={id} onClick={() => setSegId(id)} style={{
                    display: "flex", alignItems: "center", gap: 10, padding: "11px 13px", borderRadius: 12, cursor: "pointer", textAlign: "left",
                    border: `1.5px solid ${on ? "#22D3EE" : "#EEF2F6"}`, background: on ? "rgba(34,211,238,.08)" : "rgba(248,250,252,0.7)", transition: "all .15s",
                  }}>
                    <div style={{ width: 30, height: 30, borderRadius: 8, flexShrink: 0, background: `linear-gradient(150deg,${s.palette.bgB},${s.palette.bgA})`, display: "flex", alignItems: "center", justifyContent: "center", color: s.palette.cap }}>
                      <Icon name={s.icon} size={15} />
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#002B57" }}>{s.label.split(": ")[1] || s.label}</div>
                      <div style={{ fontFamily: "Space Grotesk", fontSize: 10, color: "#94A3B8" }}>{s.tag}</div>
                    </div>
                  </button>
                );
              })}
            </div>
            <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#68737D", display: "flex", alignItems: "center", gap: 6 }}>
              <Icon name="info" size={12} color="#94A3B8" /> Una sola campaña, variantes invisibles que el agente sirve según el tag del cliente.
            </div>
          </GlassCard>

          {/* refinement loop */}
          <GlassCard style={{ padding: 16, display: "flex", flexDirection: "column", gap: 11 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 28, height: 28, borderRadius: 9, background: "linear-gradient(135deg,#22D3EE,#0891B2)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff" }}><Icon name="wand-sparkles" size={15} /></div>
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 14, color: "#002B57" }}>Refinar con el agente</span>
              {refineMsg && !refining && <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "Inter", fontSize: 11.5, color: "#16A34A", fontWeight: 500 }}><Icon name="check" size={13} /> {refineMsg}</span>}
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", background: "rgba(241,245,249,0.6)", border: "1px solid #E2E8F0", borderRadius: 12, padding: 7 }}>
              <input value={refineInput} onChange={(e) => setRefineInput(e.target.value)} disabled={refining}
                onKeyDown={(e) => { if (e.key === "Enter" && refineInput.trim()) refine(refineInput); }}
                placeholder="Ej: haz el fondo más brillante, cambia el tono del botón…"
                style={{ flex: 1, border: "none", outline: "none", background: "transparent", fontFamily: "Inter", fontSize: 13, color: "#002B57", padding: "6px 8px" }} />
              <Button variant="default" icon="send" onClick={() => refineInput.trim() && refine(refineInput)} disabled={refining || !refineInput.trim()} style={{ padding: "9px 13px" }} />
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {["Haz el fondo más brillante", "Botón en color contraste"].map((s) => (
                <button key={s} onClick={() => refine(s)} disabled={refining} style={{ fontFamily: "Inter", fontSize: 11.5, padding: "6px 12px", borderRadius: 9999, border: "1px solid #E2E8F0", background: "#fff", color: "#0891B2", cursor: refining ? "default" : "pointer" }}>+ {s}</button>
              ))}
            </div>
          </GlassCard>
        </div>

        {/* RIGHT */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <ApprovalPanel approvers={approvers} onSet={setApprover} published={published} />
          <PublishPanel allApproved={allApproved} missing={missing} published={published} scheduled={scheduled}
            onPublishNow={publish} onSchedule={schedule} onEditSchedule={() => setScheduled(false)} onView={() => onPublish && onPublish()} />
          <CommentsPanel comments={comments} onResolve={resolveComment} commentMode={commentMode} setCommentMode={setCommentMode}
            editingId={editingId} onSaveDraft={saveDraft} onCancelDraft={cancelDraft} />
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { CanvasStage });
