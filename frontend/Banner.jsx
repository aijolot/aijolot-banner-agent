/* global React */
// Aijolot Banner Agent — the rendered creative component.
// Renders the literal HTML the compiler produced; palette comes from the
// active segment, layout from the variant, fluidity from banner.css.

function Bottle({ seg }) {
  return (
    <div className="cssbottle" aria-hidden="true">
      <div className="cap" />
      <div className="shoulder" />
      <div className="body" />
      <div className="label">
        <b>BOSS</b>
        <i />
        <em>{seg.product.name.includes("Alive") ? "ALIVE" : seg.product.name.includes("Set") ? "PARFUMS" : "BOTTLED"}</em>
      </div>
    </div>
  );
}

// Split a promo/CTA string into a {big, small} discount badge, e.g.
// "Comprar ya · 25% OFF" → {big:"25%", small:"OFF"}; falls back to the raw text.
function discountParts(promo) {
  const s = String(promo || "");
  const m = s.match(/(\d{1,3})\s*%/);
  if (m) return { big: m[1] + "%", small: "OFF" };
  return { big: s.slice(0, 10) || "—", small: "" };
}

function Banner({ seg, variant = "A", slot = false, font, bodyFont, accent, idSuffix = "", brighter = false, ctaContrast = false, live = null }) {
  const p = seg.palette;
  // When the backend background defines a legible copy color, use it for the live
  // banner so the headline keeps the designed contrast over the creative background.
  const inkColor = (live && live.textColor) || p.ink;
  const subColor = (live && live.textColor) || p.sub;
  const vars = {
    "--bg-a": p.bgA, "--bg-b": p.bgB, "--ink": inkColor, "--sub": subColor,
    "--accent": accent || p.accent, "--chip": accent || p.chip,
    "--glow": p.glow, "--bottle": p.bottle, "--cap": p.cap,
    "--disp": font || "Space Grotesk",
    "--body": bodyFont || "Inter",
  };
  // Real banner: backend concept copy + generated image + chosen background +
  // brand name. Falls back to the demo segment when no revision exists yet.
  const eyebrow = (live && live.eyebrow) || seg.eyebrow;
  const headline = (live && live.headline) || seg.headline;
  const sub = (live && live.sub) || seg.sub;
  const cta = (live && live.cta) || seg.cta;
  const brandName = live ? (live.brandName || "") : "HUGO BOSS";
  const discount = live ? discountParts(live.promo) : { big: "10%", small: "OFF" };
  const imageUrl = live && live.imageUrl;
  const scope = live && live.bgCss ? `hb-live-${(idSuffix || "x").replace(/[^a-z0-9]/gi, "")}` : null;
  const scopedBgCss = scope ? String(live.bgCss).split(".aijolot-banner").join(`.${scope} .hb-bg`) : null;
  // ---- LIVE MODE: a real fixed-aspect banner canvas. Background fills the whole
  // banner; copy + hero are absolutely positioned with PERCENT coordinates (never
  // fixed px) so the composition just SCALES across breakpoints (no reflow). Type
  // is in cqw so it shrinks with the banner. Layout params are data-driven
  // (live.layout, %), with sensible defaults.
  if (live) {
    const L = live.layout || {};
    const ar = L.aspectRatio || live.aspectRatio || 2.4; // 1440 : 600
    const tX = num(L.textX, 6), tY = num(L.textY, 50), tW = num(L.textW, 48);
    const tAlign = L.textAlign === "center" ? "center" : L.textAlign === "right" ? "right" : "left";
    const hW = num(L.heroW, 46), hY = num(L.heroY, 50), hCenterX = num(L.heroX, 76);
    const dX = num(L.discountX, 92), dY = num(L.discountY, 16);
    const liveVars = { ...vars, "--banner-ar": String(ar) };
    return (
      <div className={`hb-banner hb-live${scope ? " " + scope : ""}`} style={liveVars} role="img"
        aria-label={`Banner ${brandName || "promocional"} ${eyebrow} — ${String(headline).replace("\n", " ")}`}>
        {scopedBgCss ? <style dangerouslySetInnerHTML={{ __html: scopedBgCss }} /> : null}
        <div className="hb-bg" />
        <div className="hb-grain" />
        {imageUrl ? (
          <img src={imageUrl} alt="" className="hb-genimg"
            style={{ position: "absolute", left: `${hCenterX}%`, top: `${hY}%`, width: `${hW}%`, height: `${num(L.heroH, 92)}%`, transform: "translate(-50%,-50%)", objectFit: "contain", zIndex: 2 }} />
        ) : null}
        <div className="hb-live-copy" style={{ left: `${tX}%`, top: `${tY}%`, width: `${tW}%`, transform: "translateY(-50%)", textAlign: tAlign, alignItems: tAlign === "center" ? "center" : tAlign === "right" ? "flex-end" : "flex-start" }}>
          {eyebrow ? <span className="hb-eyebrow" style={{ fontFamily: "var(--body)" }}>{eyebrow}</span> : null}
          <h2 className="hb-headline">{headline}</h2>
          {sub ? <p className="hb-sub" style={{ fontFamily: "var(--body)" }}>{sub}</p> : null}
          {cta ? (
            <a className="hb-cta" style={{ fontFamily: "var(--body)" }} onClick={(e) => e.preventDefault()} href="#">
              {cta}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
            </a>
          ) : null}
        </div>
        {discount.big !== "—" ? <span className="hb-discount" style={{ left: `${dX}%`, top: `${dY}%`, right: "auto", transform: "translate(-50%,-50%) rotate(8deg)" }}><b>{discount.big}</b>{discount.small ? <span>{discount.small}</span> : null}</span> : null}
        {brandName ? <div className="hb-logo">{brandName}</div> : null}
      </div>
    );
  }

  const cls = `hb-banner hb-${variant}${brighter ? " hb-brighter" : ""}${ctaContrast ? " hb-cta-contrast" : ""}${scope ? " " + scope : ""}`;
  return (
    <div className={cls} style={vars} role="img"
      aria-label={`Banner ${brandName || "promocional"} ${eyebrow} — ${String(headline).replace("\n", " ")}`}>
      {scopedBgCss ? <style dangerouslySetInnerHTML={{ __html: scopedBgCss }} /> : null}
      <div className="hb-bg" />
      <div className="hb-grain" />
      <div className="hb-inner">
        <div className="hb-copy">
          <span className="hb-eyebrow" style={{ fontFamily: "var(--body)" }}>{eyebrow}</span>
          <h2 className="hb-headline">{headline}</h2>
          <p className="hb-sub" style={{ fontFamily: "var(--body)" }}>{sub}</p>
          <a className="hb-cta" style={{ fontFamily: "var(--body)" }} onClick={(e) => e.preventDefault()} href="#">
            {cta}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
          </a>
        </div>
        <div className="hb-product">
          <div className="hb-halo" />
          {imageUrl ? (
            <img src={imageUrl} alt="" className="hb-genimg" style={{ width: "100%", height: "100%", objectFit: "contain", position: "relative", zIndex: 2 }} />
          ) : slot ? (
            <image-slot
              id={`bottle-${seg.id}${idSuffix}`}
              shape="rect"
              fit="contain"
              placeholder="Suelta el frasco (PNG IA)"
            ></image-slot>
          ) : (
            <div className="hb-bottle"><Bottle seg={seg} /></div>
          )}
          {discount.big !== "—" ? <span className="hb-discount"><b>{discount.big}</b>{discount.small ? <span>{discount.small}</span> : null}</span> : null}
        </div>
      </div>
      {brandName ? <div className="hb-logo">{brandName}</div> : null}
    </div>
  );
}

function num(v, dflt) {
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) ? n : dflt;
}

Object.assign(window, { Banner, Bottle });
