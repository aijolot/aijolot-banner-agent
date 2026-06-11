#!/usr/bin/env python3
"""End-to-end REAL publish driver — brief -> generation -> schedule -> publish.

Drives the full banner pipeline against the REAL configured services
(Supabase + Gemini + Shopify) using the same service factories the FastAPI
routes use. Publishes well-formed banners to the live Shopify store defined in
the repo-root .env (SHOPIFY_PUBLISH_DRY_RUN must be false for real writes).

Usage:
  python scripts/e2e_real_publish.py validate <campaign_id>   # publish an already-scheduled campaign (cheap path check)
  python scripts/e2e_real_publish.py run                       # 3 fresh full-flow campaigns -> published

This is an operator tool, not a unit test: it intentionally talks to live
providers and spends real Gemini/Shopify API budget.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# --- bootstrap: load repo-root .env and put this backend on sys.path ---
HERE = Path(__file__).resolve()
BACKEND = HERE.parents[1]                      # .../backend
REPO_ROOT = HERE.parents[2]                    # repo root (holds .env)
ENV_FILE = REPO_ROOT / ".env"


def _load_env() -> None:
    import os

    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()
sys.path.insert(0, str(BACKEND))

from app.core.settings import Settings  # noqa: E402
from app.services.supabase.client import SupabaseClientFactory  # noqa: E402
from app.db.repositories.campaigns import CampaignRepository  # noqa: E402
from app.db.repositories.campaign_placements import CampaignPlacementRepository  # noqa: E402
from app.db.repositories.campaign_revisions import CampaignRevisionRepository  # noqa: E402
from app.schemas.generation import GenerationRunCreate  # noqa: E402
from app.schemas.schedules import ScheduleCreate  # noqa: E402
from app.services.banners import generation_run_service, schedule_service  # noqa: E402
from app.services.shopify.admin_factory import configured_admin_client  # noqa: E402
from app.services.shopify.publisher import configured_publisher  # noqa: E402

TEAM_ID = "00000000-0000-0000-0000-000000000001"
STORE_ID = "00000000-0000-0000-0000-000000000101"
USER_ID = "00000000-0000-0000-0000-000000000601"
BRAND_CONTEXT_ID = "00000000-0000-0000-0000-000000000201"
HERO_MAIN_PLACEMENT_TYPE_ID = "cfed186d-2e35-4c27-954b-6faecb12c71b"

SETTINGS = Settings.from_env()
SUPABASE = SupabaseClientFactory(SETTINGS).service_role_client()
CAMPAIGNS = CampaignRepository(SUPABASE)
PLACEMENTS = CampaignPlacementRepository(SUPABASE)
REVISIONS = CampaignRevisionRepository(SUPABASE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _later_iso(days: int) -> str:
    return (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=days)).isoformat()


# --- real product catalog pulled from the live store (perfume retailer) -------
# Real Shopify product GIDs + CDN images so the banner features actual catalog.
SCENARIOS = [
    {
        "title": "Black Friday VIP — Perfumes de lujo",
        "brief": {
            "goal": "Black Friday: hasta 40% en perfumes de lujo seleccionados para clientes VIP",
            "audience": "Clientes VIP amantes de fragancias premium, 25-45 años",
            "cta": "Comprar ahora",
            "tone": "Premium, elegante, urgencia alta",
            "urgency": "high",
            "promo": "Hasta 40% OFF",
            "deadline": None,
            "products": [
                {
                    "product_gid": "gid://shopify/Product/14988744786290",
                    "product_title": "Dolce & Gabbana Light Blue Summer Vibes EDT 100ml Dama",
                    "price": "1069.0",
                    "product_image_url": "https://cdn.shopify.com/s/files/1/0964/9360/1138/files/MDOLGLBSV__22175.1731099910.1280.1280.jpg?v=1772383839",
                }
            ],
        },
    },
    {
        "title": "Regalo perfecto — Sets de fragancia",
        "brief": {
            "goal": "Promocionar sets de fragancia como el regalo perfecto de temporada",
            "audience": "Compradores buscando regalos, 20-40 años",
            "cta": "Descubrir sets",
            "tone": "Cálido, aspiracional, festivo",
            "urgency": "medium",
            "promo": "Envío gratis",
            "deadline": None,
            "products": [
                {
                    "product_gid": "gid://shopify/Product/14988714901874",
                    "product_title": "Passport in South Beach Agua de tocador 100ml dama",
                    "price": "244.0",
                    "product_image_url": "https://cdn.shopify.com/s/files/1/0964/9360/1138/files/MPASSB__71653.1731099893.1280.1280.jpg",
                }
            ],
        },
    },
    {
        "title": "Frescura de verano — Eau de toilette",
        "brief": {
            "goal": "Lanzar la colección de verano con fragancias frescas y juveniles",
            "audience": "Mujeres jóvenes 18-30 que buscan aromas frescos para el día",
            "cta": "Ver colección",
            "tone": "Fresco, juvenil, luminoso",
            "urgency": "medium",
            "promo": "Nuevo",
            "deadline": None,
            "products": [
                {
                    "product_gid": "gid://shopify/Product/14988744786290",
                    "product_title": "Dolce & Gabbana Light Blue Summer Vibes EDT 100ml Dama",
                    "price": "1069.0",
                    "product_image_url": "https://cdn.shopify.com/s/files/1/0964/9360/1138/files/MDOLGLBSV__22175.1731099910.1280.1280.jpg?v=1772383839",
                }
            ],
        },
    },
]


def _placement_payload() -> dict:
    return {
        "placement_type_id": HERO_MAIN_PLACEMENT_TYPE_ID,
        "mode": "existing_section",
        "target_type": "home",
        "slot": "hero",
    }


def _summarize_revision(revision: dict) -> dict:
    concept = revision.get("concept") or {}
    copy = concept.get("copy") or {}
    liquid = revision.get("liquid_config") or {}
    html = revision.get("html_preview") or ""
    art = (concept.get("generated_art") or [{}])
    image_url = (art[0].get("public_url") if art else None) or (concept.get("background") or {}).get("image_url")
    return {
        "revision_id": revision.get("id"),
        "headline": copy.get("headline"),
        "subheadline": copy.get("subheadline"),
        "cta": copy.get("cta"),
        "image_url": image_url,
        "has_html": bool(html and "<" in html),
        "html_len": len(html),
        "has_liquid_section": bool(liquid.get("section")),
    }


def _publish(campaign_id: str) -> dict:
    publisher = configured_publisher(team_id=TEAM_ID)
    print(f"    publisher dry_run={publisher.dry_run}")
    job = publisher.publish_campaign(campaign_id)
    return {"job_id": job.id, "status": job.status, "resource_id": getattr(job, "shopify_resource_id", None)}


def _verify_metafield(campaign_id: str) -> dict:
    client = configured_admin_client(SETTINGS)
    mf = client.get_shop_metafield(namespace="aijolot", key="banner_campaigns")
    present = False
    count = 0
    if mf and mf.get("value"):
        import json

        try:
            entries = json.loads(mf["value"])
            if isinstance(entries, list):
                count = len(entries)
                present = any(str(e.get("campaign_id")) == str(campaign_id) for e in entries)
        except Exception:
            pass
    return {"metafield_present": present, "metafield_total_campaigns": count}


def validate_existing(campaign_id: str) -> None:
    print(f"== VALIDATE publish path on existing scheduled campaign {campaign_id} ==")
    pub = _publish(campaign_id)
    print("    publish:", pub)
    print("    verify:", _verify_metafield(campaign_id))
    storefront = f"https://{SETTINGS.shopify_shop_domain.strip('/').removeprefix('https://').removeprefix('http://')}"
    print("    storefront:", storefront)


def run_full_flow(scenario: dict, index: int) -> dict:
    title = scenario["title"]
    brief = scenario["brief"]
    print(f"\n== SCENARIO {index}: {title} ==")

    # 1) create campaign row (same repo the publisher reads)
    campaign = CAMPAIGNS.create(
        team_id=TEAM_ID,
        store_id=STORE_ID,
        title=title,
        raw_brief=brief["goal"],
        structured_brief=brief,
        status="needs_review",
        created_by=USER_ID,
        brand_context_id=BRAND_CONTEXT_ID,
    )
    campaign_id = str(campaign["id"])
    print(f"  [1] campaign created: {campaign_id}")

    # 2) real generation run (Gemini image, render, audit) -> selected revision.
    # Build the Supabase-backed service but force INLINE execution (the default
    # factory runs in a daemon thread and returns "running", which would die when
    # this short-lived script exits).
    gen = generation_run_service.GenerationRunService.from_supabase_client(SUPABASE, team_id=TEAM_ID)
    gen.background = False
    run = gen.start_generation_run(campaign_id, GenerationRunCreate(started_by=USER_ID, metadata={"source": "e2e-real-publish", "scenario": index}))
    print(f"  [2] generation: status={run.status} step={run.frontend_step}")
    if run.status != "succeeded":
        return {"campaign_id": campaign_id, "title": title, "error": f"generation {run.status}", "events": [e.model_dump() for e in gen.list_events(run.id)]}

    revision = REVISIONS.get_latest_by_campaign_id(campaign_id=campaign_id)
    summary = _summarize_revision(revision or {})
    print(f"  [2] revision: headline={summary['headline']!r} cta={summary['cta']!r} html_len={summary['html_len']} liquid={summary['has_liquid_section']} image={summary['image_url']}")

    # 3) approve (operator HITL bypass) so scheduling is allowed
    CAMPAIGNS.update(campaign_id=campaign_id, data={"status": "approved"}, team_id=TEAM_ID)
    print("  [3] campaign approved")

    # 4) placement (hero_main / home)
    PLACEMENTS.upsert_for_campaign(campaign_id=campaign_id, data=_placement_payload())
    print("  [4] placement set: hero_main / home")

    # 5) schedule (active now for 7 days)
    sched = schedule_service.configured_service_for_team(TEAM_ID)
    schedule = sched.schedule_campaign(campaign_id, ScheduleCreate(starts_at=_now_iso(), ends_at=_later_iso(7), timezone="UTC", created_by=USER_ID))
    print(f"  [5] scheduled: {schedule.starts_at} -> {schedule.ends_at} status={schedule.status}")

    # 6) publish to the live store
    pub = _publish(campaign_id)
    print(f"  [6] publish: {pub}")

    # 7) verify the live shop metafield carries this campaign
    verify = _verify_metafield(campaign_id)
    print(f"  [7] verify: {verify}")

    return {"campaign_id": campaign_id, "title": title, "publish": pub, "verify": verify, **summary}


def run_all() -> None:
    print(f"REAL publish run :: store={SETTINGS.shopify_shop_domain} theme={SETTINGS.shopify_theme_id} dry_run={SETTINGS.shopify_publish_dry_run}")
    if SETTINGS.shopify_publish_dry_run:
        print("WARNING: SHOPIFY_PUBLISH_DRY_RUN is true — no real writes will happen.")
    results = []
    for i, scenario in enumerate(SCENARIOS, start=1):
        try:
            results.append(run_full_flow(scenario, i))
        except Exception as exc:  # noqa: BLE001 — report per-scenario, keep going
            import traceback

            traceback.print_exc()
            results.append({"title": scenario["title"], "error": repr(exc)})

    print("\n==================== SUMMARY ====================")
    domain = SETTINGS.shopify_shop_domain.strip("/").removeprefix("https://").removeprefix("http://")
    for r in results:
        ok = r.get("publish", {}).get("status") == "succeeded" and r.get("verify", {}).get("metafield_present")
        mark = "OK " if ok else "XX "
        print(f"{mark} {r.get('title')}")
        if "error" in r:
            print(f"     error: {r['error']}")
            continue
        print(f"     campaign={r.get('campaign_id')}  headline={r.get('headline')!r}  cta={r.get('cta')!r}")
        print(f"     image={r.get('image_url')}")
        print(f"     publish={r.get('publish')}  verify={r.get('verify')}")
    print(f"\nStorefront: https://{domain}")
    print("================================================")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "validate" and len(args) >= 2:
        validate_existing(args[1])
    elif args and args[0] == "run":
        run_all()
    else:
        print(__doc__)
        sys.exit(2)
