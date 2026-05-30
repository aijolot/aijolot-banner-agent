/* global React, Icon, GlassCard, Button, Badge, Kicker, Spinner, Banner, BrandAPI, SEGMENTS */
// Aijolot Banner Agent — Brand Context (GH-26).
// Multi-brand CRUD wired to the FastAPI bridge (GET/PUT /brands), with a live
// banner preview driven by the selected brand. Falls back to in-memory seeds
// when the bridge is unreachable (BrandAPI handles that transparently).
const { useState: useStateBC, useEffect: useEffectBC, useRef: useRefBC, useMemo: useMemoBC } = React;

const HEX_RE = /^#[0-9a-fA-F]{6}$/;
const FONTS = ["Space Grotesk", "Inter", "Georgia", "Helvetica", "Playfair Display"];

// ---- color helpers (for the live preview mapping) ----
function _hx(hex, i) { return parseInt(hex.replace("#", "").slice(i, i + 2), 16); }
function hexLum(hex) {
  const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(_hx(hex, 0)) + 0.7152 * f(_hx(hex, 2)) + 0.0722 * f(_hx(hex, 4));
}
function hexSat(hex) {
  const r = _hx(hex, 0) / 255, g = _hx(hex, 2) / 255, b = _hx(hex, 4) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
  return mx === 0 ? 0 : (mx - mn) / mx;
}
function hexRgba(hex, a) { return `rgba(${_hx(hex, 0)},${_hx(hex, 2)},${_hx(hex, 4)},${a})`; }

// Map an arbitrary brand palette → the Banner's palette variables.
function paletteToVars(palette) {
  const valid = (palette || []).filter((c) => HEX_RE.test(c.hex));
  if (!valid.length) return SEGMENTS.masculino.palette;
  const byLum = [...valid].sort((a, b) => hexLum(a.hex) - hexLum(b.hex));
  const bgA = byLum[0].hex, bgB = (byLum[1] || byLum[0]).hex, ink = byLum[byLum.length - 1].hex;
  const accent = [...valid].sort((a, b) => hexSat(b.hex) - hexSat(a.hex))[0].hex;
  return { bgA, bgB, ink, sub: hexRgba(ink, 0.72), accent, chip: accent, glow: hexRgba(accent, 0.32), bottle: `linear-gradient(160deg,${bgB},${bgA})`, cap: accent };
}

function brandToSeg(brand) {
  const phrases = (brand.voice && brand.voice.required_phrases) || [];
  return {
    id: brand.id || "preview",
    eyebrow: (brand.name || "Marca").toUpperCase(),
    headline: "Tu estilo,\ntu momento.",
    sub: phrases[0] || "Descubre la nueva colección esta semana.",
    cta: "Comprar ahora",
    product: { name: brand.name || "Producto" },
    palette: paletteToVars(brand.palette),
  };
}

// ---- small editors ----
function Field({ label, value, onChange, placeholder, error, mono }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5, flex: 1, minWidth: 0 }}>
      <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, color: "#68737D" }}>{label}</span>
      <input value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={{
        border: `1px solid ${error ? "#F87171" : "#E2E8F0"}`, borderRadius: 9, padding: "8px 11px", outline: "none",
        fontFamily: mono ? "Space Grotesk" : "Inter", fontSize: 12.5, color: "#002B57", background: "#fff",
      }} />
      {error ? <span style={{ fontFamily: "Inter", fontSize: 10.5, color: "#EF4444" }}>{error}</span> : null}
    </div>
  );
}

function ChipList({ items, onChange, placeholder, tone = "cyan", emptyHint }) {
  const [val, setVal] = useStateBC("");
  const TONE = { cyan: ["#22D3EE", "rgba(34,211,238,.12)", "#0891B2"], pink: ["#F72585", "rgba(247,37,133,.1)", "#F72585"], green: ["#10B981", "rgba(16,185,129,.1)", "#16A34A"] }[tone];
  const add = () => { const v = val.trim(); if (!v) return; if (!items.includes(v)) onChange([...items, v]); setVal(""); };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
        {items.length === 0 && emptyHint ? <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#94A3B8" }}>{emptyHint}</span> : null}
        {items.map((t) => (
          <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "Inter", fontSize: 11, fontWeight: 600, padding: "4px 10px", borderRadius: 9999, border: `1px solid ${TONE[0]}`, background: TONE[1], color: TONE[2] }}>
            {t}
            <button onClick={() => onChange(items.filter((x) => x !== t))} style={{ border: "none", background: "transparent", cursor: "pointer", color: TONE[2], padding: 0, display: "inline-flex" }}><Icon name="x" size={11} /></button>
          </span>
        ))}
      </div>
      <div style={{ display: "flex", gap: 7 }}>
        <input value={val} onChange={(e) => setVal(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} placeholder={placeholder} style={{ flex: 1, border: "1px solid #E2E8F0", borderRadius: 8, padding: "7px 10px", fontFamily: "Inter", fontSize: 12, color: "#002B57", outline: "none" }} />
        <Button variant="secondary" icon="plus" onClick={add}>Añadir</Button>
      </div>
    </div>
  );
}

function PaletteEditor({ palette, onChange }) {
  const set = (i, patch) => onChange(palette.map((c, j) => j === i ? { ...c, ...patch } : c));
  const remove = (i) => onChange(palette.filter((_, j) => j !== i));
  const add = () => onChange([...palette, { name: "Nuevo", hex: "#22D3EE" }]);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
      {palette.map((c, i) => {
        const bad = !HEX_RE.test(c.hex);
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <label style={{ width: 38, height: 38, borderRadius: 10, flexShrink: 0, border: "1px solid rgba(0,0,0,.08)", background: bad ? "#F1F5F9" : c.hex, position: "relative", cursor: "pointer", boxShadow: "0 4px 12px rgba(15,23,42,.1)" }}>
              <input type="color" value={bad ? "#000000" : c.hex} onChange={(e) => set(i, { hex: e.target.value.toUpperCase() })} style={{ opacity: 0, width: "100%", height: "100%", cursor: "pointer" }} />
            </label>
            <input value={c.name} onChange={(e) => set(i, { name: e.target.value })} placeholder="Nombre" style={{ flex: 1, minWidth: 0, border: "1px solid #E2E8F0", borderRadius: 8, padding: "7px 10px", fontFamily: "Inter", fontSize: 12.5, color: "#002B57", outline: "none" }} />
            <input value={c.hex} onChange={(e) => set(i, { hex: e.target.value })} placeholder="#RRGGBB" style={{ width: 104, border: `1px solid ${bad ? "#F87171" : "#E2E8F0"}`, borderRadius: 8, padding: "7px 10px", fontFamily: "Space Grotesk", fontSize: 12.5, color: bad ? "#EF4444" : "#002B57", outline: "none" }} />
            <button onClick={() => remove(i)} disabled={palette.length <= 1} title="Quitar color" style={{ width: 30, height: 30, borderRadius: 8, border: "none", background: "transparent", cursor: palette.length <= 1 ? "default" : "pointer", color: palette.length <= 1 ? "#CBD5E1" : "#94A3B8", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><Icon name="trash-2" size={15} /></button>
          </div>
        );
      })}
      <button onClick={add} style={{ alignSelf: "flex-start", display: "inline-flex", alignItems: "center", gap: 6, padding: "7px 13px", borderRadius: 9, cursor: "pointer", border: "1.5px dashed #CBD5E1", background: "transparent", color: "#0891B2", fontFamily: "Inter", fontSize: 12, fontWeight: 600 }}><Icon name="plus" size={13} /> Añadir color</button>
    </div>
  );
}

function BCard({ icon, title, children }) {
  return (
    <GlassCard style={{ padding: 20, display: "flex", flexDirection: "column", gap: 13 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <div style={{ width: 30, height: 30, borderRadius: 9, background: "rgba(34,211,238,0.12)", display: "flex", alignItems: "center", justifyContent: "center", color: "#0891B2" }}><Icon name={icon} size={16} /></div>
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>{title}</span>
      </div>
      {children}
    </GlassCard>
  );
}

function BrandContextView() {
  const [brands, setBrands] = useStateBC([]);
  const [selId, setSelId] = useStateBC(null);
  const [draft, setDraft] = useStateBC(null);
  const [loading, setLoading] = useStateBC(true);
  const [loadErr, setLoadErr] = useStateBC("");
  const [saveState, setSaveState] = useStateBC("idle"); // idle | saving | saved | error
  const [saveErr, setSaveErr] = useStateBC("");
  const [online, setOnline] = useStateBC(null);
  const original = useRefBC(null);

  // initial load
  useEffectBC(() => {
    let alive = true;
    (async () => {
      try {
        const list = await BrandAPI.list();
        if (!alive) return;
        setBrands(list); setOnline(BrandAPI.online);
        if (list.length) await select(list[0].id);
      } catch (e) {
        if (alive) setLoadErr(e.body || e.message || "No se pudo cargar la lista de marcas");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  async function select(id) {
    setSelId(id); setSaveState("idle"); setSaveErr("");
    try {
      const b = await BrandAPI.get(id);
      original.current = JSON.stringify(b);
      setDraft(b); setOnline(BrandAPI.online);
    } catch (e) {
      setLoadErr(e.body || e.message || "No se pudo cargar la marca");
    }
  }

  const patch = (p) => { setDraft((d) => ({ ...d, ...p })); setSaveState("idle"); };
  const patchVoice = (p) => patch({ voice: { ...draft.voice, ...p } });
  const patchShopify = (p) => patch({ shopify: { ...draft.shopify, ...p } });

  const seg = useMemoBC(() => (draft ? brandToSeg(draft) : null), [draft]);

  const paletteValid = draft && draft.palette.length > 0 && draft.palette.every((c) => HEX_RE.test(c.hex));
  const domainValid = draft && (draft.shopify.store_domain || "").trim().length > 0;
  const valid = paletteValid && domainValid;
  const dirty = draft && original.current !== JSON.stringify(draft);

  async function save() {
    if (!valid || !draft) return;
    setSaveState("saving"); setSaveErr("");
    try {
      const saved = await BrandAPI.put(draft.id, draft);
      original.current = JSON.stringify(saved);
      setDraft(saved); setOnline(BrandAPI.online); setSaveState("saved");
      setBrands((bs) => bs.map((b) => b.id === saved.id ? { id: saved.id, name: saved.name, palette: saved.palette } : b));
    } catch (e) {
      setSaveState("error");
      setSaveErr(e.status === 422 ? "El backend rechazó los datos (validación). Revisa los campos." : (e.body || e.message || "Error al guardar"));
    }
  }

  if (loading) {
    return <GlassCard style={{ padding: 48, display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}><Spinner size={18} /><span style={{ fontFamily: "Inter", fontSize: 14, color: "#0891B2" }}>Cargando marcas…</span></GlassCard>;
  }
  if (loadErr) {
    return <GlassCard style={{ padding: 32, display: "flex", alignItems: "center", gap: 12, border: "1px solid rgba(248,113,113,.4)" }}><Icon name="triangle-alert" size={20} color="#EF4444" /><span style={{ fontFamily: "Inter", fontSize: 13.5, color: "#EF4444" }}>{loadErr}</span></GlassCard>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      {/* header */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Kicker>Guardián de identidad</Kicker>
          <h1 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 38, letterSpacing: "-0.02em", color: "#002B57", margin: 0, lineHeight: 1.05 }}>Contexto de marca</h1>
          <p style={{ fontFamily: "Inter", fontSize: 14.5, color: "#68737D", margin: 0, maxWidth: 560 }}>El filtro que el agente aplica antes de diseñar. Selecciona una tienda, edita sus tokens y guárdalos — se persisten en <span style={{ fontFamily: "Space Grotesk" }}>brands/{(draft && draft.id) || "{id}"}.md</span>.</p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
          {online === true ? <Badge tone="green" icon="wifi">Bridge conectado</Badge>
            : online === false ? <Badge tone="amber" icon="wifi-off">Modo offline · mock</Badge> : null}
          <div style={{ display: "flex", gap: 9 }}>
            {saveState === "saved" && !dirty ? <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "Inter", fontSize: 12, color: "#16A34A", fontWeight: 600 }}><Icon name="check-circle-2" size={15} /> Guardado</span> : null}
            <Button variant={valid && dirty ? "shine" : "secondary"} icon={saveState === "saving" ? null : "save"} disabled={!valid || !dirty || saveState === "saving"} onClick={save}>
              {saveState === "saving" ? <><span style={{ display: "inline-flex", marginRight: 6 }}><Spinner size={13} color="#fff" /></span>Guardando…</> : "Guardar cambios"}
            </Button>
          </div>
        </div>
      </div>

      {saveState === "error" ? (
        <GlassCard style={{ padding: "13px 16px", display: "flex", alignItems: "center", gap: 11, border: "1px solid rgba(248,113,113,.4)", background: "rgba(248,113,113,.06)" }}>
          <Icon name="triangle-alert" size={17} color="#EF4444" /><span style={{ fontFamily: "Inter", fontSize: 13, color: "#EF4444", fontWeight: 500 }}>{saveErr}</span>
        </GlassCard>
      ) : null}

      {/* brand selector */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontFamily: "Inter", fontSize: 12, color: "#94A3B8", display: "inline-flex", alignItems: "center", gap: 6 }}><Icon name="store" size={14} /> Tienda:</span>
        <div style={{ display: "flex", gap: 3, background: "rgba(255,255,255,0.7)", border: "1px solid rgba(255,255,255,0.6)", borderRadius: 11, padding: 3, boxShadow: "0 6px 18px rgba(15,23,42,.05)", flexWrap: "wrap" }}>
          {brands.map((b) => {
            const on = selId === b.id;
            return (
              <button key={b.id} onClick={() => select(b.id)} style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "7px 13px", borderRadius: 9, cursor: "pointer", border: "1px solid " + (on ? "rgba(34,211,238,.5)" : "transparent"), background: on ? "rgba(34,211,238,.14)" : "transparent", color: on ? "#0891B2" : "#68737D", fontFamily: "Inter", fontSize: 12.5, fontWeight: 600 }}>
                <span style={{ display: "inline-flex", gap: 2 }}>{(b.palette || []).slice(0, 3).map((c, i) => <span key={i} style={{ width: 10, height: 10, borderRadius: 3, background: c.hex, border: "1px solid rgba(0,0,0,.06)" }} />)}</span>
                {b.name}
              </button>
            );
          })}
        </div>
      </div>

      {draft ? (
        <>
          {/* live preview */}
          <GlassCard style={{ padding: 18, display: "flex", flexDirection: "column", gap: 10, background: "rgba(255,255,255,0.55)", backgroundImage: "radial-gradient(rgba(148,163,184,.18) 1px, transparent 1px)", backgroundSize: "18px 18px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "Space Grotesk", fontSize: 12, color: "#94A3B8" }}>
              <Icon name="eye" size={14} /> Preview en vivo · refleja la paleta y tipografía de la marca
            </div>
            <Banner seg={seg} variant="A" font={draft.typography.display} />
          </GlassCard>

          {/* editable cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 16 }}>
            <Field label="Nombre de la marca" value={draft.name} onChange={(v) => patch({ name: v })} placeholder="Avocado Store" error={!draft.name.trim() ? "Requerido" : ""} />
            <Field label="Logo URL" value={draft.logo_url} onChange={(v) => patch({ logo_url: v })} placeholder="https://…/logo.svg" />
          </div>

          <BCard icon="palette" title="Paleta autorizada">
            <PaletteEditor palette={draft.palette} onChange={(p) => patch({ palette: p })} />
            {!paletteValid ? <span style={{ fontFamily: "Inter", fontSize: 11.5, color: "#EF4444", display: "inline-flex", alignItems: "center", gap: 6 }}><Icon name="triangle-alert" size={13} /> Cada color debe ser un hex válido (#RRGGBB) y debe haber al menos uno.</span> : null}
          </BCard>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 16 }}>
            <BCard icon="type" title="Tipografías">
              <div style={{ display: "flex", gap: 12 }}>
                {[["display", "Display"], ["body", "Texto"]].map(([k, label]) => (
                  <div key={k} style={{ display: "flex", flexDirection: "column", gap: 5, flex: 1 }}>
                    <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, color: "#68737D" }}>{label}</span>
                    <select value={draft.typography[k]} onChange={(e) => patch({ typography: { ...draft.typography, [k]: e.target.value } })} style={{ border: "1px solid #E2E8F0", borderRadius: 9, padding: "8px 10px", fontFamily: "Inter", fontSize: 12.5, color: "#002B57", background: "#fff", outline: "none" }}>
                      {FONTS.concat(FONTS.includes(draft.typography[k]) ? [] : [draft.typography[k]]).map((f) => <option key={f} value={f}>{f}</option>)}
                    </select>
                  </div>
                ))}
              </div>
            </BCard>

            <BCard icon="shopping-bag" title="Shopify">
              <Field label="Store domain" value={draft.shopify.store_domain} onChange={(v) => patchShopify({ store_domain: v })} placeholder="tienda.myshopify.com" mono error={!domainValid ? "Requerido" : ""} />
              <div style={{ display: "flex", gap: 12 }}>
                <Field label="Theme ID" value={draft.shopify.theme_id} onChange={(v) => patchShopify({ theme_id: v })} placeholder="128934771" mono />
                <Field label="Placement por defecto" value={draft.shopify.default_placement} onChange={(v) => patchShopify({ default_placement: v })} placeholder="hero" mono />
              </div>
            </BCard>
          </div>

          <BCard icon="message-circle" title="Tono y voz">
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "#0891B2" }}>Tono</span>
                <ChipList items={draft.voice.tone} onChange={(v) => patchVoice({ tone: v })} placeholder="ej. Premium, Directo…" tone="cyan" emptyHint="Sin atributos de tono aún." />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "#F72585" }}>Palabras prohibidas</span>
                  <ChipList items={draft.voice.prohibited_words} onChange={(v) => patchVoice({ prohibited_words: v })} placeholder="ej. barato…" tone="pink" emptyHint="Ninguna." />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "#16A34A" }}>Frases obligatorias</span>
                  <ChipList items={draft.voice.required_phrases} onChange={(v) => patchVoice({ required_phrases: v })} placeholder="ej. envío gratis +$50…" tone="green" emptyHint="Ninguna." />
                </div>
              </div>
            </div>
          </BCard>

          <BCard icon="image" title="Directivas de estilo de imagen">
            <ChipList items={draft.image_style_directives} onChange={(v) => patch({ image_style_directives: v })} placeholder="ej. luz natural, sombras suaves…" tone="cyan" emptyHint="Sin directivas aún." />
          </BCard>

          <GlassCard style={{ padding: 18, display: "flex", alignItems: "center", gap: 12, background: "linear-gradient(120deg, rgba(34,211,238,0.08), rgba(139,92,246,0.05))", border: "1px solid rgba(34,211,238,0.22)" }}>
            <div style={{ width: 36, height: 36, borderRadius: 11, background: "linear-gradient(135deg,#22D3EE,#0891B2)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", flexShrink: 0 }}><Icon name="wand-sparkles" size={18} /></div>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 14, color: "#002B57" }}>El agente aplica este contexto en cada generación</div>
              <div style={{ fontFamily: "Inter", fontSize: 12.5, color: "#68737D" }}>Paleta, tipografía, voz y reglas se inyectan al nodo <span style={{ fontFamily: "Space Grotesk" }}>load_brand_context</span> antes de diseñar.</div>
            </div>
            <Badge tone="purple" icon="lock">Bloqueado por marca</Badge>
          </GlassCard>
        </>
      ) : null}
    </div>
  );
}

Object.assign(window, { BrandContextView });
