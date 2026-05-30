/* global React, Icon, GlassCard, Button, Badge, Kicker, Spinner, ConfirmDialog, BRAND, CATALOG */
// Aijolot Banner Agent — Brand Context module (Guardián de identidad de marca).
const { useState: useStateBC, useRef: useRefBC } = React;

const TONE0 = ["Profesional", "Premium", "Confiable", "Directo", "Sin exclamaciones"];
const DONTS = ["Sin degradados arcoíris", "Sin emojis", "No distorsionar el frasco", "No tapar el producto con texto"];

function BCard({ icon, title, editing, children }) {
  return (
    <GlassCard style={{ padding: 20, display: "flex", flexDirection: "column", gap: 13, border: editing ? "1px solid rgba(34,211,238,0.4)" : "1px solid rgba(255,255,255,0.6)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <div style={{ width: 30, height: 30, borderRadius: 9, background: "rgba(34,211,238,0.12)", display: "flex", alignItems: "center", justifyContent: "center", color: "#0891B2" }}><Icon name={icon} size={16} /></div>
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 15, color: "#002B57" }}>{title}</span>
        {editing ? <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 4, fontFamily: "Inter", fontSize: 10.5, color: "#0891B2" }}><Icon name="pencil" size={11} /> editable</span> : null}
      </div>
      {children}
    </GlassCard>
  );
}

function BrandContextView() {
  const [editing, setEditing] = useStateBC(false);
  const [importing, setImporting] = useStateBC("idle"); // idle | working | done
  const [srcName, setSrcName] = useStateBC("");
  const [tone, setTone] = useStateBC(TONE0);
  const [toneInput, setToneInput] = useStateBC("");
  const [confirmOpen, setConfirmOpen] = useStateBC(false);
  const [savedAt, setSavedAt] = useStateBC(false);
  const fileRef = useRefBC(null);

  function onFile(e) {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    setSrcName(f.name);
    setImporting("working");
    setSavedAt(false);
    setTimeout(() => {
      setImporting("done");
      setEditing(true);
      setTone((t) => Array.from(new Set([...t, "Aspiracional", "Cálido"])));
    }, 1700);
  }
  function addTone() { const v = toneInput.trim(); if (!v) return; setTone((t) => t.includes(v) ? t : [...t, v]); setToneInput(""); }
  function removeTone(x) { setTone((t) => t.filter((v) => v !== x)); }
  function cancel() { setEditing(false); setImporting("idle"); }
  function save() { setConfirmOpen(true); }
  function doSave() { setConfirmOpen(false); setEditing(false); setImporting("idle"); setSavedAt(true); }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      <input ref={fileRef} type="file" accept=".pdf,.fig,application/pdf" onChange={onFile} style={{ display: "none" }} />

      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Kicker>Guardián de identidad</Kicker>
          <h1 style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 38, letterSpacing: "-0.02em", color: "#002B57", margin: 0, lineHeight: 1.05 }}>Contexto de marca</h1>
          <p style={{ fontFamily: "Inter", fontSize: 14.5, color: "#68737D", margin: 0, maxWidth: 560 }}>El filtro que el agente aplica antes de diseñar. Impórtalo desde tu brandbook o edítalo a mano.</p>
        </div>
        <div style={{ display: "flex", gap: 9 }}>
          {editing ? (
            <>
              <Button variant="ghost" icon="x" onClick={cancel}>Cancelar</Button>
              <Button variant="shine" icon="save" onClick={save}>Guardar cambios</Button>
            </>
          ) : (
            <>
              <Button variant="outline" icon="upload" onClick={() => fileRef.current && fileRef.current.click()}>Importar PDF / .fig</Button>
              <Button variant="secondary" icon="pencil" onClick={() => setEditing(true)}>Editar</Button>
            </>
          )}
        </div>
      </div>

      {/* status banner */}
      {importing === "working" ? (
        <GlassCard style={{ padding: "13px 16px", display: "flex", alignItems: "center", gap: 11, border: "1px solid rgba(34,211,238,0.3)" }}>
          <Spinner size={16} /><span style={{ fontFamily: "Inter", fontSize: 13, color: "#0891B2", fontWeight: 500 }}>Analizando <b>{srcName}</b> — extrayendo paleta, tipografías, logos y tono…</span>
        </GlassCard>
      ) : null}
      {importing === "done" && editing ? (
        <GlassCard style={{ padding: "13px 16px", display: "flex", alignItems: "center", gap: 11, border: "1px solid rgba(16,185,129,0.3)", background: "rgba(16,185,129,0.06)" }}>
          <Icon name="check-circle-2" size={17} color="#10B981" /><span style={{ fontFamily: "Inter", fontSize: 13, color: "#16A34A", fontWeight: 500 }}>Marca importada de <b>{srcName}</b>. Revisa los campos y guarda para aplicarla.</span>
        </GlassCard>
      ) : null}
      {savedAt ? (
        <GlassCard style={{ padding: "13px 16px", display: "flex", alignItems: "center", gap: 11, border: "1px solid rgba(16,185,129,0.3)", background: "rgba(16,185,129,0.06)" }}>
          <Icon name="shield-check" size={17} color="#10B981" /><span style={{ fontFamily: "Inter", fontSize: 13, color: "#16A34A", fontWeight: 500 }}>Contexto actualizado · se aplica a todos los próximos diseños del agente.</span>
        </GlassCard>
      ) : (
        <Badge tone="green" icon="shield-check">Bloqueado · aplicado a cada arte</Badge>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 16 }}>
        <BCard icon="hexagon" title="Logotipos" editing={editing}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ height: 70, borderRadius: 10, background: "#0F172A", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 18, color: "#fff", letterSpacing: ".18em" }}>MAISON</div>
              <span style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8", textAlign: "center" }}>Principal (oscuro)</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <image-slot id="brand-logo" shape="rounded" radius="10" style={{ width: "100%", height: 70 }} placeholder="Sube tu logo (SVG/PNG)"></image-slot>
              <span style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8", textAlign: "center" }}>Variante de marca</span>
            </div>
          </div>
        </BCard>

        <BCard icon="palette" title="Paleta autorizada" editing={editing}>
          <div style={{ display: "flex", gap: 9, flexWrap: "wrap" }}>
            {BRAND.palette.map((p) => (
              <div key={p.hex} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flex: "1 0 60px" }}>
                <div style={{ width: "100%", height: 50, borderRadius: 11, background: p.hex, border: "1px solid rgba(0,0,0,.06)", boxShadow: "0 6px 16px rgba(15,23,42,.1)" }} />
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontFamily: "Inter", fontSize: 10.5, fontWeight: 600, color: "#002B57" }}>{p.name}</div>
                  <div style={{ fontFamily: "Space Grotesk", fontSize: 9.5, color: "#94A3B8" }}>{p.hex}</div>
                </div>
              </div>
            ))}
          </div>
        </BCard>

        <BCard icon="type" title="Tipografías" editing={editing}>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ padding: "12px 14px", borderRadius: 10, background: "rgba(248,250,252,0.8)", border: "1px solid #EEF2F6" }}>
              <div style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 24, color: "#002B57", letterSpacing: "-.02em" }}>Define tu presencia</div>
              <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8", marginTop: 3 }}>Space Grotesk · Display + datos</div>
            </div>
            <div style={{ padding: "12px 14px", borderRadius: 10, background: "rgba(248,250,252,0.8)", border: "1px solid #EEF2F6" }}>
              <div style={{ fontFamily: "Inter", fontSize: 14, color: "#475569" }}>El icónico Boss Bottled. Carácter en cada nota.</div>
              <div style={{ fontFamily: "Inter", fontSize: 11, color: "#94A3B8", marginTop: 3 }}>Inter · cuerpo + UI</div>
            </div>
          </div>
        </BCard>

        <BCard icon="message-circle" title="Tono y voz" editing={editing}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {tone.map((t) => (
              <span key={t} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "Inter", fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", padding: "3px 9px", borderRadius: 9999, border: "1px solid #22D3EE", background: "rgba(34,211,238,0.12)", color: "#0891B2" }}>
                {t}{editing ? <button onClick={() => removeTone(t)} style={{ border: "none", background: "transparent", cursor: "pointer", color: "#0891B2", padding: 0, display: "inline-flex" }}><Icon name="x" size={11} /></button> : null}
              </span>
            ))}
          </div>
          {editing ? (
            <div style={{ display: "flex", gap: 7 }}>
              <input value={toneInput} onChange={(e) => setToneInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") addTone(); }} placeholder="Añadir atributo de tono…" style={{ flex: 1, border: "1px solid #E2E8F0", borderRadius: 8, padding: "7px 10px", fontFamily: "Inter", fontSize: 12.5, color: "#002B57", outline: "none" }} />
              <Button variant="secondary" icon="plus" onClick={addTone}>Añadir</Button>
            </div>
          ) : (
            <p style={{ fontFamily: "Inter", fontSize: 12.5, color: "#68737D", margin: 0, lineHeight: 1.5 }}>Segunda persona para acciones, neutral en descripciones. Calmado, confiado, sin ruido.</p>
          )}
        </BCard>

        <BCard icon="shield-check" title="Reglas de composición" editing={editing}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "#16A34A" }}>Permitido</span>
              {BRAND.rules.map((r) => (
                <div key={r} style={{ display: "flex", alignItems: "flex-start", gap: 7, fontFamily: "Inter", fontSize: 12.5, color: "#475569" }}>
                  <Icon name="check" size={13} color="#10B981" style={{ marginTop: 2, flexShrink: 0 }} /> {r}
                </div>
              ))}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "#F72585" }}>Prohibido</span>
              {DONTS.map((r) => (
                <div key={r} style={{ display: "flex", alignItems: "flex-start", gap: 7, fontFamily: "Inter", fontSize: 12.5, color: "#475569" }}>
                  <Icon name="x" size={13} color="#F72585" style={{ marginTop: 2, flexShrink: 0 }} /> {r}
                </div>
              ))}
            </div>
          </div>
        </BCard>

        <BCard icon="package" title="Imágenes de producto" editing={editing}>
          <p style={{ fontFamily: "Inter", fontSize: 12.5, color: "#68737D", margin: 0, lineHeight: 1.5 }}>Assets reales sincronizados desde Shopify — PNG recortado con precisión. El producto es sagrado: no se inventa ni distorsiona.</p>
          <div style={{ display: "flex", gap: 9 }}>
            {CATALOG.slice(0, 4).map((c) => (
              <div key={c.sku} style={{ flex: 1, height: 56, borderRadius: 9, background: "linear-gradient(160deg,#1b2c43,#0b1622)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Icon name="spray-can" size={18} color="#28C7F0" />
              </div>
            ))}
          </div>
        </BCard>
      </div>

      <GlassCard style={{ padding: 18, display: "flex", alignItems: "center", gap: 12, background: "linear-gradient(120deg, rgba(34,211,238,0.08), rgba(139,92,246,0.05))", border: "1px solid rgba(34,211,238,0.22)" }}>
        <div style={{ width: 36, height: 36, borderRadius: 11, background: "linear-gradient(135deg,#22D3EE,#0891B2)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", flexShrink: 0 }}><Icon name="wand-sparkles" size={18} /></div>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 14, color: "#002B57" }}>El agente aplica este contexto en cada generación</div>
          <div style={{ fontFamily: "Inter", fontSize: 12.5, color: "#68737D" }}>Plantillas inteligentes que combinan estos elementos de forma infinita pero controlada.</div>
        </div>
        <Badge tone="purple" icon="lock">Preentrenado</Badge>
      </GlassCard>

      <ConfirmDialog open={confirmOpen} title="Guardar contexto de marca"
        message="Estás por actualizar el contexto de marca. Este cambio se aplicará a TODOS los diseños que el agente genere a partir de ahora. Revísalo bien antes de continuar."
        phrase="confirmar" confirmLabel="Guardar y aplicar" onConfirm={doSave} onCancel={() => setConfirmOpen(false)} />
    </div>
  );
}

Object.assign(window, { BrandContextView });
