from __future__ import annotations

from typing import Any

SECTION_KEY = "sections/aijolot-banner-agent.liquid"
SNIPPET_KEY = "snippets/aijolot-banner-agent-block.liquid"

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
<div class="aijolot-banner-agent" data-aijolot-banner-agent>
  {% for campaign in campaigns %}
    {% assign active_from_s = campaign.active_from | date: '%s' | plus: 0 %}
    {% assign active_until_s = campaign.active_until | date: '%s' | plus: 0 %}
    {% if campaign.active_from == blank or active_from_s <= now_s %}
      {% if campaign.active_until == blank or active_until_s > now_s %}
        {% render 'aijolot-banner-agent-block', campaign: campaign %}
      {% endif %}
    {% endif %}
  {% endfor %}
</div>
{% schema %}
{"name":"Aijolot Banner Agent","settings":[],"presets":[{"name":"Aijolot Banner Agent"}]}
{% endschema %}
"""

CONTROLLED_SNIPPET = """{% comment %} Aijolot Banner Agent controlled block. {% endcomment %}
{% assign headline = campaign.headline | default: campaign.title %}
{% assign subheadline = campaign.subheadline | default: campaign.subtitle %}
{% assign cta_text = campaign.cta_text | default: campaign.cta %}
{% assign anchor = campaign.placement.anchor | default: '' %}
<div class="aijolot-banner-agent__block" data-aijolot-anchor="{{ anchor | escape }}" data-campaign-id="{{ campaign.campaign_id | escape }}" data-revision-id="{{ campaign.revision_id | escape }}">
  {% if campaign.image_url %}<img class="aijolot-banner-agent__image" src="{{ campaign.image_url | escape }}" alt="{{ campaign.alt_text | default: headline | escape }}" loading="lazy">{% endif %}
  {% if headline %}<h2 class="aijolot-banner-agent__headline">{{ headline | escape }}</h2>{% endif %}
  {% if subheadline %}<p class="aijolot-banner-agent__subheadline">{{ subheadline | escape }}</p>{% endif %}
  {% if cta_text and campaign.cta_url %}<a class="aijolot-banner-agent__cta" href="{{ campaign.cta_url | escape }}">{{ cta_text | escape }}</a>{% endif %}
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


def install_theme_files(client: Any, *, theme_id: str) -> list[dict[str, Any]]:
    """Idempotently upsert controlled Liquid files + per-anchor placeholders.

    All writes are append-only `aijolot-*` assets; merchant templates are never
    overwritten. The merchant references the anchor snippets at the desired
    spots once via `{% render '<anchor>' %}`.
    """

    results = [
        client.put_theme_asset(theme_id=theme_id, key=SECTION_KEY, value=CONTROLLED_SECTION),
        client.put_theme_asset(theme_id=theme_id, key=SNIPPET_KEY, value=CONTROLLED_SNIPPET),
    ]
    for anchor in dict.fromkeys(ANCHOR_BY_PLACEMENT_KEY.values()):
        results.append(
            client.put_theme_asset(theme_id=theme_id, key=anchor_snippet_key(anchor), value=_anchor_snippet(anchor))
        )
    return results


def installed_asset_keys() -> list[str]:
    """Asset keys install_theme_files writes — used for dry-run reporting."""

    keys = [SECTION_KEY, SNIPPET_KEY]
    keys.extend(anchor_snippet_key(a) for a in dict.fromkeys(ANCHOR_BY_PLACEMENT_KEY.values()))
    return keys
