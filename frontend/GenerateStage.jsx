/* global React, Icon, GlassCard, Button, Badge, Spinner, Kicker, Banner, PIPELINE, CODE_LINES, BRAND, CATALOG, SEGMENTS */
// Aijolot Banner Agent — Stage 2: live generation pipeline (Modules 1–5).
const { useState: useStateG, useEffect: useEffectG, useRef: useRefG } = React;

const DUR = [1300, 1250, 1650, 1700, 1750]; // ms per module

function StepRail({ phase }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {PIPELINE.map((s, i) => {
        const done = phase > i, running = phase === i;
        return (
          <div key={s.id} style={{
            display: "flex", alignItems: "center", gap: 13, padding: "13px 15px", borderRadius: 13,
            background: running ? "rgba(34,211,238,0.1)" : done ? "rgba(16,185,129,0.06)" : "rgba(248,250,252,0.7)",
            border: `1px solid ${running ? "rgba(34,211,238,0.35)" : done ? "rgba(16,185,129,0.2)" : "#EEF2F6"}`,
            transition: "background .3s, border .3s", opacity: phase < i ? 0.55 : 1,
          }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
              background: done ? "rgba(16,185,129,0.14)" : running ? "rgba(34,211,238,0.16)" : "#fff",
              color: done ? "#10B981" : running ? "#0891B2" : "#CBD5E1", border: running ? "none" : "1px solid #EEF2F6" }}>
              {done ? <Icon name="check" size={18} /> : running ? <Spinner size={17} /> : <Icon name={s.icon} size={17} />}
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 13.5, color: "#002B57" }}>{s.title}</div>
              <div style={{ fontFamily: "Inter", fontSize: 11.5, color: done ? "#16A34A" : "#94A3B8", marginTop: 2, transition: "color .3s" }}>
                {done ? s.done : running ? s.sub : "En espera"}
              </div>
            </div>
            {done && <Badge tone="green" icon="check">OK</Badge>}
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

function Viewport({ phase, typed, shieldOn }) {
  // phase 0 query | 1 brand | 2 image | 3 code | 4 shield | 5 done
  const seg = SEGMENTS.masculino;
  if (phase >= 5) {
    return (
      <div className="fade-up" style={{ display: "flex", flexDirection: "column", gap: 14, alignItems: "center", justifyContent: "center", height: "100%" }}>
        <Badge tone="green" icon="sparkles">Banner generado</Badge>
        <div style={{ width: "100%" }}><Banner seg={seg} variant="A" /></div>
        <div style={{ fontFamily: "Inter", fontSize: 12, color: "#94A3B8" }}>3 variantes compiladas · abriendo el lienzo…</div>
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
  // phase 4 shield
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

function GenerateStage({ onDone }) {
  const [phase, setPhase] = useStateG(0);
  const [typed, setTyped] = useStateG(0);
  const [shieldOn, setShieldOn] = useStateG(false);
  const skipped = useRefG(false);

  // advance through phases
  useEffectG(() => {
    if (phase >= 5) { const t = setTimeout(() => !skipped.current && onDone(), 1500); return () => clearTimeout(t); }
    let dur = DUR[phase];
    if (phase === 3) dur = CODE_LINES.length * 95 + 500;
    if (phase === 4) { const s = setTimeout(() => setShieldOn(true), 120); }
    const t = setTimeout(() => setPhase((p) => p + 1), dur);
    return () => clearTimeout(t);
  }, [phase]);

  // type code lines during phase 3
  useEffectG(() => {
    if (phase !== 3) { if (phase < 3) setTyped(0); return; }
    setTyped(0);
    const iv = setInterval(() => setTyped((n) => { if (n >= CODE_LINES.length) { clearInterval(iv); return n; } return n + 1; }), 95);
    return () => clearInterval(iv);
  }, [phase]);

  function skip() { skipped.current = true; onDone(); }

  const pct = Math.min(100, Math.round((phase / 5) * 100));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Kicker>Paso 4 de 6 · Generación</Kicker>
          <h2 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 26, color: "#002B57", margin: 0 }}>Construyendo tu banner</h2>
        </div>
        <Button variant="ghost" icon="chevron-right" iconRight="chevron-right" onClick={skip} style={{ color: "#94A3B8" }}>Saltar animación</Button>
      </div>

      <div style={{ height: 6, borderRadius: 9999, background: "#EEF2F6", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: "linear-gradient(90deg,#22D3EE,#0891B2)", borderRadius: 9999, transition: "width .5s ease" }} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1.1fr)", gap: 16, alignItems: "stretch" }}>
        <GlassCard style={{ padding: 18 }}><StepRail phase={phase} /></GlassCard>
        <GlassCard style={{ padding: 20, minHeight: 360, display: "flex", flexDirection: "column" }}>
          <Viewport phase={phase} typed={typed} shieldOn={shieldOn} />
        </GlassCard>
      </div>
    </div>
  );
}

Object.assign(window, { GenerateStage });
