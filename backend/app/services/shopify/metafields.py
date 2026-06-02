from __future__ import annotations

import json
from typing import Any


def _current_configs(client: Any, *, namespace: str, key: str) -> list[dict[str, Any]]:
    if not hasattr(client, "get_shop_metafield"):
        return []
    raw = client.get_shop_metafield(namespace=namespace, key=key)
    if not raw:
        return []
    value = raw.get("value") if isinstance(raw, dict) else raw
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def _upsert_config(configs: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    campaign_id = str(config.get("campaign_id") or "")
    if not campaign_id:
        return [*configs, config]
    merged = [row for row in configs if str(row.get("campaign_id") or "") != campaign_id]
    merged.append(config)
    return merged


def publish_campaign_config(client: Any, *, namespace: str, key: str, config: dict[str, Any]) -> dict[str, Any]:
    configs = _upsert_config(_current_configs(client, namespace=namespace, key=key), config)
    return client.put_shop_metafield(namespace=namespace, key=key, value=json.dumps(configs, sort_keys=True, separators=(",", ":")), type="json")


def clear_campaign_config(client: Any, *, namespace: str, key: str, campaign_id: str | None = None) -> dict[str, Any]:
    if not campaign_id:
        return client.put_shop_metafield(namespace=namespace, key=key, value=json.dumps([]), type="json")
    configs = [row for row in _current_configs(client, namespace=namespace, key=key) if str(row.get("campaign_id") or "") != str(campaign_id)]
    return client.put_shop_metafield(namespace=namespace, key=key, value=json.dumps(configs, sort_keys=True, separators=(",", ":")), type="json")
