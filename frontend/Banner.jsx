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

function Banner({ seg, variant = "A", slot = false, font, accent, idSuffix = "", brighter = false, ctaContrast = false }) {
  const p = seg.palette;
  const vars = {
    "--bg-a": p.bgA, "--bg-b": p.bgB, "--ink": p.ink, "--sub": p.sub,
    "--accent": accent || p.accent, "--chip": accent || p.chip,
    "--glow": p.glow, "--bottle": p.bottle, "--cap": p.cap,
    "--disp": font || "Space Grotesk",
  };
  const cls = `hb-banner hb-${variant}${brighter ? " hb-brighter" : ""}${ctaContrast ? " hb-cta-contrast" : ""}`;
  return (
    <div className={cls} style={vars} role="img"
      aria-label={`Banner Hugo Boss ${seg.eyebrow}, 10% de descuento — ${seg.headline.replace("\n", " ")}`}>
      <div className="hb-bg" />
      <div className="hb-grain" />
      <div className="hb-inner">
        <div className="hb-copy">
          <span className="hb-eyebrow">{seg.eyebrow}</span>
          <h2 className="hb-headline">{seg.headline}</h2>
          <p className="hb-sub">{seg.sub}</p>
          <a className="hb-cta" onClick={(e) => e.preventDefault()} href="#">
            {seg.cta}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
          </a>
        </div>
        <div className="hb-product">
          <div className="hb-halo" />
          {slot ? (
            <image-slot
              id={`bottle-${seg.id}${idSuffix}`}
              shape="rect"
              fit="contain"
              placeholder="Suelta el frasco (PNG IA)"
            ></image-slot>
          ) : (
            <div className="hb-bottle"><Bottle seg={seg} /></div>
          )}
          <span className="hb-discount"><b>10%</b><span>OFF</span></span>
        </div>
      </div>
      <div className="hb-logo">HUGO BOSS</div>
    </div>
  );
}

Object.assign(window, { Banner, Bottle });
