from __future__ import annotations

import json
import re
from typing import Any

SECTION_KEY = "sections/aijolot-banner-agent.liquid"
SNIPPET_KEY = "snippets/aijolot-banner-agent-block.liquid"
CSS_KEY = "assets/aijolot-banner-agent.css"
ACTIVE_BANNER_KEY = "snippets/aijolot-active-banner.liquid"

# Placement type -> stable anchor key. Each anchor has a placeholder snippet the
# merchant drops once into the theme at the matching spot. Publish never edits
# merchant templates; it only writes the shop metafield config the snippets read.
ANCHOR_BY_PLACEMENT_KEY: dict[str, str] = {
    "announcement_bar": "aijolot-announce",
    "hero_main": "aijolot-hero",
    "promo_card": "aijolot-promo",
    "collection_header": "aijolot-collection-header",
    "pdp_strip": "aijolot-pdp-strip",
    "pdp_cross_sell": "aijolot-pdp-cross",
    "footer_cta": "aijolot-footer",
    "search_results_banner": "aijolot-search",
}


def anchor_snippet_key(anchor: str) -> str:
    return f"snippets/{anchor}.liquid"


CONTROLLED_SECTION = """{% comment %} Aijolot Banner Agent controlled section. Renders all active campaigns. {% endcomment %}
{% assign now_s = 'now' | date: '%s' | plus: 0 %}
{% assign campaigns = shop.metafields.aijolot.banner_campaigns.value %}
{% if campaigns == blank %}{% assign campaigns = shop.metafields.aijolot.banner_campaigns %}{% endif %}
{% for campaign in campaigns %}
  {% assign active_from_s = campaign.active_from | date: '%s' | plus: 0 %}
  {% assign active_until_s = campaign.active_until | date: '%s' | plus: 0 %}
  {% if campaign.active_from == blank or active_from_s <= now_s %}
    {% if campaign.active_until == blank or active_until_s > now_s %}
      {% render 'aijolot-active-banner' %}
    {% endif %}
  {% endif %}
{% endfor %}
{% schema %}
{"name":"Aijolot Banner Agent","settings":[],"presets":[{"name":"Aijolot Banner Agent"}]}
{% endschema %}
"""

BANNER_CSS = """.aijolot-banner-agent {
  width: 100%;
  margin: 0;
  padding: 0;
}

.aijolot-banner-agent__block {
  position: relative;
  width: 100%;
  min-height: clamp(360px, 56vw, 720px);
  display: grid;
  align-items: center;
  overflow: hidden;
  background: #F4F1EA;
  background-position: center;
  background-size: cover;
}

/* Hidden accessibility img — visual comes from the CSS background-image */
.aijolot-banner-agent__media {
  position: absolute;
  inset: 0;
  z-index: 0;
  opacity: .01;
  pointer-events: none;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.aijolot-banner-agent__content {
  position: relative;
  z-index: 1;
  width: min(1120px, 92vw);
  padding: clamp(28px, 6vw, 80px);
}

.aijolot-banner-agent__copy {
  max-width: 620px;
  padding: clamp(18px, 3vw, 32px);
  border-radius: 28px;
  background: rgba(255,255,255,.78);
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
  color: #111827;
}

.aijolot-banner-agent__eyebrow {
  margin: 0 0 12px;
  font-size: .82rem;
  font-weight: 800;
  letter-spacing: .13em;
  text-transform: uppercase;
}

.aijolot-banner-agent__headline {
  margin: 0;
  font-size: clamp(2rem, 6vw, 5.25rem);
  font-weight: 700;
  line-height: .96;
  letter-spacing: -.055em;
}

.aijolot-banner-agent__subheadline {
  margin: 12px 0 0;
  font-size: clamp(1rem, 2vw, 1.35rem);
  line-height: 1.45;
  max-width: 54ch;
}

.aijolot-banner-agent__cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 48px;
  margin-top: 20px;
  padding: 0 22px;
  border-radius: 999px;
  background: #2563EB;
  color: #ffffff;
  font-weight: 800;
  text-decoration: none;
}

.aijolot-banner-agent__cta:hover {
  opacity: .88;
  color: #ffffff;
}

@media (max-width: 640px) {
  .aijolot-banner-agent__block {
    min-height: 520px;
    background-position: center;
  }
  .aijolot-banner-agent__content {
    padding: 20px;
  }
  .aijolot-banner-agent__copy {
    border-radius: 20px;
  }
}
"""

CONTROLLED_SNIPPET = """{% comment %} Aijolot Banner Agent controlled block. {% endcomment %}
{% assign headline = campaign.headline | default: campaign.title %}
{% assign subheadline = campaign.subheadline | default: campaign.subtitle %}
{% assign cta_text = campaign.cta_text | default: campaign.cta %}
{% assign anchor = campaign.placement.anchor | default: '' %}
{% assign palette_bg = campaign.palette_bg | default: '#F4F1EA' %}
{% assign palette_cta_bg = campaign.palette_cta_bg | default: '#2563EB' %}
{% assign palette_cta_text = campaign.palette_cta_text | default: '#FFFFFF' %}
{% assign palette_text = campaign.palette_text | default: '#111827' %}
<div class="aijolot-banner-agent__block" data-aijolot-anchor="{{ anchor | escape }}" data-campaign-id="{{ campaign.campaign_id | escape }}" data-revision-id="{{ campaign.revision_id | escape }}"{% if campaign.image_url %} style="background-image:linear-gradient(90deg,rgba(0,0,0,.38),rgba(0,0,0,.06)),url({{ campaign.image_url | escape }});background-size:cover;background-position:center;"{% else %} style="background-color:{{ palette_bg | escape }};"{% endif %}>
  {% if campaign.image_url %}<img class="aijolot-banner-agent__media" src="{{ campaign.image_url | escape }}" alt="{{ campaign.alt_text | default: headline | escape }}" loading="lazy" aria-hidden="true">{% endif %}
  <div class="aijolot-banner-agent__content">
    <div class="aijolot-banner-agent__copy" style="color:{{ palette_text | escape }};">
      {% if campaign.eyebrow %}<p class="aijolot-banner-agent__eyebrow">{{ campaign.eyebrow | escape }}</p>{% endif %}
      {% if headline %}<h2 class="aijolot-banner-agent__headline">{{ headline | escape }}</h2>{% endif %}
      {% if subheadline %}<p class="aijolot-banner-agent__subheadline">{{ subheadline | escape }}</p>{% endif %}
      {% if cta_text and campaign.cta_url %}<a class="aijolot-banner-agent__cta" href="{{ campaign.cta_url | escape }}" style="background:{{ palette_cta_bg | escape }};color:{{ palette_cta_text | escape }};">{{ cta_text | escape }}</a>{% endif %}
    </div>
  </div>
</div>
"""


def _anchor_snippet(anchor: str) -> str:
    """Placeholder snippet for one anchor: render only campaigns bound to it.

    Drop `{% render '<anchor>' %}` into the theme at the matching location once.
    """

    return (
        "{% comment %} Aijolot anchor placeholder: " + anchor + ". "
        "Drop {% render '" + anchor + "' %} where this banner should appear. {% endcomment %}\n"
        "{% assign now_s = 'now' | date: '%s' | plus: 0 %}\n"
        "{% assign campaigns = shop.metafields.aijolot.banner_campaigns.value %}\n"
        "{% if campaigns == blank %}{% assign campaigns = shop.metafields.aijolot.banner_campaigns %}{% endif %}\n"
        '<div class="aijolot-anchor aijolot-anchor--' + anchor + '" data-aijolot-anchor="' + anchor + '">\n'
        "  {% for campaign in campaigns %}\n"
        "    {% if campaign.placement.anchor == '" + anchor + "' %}\n"
        "      {% assign active_from_s = campaign.active_from | date: '%s' | plus: 0 %}\n"
        "      {% assign active_until_s = campaign.active_until | date: '%s' | plus: 0 %}\n"
        "      {% if campaign.active_from == blank or active_from_s <= now_s %}\n"
        "        {% if campaign.active_until == blank or active_until_s > now_s %}\n"
        "          {% render 'aijolot-banner-agent-block', campaign: campaign %}\n"
        "        {% endif %}\n"
        "      {% endif %}\n"
        "    {% endif %}\n"
        "  {% endfor %}\n"
        "</div>\n"
    )


def _extract_gradients(css_value: str) -> str:
    """Extract all *-gradient(...) layers from a CSS background value string.

    Uses balanced-parenthesis matching so nested url(#id) or color functions
    inside the gradient don't confuse the parser. Returns them as a comma-joined
    string safe for use in an HTML style attribute (no double quotes).
    Returns empty string if no gradient layers are found.
    """
    gradients: list[str] = []
    pattern = re.compile(r"(?:linear|radial|conic)-gradient\(")
    for m in pattern.finditer(css_value):
        start = m.start()
        depth = 0
        i = start
        while i < len(css_value):
            if css_value[i] == "(":
                depth += 1
            elif css_value[i] == ")":
                depth -= 1
                if depth == 0:
                    gradients.append(css_value[start : i + 1])
                    break
            i += 1
    return ", ".join(gradients)


def _inject_bg_inline(inner_html: str, bg_css: str) -> str:
    """Inject the gradient background from bgCss directly into the #hbL div's
    inline style attribute.

    Inline styles beat any class or ID rule from an external stylesheet, so the
    gradient renders even when the Shopify theme has conflicting CSS.

    We extract only *-gradient() functions (safe for HTML attributes) and discard
    url(data:...) texture layers — double-quotes inside those break the HTML
    style attribute and they may be CSP-blocked anyway.
    """
    if not bg_css or 'class="hb-banner hb-live" style="' not in inner_html:
        return inner_html

    # Extract CSS properties from inside the first {…} block.
    m = re.search(r"\{([^}]+)\}", bg_css, re.DOTALL)
    if not m:
        return inner_html
    props = m.group(1).strip()

    inline_parts: list[str] = []

    # Look for gradient layers in background / background-image properties.
    for prop_name in ("background-image", "background"):
        bp = re.search(rf"{prop_name}\s*:\s*(.+?)(?=;[^;]|\Z)", props, re.DOTALL | re.IGNORECASE)
        if bp:
            safe = _extract_gradients(bp.group(1))
            if safe:
                inline_parts.append(f"background:{safe}")
            break

    # If no gradient found, fall back to a plain background-color if present.
    if not inline_parts:
        bc = re.search(r"background-color\s*:\s*([^;]+)", props, re.IGNORECASE)
        if bc:
            inline_parts.append(f"background:{bc.group(1).strip()}")

    # CSS custom properties (--bg-a / --bg-b) — used when bgCss sets vars only.
    if not inline_parts:
        for var in ("--bg-a", "--bg-b", "--glow"):
            vm = re.search(rf"{re.escape(var)}\s*:\s*([^;]+)", props)
            if vm:
                inline_parts.append(f"{var}:{vm.group(1).strip()}")

    if not inline_parts:
        return inner_html

    injection = ";".join(inline_parts) + ";"
    return inner_html.replace(
        'class="hb-banner hb-live" style="',
        f'class="hb-banner hb-live" style="{injection}',
        1,
    )


def install_live_banner_as_snippet(
    client: Any,
    *,
    theme_id: str,
    live_spec: dict[str, Any],
    image_url: str = "",
    cta_url: str = "",
) -> dict[str, Any]:
    """Generate the exact canvas banner via banner_template.js (Node) and install it
    as snippets/aijolot-active-banner.liquid.  The output is pixel-for-pixel what
    the web app canvas preview shows — same JS template, same CSS, same spec.

    Falls back silently to an empty dict if Node is unavailable or spec is empty.
    """
    from app.services.banners.banner_render import _banner_css, _banner_inner_html, _font_link

    # Inject cta_url into the spec so banner_template.js writes the real href.
    spec = dict(live_spec)
    if cta_url and not spec.get("ctaUrl"):
        spec["ctaUrl"] = cta_url

    try:
        inner_html = _banner_inner_html(spec, "desktop")
    except Exception:
        inner_html = ""

    if not inner_html:
        return {}

    # Replace any remaining localhost asset URLs with the rehosted CDN URL.
    if image_url and not image_url.startswith(("http://127.", "http://localhost")):
        inner_html = re.sub(
            r"https?://(?:127\.0\.0\.1|localhost):\d+/[^\s\"'\\)>]+",
            image_url,
            inner_html,
        )

    # Inject the background gradient directly into the banner wrapper's inline
    # style so the Shopify theme can't wash it out via class-level CSS rules.
    inner_html = _inject_bg_inline(inner_html, str(spec.get("bgCss") or ""))

    display = str(spec.get("displayFont") or "Space Grotesk")
    body = str(spec.get("bodyFont") or "Inter")
    font_link = _font_link(display, body)
    css = _banner_css()

    snippet = (
        "{%- comment -%} Aijolot active banner — canvas-exact. Do not edit manually. {%- endcomment -%}\n"
        f"{font_link}\n"
        f"<style>{css}</style>\n"
        f"{inner_html}\n"
    )
    return client.put_theme_asset(theme_id=theme_id, key=ACTIVE_BANNER_KEY, value=snippet)


def install_campaign_preview_as_snippet(
    client: Any,
    *,
    theme_id: str,
    html_preview: str,
    image_url: str = "",
    cta_url: str = "",
) -> dict[str, Any]:
    """Extract CSS + HTML from html_preview, scope global selectors, and write as
    snippets/aijolot-active-banner.liquid so the storefront renders an exact copy
    of the preview instead of a manually-crafted approximation.

    Called by publisher after rehost_config_assets so image_url is already CDN.
    """
    # --- Extract <style> block ---
    style_match = re.search(r"<style>(.*?)</style>", html_preview, re.DOTALL)
    raw_css = style_match.group(1) if style_match else ""

    # Scope global selectors so they don't bleed into the Shopify theme.
    scoped_css = raw_css
    # Pull body color into .aij-banner scope instead of deleting it entirely.
    scoped_css = re.sub(r"\bbody\s*\{([^}]*)\}", lambda m: ".aij-banner__copy {" + m.group(1) + "}", scoped_css)
    scoped_css = re.sub(r"(?<!\S)\*\s*\{", ".aij-banner * {", scoped_css)  # * {} → .aij-banner * {}
    scoped_css = re.sub(r"\bh1\s*\{", ".aij-banner h1 {", scoped_css)   # h1 {} → scoped
    scoped_css = re.sub(r"(?<![.#\w])p\s*\{", ".aij-banner p {", scoped_css)  # p {} → scoped

    # --- Extract <main> content ---
    main_match = re.search(r"<main>(.*?)</main>", html_preview, re.DOTALL)
    main_html = main_match.group(1).strip() if main_match else ""

    # Replace the preview placeholder CTA href with the real destination URL.
    if cta_url:
        main_html = main_html.replace('href="#banner-cta"', f'href="{cta_url}"')

    snippet = (
        "{%- comment -%} Aijolot active banner — exact preview HTML. Do not edit manually. {%- endcomment -%}\n"
        f"<style>{scoped_css}</style>\n"
        f"{main_html}\n"
    )

    # Replace ALL localhost asset URLs (in both CSS and HTML) with the CDN URL.
    # The preview uses 127.0.0.1:PORT for local Supabase; Shopify visitors can't reach it.
    if image_url and not image_url.startswith(("http://127.", "http://localhost")):
        snippet = re.sub(
            r"https?://(?:127\.0\.0\.1|localhost):\d+/[^\s\"'\\)>]+",
            image_url,
            snippet,
        )
    return client.put_theme_asset(theme_id=theme_id, key=ACTIVE_BANNER_KEY, value=snippet)


def install_theme_files(client: Any, *, theme_id: str) -> list[dict[str, Any]]:
    """Idempotently upsert controlled Liquid files + per-anchor placeholders.

    All writes are append-only `aijolot-*` assets; merchant templates are never
    overwritten. The merchant references the anchor snippets at the desired
    spots once via `{% render '<anchor>' %}`.
    """

    # Controlled Liquid first (merchant-referenceable anchors), then the
    # supplementary stylesheet asset. The banner itself renders from inline
    # styles, so the CSS asset is a non-load-bearing extra and need not lead.
    results = [
        client.put_theme_asset(theme_id=theme_id, key=SECTION_KEY, value=CONTROLLED_SECTION),
        client.put_theme_asset(theme_id=theme_id, key=SNIPPET_KEY, value=CONTROLLED_SNIPPET),
        client.put_theme_asset(theme_id=theme_id, key=CSS_KEY, value=BANNER_CSS),
    ]
    for anchor in dict.fromkeys(ANCHOR_BY_PLACEMENT_KEY.values()):
        results.append(
            client.put_theme_asset(theme_id=theme_id, key=anchor_snippet_key(anchor), value=_anchor_snippet(anchor))
        )
    return results


def installed_asset_keys() -> list[str]:
    """Asset keys install_theme_files writes — used for dry-run reporting."""

    keys = [SECTION_KEY, SNIPPET_KEY, CSS_KEY]
    keys.extend(anchor_snippet_key(a) for a in dict.fromkeys(ANCHOR_BY_PLACEMENT_KEY.values()))
    return keys


# Map campaign placement target_type to its OS 2.0 template file.
_TEMPLATE_BY_TARGET_TYPE: dict[str, str] = {
    "home": "templates/index.json",
    "collection": "templates/collection.json",
    "product": "templates/product.json",
    "all": "templates/index.json",
}

_SECTION_ID = "aijolot-banner-agent"
_SECTION_TYPE = "aijolot-banner-agent"


def inject_section_into_template(client: Any, *, theme_id: str, target_type: str | None) -> bool:
    """Add the aijolot section to the matching OS 2.0 template JSON if not already present.

    Reads the current template, prepends the section to the order list, and writes
    it back. Never overwrites existing merchant sections — only adds ours at position 0.
    Returns True if the template was modified, False if already present or on any error.
    """
    template_key = _TEMPLATE_BY_TARGET_TYPE.get(str(target_type or ""))
    if not template_key:
        return False

    try:
        asset = client.get_theme_asset(theme_id=theme_id, key=template_key)
    except Exception:
        return False

    value = (asset or {}).get("value") or ""
    if not value:
        return False

    try:
        template = json.loads(value)
    except json.JSONDecodeError:
        return False

    sections = template.get("sections") or {}
    order = list(template.get("order") or [])

    if _SECTION_ID in sections:
        return False

    sections[_SECTION_ID] = {"type": _SECTION_TYPE, "settings": {}}
    order.insert(0, _SECTION_ID)
    template["sections"] = sections
    template["order"] = order

    try:
        client.put_theme_asset(theme_id=theme_id, key=template_key, value=json.dumps(template, indent=2))
    except Exception:
        return False

    return True
