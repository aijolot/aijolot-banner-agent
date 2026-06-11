"""CatalogSignalService (F3) — catalog awareness → proactive suggestions.

Deterministic rules over the cached Shopify products turn inventory state into
campaign suggestions: low stock → urgency/liquidation, best-seller → highlight,
new product → launch banner, product without an active banner → coverage. Each
signal is materialized in ``catalog_signals`` (queryable/testable) and upserted
into ``agent_suggestions`` (kind='catalog_signal') with a prefilled brief.

Runs as the ``catalog_scan`` agent job (Fase 0 queue). No LLM required — copy
comes from Spanish templates; demo seed data produces signals deterministically.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

LOW_STOCK_THRESHOLD = 15
NEW_PRODUCT_DAYS = 30
BEST_SELLER_TOP_N = 1
ACTIVE_CAMPAIGN_STATUSES = ("approved", "scheduled", "publishing", "published")


class CatalogSignalRepositoryProtocol(Protocol):
    def upsert(self, *, team_id: str, product_gid: str, signal_type: str, value: dict[str, Any], store_id: str | None = None) -> dict[str, Any]: ...
    def list(self, *, team_id: str, limit: int = 100) -> list[dict[str, Any]]: ...


class InMemoryCatalogSignals:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str], dict[str, Any]] = {}

    def upsert(self, *, team_id: str, product_gid: str, signal_type: str, value: dict[str, Any], store_id: str | None = None) -> dict[str, Any]:
        key = (team_id, product_gid, signal_type)
        row = self.rows.get(key) or {"id": str(uuid4()), "team_id": team_id, "product_gid": product_gid, "signal_type": signal_type}
        row.update({"store_id": store_id, "value": value, "computed_at": datetime.now(timezone.utc).isoformat()})
        self.rows[key] = row
        return dict(row)

    def list(self, *, team_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = [dict(r) for r in self.rows.values() if r.get("team_id") == team_id]
        rows.sort(key=lambda r: str(r.get("computed_at") or ""), reverse=True)
        return rows[:limit]


class SupabaseCatalogSignals:
    table_name = "catalog_signals"
    columns = "id,team_id,store_id,product_gid,signal_type,value,computed_at"

    def __init__(self, client: Any) -> None:
        self.client = client

    def upsert(self, *, team_id: str, product_gid: str, signal_type: str, value: dict[str, Any], store_id: str | None = None) -> dict[str, Any]:
        from app.db.repositories._supabase import execute_data

        payload = {"team_id": team_id, "store_id": store_id, "product_gid": product_gid, "signal_type": signal_type, "value": value}
        out = execute_data(
            self.client.table(self.table_name).upsert(payload, on_conflict="team_id,product_gid,signal_type").select(self.columns)
        )
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def list(self, *, team_id: str, limit: int = 100) -> list[dict[str, Any]]:
        from app.db.repositories._supabase import execute_data

        out = execute_data(
            self.client.table(self.table_name).select(self.columns).eq("team_id", team_id)
            .order("computed_at", desc=True).limit(limit)
        )
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])


def _product_fields(product: Any) -> dict[str, Any]:
    """Normalize a cached product (ShopifyResourceSummary or dict) to plain fields."""
    get = (lambda k, d=None: product.get(k, d)) if isinstance(product, dict) else (lambda k, d=None: getattr(product, k, d))
    # Cache rows carry `raw`; ShopifyResourceSummary surfaces it as `metadata`.
    raw = dict(get("raw") or get("metadata") or {})
    return {
        "gid": str(get("shopify_gid") or raw.get("gid") or ""),
        "title": str(get("title") or ""),
        "image_url": get("image_url"),
        "stock": raw.get("stock") if isinstance(raw.get("stock"), int) else get("inventory_quantity"),
        "sales_rank": raw.get("sales_rank") if isinstance(raw.get("sales_rank"), int) else get("sales_rank"),
        "published_at": raw.get("published_at") or get("published_at_shop"),
        "price": raw.get("price"),
        "sale": raw.get("sale"),
    }


def _brief_payload(product: dict[str, Any], *, goal: str, urgency: str, promo: str = "", lang: str = "es") -> dict[str, Any]:
    return {
        "title": f"{goal[:60]}",
        "product_image_url": product.get("image_url"),
        "structured_brief": {
            "language": lang,
            "goal": goal,
            "urgency": urgency,
            **({"promo": promo} if promo else {}),
            "products": [
                {
                    "product_gid": product["gid"] or None,
                    "product_title": product["title"],
                    "product_image_url": product.get("image_url"),
                }
            ],
        },
    }


class CatalogSignalService:
    def __init__(
        self,
        *,
        signals: CatalogSignalRepositoryProtocol,
        suggestions: Any,  # SuggestionService
        team_id: str,
        store_id: str | None = None,
        low_stock_threshold: int = LOW_STOCK_THRESHOLD,
        lang: str = "es",
    ) -> None:
        self.signals = signals
        self.suggestions = suggestions
        self.team_id = team_id
        self.store_id = store_id
        self.low_stock_threshold = low_stock_threshold
        self.lang = lang

    def scan(self, *, products: list[Any], active_product_gids: set[str] | None = None) -> dict[str, Any]:
        """Compute signals over the cached products and upsert suggestions.

        ``active_product_gids``: product GIDs already covered by an active
        campaign (approved/scheduled/published) — used for ``no_active_banner``.
        Returns a summary for the agent-job result.
        """
        normalized = [_product_fields(p) for p in products]
        normalized = [p for p in normalized if p["title"]]
        active = active_product_gids or set()
        now = datetime.now(timezone.utc)
        created: list[str] = []

        # best_seller: explicit sales_rank when available, else deterministic
        # catalog-order proxy (first product = merchandised best seller).
        ranked = sorted(
            normalized,
            key=lambda p: (p["sales_rank"] if isinstance(p["sales_rank"], int) else 10_000),
        )
        best_sellers = ranked[:BEST_SELLER_TOP_N] if ranked else []

        for product in normalized:
            stock = product.get("stock")
            if isinstance(stock, int) and 0 < stock <= self.low_stock_threshold:
                self.signals.upsert(
                    team_id=self.team_id, store_id=self.store_id, product_gid=product["gid"],
                    signal_type="low_stock", value={"stock": stock},
                )
                from app.core.i18n import t

                self.suggestions.upsert_by_dedupe_key(
                    kind="catalog_signal",
                    dedupe_key=f"catalog:low_stock:{product['gid'] or product['title']}",
                    title=t(self.lang, "catalog.low_stock.title", title=product["title"]),
                    rationale=t(self.lang, "catalog.low_stock.rationale", stock=stock),
                    payload=_brief_payload(product, goal=t(self.lang, "catalog.low_stock.goal", title=product["title"]), urgency="high", lang=self.lang),
                    source_refs=[{"type": "catalog_item", "id": product["gid"], "title": product["title"]}],
                )
                created.append("low_stock")

            published = product.get("published_at")
            if published:
                try:
                    published_dt = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
                    if (now - published_dt).days <= NEW_PRODUCT_DAYS:
                        self.signals.upsert(
                            team_id=self.team_id, store_id=self.store_id, product_gid=product["gid"],
                            signal_type="new_product", value={"published_at": str(published)},
                        )
                        from app.core.i18n import t

                        self.suggestions.upsert_by_dedupe_key(
                            kind="catalog_signal",
                            dedupe_key=f"catalog:new_product:{product['gid'] or product['title']}",
                            title=t(self.lang, "catalog.new.title", title=product["title"]),
                            rationale=t(self.lang, "catalog.new.rationale"),
                            payload=_brief_payload(product, goal=t(self.lang, "catalog.new.goal", title=product["title"]), urgency="medium", lang=self.lang),
                            source_refs=[{"type": "catalog_item", "id": product["gid"], "title": product["title"]}],
                        )
                        created.append("new_product")
                except ValueError:
                    pass

            if product["gid"] and active and product["gid"] not in active:
                self.signals.upsert(
                    team_id=self.team_id, store_id=self.store_id, product_gid=product["gid"],
                    signal_type="no_active_banner", value={},
                )

        for product in best_sellers:
            self.signals.upsert(
                team_id=self.team_id, store_id=self.store_id, product_gid=product["gid"],
                signal_type="best_seller",
                value={"sales_rank": product.get("sales_rank"), "proxy": product.get("sales_rank") is None},
            )
            from app.core.i18n import t

            self.suggestions.upsert_by_dedupe_key(
                kind="catalog_signal",
                dedupe_key=f"catalog:best_seller:{product['gid'] or product['title']}",
                title=t(self.lang, "catalog.best.title", title=product["title"]),
                rationale=t(self.lang, "catalog.best.rationale")
                + (t(self.lang, "catalog.best.proxy") if product.get("sales_rank") is None else ""),
                payload=_brief_payload(product, goal=t(self.lang, "catalog.best.goal", title=product["title"]), urgency="medium", lang=self.lang),
                source_refs=[{"type": "catalog_item", "id": product["gid"], "title": product["title"]}],
            )
            created.append("best_seller")

        return {"products_scanned": len(normalized), "suggestions": created}

    def list_signals(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.signals.list(team_id=self.team_id, limit=limit)


# --- agent-job handler (kind='catalog_scan') ----------------------------------


def handle_catalog_scan_job(job: dict[str, Any]) -> dict[str, Any]:
    """Fase 0 job handler: scan the team's cached catalog and upsert suggestions."""
    from app.core.settings import Settings
    from app.services.banners.suggestion_service import configured_service_for_team
    from app.services.shopify.resource_service import ShopifyResourceService
    from app.services.supabase.client import SupabaseClientFactory

    team_id = str(job.get("team_id") or "")
    settings = Settings.from_env()
    has_supabase = bool(settings.supabase_url and settings.supabase_service_role_key)
    if has_supabase:
        client = SupabaseClientFactory(settings).service_role_client()
        resource_service = ShopifyResourceService.from_supabase_client(client, team_id=team_id)
        signals: CatalogSignalRepositoryProtocol = SupabaseCatalogSignals(client)
    else:
        resource_service = ShopifyResourceService()
        signals = InMemoryCatalogSignals()
    suggestions = configured_service_for_team(team_id)

    from app.services.banners.calendar_service import configured_calendar_service_for_team

    team_lang = configured_calendar_service_for_team(team_id).lang
    stores = resource_service.list_stores(limit=5)
    summary: dict[str, Any] = {"stores": len(stores), "suggestions": []}
    for store in stores:
        products = resource_service.list_resources(store.id, resource_type="product", limit=100)
        service = CatalogSignalService(signals=signals, suggestions=suggestions, team_id=team_id, store_id=store.id, lang=team_lang)
        result = service.scan(products=products)
        summary["suggestions"].extend(result["suggestions"])
    return summary
