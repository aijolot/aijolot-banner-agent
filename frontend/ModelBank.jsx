/* global React, Icon, Button, Spinner */
// Aijolot Banner Agent — Usage-shot model bank + brand model creator.
const { useState: useStateMB } = React;

function ModelCard({ m, on, onClick }) {
  return (
    <button onClick={onClick} style={{
      display: "flex", flexDirection: "column", gap: 0, padding: 0, borderRadius: 12, overflow: "hidden", cursor: "pointer",
      border: "2px solid " + (on ? "#22D3EE" : "#EEF2F6"), background: "#fff", textAlign: "left",
    }}>
      <div style={{ position: "relative", height: 64, background: m.grad, display: "flex", alignItems: "flex-end", justifyContent: "center" }}>
        <Icon name="user-round" size={30} color="rgba(255,255,255,.85)" style={{ marginBottom: -2 }} />
        {on ? <span style={{ position: "absolute", top: 5, right: 5, width: 17, height: 17, borderRadius: 9999, background: "#22D3EE", display: "flex", alignItems: "center", justifyContent: "center" }}><Icon name="check" size={11} color="#06121f" /></span> : null}
        {m.ai ? <span style={{ position: "absolute", top: 5, left: 5, fontFamily: "Inter", fontSize: 8.5, fontWeight: 700, letterSpacing: ".06em", color: "#06121f", background: "rgba(255,255,255,.9)", padding: "2px 6px", borderRadius: 9999 }}>IA</span> : null}
      </div>
      <div style={{ padding: "7px 9px" }}>
        <div style={{ fontFamily: "Inter", fontSize: 12, fontWeight: 600, color: "#002B57" }}>{m.name}</div>
        <div style={{ fontFamily: "Space Grotesk", fontSize: 9.5, color: "#94A3B8" }}>{m.tag}</div>
      </div>
    </button>
  );
}

function ModelBank({ models, selected, onSelect, onCreate }) {
  const [open, setOpen] = useStateMB(false);
  const [prompt, setPrompt] = useStateMB("");
  const [gen, setGen] = useStateMB("");
  const [gender, setGender] = useStateMB("Mujer");

  function generate() {
    if (!prompt.trim() || gen) return;
    setGen("working");
    setTimeout(() => {
      onCreate({ name: "Modelo IA", tag: gender + " · de marca", grad: "linear-gradient(150deg,#0891B2,#8B5CF6)", ai: true, desc: prompt.trim() });
      setGen(""); setPrompt(""); setOpen(false);
    }, 1600);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8 }}>
        {models.map((m) => <ModelCard key={m.id} m={m} on={selected === m.id} onClick={() => onSelect(m.id)} />)}
        <button onClick={() => setOpen((o) => !o)} style={{
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, borderRadius: 12, cursor: "pointer", minHeight: 109,
          border: "1.5px dashed " + (open ? "#22D3EE" : "#CBD5E1"), background: open ? "rgba(34,211,238,.06)" : "rgba(248,250,252,0.7)", color: open ? "#0891B2" : "#64748B",
        }}>
          <Icon name="user-plus" size={20} />
          <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, textAlign: "center", lineHeight: 1.3 }}>Crear<br />modelo</span>
        </button>
      </div>

      {open ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: 12, borderRadius: 12, background: "rgba(248,250,252,0.85)", border: "1px solid #EEF2F6" }}>
          <div style={{ fontFamily: "Inter", fontSize: 11.5, fontWeight: 600, color: "#475569" }}>Modelo de marca</div>
          <image-slot id="brand-model" shape="rounded" radius="10" style={{ width: "100%", height: 92 }} placeholder="Sube tu modelo (foto de marca)"></image-slot>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "Inter", fontSize: 10.5, color: "#94A3B8" }}>
            <span style={{ flex: 1, height: 1, background: "#E2E8F0" }} /> o genera con IA <span style={{ flex: 1, height: 1, background: "#E2E8F0" }} />
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {["Mujer", "Hombre", "Unisex"].map((g) => (
              <button key={g} onClick={() => setGender(g)} style={{ flex: 1, fontFamily: "Inter", fontSize: 11, fontWeight: 600, padding: "6px 0", borderRadius: 8, cursor: "pointer", border: "1px solid " + (gender === g ? "#22D3EE" : "#E2E8F0"), background: gender === g ? "rgba(34,211,238,.12)" : "#fff", color: gender === g ? "#0891B2" : "#64748B" }}>{g}</button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 7, alignItems: "center", border: "1px solid #E2E8F0", borderRadius: 9, padding: "7px 10px", background: "#fff" }}>
            <Icon name="sparkles" size={13} color="#94A3B8" />
            <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="ej. modelo elegante, luz cálida, 30s" style={{ flex: 1, border: "none", outline: "none", background: "transparent", fontFamily: "Inter", fontSize: 12, color: "#002B57" }} />
          </div>
          <Button variant={gen ? "secondary" : "default"} icon={gen ? null : "wand-sparkles"} disabled={!prompt.trim() || !!gen} onClick={generate} style={{ justifyContent: "center" }}>
            {gen ? <><span style={{ display: "inline-flex", marginRight: 6 }}><Spinner size={13} /></span>Generando modelo…</> : "Generar modelo"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

Object.assign(window, { ModelBank });
