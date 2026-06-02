from __future__ import annotations

from typing import Any

SECTION_KEY = "sections/aijolot-banner-agent.liquid"
SNIPPET_KEY = "snippets/aijolot-banner-agent-block.liquid"

CONTROLLED_SECTION = """{% comment %} Aijolot Banner Agent controlled section. Reads JSON config from shop metafield. {% endcomment %}
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
<div class="aijolot-banner-agent__block" data-campaign-id="{{ campaign.campaign_id | escape }}" data-revision-id="{{ campaign.revision_id | escape }}">
  {% if campaign.image_url %}<img class="aijolot-banner-agent__image" src="{{ campaign.image_url | escape }}" alt="{{ campaign.alt_text | default: headline | escape }}" loading="lazy">{% endif %}
  {% if headline %}<h2 class="aijolot-banner-agent__headline">{{ headline | escape }}</h2>{% endif %}
  {% if subheadline %}<p class="aijolot-banner-agent__subheadline">{{ subheadline | escape }}</p>{% endif %}
  {% if cta_text and campaign.cta_url %}<a class="aijolot-banner-agent__cta" href="{{ campaign.cta_url | escape }}">{{ cta_text | escape }}</a>{% endif %}
</div>
"""


def install_theme_files(client: Any, *, theme_id: str) -> list[dict[str, Any]]:
    """Idempotently upsert controlled Liquid files into a Shopify theme."""
    return [
        client.put_theme_asset(theme_id=theme_id, key=SECTION_KEY, value=CONTROLLED_SECTION),
        client.put_theme_asset(theme_id=theme_id, key=SNIPPET_KEY, value=CONTROLLED_SNIPPET),
    ]
