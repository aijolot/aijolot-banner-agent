from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.agents.state import BannerAssets, Concept
from app.services.brands.color_roles import resolve_color_token

_DEFAULT_BG = "#F4F1EA"
_DEFAULT_TEXT = "#111827"
_DEFAULT_ACCENT = "#2563EB"
_DEFAULT_ACCENT_TEXT = "#FFFFFF"
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class RenderedPreview:
    html: str
    metadata: dict[str, Any]


def _dump_model(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def _brand_name(brand: Any) -> str:
    data = _dump_model(brand)
    return str(data.get("name") or getattr(brand, "name", "Brand") or "Brand")


def _color(concept: Concept, brand: Any, key: str, fallback: str) -> str:
    token = (concept.palette_usage or {}).get(key, "")
    value = resolve_color_token(brand, token) or token
    return value.upper() if isinstance(value, str) and _HEX_RE.match(value) else fallback


def _asset_url_map(source: dict[Any, str] | None) -> dict[int, str]:
    out: dict[int, str] = {}
    for key, url in (source or {}).items():
        try:
            width = int(key)
        except (TypeError, ValueError):
            continue
        if url:
            safe_url = _safe_url(str(url))
            if safe_url:
                out[width] = safe_url
    return dict(sorted(out.items()))


def _best_image_url(assets: BannerAssets) -> str:
    for mapping in (assets.webp, assets.avif, assets.fallback_jpg):
        urls = _asset_url_map(mapping)
        if urls:
            return _safe_url(urls[max(urls)])
    for record in assets.asset_records:
        url = record.get("public_url") or record.get("url")
        if url:
            return _safe_url(str(url))
    return ""


def _safe_url(url: str) -> str:
    parsed = urlparse(str(url).strip())
    if parsed.scheme in {"http", "https", "data", "memory"}:
        return str(url).strip()
    return ""


def _css_url(url: str) -> str:
    return (
        _safe_url(url)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "")
        .replace("\r", "")
        .replace("<", "\\3C ")
        .replace(">", "\\3E ")
    )


def _srcset(mapping: dict[Any, str] | None) -> str:
    urls = _asset_url_map(mapping)
    return ", ".join(f"{html.escape(url, quote=True)} {width}w" for width, url in urls.items())


def _copy(concept: Concept, key: str, fallback: str = "") -> str:
    value = (concept.copy or {}).get(key, fallback)
    return str(value or fallback).strip()


def _json_script(value: dict[str, Any]) -> str:
    return (
        json.dumps(value, sort_keys=True)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_banner_preview(concept: Concept, assets: BannerAssets, *, brand: Any = None) -> RenderedPreview:
    """Render deterministic, escaped standalone HTML for banner preview.

    Copy is always HTML text; imagery is referenced through responsive CSS/background
    assets so generated image pixels never need to contain text.
    """

    headline = _copy(concept, "headline", "Seasonal offer")
    subheadline = _copy(concept, "subheadline", _copy(concept, "body", "Discover the collection."))
    eyebrow = _copy(concept, "eyebrow", _copy(concept, "kicker", "Featured"))
    cta = _copy(concept, "cta", "Shop now")
    alt_text = assets.alt_text_suggestion or f"{_brand_name(brand)} promotional banner background"
    image_url = _best_image_url(assets)

    bg = _color(concept, brand, "background", _DEFAULT_BG)
    text = _color(concept, brand, "text", _DEFAULT_TEXT)
    cta_bg = _color(concept, brand, "cta_background", _DEFAULT_ACCENT)
    cta_text = _color(concept, brand, "cta_text", _DEFAULT_ACCENT_TEXT)

    schema = {
        "@context": "https://schema.org",
        "@type": "Offer",
        "name": headline,
        "description": subheadline,
        "availability": "https://schema.org/InStock",
        "url": "#banner-cta",
    }
    css_image = f"background-image: linear-gradient(90deg, rgba(0,0,0,.38), rgba(0,0,0,.06)), url(\"{_css_url(image_url)}\");" if image_url else ""

    avif_source = f'<source type="image/avif" srcset="{_srcset(assets.avif)}" sizes="100vw">' if _srcset(assets.avif) else ""
    webp_source = f'<source type="image/webp" srcset="{_srcset(assets.webp)}" sizes="100vw">' if _srcset(assets.webp) else ""
    fallback = html.escape(next(iter(_asset_url_map(assets.fallback_jpg).values()), image_url), quote=True)

    html_out = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(headline)} | {html.escape(_brand_name(brand))}</title>
  <meta name="description" content="{html.escape(subheadline, quote=True)}">
  <meta property="og:title" content="{html.escape(headline, quote=True)}">
  <meta property="og:description" content="{html.escape(subheadline, quote=True)}">
  <meta property="og:image" content="{html.escape(image_url, quote=True)}">
  <style>
    :root {{--aij-bg:{bg};--aij-text:{text};--aij-cta-bg:{cta_bg};--aij-cta-text:{cta_text};}}
    * {{box-sizing:border-box}} body {{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;background:#fff;color:var(--aij-text)}}
    .aij-banner {{position:relative;min-height:clamp(360px,56vw,720px);display:grid;align-items:center;overflow:hidden;background:var(--aij-bg);{css_image}background-position:center;background-size:cover;}}
    .aij-banner__media {{position:absolute;inset:0;z-index:0;opacity:.01;pointer-events:none}} .aij-banner__media img {{width:100%;height:100%;object-fit:cover}}
    .aij-banner__content {{position:relative;z-index:1;width:min(1120px,92vw);padding:clamp(28px,6vw,80px);}}
    .aij-banner__copy {{max-width:620px;padding:clamp(18px,3vw,32px);border-radius:28px;background:rgba(255,255,255,.78);backdrop-filter:blur(6px)}}
    .aij-eyebrow {{margin:0 0 12px;font-size:.82rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase}}
    h1 {{margin:0;font-size:clamp(2rem,6vw,5.25rem);line-height:.96;letter-spacing:-.055em}} p {{font-size:clamp(1rem,2vw,1.35rem);line-height:1.45;max-width:54ch}}
    .aij-cta {{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:0 22px;border-radius:999px;background:var(--aij-cta-bg);color:var(--aij-cta-text);font-weight:800;text-decoration:none}}
    .sr-only {{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}}
    @media (max-width: 640px) {{.aij-banner {{min-height:520px;background-position:center}} .aij-banner__content {{padding:20px}} .aij-banner__copy {{border-radius:20px}}}}
  </style>
  <script type="application/ld+json">{_json_script(schema)}</script>
</head>
<body>
  <main>
    <section class="aij-banner" aria-labelledby="aij-banner-title" role="region">
      <picture class="aij-banner__media" aria-hidden="true">
        {avif_source}
        {webp_source}
        <img src="{fallback}" alt="" loading="eager" decoding="async">
      </picture>
      <div class="aij-banner__content">
        <div class="aij-banner__copy">
          <p class="aij-eyebrow">{html.escape(eyebrow)}</p>
          <h1 id="aij-banner-title">{html.escape(headline)}</h1>
          <p>{html.escape(subheadline)}</p>
          <a class="aij-cta" href="#banner-cta" aria-label="{html.escape(cta, quote=True)}">{html.escape(cta)}</a>
          <span class="sr-only">{html.escape(alt_text)}</span>
        </div>
      </div>
    </section>
  </main>
</body>
</html>"""
    return RenderedPreview(
        html=html_out,
        metadata={
            "headline": headline,
            "description": subheadline,
            "image_url": image_url,
            "alt_text": alt_text,
            "schema_type": "Offer",
            "breakpoints": sorted(set(_asset_url_map(assets.webp)) | set(_asset_url_map(assets.avif)) | set(_asset_url_map(assets.fallback_jpg))),
            "avif_skipped": bool((assets.optimization_report or {}).get("avif_skipped")),
            "optimization_report": assets.optimization_report or {},
        },
    )


__all__ = ["RenderedPreview", "render_banner_preview"]
