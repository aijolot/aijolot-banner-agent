/* global React, Icon, BannerLayout, layoutCells, HERO_STYLES */
// Aijolot Banner Agent — composition preview (one tile + fold viewport).

// One composition tile (bg layer + optional usage model + product + live copy).
// When a `live` object is provided (real backend concept/background/image), it
// overrides the hardcoded demo segment so the preview reflects the actual
// generated banner: real copy, chosen AI background, generated product image.
function Comp({ art, seg, allModels, mini, live }) {
  const p = seg.palette;
  const hero = HERO_STYLES.find((h) => h.id === art.heroStyle) || HERO_STYLES[0];
  const model = allModels.find((m) => m.id === art.model);
  const useLiveBg = !!(live && live.bgCss && live.scopeClass);
  const imageUrl = live && live.imageUrl;
  const bg = art.bg === "hero" ? hero.grad : `linear-gradient(120deg,${p.bgA},${p.bgB})`;
  const ink = useLiveBg ? (live.ink || "#ffffff") : p.ink;
  const accent = (live && live.accent) || p.accent;
  const eyebrow = (live && live.eyebrow) || seg.eyebrow;
  const headline = (live && live.headline) || seg.headline;
  const promo = (live && live.promo) || "";
  return (
    <div style={{ position: "relative", height: "100%", minHeight: mini ? 90 : 150, width: "100%", flex: 1, borderRadius: 8, overflow: "hidden", background: useLiveBg ? "#0b1622" : bg, display: "flex", alignItems: "center", padding: mini ? "10px 13px" : "16px 22px", color: ink }}>
      {useLiveBg ? (<><style dangerouslySetInnerHTML={{ __html: live.bgCss }} /><div className={live.scopeClass} style={{ position: "absolute", inset: 0, zIndex: 0 }} /></>) : null}
      {!useLiveBg && art.bg === "usage" && model && !imageUrl ? (
        <div style={{ position: "absolute", right: 0, top: 0, bottom: 0, width: "46%", background: model.grad, display: "flex", alignItems: "flex-end", justifyContent: "center", WebkitMaskImage: "linear-gradient(90deg,transparent,#000 38%)", maskImage: "linear-gradient(90deg,transparent,#000 38%)" }}>
          <Icon name="user-round" size={mini ? 30 : 58} color="rgba(255,255,255,.85)" />
        </div>
      ) : null}
      {!useLiveBg && art.bg === "hero" ? <div style={{ position: "absolute", right: "12%", top: "50%", transform: "translateY(-50%)", width: "40%", aspectRatio: "1", borderRadius: "50%", background: `radial-gradient(circle,${p.glow},transparent 62%)` }} /> : null}
      <div style={{ position: "relative", zIndex: 2, maxWidth: imageUrl ? "55%" : "60%", display: "flex", flexDirection: "column", gap: mini ? 4 : 8 }}>
        <span style={{ fontFamily: "Inter", fontSize: mini ? 7 : 10, fontWeight: 600, letterSpacing: ".22em", color: accent }}>{eyebrow}</span>
        <span style={{ fontFamily: "Space Grotesk", fontWeight: 700, fontSize: mini ? 14 : 26, lineHeight: 1.02, letterSpacing: "-.02em", whiteSpace: "pre-line", textShadow: useLiveBg ? "0 1px 8px rgba(0,0,0,.45)" : "none" }}>{headline}</span>
        <span style={{ alignSelf: "flex-start", marginTop: mini ? 2 : 4, fontFamily: "Inter", fontWeight: 600, fontSize: mini ? 8 : 12, padding: mini ? "4px 9px" : "8px 15px", borderRadius: 9999, background: accent, color: "#06121f" }}>{promo}</span>
      </div>
      {imageUrl ? (
        <img src={imageUrl} alt="" style={{ position: "absolute", right: mini ? "4%" : "6%", top: "50%", transform: "translateY(-50%)", width: mini ? "34%" : "38%", height: mini ? "78%" : "82%", objectFit: "cover", borderRadius: 10, zIndex: 1, boxShadow: "0 14px 22px rgba(0,0,0,.4)" }} />
      ) : (
        <div style={{ position: "absolute", right: art.bg === "usage" ? "30%" : "11%", top: "50%", transform: "translateY(-50%)", width: mini ? 26 : 46, height: mini ? 56 : 100, borderRadius: "16% 16% 11% 11%", background: p.bottle, border: "1px solid rgba(255,255,255,.16)", boxShadow: "0 14px 22px rgba(0,0,0,.4)", zIndex: 1 }}>
          <div style={{ position: "absolute", left: "33%", right: "33%", top: -6, height: "16%", borderRadius: 3, background: p.cap }} />
          <div style={{ position: "absolute", left: "22%", right: "22%", top: "42%", height: "26%", borderRadius: 2, background: "rgba(255,255,255,.85)" }} />
        </div>
      )}
    </div>
  );
}

function FoldPreview({ art, layout, seg, allModels, live }) {
  const n = layoutCells(layout);
  return (
    <div style={{ position: "relative", width: "100%", aspectRatio: "16/10", borderRadius: 12, overflow: "hidden", background: "#fff", border: "1px solid #EEF2F6" }}>
      <div style={{ height: `${art.fold}%`, padding: 10, display: "flex" }}>
        <BannerLayout layout={layout} gap={8} cell={(i) => <Comp key={i} art={art} seg={seg} allModels={allModels} mini={n > 1} live={live} />} />
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: `${art.fold}%`, bottom: 0, padding: 12, background: "#FAFBFC", display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ height: 8, width: "34%", background: "#E2E8F0", borderRadius: 4 }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8, flex: 1 }}>
          {[0, 1, 2, 3].map((i) => <div key={i} style={{ background: "#F1F5F9", borderRadius: 6 }} />)}
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: `${art.fold}%`, borderTop: "2px dashed #F72585", display: "flex", justifyContent: "center" }}>
        <span style={{ transform: "translateY(-50%)", fontFamily: "Inter", fontSize: 10, fontWeight: 700, letterSpacing: ".04em", color: "#fff", background: "#F72585", padding: "2px 10px", borderRadius: 9999, display: "inline-flex", alignItems: "center", gap: 5 }}>
          <Icon name="fold-vertical" size={11} /> Pliegue · {art.fold}% sobre el alto
        </span>
      </div>
    </div>
  );
}

Object.assign(window, { Comp, FoldPreview });
