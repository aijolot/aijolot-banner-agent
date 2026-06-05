/* Aijolot Banner Agent — SINGLE SOURCE OF TRUTH for the live banner markup.
 *
 * Isomorphic plain JS used by BOTH the in-browser Canvas (Banner.jsx injects this
 * HTML) and the backend headless review (Python runs this file via Node). The CSS
 * lives only in banner.css; this module emits the DOM + scoped background + the
 * percent composition. Keep it framework-free so it runs in the browser and in Node.
 *
 * Creative liberties (optional, agent-driven):
 *  - hero W/H growth + `heroBehind`: the hero may grow and sit BEHIND the copy.
 *  - styled headline runs: per-word bold/italic/underline/color/scale to emphasize.
 */
(function (root) {
  function esc(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function num(v, d) { var n = typeof v === "number" ? v : parseFloat(v); return isFinite(n) ? n : d; }
  // Only allow safe color tokens (hex / rgb[a] / a few names) — never arbitrary CSS.
  function safeColor(c) {
    c = String(c || "").trim();
    if (/^#[0-9a-fA-F]{3,8}$/.test(c)) return c;
    if (/^rgba?\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*(,\s*[\d.]+\s*)?\)$/.test(c)) return c;
    if (/^[a-zA-Z]{3,20}$/.test(c)) return c;
    return null;
  }

  function discountParts(promo) {
    var s = String(promo || "");
    var m = s.match(/(\d{1,3})\s*%/);
    if (m) return { big: m[1] + "%", small: "OFF" };
    return { big: (s.slice(0, 10) || "—"), small: "" };
  }

  function aspectFor(bp, L) {
    L = L || {};
    if (bp === "tablet") return num(L.aspectRatioTablet, 1.0);
    if (bp === "mobile") return num(L.aspectRatioMobile, 0.82);
    return num(L.aspectRatio, 2.4);
  }

  // Render the headline: either styled runs (per-word emphasis) or plain text.
  function renderHeadline(headline, runs) {
    if (Array.isArray(runs) && runs.length) {
      var out = "";
      for (var i = 0; i < runs.length; i++) {
        var r = runs[i] || {};
        var st = [];
        if (r.b) st.push("font-weight:900");
        if (r.i) st.push("font-style:italic");
        if (r.u) st.push("text-decoration:underline;text-decoration-thickness:.08em;text-underline-offset:.08em");
        var col = safeColor(r.color);
        if (col) st.push("color:" + col);
        var sc = num(r.scale, 1);
        if (sc && sc !== 1) st.push("font-size:" + Math.max(0.6, Math.min(2.0, sc)) + "em");
        var txt = esc(r.text).replace(/\n/g, "<br>");
        out += st.length ? '<span style="' + st.join(";") + '">' + txt + "</span>" : txt;
        // preserve a space between runs unless the run already ends/starts with one
        if (i < runs.length - 1 && !/\s$/.test(r.text || "")) out += " ";
      }
      return out;
    }
    return esc(headline).replace(/\n/g, "<br>");
  }

  function scopedBg(bgCss, scopeId) {
    return String(bgCss || "").split(".aijolot-banner").join("#" + scopeId + " .hb-bg");
  }

  // Returns "<style>…scoped bg…</style><div class=hb-banner …>…</div>" for one breakpoint.
  function bannerLiveHTML(live, breakpoint, scopeId) {
    live = live || {};
    breakpoint = breakpoint || "desktop";
    scopeId = scopeId || "hbL";
    var L = live.layout || {};
    var stacked = breakpoint === "tablet" || breakpoint === "mobile";
    var ar = aspectFor(breakpoint, L);
    var disp = live.displayFont || "Space Grotesk";
    var body = live.bodyFont || "Inter";
    var ink = safeColor(live.textColor) || "#111111";
    var vars = "--banner-ar:" + ar + ";--disp:'" + disp + "';--body:'" + body + "';--ink:" + ink +
      ";--accent:#22D3EE;--chip:#FFD23F;--glow:rgba(255,255,255,.3)";

    var eyebrow = esc(String(live.eyebrow || "").toUpperCase());
    var headlineHTML = renderHeadline(live.headline, live.headlineRuns);
    var sub = esc(live.sub || "");
    var cta = esc(live.cta || "");
    var img = live.imageUrl || "";
    var d = discountParts(live.promo);
    var heroBehind = !!L.heroBehind;
    var heroZ = heroBehind ? 1 : 2;

    var copyInner =
      (eyebrow ? '<span class="hb-eyebrow" style="font-family:var(--body)">' + eyebrow + "</span>" : "") +
      '<h2 class="hb-headline">' + headlineHTML + "</h2>" +
      (sub ? '<p class="hb-sub" style="font-family:var(--body)">' + sub + "</p>" : "") +
      (cta ? '<a class="hb-cta" style="font-family:var(--body)">' + cta +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>' : "");
    var badge = (d.big !== "—")
      ? '<span class="hb-discount"><b>' + esc(d.big) + "</b>" + (d.small ? "<span>" + esc(d.small) + "</span>" : "") + "</span>"
      : "";

    var style = "<style>" + scopedBg(live.bgCss, scopeId) + "</style>";
    var inner;
    var cls;
    if (stacked) {
      cls = "hb-banner hb-live hb-live-stack";
      var stackHero = img ? '<img class="hb-genimg hb-stack-hero" src="' + esc(img) + '">' : "";
      inner = '<div class="hb-bg"></div>' + badge +
        '<div class="hb-stack-inner">' + stackHero +
        '<div class="hb-live-copy hb-stack-copy">' + copyInner + "</div></div>";
    } else {
      cls = "hb-banner hb-live";
      var tX = num(L.textX, 6), tY = num(L.textY, 50), tW = num(L.textW, 48);
      var align = (L.textAlign === "center" || L.textAlign === "right") ? L.textAlign : "left";
      var items = align === "center" ? "center" : align === "right" ? "flex-end" : "flex-start";
      var hX = num(L.heroX, 76), hY = num(L.heroY, 50), hW = num(L.heroW, 46), hH = num(L.heroH, 92);
      var hero = img
        ? '<img class="hb-genimg" style="position:absolute;left:' + hX + "%;top:" + hY + "%;width:" + hW +
          "%;height:" + hH + "%;transform:translate(-50%,-50%);object-fit:contain;z-index:" + heroZ + '" src="' + esc(img) + '">'
        : "";
      var copy = '<div class="hb-live-copy" style="left:' + tX + "%;top:" + tY + "%;width:" + tW +
        "%;transform:translateY(-50%);text-align:" + align + ";align-items:" + items + ";z-index:3\">" + copyInner + "</div>";
      inner = '<div class="hb-bg"></div>' + hero + copy + badge;
    }
    return style + '<div id="' + scopeId + '" class="' + cls + '" style="' + vars + '">' + inner + "</div>";
  }

  var api = { bannerLiveHTML: bannerLiveHTML, aspectFor: aspectFor };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) { root.bannerLiveHTML = bannerLiveHTML; root.AijolotBannerTemplate = api; }

  // Node CLI: `node banner_template.js <breakpoint>` with the live spec JSON on stdin
  // → prints the banner HTML (style + div). Used by the backend headless review.
  if (typeof process !== "undefined" && process.argv && process.argv[1] && /banner_template\.js$/.test(process.argv[1]) && !process.argv[1].match(/test/)) {
    var bp = process.argv[2] || "desktop";
    var chunks = "";
    process.stdin.on("data", function (c) { chunks += c; });
    process.stdin.on("end", function () {
      var spec = {};
      try { spec = JSON.parse(chunks || "{}"); } catch (e) { spec = {}; }
      process.stdout.write(bannerLiveHTML(spec, bp, "hbL"));
    });
  }
})(typeof window !== "undefined" ? window : null);
