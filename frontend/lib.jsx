/* global React */
// Aijolot Banner Agent — shared primitives (glassmorphism)
const { useState, useEffect, useRef, useCallback } = React;

// --- Lucide icon ---
function Icon({ name, size = 16, color, style, strokeWidth = 2 }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current && window.lucide) {
      ref.current.innerHTML = "";
      const el = document.createElement("i");
      el.setAttribute("data-lucide", name);
      ref.current.appendChild(el);
      window.lucide.createIcons({
        attrs: { width: size, height: size, "stroke-width": strokeWidth },
        nameAttr: "data-lucide",
      });
    }
  }, [name, size, strokeWidth]);
  return <span ref={ref} style={{ display: "inline-flex", color: color || "currentColor", lineHeight: 0, ...style }} />;
}

// --- Glass card ---
function GlassCard({ children, style, radius = 14, className = "", onClick, id }) {
  return (
    <div
      id={id}
      onClick={onClick}
      className={className}
      style={{
        background: "rgba(255,255,255,0.8)",
        backdropFilter: "blur(18px)",
        WebkitBackdropFilter: "blur(18px)",
        border: "1px solid rgba(255,255,255,0.6)",
        borderRadius: radius,
        boxShadow: "0 10px 28px rgba(15,23,42,0.08)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// --- Button ---
function Button({ variant = "default", children, icon, iconRight, onClick, style, disabled, type = "button", title }) {
  const [hover, setHover] = useState(false);
  const base = {
    fontFamily: "Inter, sans-serif", fontWeight: 500, fontSize: 13.5,
    padding: "9px 16px", borderRadius: 8, border: "none",
    cursor: disabled ? "not-allowed" : "pointer", display: "inline-flex",
    alignItems: "center", gap: 7, position: "relative", overflow: "hidden",
    transition: "filter .15s, background .15s, box-shadow .15s, transform .05s", whiteSpace: "nowrap",
    opacity: disabled ? 0.5 : 1,
  };
  const variants = {
    default: { background: "#22D3EE", color: "#fff", boxShadow: "0 10px 30px rgba(34,211,238,.18)" },
    shine: { background: "#22D3EE", color: "#fff", boxShadow: "0 10px 30px rgba(34,211,238,.18)" },
    navy: { background: "#002B57", color: "#fff", boxShadow: "0 10px 26px rgba(0,43,87,.22)" },
    destructive: { background: "#F72585", color: "#fff", boxShadow: "0 10px 30px rgba(247,37,133,.18)" },
    outline: { background: "rgba(255,255,255,0.6)", color: "#002B57", border: "1px solid #E2E8F0" },
    ghost: { background: hover && !disabled ? "rgba(34,211,238,0.1)" : "transparent", color: "#68737D" },
    secondary: { background: "#F8FAFC", color: "#002B57", border: "1px solid #E2E8F0" },
  };
  const v = variants[variant] || variants.default;
  return (
    <button
      type={type} onClick={disabled ? undefined : onClick} disabled={disabled} title={title}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ ...base, ...v, filter: hover && !disabled && variant !== "ghost" ? "brightness(1.06)" : "none", ...style }}
    >
      {icon && <Icon name={icon} size={15} />}
      {children}
      {iconRight && <Icon name={iconRight} size={15} />}
      {(variant === "shine" || variant === "default") && hover && !disabled && (
        <span style={{ position: "absolute", inset: 0, background: "linear-gradient(110deg,transparent 35%,rgba(255,255,255,.5) 50%,transparent 65%)", animation: "uikShine 1.4s linear infinite" }} />
      )}
    </button>
  );
}

// --- Badge ---
const BADGE_TONES = {
  cyan: { bg: "rgba(34,211,238,0.12)", bd: "#22D3EE", fg: "#0891B2" },
  pink: { bg: "rgba(247,37,133,0.12)", bd: "#F72585", fg: "#F72585" },
  green: { bg: "rgba(34,197,94,0.12)", bd: "#4ADE80", fg: "#16A34A" },
  amber: { bg: "rgba(245,158,11,0.12)", bd: "#FBBF24", fg: "#B45309" },
  purple: { bg: "rgba(139,92,246,0.12)", bd: "#A78BFA", fg: "#7C3AED" },
  slate: { bg: "rgba(100,116,139,0.1)", bd: "#CBD5E1", fg: "#64748B" },
  red: { bg: "rgba(239,68,68,0.12)", bd: "#F87171", fg: "#EF4444" },
};
function Badge({ tone = "cyan", children, icon, style }) {
  const t = BADGE_TONES[tone] || BADGE_TONES.cyan;
  return (
    <span style={{
      fontFamily: "Inter, sans-serif", fontSize: 10, fontWeight: 600,
      textTransform: "uppercase", letterSpacing: "0.06em", padding: "3px 9px",
      borderRadius: 9999, border: `1px solid ${t.bd}`, background: t.bg, color: t.fg,
      display: "inline-flex", alignItems: "center", gap: 5, whiteSpace: "nowrap", ...style,
    }}>
      {icon && <Icon name={icon} size={11} />}
      {children}
    </span>
  );
}

// --- Kicker (chapter-line + uppercase label) ---
function Kicker({ children, color = "#0891B2" }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{ width: 26, height: 3, borderRadius: 9999, background: color }} />
      <span style={{ fontFamily: "Inter", fontSize: 11, fontWeight: 600, letterSpacing: "0.14em", textTransform: "uppercase", color }}>{children}</span>
    </div>
  );
}

// --- spinner ---
function Spinner({ size = 16, color = "#22D3EE" }) {
  return <span style={{ width: size, height: size, borderRadius: 9999, border: `2px solid ${color}33`, borderTopColor: color, display: "inline-block", animation: "spin .8s linear infinite" }} />;
}

// --- Avatar ---
function Avatar({ initials, gradient = "linear-gradient(135deg,#F72585,#8B5CF6)", size = 32, title }) {
  return (
    <div title={title} style={{
      width: size, height: size, borderRadius: 9999, background: gradient, color: "#fff",
      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      fontFamily: "Space Grotesk", fontWeight: 600, fontSize: size * 0.4,
    }}>{initials}</div>
  );
}

Object.assign(window, { Icon, GlassCard, Button, Badge, BADGE_TONES, Kicker, Spinner, Avatar });
