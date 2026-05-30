/* global React, Icon, GlassCard, Button */
// Aijolot Banner Agent — confirmation dialog requiring a typed phrase.
const { useState: useStateCD, useEffect: useEffectCD } = React;

function ConfirmDialog({ open, title, message, phrase = "confirmar", confirmLabel = "Guardar cambios", tone = "default", onConfirm, onCancel }) {
  const [txt, setTxt] = useStateCD("");
  useEffectCD(() => { if (open) setTxt(""); }, [open]);
  if (!open) return null;
  const ok = txt.trim().toLowerCase() === phrase.toLowerCase();
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(2,12,27,.45)", backdropFilter: "blur(3px)", WebkitBackdropFilter: "blur(3px)", padding: 20 }}>
      <GlassCard radius={18} style={{ width: 440, maxWidth: "100%", padding: 24, background: "rgba(255,255,255,0.97)", boxShadow: "0 30px 80px rgba(2,12,27,.35)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 12 }}>
          <div style={{ width: 38, height: 38, borderRadius: 11, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(245,158,11,0.14)", color: "#B45309" }}><Icon name="shield-alert" size={20} /></div>
          <div style={{ fontFamily: "Space Grotesk", fontWeight: 600, fontSize: 17, color: "#002B57" }}>{title}</div>
        </div>
        <p style={{ fontFamily: "Inter", fontSize: 13.5, color: "#475569", lineHeight: 1.55, margin: "0 0 16px" }}>{message}</p>
        <label style={{ fontFamily: "Inter", fontSize: 12, fontWeight: 600, color: "#68737D", display: "block", marginBottom: 6 }}>
          Escribe <b style={{ color: "#002B57", fontFamily: "Space Grotesk" }}>{phrase}</b> para continuar
        </label>
        <input value={txt} onChange={(e) => setTxt(e.target.value)} autoFocus placeholder={phrase}
          onKeyDown={(e) => { if (e.key === "Enter" && ok) onConfirm(); }}
          style={{ width: "100%", border: `1px solid ${ok ? "#22D3EE" : "#E2E8F0"}`, borderRadius: 9, padding: "10px 12px", fontFamily: "Space Grotesk", fontSize: 14, color: "#002B57", outline: "none", marginBottom: 18 }} />
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <Button variant="secondary" onClick={onCancel}>Cancelar</Button>
          <Button variant={tone === "destructive" ? "destructive" : "shine"} icon="check" disabled={!ok} onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </GlassCard>
    </div>
  );
}

Object.assign(window, { ConfirmDialog });
