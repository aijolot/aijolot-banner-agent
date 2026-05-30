"""ADK Tool: Shopify Admin API (themeFilesUpsert, themeFilesGet).

WRITE ACTION — only invoked after HITL approve at node 10. Coordinator
enforces this contract. Idempotent guard via payload hash. Lands in GH-19.
"""

from __future__ import annotations


async def theme_files_upsert(
    *,
    theme_id: str,
    liquid_section: str,
    block_snippet: str,
    assets: dict[str, bytes],
) -> dict:
    """Return {'shopify_section_id': ..., 'theme_id': ..., 'asset_urls': [...]}."""
    raise NotImplementedError("Lands in services/shopify/admin_client.py + GH-19.")


async def theme_files_get(theme_id: str, path: str) -> str:
    raise NotImplementedError("Lands in services/shopify/admin_client.py + GH-19.")
