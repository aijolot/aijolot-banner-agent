/* global React, Icon, GlassCard, Button, Badge, Avatar, Spinner */
// Aijolot Banner Agent — Canvas side panels: approval governance + comments.
const { useState: useStateCP, useRef: useRefCP, useEffect: useEffectCP } = React;

const STATUS_META = {
  approved: { tone: "green", label: "Aprobado", icon: "check" },
  pending: { tone: "amber", label: "Pendiente", icon: "clock" },
  changes: { tone: "pink", label: "Cambios", icon: "rotate-ccw" },
};

function ApprovalPanel({ approvers, onSet, published, mode = "local", threadStatus }) {
  const approved = approvers.filter((a) => a.status === "approved").length;
  const all = approved === approvers.length;
  return (
    <GlassCard style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <Icon name="shield-check" size={17} color="#0891B2" />
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>Aprobaciones</span>
        <Badge tone={mode === "backend" ? "green" : "amber"} icon={mode === "backend" ? "database" : "flask-conical"}>{mode === "backend" ? `Backend ${threadStatus || "open"}` : "Locales/prototipo"}</Badge>
        <span style={{ marginLeft: "auto", fontFamily: "Space Grotesk", fontSize: 12.5, fontWeight: 600, color: all ? "#16A34A" : "#B45309" }}>{approved}/{approvers.length}</span>
      </div>
      <div style={{ height: 6, borderRadius: 9999, background: "#EEF2F6", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${(approved / approvers.length) * 100}%`, background: all ? "#10B981" : "linear-gradient(90deg,#22D3EE,#0891B2)", borderRadius: 9999, transition: "width .4s ease" }} />
      </div>

      {mode !== "backend" && (
        <div style={{ display: "flex", alignItems: "flex-start", gap: 7, padding: "9px 11px", borderRadius: 10, background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.25)", fontFamily: "Inter", fontSize: 11.5, color: "#B45309", lineHeight: 1.35 }}>
          <Icon name="triangle-alert" size={13} />
          <span>Estas aprobaciones son locales/prototipo. No habilitan programación ni publicación backend hasta que exista hilo aprobado en backend.</span>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {approvers.map((a) => {
          const m = STATUS_META[a.status];
          return (
            <div key={a.id} style={{ display: "flex", alignItems: "flex-start", gap: 11 }}>
              <Avatar initials={a.initials} gradient={a.grad} size={34} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontFamily: "Inter", fontSize: 13, fontWeight: 600, color: "#002B57" }}>{a.name}</span>
                  <Badge tone={m.tone} icon={m.icon}>{m.label}</Badge>
                </div>
                <div style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8", marginTop: 1 }}>{a.role}</div>
                {a.note && <div style={{ fontFamily: "Inter", fontSize: 12, color: "#68737D", marginTop: 5, fontStyle: "italic" }}>“{a.note}”</div>}
                {a.status !== "approved" && !published && (
                  <div style={{ display: "flex", gap: 7, marginTop: 8 }}>
                    <button onClick={() => onSet(a.id, "approved")} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "Inter", fontSize: 11.5, fontWeight: 600, padding: "5px 11px", borderRadius: 8, border: "1px solid rgba(16,185,129,.4)", background: "rgba(16,185,129,.08)", color: "#16A34A", cursor: "pointer" }}>
                      <Icon name="check" size={12} /> Aprobar
                    </button>
                    {a.status !== "changes" && (
                      <button onClick={() => onSet(a.id, "changes")} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "Inter", fontSize: 11.5, fontWeight: 600, padding: "5px 11px", borderRadius: 8, border: "1px solid #E2E8F0", background: "#fff", color: "#68737D", cursor: "pointer" }}>
                        <Icon name="rotate-ccw" size={12} /> Cambios
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}

function CommentsPanel({ comments, onResolve, commentMode, setCommentMode, editingId, onSaveDraft, onCancelDraft }) {
  const open = comments.filter((c) => !c.resolved).length;
  const inputRef = useRefCP(null);
  useEffectCP(() => { if (editingId && inputRef.current) inputRef.current.focus(); }, [editingId]);
  const [draftText, setDraftText] = useStateCP("");
  useEffectCP(() => { setDraftText(""); }, [editingId]);

  return (
    <GlassCard style={{ padding: 20, display: "flex", flexDirection: "column", gap: 13 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <Icon name="message-square" size={16} color="#0891B2" />
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>Comentarios</span>
        <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>{open} abiertos</span>
        <button onClick={() => setCommentMode(!commentMode)} style={{
          marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "Inter", fontSize: 11.5, fontWeight: 600,
          padding: "6px 11px", borderRadius: 8, cursor: "pointer",
          border: `1px solid ${commentMode ? "rgba(34,211,238,.5)" : "#E2E8F0"}`,
          background: commentMode ? "rgba(34,211,238,.12)" : "#fff", color: commentMode ? "#0891B2" : "#68737D",
        }}>
          <Icon name="message-square-plus" size={13} /> {commentMode ? "Toca el banner…" : "Comentar"}
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxHeight: 290, overflowY: "auto" }}>
        {comments.length === 0 && <div style={{ fontFamily: "Inter", fontSize: 12.5, color: "#94A3B8", padding: "10px 0" }}>Sin comentarios. Activa “Comentar” y toca el banner para anclar uno.</div>}
        {comments.map((c, i) => (
          <div key={c.id} style={{ display: "flex", gap: 10, opacity: c.resolved ? 0.55 : 1 }}>
            <div style={{ width: 22, height: 22, borderRadius: 9999, flexShrink: 0, background: c.resolved ? "#CBD5E1" : "#22D3EE", color: "#06121f", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 11 }}>{i + 1}</div>
            <div style={{ flex: 1, minWidth: 0, background: "rgba(248,250,252,0.8)", border: "1px solid #EEF2F6", borderRadius: 11, padding: "9px 11px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <Avatar initials={c.initials} gradient={c.grad} size={20} />
                <span style={{ fontFamily: "Inter", fontSize: 12, fontWeight: 600, color: "#002B57" }}>{c.author}</span>
                <span style={{ fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8" }}>{c.time}</span>
                {!c.resolved && c.id !== editingId && (
                  <button onClick={() => onResolve(c.id)} title="Resolver" style={{ marginLeft: "auto", border: "none", background: "transparent", cursor: "pointer", color: "#94A3B8", display: "inline-flex" }}><Icon name="check" size={14} /></button>
                )}
                {c.resolved && <span style={{ marginLeft: "auto", display: "inline-flex" }}><Badge tone="green">Resuelto</Badge></span>}
              </div>
              {c.id === editingId ? (
                <div style={{ marginTop: 8 }}>
                  <textarea ref={inputRef} rows={2} value={draftText} onChange={(e) => setDraftText(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (draftText.trim()) onSaveDraft(c.id, draftText.trim()); } }}
                    placeholder="Escribe tu comentario…"
                    style={{ width: "100%", border: "1px solid #E2E8F0", borderRadius: 8, padding: "7px 9px", fontFamily: "Inter", fontSize: 12.5, color: "#002B57", outline: "none", resize: "none" }} />
                  <div style={{ display: "flex", gap: 7, marginTop: 7 }}>
                    <Button variant="default" onClick={() => draftText.trim() && onSaveDraft(c.id, draftText.trim())} disabled={!draftText.trim()} style={{ padding: "6px 12px", fontSize: 12 }}>Comentar</Button>
                    <Button variant="ghost" onClick={() => onCancelDraft(c.id)} style={{ padding: "6px 10px", fontSize: 12 }}>Cancelar</Button>
                  </div>
                </div>
              ) : (
                <p style={{ fontFamily: "Inter", fontSize: 12.5, color: "#475569", margin: "6px 0 0", lineHeight: 1.45, textDecoration: c.resolved ? "line-through" : "none" }}>{c.text}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

function fmtDT(v) {
  if (!v) return "—";
  const d = new Date(v);
  const M = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const hh = String(d.getHours()).padStart(2, "0"), mm = String(d.getMinutes()).padStart(2, "0");
  return `${d.getDate()} ${M[d.getMonth()]} · ${hh}:${mm}`;
}
function relTime(v) {
  if (!v) return "";
  const ms = new Date(v).getTime() - Date.now();
  if (ms <= 0) return "ahora";
  const d = Math.floor(ms / 86400000), h = Math.floor((ms % 86400000) / 3600000);
  if (d > 0) return `en ${d} día${d > 1 ? "s" : ""}`;
  if (h > 0) return `en ${h} h`;
  return "en breve";
}

function MiniSwitch({ on, onToggle, disabled }) {
  return (
    <button onClick={() => !disabled && onToggle(!on)} disabled={disabled} style={{
      width: 38, height: 22, borderRadius: 9999, border: "none", cursor: disabled ? "not-allowed" : "pointer", flexShrink: 0,
      background: on ? "#22D3EE" : "#CBD5E1", position: "relative", transition: "background .2s", opacity: disabled ? 0.5 : 1, padding: 0,
    }}>
      <span style={{ position: "absolute", top: 2, left: on ? 18 : 2, width: 18, height: 18, borderRadius: 9999, background: "#fff", transition: "left .2s", boxShadow: "0 1px 3px rgba(0,0,0,.25)" }} />
    </button>
  );
}

const pad2 = (n) => String(n).padStart(2, "0");
const toVal = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
function defaultScheduleWindow(now = new Date()) {
  const start = new Date(now.getTime() + 60 * 60 * 1000);
  const end = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  return { start: toVal(start), end: toVal(end) };
}
function scheduleDateError(start, end, auto) {
  const startAt = new Date(start);
  const endAt = auto && end ? new Date(end) : null;
  if (!start || Number.isNaN(startAt.getTime())) return "El inicio de programación no es válido.";
  if (startAt.getTime() <= Date.now()) return "El inicio debe estar en el futuro.";
  if (auto) {
    if (!end || !endAt || Number.isNaN(endAt.getTime())) return "El fin de programación no es válido.";
    if (endAt.getTime() <= startAt.getTime()) return "El fin debe ser posterior al inicio.";
  }
  return "";
}
const MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const WD_ES = ["L", "M", "X", "J", "V", "S", "D"];

function TimeStepper({ value, onStep }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4, background: "#fff", border: "1px solid #E2E8F0", borderRadius: 8, padding: "3px 4px 3px 8px" }}>
      <span style={{ fontFamily: "Space Grotesk", fontSize: 15, fontWeight: 600, color: "#002B57", fontVariantNumeric: "tabular-nums", minWidth: 20, textAlign: "center" }}>{pad2(value)}</span>
      <div style={{ display: "flex", flexDirection: "column" }}>
        {["up", "down"].map((dir) => (
          <button key={dir} onMouseDown={(e) => { e.preventDefault(); onStep(dir === "up" ? 1 : -1); }} style={{ border: "none", background: "transparent", cursor: "pointer", color: "#94A3B8", padding: 0, height: 12, display: "flex", alignItems: "center" }}>
            <Icon name={dir === "up" ? "chevron-up" : "chevron-down"} size={13} />
          </button>
        ))}
      </div>
    </div>
  );
}

function DateField({ label, value, onChange, disabled, align = "left" }) {
  const [open, setOpen] = useStateCP(false);
  const d = new Date(value);
  const [view, setView] = useStateCP(new Date(d.getFullYear(), d.getMonth(), 1));
  const ref = useRefCP(null);
  useEffectCP(() => {
    if (!open) return;
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  function toggle() { if (disabled) return; setView(new Date(d.getFullYear(), d.getMonth(), 1)); setOpen((o) => !o); }
  function pickDay(day) { const nd = new Date(d); nd.setFullYear(view.getFullYear(), view.getMonth(), day); onChange(toVal(nd)); }
  function stepH(delta) { const nd = new Date(d); nd.setHours((d.getHours() + delta + 24) % 24); onChange(toVal(nd)); }
  function stepM(delta) { const nd = new Date(d); nd.setMinutes((Math.round(d.getMinutes() / 5) * 5 + delta * 5 + 60) % 60); onChange(toVal(nd)); }
  function shiftMonth(delta) { setView((v) => new Date(v.getFullYear(), v.getMonth() + delta, 1)); }

  const startWd = (new Date(view.getFullYear(), view.getMonth(), 1).getDay() + 6) % 7;
  const dim = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startWd; i++) cells.push(null);
  for (let dd = 1; dd <= dim; dd++) cells.push(dd);
  const today = new Date();
  const same = (a, b, dd) => dd && a.getFullYear() === view.getFullYear() && a.getMonth() === view.getMonth() && a.getDate() === dd;

  return (
    <div ref={ref} style={{ position: "relative", flex: 1, minWidth: 0 }}>
      <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, color: "#68737D", display: "block", marginBottom: 5 }}>{label}</span>
      <button onClick={toggle} disabled={disabled} style={{
        width: "100%", display: "flex", alignItems: "center", gap: 8, cursor: disabled ? "not-allowed" : "pointer",
        border: `1px solid ${open ? "rgba(34,211,238,.5)" : "#E2E8F0"}`, borderRadius: 9, padding: "8px 10px",
        background: disabled ? "#F8FAFC" : "#fff", opacity: disabled ? 0.6 : 1,
      }}>
        <Icon name="calendar" size={14} color="#0891B2" />
        <span style={{ fontFamily: "Space Grotesk", fontSize: 12.5, fontWeight: 600, color: "#002B57", fontVariantNumeric: "tabular-nums" }}>{fmtDT(value)}</span>
        <Icon name="chevron-down" size={13} color="#94A3B8" style={{ marginLeft: "auto" }} />
      </button>

      {open && (
        <GlassCard radius={14} style={{ position: "absolute", top: "calc(100% + 6px)", [align]: 0, zIndex: 60, width: 252, padding: 12, background: "rgba(255,255,255,0.96)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <button onMouseDown={(e) => { e.preventDefault(); shiftMonth(-1); }} style={{ border: "none", background: "rgba(248,250,252,0.9)", borderRadius: 8, width: 26, height: 26, cursor: "pointer", color: "#68737D", display: "flex", alignItems: "center", justifyContent: "center" }}><Icon name="chevron-left" size={15} /></button>
            <span style={{ fontFamily: "Space Grotesk", fontSize: 13.5, fontWeight: 600, color: "#002B57", textTransform: "capitalize" }}>{MONTHS_ES[view.getMonth()]} {view.getFullYear()}</span>
            <button onMouseDown={(e) => { e.preventDefault(); shiftMonth(1); }} style={{ border: "none", background: "rgba(248,250,252,0.9)", borderRadius: 8, width: 26, height: 26, cursor: "pointer", color: "#68737D", display: "flex", alignItems: "center", justifyContent: "center" }}><Icon name="chevron-right" size={15} /></button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 2, marginBottom: 4 }}>
            {WD_ES.map((w, i) => <span key={i} style={{ fontFamily: "Inter", fontSize: 10, fontWeight: 600, color: "#94A3B8", textAlign: "center", padding: "2px 0" }}>{w}</span>)}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 2 }}>
            {cells.map((dd, i) => {
              const sel = same(d, null, dd), tod = same(today, null, dd);
              return (
                <button key={i} disabled={!dd} onMouseDown={(e) => { e.preventDefault(); if (dd) pickDay(dd); }} style={{
                  height: 28, borderRadius: 8, border: tod && !sel ? "1px solid #22D3EE" : "1px solid transparent", cursor: dd ? "pointer" : "default",
                  background: sel ? "#22D3EE" : "transparent", color: sel ? "#06121f" : dd ? "#334155" : "transparent",
                  fontFamily: "Space Grotesk", fontSize: 12, fontWeight: sel ? 700 : 500, fontVariantNumeric: "tabular-nums",
                }}
                  onMouseEnter={(e) => { if (dd && !sel) e.currentTarget.style.background = "rgba(34,211,238,.1)"; }}
                  onMouseLeave={(e) => { if (dd && !sel) e.currentTarget.style.background = "transparent"; }}>
                  {dd || ""}
                </button>
              );
            })}
          </div>
          <div style={{ borderTop: "1px solid #EEF2F6", marginTop: 10, paddingTop: 10, display: "flex", alignItems: "center", gap: 9 }}>
            <span style={{ fontFamily: "Inter", fontSize: 11.5, fontWeight: 600, color: "#68737D", display: "inline-flex", alignItems: "center", gap: 5 }}><Icon name="clock" size={13} color="#0891B2" /> Hora</span>
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 5 }}>
              <TimeStepper value={d.getHours()} onStep={stepH} />
              <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, color: "#94A3B8" }}>:</span>
              <TimeStepper value={d.getMinutes()} onStep={stepM} />
            </div>
          </div>
        </GlassCard>
      )}
    </div>
  );
}

function PublishPanel({ allApproved, missing, published, scheduled, dryRun = false, onPublishNow, onSchedule, onEditSchedule, onView,
  backendScheduleReady = false, backendPublishReady = false, scheduleGuardReason = "", publishGuardReason = "",
  approvalMode = "local", backendStatus = "draft" }) {
  const [mode, setMode] = useStateCP("schedule");
  const initialWindow = defaultScheduleWindow();
  const [start, setStart] = useStateCP(initialWindow.start);
  const [end, setEnd] = useStateCP(initialWindow.end);
  const [auto, setAuto] = useStateCP(true);
  const scheduleError = mode === "schedule" ? scheduleDateError(start, end, auto) : "";
  const activeReady = mode === "now" ? backendPublishReady : backendScheduleReady && !scheduleError;
  const activeReason = mode === "now" ? publishGuardReason : (scheduleError || scheduleGuardReason);
  const primaryLabel = !activeReady
    ? (mode === "now" ? "Publicación backend no disponible" : "Programación bloqueada")
    : mode === "now" ? "Simular publicación / dry-run" : "Programar publicación";
  const primaryIcon = activeReady ? (mode === "now" ? "rocket" : "calendar-check") : "lock";

  return (
    <GlassCard style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <Icon name="calendar-clock" size={17} color="#0891B2" />
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>Publicación y agenda</span>
        {scheduled && !published && <span style={{ marginLeft: "auto" }}><Badge tone="purple" icon="clock">Programada</Badge></span>}
        {published && <span style={{ marginLeft: "auto" }}><Badge tone={dryRun ? "cyan" : "green"} icon="check">{dryRun ? "Dry-run" : "En vivo"}</Badge></span>}
      </div>
      {!published && !scheduled && (
        <div style={{ display: "flex", alignItems: "flex-start", gap: 7, padding: "9px 11px", borderRadius: 10, background: activeReady ? "rgba(16,185,129,0.08)" : "rgba(245,158,11,0.08)", border: `1px solid ${activeReady ? "rgba(16,185,129,0.25)" : "rgba(245,158,11,0.25)"}`, fontFamily: "Inter", fontSize: 11.5, color: activeReady ? "#16A34A" : "#B45309", lineHeight: 1.35 }}>
          <Icon name={activeReady ? "shield-check" : "triangle-alert"} size={13} />
          <span>{activeReady ? `Guardrails backend OK · estado ${backendStatus}` : (activeReason || `Guardrails backend pendientes · estado ${backendStatus} · aprobaciones ${approvalMode}`)}</span>
        </div>
      )}

      {published ? (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "11px 13px", borderRadius: 10, background: dryRun ? "rgba(34,211,238,0.1)" : "rgba(16,185,129,0.1)", border: `1px solid ${dryRun ? "rgba(34,211,238,0.3)" : "rgba(16,185,129,0.3)"}` }}>
            <Icon name="check-circle-2" size={16} color={dryRun ? "#0891B2" : "#10B981"} />
            <span style={{ fontFamily: "Inter", fontSize: 12.5, color: dryRun ? "#0891B2" : "#16A34A", fontWeight: 600 }}>{dryRun ? "Simulación de publicación / dry-run · sin mutación live Shopify" : "Publicado en Shopify · ahora"}</span>
          </div>
          <Button variant="secondary" icon="bar-chart-3" onClick={onView} style={{ justifyContent: "center" }}>Ver performance</Button>
        </>
      ) : scheduled ? (
        <>
          {/* timeline */}
          <div style={{ display: "flex", alignItems: "center", gap: 0, padding: "4px 2px" }}>
            {[{ t: "Hoy", s: "—", c: "#22D3EE", solid: true }, { t: "Publica", s: fmtDT(start), c: "#10B981", solid: true }, auto ? { t: "Despublica", s: fmtDT(end), c: "#F59E0B", solid: true } : null].filter(Boolean).map((n, i, arr) => (
              <React.Fragment key={n.t}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 5, flexShrink: 0 }}>
                  <span style={{ width: 11, height: 11, borderRadius: 9999, background: n.c, boxShadow: `0 0 0 3px ${n.c}22` }} />
                  <span style={{ fontFamily: "Inter", fontSize: 10.5, fontWeight: 600, color: "#475569" }}>{n.t}</span>
                  <span style={{ fontFamily: "Space Grotesk", fontSize: 9.5, color: "#94A3B8", whiteSpace: "nowrap" }}>{n.s}</span>
                </div>
                {i < arr.length - 1 && <span style={{ flex: 1, height: 2, background: "linear-gradient(90deg,#CBD5E1,#E2E8F0)", margin: "0 6px", marginBottom: 26 }} />}
              </React.Fragment>
            ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 12px", borderRadius: 10, background: "rgba(139,92,246,0.08)", border: "1px solid rgba(139,92,246,0.22)" }}>
            <Icon name="zap" size={14} color="#7C3AED" />
            <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#6D28D9", fontWeight: 500 }}>
              Auto-publica {relTime(start)}{auto ? ` · auto-despublica el ${fmtDT(end).split(" ·")[0]}` : ""}
            </span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="outline" icon="pencil" onClick={onEditSchedule} style={{ flex: 1, justifyContent: "center" }}>Editar agenda</Button>
            <Button variant="secondary" icon="bar-chart-3" onClick={onView} style={{ flex: 1, justifyContent: "center" }}>Vista previa</Button>
          </div>
        </>
      ) : (
        <>
          <div style={{ display: "flex", gap: 3, background: "rgba(248,250,252,0.9)", borderRadius: 11, padding: 3 }}>
            {[["now", backendPublishReady ? "Simular publicación" : "Publicar no disponible", "rocket"], ["schedule", "Programar", "calendar"]].map(([id, label, ic]) => (
              <button key={id} onClick={() => setMode(id)} style={{
                flex: 1, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "8px 10px", borderRadius: 9, cursor: "pointer",
                border: `1px solid ${mode === id ? "rgba(34,211,238,.5)" : "transparent"}`, background: mode === id ? "rgba(34,211,238,.14)" : "transparent",
                color: mode === id ? "#0891B2" : "#68737D", fontFamily: "Inter", fontSize: 12.5, fontWeight: 600,
              }}><Icon name={ic} size={14} /> {label}</button>
            ))}
          </div>

          {mode === "schedule" && (
            <>
              <div style={{ display: "flex", gap: 10 }}>
                <DateField label="Inicio (publica)" value={start} onChange={setStart} disabled={!backendScheduleReady} />
                <DateField label="Fin (despublica)" value={end} onChange={setEnd} disabled={!backendScheduleReady || !auto} align="right" />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 11px", borderRadius: 10, background: "rgba(248,250,252,0.8)", border: "1px solid #EEF2F6" }}>
                <MiniSwitch on={auto} onToggle={setAuto} disabled={!backendScheduleReady} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontFamily: "Inter", fontSize: 12.5, fontWeight: 600, color: "#002B57" }}>Despublicar automáticamente</div>
                  <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8" }}>Al terminar la ventana, el agente retira el banner.</div>
                </div>
              </div>
            </>
          )}

          <Button variant={activeReady ? "shine" : "secondary"} icon={primaryIcon} disabled={!activeReady}
            onClick={() => mode === "now" ? onPublishNow() : onSchedule({ start, end, auto })} style={{ justifyContent: "center" }}>
            {primaryLabel}
          </Button>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 6, fontFamily: "Inter", fontSize: 11, color: activeReady ? "#16A34A" : "#B45309" }}>
            <Icon name={activeReady ? "shield-check" : "lock"} size={11} /> {activeReady ? (mode === "now" ? "Backend realizará una simulación dry-run; no debe mutar Shopify live." : "Backend aceptará la acción si el endpoint responde OK.") : (activeReason || "Acción fail-closed: no se marcará como programada/publicada localmente.")}
          </div>
        </>
      )}
    </GlassCard>
  );
}

Object.assign(window, { ApprovalPanel, CommentsPanel, PublishPanel });
