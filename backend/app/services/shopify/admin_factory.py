"""Single safe construction point for the Shopify Admin client.

Used by both live reads (fail-soft) and publishing (fail-closed). The access
token is read only here via ``require_shopify_admin`` and never logged or echoed
into any payload/response.
"""

from __future__ import annotations

from app.core.settings import MissingSettingsError, Settings
from app.services.shopify.client import ShopifyAdminClient


def configured_admin_client(settings: Settings | None = None) -> ShopifyAdminClient:
    """Build a client or raise ``MissingSettingsError`` when creds are absent.

    Use for write/publish paths that must fail closed.
    """

    resolved = settings or Settings.from_env()
    shop_domain, access_token, api_version = resolved.require_shopify_admin()
    return ShopifyAdminClient(
        shop_domain=shop_domain,
        access_token=access_token,
        api_version=api_version,
    )


def admin_client_or_none(settings: Settings | None = None) -> ShopifyAdminClient | None:
    """Return a client when configured, else ``None`` (fail-soft for reads)."""

    try:
        return configured_admin_client(settings)
    except (MissingSettingsError, ValueError):
        return None
