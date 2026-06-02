"""ADK Tool: Shopify Admin API wrappers.

The concrete Shopify client is injectable so automated tests never make live
Shopify calls. Callers must supply a configured client adapter after HITL approval.
"""

from __future__ import annotations

from typing import Any

from app.services.shopify import theme_files


async def theme_files_upsert(
    *,
    client: Any,
    theme_id: str,
    liquid_section: str | None = None,
    block_snippet: str | None = None,
    assets: dict[str, bytes] | None = None,
) -> dict:
    if liquid_section is None and block_snippet is None:
        installed = theme_files.install_theme_files(client, theme_id=theme_id)
        return {"theme_id": theme_id, "assets": installed}
    out = []
    if liquid_section is not None:
        out.append(client.put_theme_asset(theme_id=theme_id, key=theme_files.SECTION_KEY, value=liquid_section))
    if block_snippet is not None:
        out.append(client.put_theme_asset(theme_id=theme_id, key=theme_files.SNIPPET_KEY, value=block_snippet))
    return {"theme_id": theme_id, "assets": out, "asset_urls": []}


async def theme_files_get(*, client: Any, theme_id: str, path: str) -> str:
    if not hasattr(client, "get_theme_asset"):
        raise NotImplementedError("client adapter does not implement get_theme_asset")
    return str(client.get_theme_asset(theme_id=theme_id, key=path))
