"""Standalone HTML render of the live banner + headless screenshots.

Mirrors the frontend Banner.jsx "live" render (banner.css .hb-live / .hb-live-stack)
as a self-contained HTML string so the assembly agent can render it headlessly at the
three breakpoints and screenshot it for a visual self-review loop.

Desktop  → wide banner (≈2.4), absolute %-composed copy + hero.
Tablet/Mobile → taller fold, vertical-flow stack (hero on top, copy below).
"""

from __future__ import annotations

import html as _html
from typing import Any

# (width_px, default_aspect_ratio, stacked) per breakpoint — matches the frontend.
BREAKPOINTS: dict[str, tuple[int, float, bool]] = {
    "desktop": (1440, 2.4, False),
    "tablet": (768, 1.0, True),
    "mobile": (390, 0.82, True),
}


def aspect_for(breakpoint: str, layout: dict[str, Any] | None) -> float:
    """Per-breakpoint aspect ratio, overridable from the layout (the review loop
    lowers it to give a taller fold when stacked content overflows)."""
    _, default_ar, _ = BREAKPOINTS.get(breakpoint, BREAKPOINTS["desktop"])
    L = layout or {}
    key = {"desktop": "aspectRatio", "tablet": "aspectRatioTablet", "mobile": "aspectRatioMobile"}.get(breakpoint)
    try:
        v = L.get(key)
        return float(v) if v is not None else default_ar
    except (TypeError, ValueError):
        return default_ar


def _esc(value: Any) -> str:
    return _html.escape(str(value or ""))


def _font_link(*families: str) -> str:
    fams = [f for f in dict.fromkeys(families) if f]
    if not fams:
        return ""
    spec = "&".join("family=" + f.replace(" ", "+") + ":wght@400;600;700;800;900" for f in fams)
    return f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{spec}&display=swap">'


def _scoped_bg(bg_css: str) -> str:
    # Banner.jsx scopes the agent CSS from `.aijolot-banner` onto `.hb-bg`.
    return str(bg_css or "").replace(".aijolot-banner", ".hb-bg")


def render_banner_html(spec: dict[str, Any], *, breakpoint: str = "desktop") -> str:
    """Return a self-contained HTML document for one breakpoint."""
    width, _default_ar, stacked = BREAKPOINTS.get(breakpoint, BREAKPOINTS["desktop"])
    L = spec.get("layout") or {}
    ar = aspect_for(breakpoint, L)
    display = spec.get("displayFont") or "Space Grotesk"
    body = spec.get("bodyFont") or "Inter"
    ink = spec.get("textColor") or "#111111"
    headline = _esc(spec.get("headline") or "")
    eyebrow = _esc((spec.get("eyebrow") or "").upper())
    sub = _esc(spec.get("sub") or "")
    cta = _esc(spec.get("cta") or "")
    img = spec.get("imageUrl") or ""
    promo = str(spec.get("promo") or "")
    disc = _discount(promo)

    def n(key: str, d: float) -> float:
        try:
            return float(L.get(key, d))
        except (TypeError, ValueError):
            return d

    css = _BASE_CSS + "\n" + _scoped_bg(spec.get("bgCss") or "")
    badge = (
        f'<span class="hb-discount"><b>{_esc(disc[0])}</b>{("<span>" + _esc(disc[1]) + "</span>") if disc[1] else ""}</span>'
        if disc[0] != "—" else ""
    )
    copy_inner = (
        (f'<span class="hb-eyebrow">{eyebrow}</span>' if eyebrow else "")
        + f'<h2 class="hb-headline">{headline}</h2>'
        + (f'<p class="hb-sub">{sub}</p>' if sub else "")
        + (f'<a class="hb-cta">{cta}</a>' if cta else "")
    )

    if stacked:
        stack_hero = f'<img class="hb-genimg hb-stack-hero" src="{_esc(img)}">' if img else ""
        body_html = (
            f'<div class="hb-bg"></div>{badge}'
            f'<div class="hb-stack-inner">'
            f'{stack_hero}'
            f'<div class="hb-live-copy hb-stack-copy">{copy_inner}</div>'
            f'</div>'
        )
        cls = "hb-banner hb-live hb-live-stack"
    else:
        tX, tY, tW = n("textX", 6), n("textY", 50), n("textW", 48)
        align = (L.get("textAlign") or "left").lower()
        align = align if align in {"left", "center", "right"} else "left"
        items = {"left": "flex-start", "center": "center", "right": "flex-end"}[align]
        hX, hY, hW, hH = n("heroX", 76), n("heroY", 50), n("heroW", 46), n("heroH", 92)
        hero = (
            f'<img class="hb-genimg" style="position:absolute;left:{hX}%;top:{hY}%;width:{hW}%;height:{hH}%;'
            f'transform:translate(-50%,-50%);object-fit:contain;z-index:2" src="{_esc(img)}">'
            if img else ""
        )
        copy = (
            f'<div class="hb-live-copy" style="left:{tX}%;top:{tY}%;width:{tW}%;transform:translateY(-50%);'
            f'text-align:{align};align-items:{items}">{copy_inner}</div>'
        )
        body_html = f'<div class="hb-bg"></div>{hero}{copy}{badge}'
        cls = "hb-banner hb-live"

    style_vars = (
        f"--banner-ar:{ar};--disp:'{display}';--body:'{body}';--ink:{ink};"
        f"--accent:#22D3EE;--chip:#FFD23F;--glow:rgba(255,255,255,.3)"
    )
    return f"""<!doctype html><html><head><meta charset="utf-8">
{_font_link(display, body)}
<style>{css}</style></head>
<body style="margin:0;background:#eef2f6;">
<div style="width:{width}px;">
  <div class="{cls}" style="{style_vars}">{body_html}</div>
</div>
</body></html>"""


def _discount(promo: str) -> tuple[str, str]:
    import re

    m = re.search(r"(\d{1,3})\s*%", promo or "")
    if m:
        return (m.group(1) + "%", "OFF")
    return ((promo[:10] or "—"), "")


async def screenshot_breakpoints(spec: dict[str, Any], *, breakpoints: list[str] | None = None) -> dict[str, bytes]:
    """Render the banner headlessly at each breakpoint; return {breakpoint: png_bytes}."""
    from playwright.async_api import async_playwright

    bps = breakpoints or ["desktop", "tablet", "mobile"]
    out: dict[str, bytes] = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        try:
            for bp in bps:
                width, _d, _ = BREAKPOINTS.get(bp, BREAKPOINTS["desktop"])
                ar = aspect_for(bp, spec.get("layout"))
                height = int(width / ar) + 28
                page = await browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                await page.set_content(render_banner_html(spec, breakpoint=bp), wait_until="networkidle")
                await page.wait_for_timeout(450)  # let webfonts/hero settle
                el = await page.query_selector(".hb-banner")
                out[bp] = await (el.screenshot(type="png") if el else page.screenshot(type="png"))
                await page.close()
        finally:
            await browser.close()
    return out


_BASE_CSS = """
*{box-sizing:border-box}
.hb-banner{container-type:inline-size;position:relative;width:100%;border-radius:18px;overflow:hidden;isolation:isolate;color:var(--ink);font-family:var(--body),'Inter',sans-serif;}
.hb-live{aspect-ratio:var(--banner-ar,2.4);width:100%;}
.hb-bg{position:absolute;inset:0;z-index:0;background:linear-gradient(120deg,#ff9a3c,#ff5f9e);}
.hb-live-copy{position:absolute;z-index:3;display:flex;flex-direction:column;gap:clamp(6px,1.2cqw,16px);}
.hb-live .hb-eyebrow{font-family:var(--body);font-weight:600;letter-spacing:.24em;text-transform:uppercase;font-size:clamp(8px,1.15cqw,14px);color:var(--ink);opacity:.85;margin:0;}
.hb-live .hb-headline{font-family:var(--disp),sans-serif;font-weight:800;font-size:clamp(20px,5.4cqw,72px);line-height:.98;letter-spacing:-.02em;white-space:pre-line;margin:0;color:var(--ink);}
.hb-live .hb-sub{font-family:var(--body);font-size:clamp(10px,1.7cqw,21px);line-height:1.45;color:var(--ink);opacity:.92;margin:0;max-width:42ch;}
.hb-live .hb-cta{align-self:flex-start;margin-top:clamp(4px,1.2cqw,14px);display:inline-flex;align-items:center;gap:.5em;font-family:var(--body);font-weight:700;font-size:clamp(10px,1.5cqw,18px);padding:clamp(8px,1.4cqw,16px) clamp(14px,2.4cqw,30px);border-radius:9999px;background:var(--accent);color:#06121f;box-shadow:0 12px 30px -8px var(--glow);}
.hb-live .hb-genimg{filter:drop-shadow(0 18px 36px rgba(0,0,0,.28));}
.hb-live .hb-discount{position:absolute;z-index:4;top:14%;right:7%;display:flex;flex-direction:column;align-items:center;justify-content:center;width:clamp(40px,7cqw,84px);aspect-ratio:1;border-radius:50%;background:var(--chip);color:#0b0b0d;font-family:var(--disp);font-weight:800;line-height:1;transform:rotate(8deg);box-shadow:0 8px 22px -6px rgba(0,0,0,.45);}
.hb-live .hb-discount b{font-size:clamp(13px,2.6cqw,28px)}
.hb-live .hb-discount span{font-size:clamp(6px,1cqw,11px);letter-spacing:.1em}
.hb-live-stack .hb-stack-inner{position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:clamp(8px,2.4cqw,20px);padding:clamp(18px,6cqw,40px) clamp(16px,7cqw,48px);text-align:center;}
.hb-live-stack .hb-stack-hero{flex:0 1 auto;max-height:46%;width:auto;max-width:74%;object-fit:contain;filter:drop-shadow(0 16px 30px rgba(0,0,0,.26));}
.hb-live-stack .hb-stack-copy{position:static;transform:none;width:100%;display:flex;flex-direction:column;align-items:center;gap:clamp(5px,1.6cqw,12px);}
.hb-live-stack .hb-eyebrow{font-size:clamp(9px,2.4cqw,14px);letter-spacing:.22em;}
.hb-live-stack .hb-headline{font-size:clamp(22px,8.2cqw,44px);line-height:1.0;}
.hb-live-stack .hb-sub{font-size:clamp(11px,3.2cqw,18px);max-width:32ch;}
.hb-live-stack .hb-cta{align-self:center;}
.hb-live-stack .hb-discount{top:5%;right:6%;}
"""


__all__ = ["render_banner_html", "screenshot_breakpoints", "BREAKPOINTS"]
