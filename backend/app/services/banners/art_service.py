"""Art prompt proposal + generation service (F8).

Two-step contract:
1. propose_art_prompts / propose_model_prompts — cheap text proposals (A/B/C).
2. generate_art — generate the chosen prompt's image, optimize + upload it, and
   attach it to the campaign revision. For usage shots a background option (F7)
   can be composed behind the generated image and persisted alongside it.

Reuses the shared image seam (image_gen + image-asset-optimize) and usage guard
without touching the provider boundary.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.campaign_revisions import CampaignRevisionRepository
from app.db.repositories.campaigns import CampaignRepository
from app.schemas.art_prompts import (
    ArtPromptsRequest,
    ArtPromptsResponse,
    GenerateArtRequest,
    GenerateArtResponse,
    GeneratedAsset,
    ModelPromptsRequest,
)
from app.services.banners.async_run import run_coro
from app.services.banners.brand_resolver import resolve_brand_context
from app.services.supabase.client import SupabaseClientFactory
from app.workflows.banner_creation import _load_runtime_skill


class CampaignNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class RevisionNotFound(Exception):
    def __init__(self, revision_id: str) -> None:
        super().__init__(f"revision '{revision_id}' not found")
        self.revision_id = revision_id


class CampaignRepositoryProtocol(Protocol):
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...


class RevisionRepositoryProtocol(Protocol):
    def get(self, *, revision_id: str) -> dict[str, Any] | None: ...
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...
    def update(self, *, revision_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...


class ArtService:
    def __init__(
        self,
        *,
        campaigns: CampaignRepositoryProtocol | None = None,
        revisions: RevisionRepositoryProtocol | None = None,
        asset_service: Any = None,
        settings: Settings | None = None,
        team_id: str | None = None,
    ) -> None:
        self.campaigns = campaigns
        self.revisions = revisions
        self.asset_service = asset_service
        self.settings = settings
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, settings: Settings | None = None, team_id: str | None = None) -> "ArtService":
        from app.services.banners.asset_service import BannerAssetService

        try:
            asset_service: Any = BannerAssetService.from_supabase_client(client)
        except Exception:  # noqa: BLE001 — assets stay in-memory if storage unconfigured
            asset_service = None
        return cls(
            campaigns=CampaignRepository(client),
            revisions=CampaignRevisionRepository(client),
            asset_service=asset_service,
            settings=settings,
            team_id=team_id,
        )

    # --- step 1: propose -------------------------------------------------

    def propose_art_prompts(self, campaign_id: str, request: ArtPromptsRequest) -> ArtPromptsResponse:
        revision, concept, brand = self._context(campaign_id, request.revision_id)
        skill = _load_runtime_skill("art-prompt-propose")
        options, source = run_coro(
            skill.run(
                concept,
                brand,
                shot_type=request.shot_type,
                count=request.count,
                background_ref=request.background_ref,
                settings=self.settings,
            )
        )
        return ArtPromptsResponse(
            campaign_id=campaign_id,
            revision_id=str(revision["id"]) if revision and revision.get("id") else request.revision_id,
            shot_type=request.shot_type,
            source=source,
            options=options,
        )

    def propose_model_prompts(self, campaign_id: str, request: ModelPromptsRequest) -> ArtPromptsResponse:
        revision, concept, brand = self._context(campaign_id, request.revision_id)
        skill = _load_runtime_skill("art-prompt-propose")
        options, source = run_coro(
            skill.propose_models(
                concept,
                brand,
                gender=request.gender,
                base_prompt=request.prompt,
                count=request.count,
                settings=self.settings,
            )
        )
        return ArtPromptsResponse(
            campaign_id=campaign_id,
            revision_id=str(revision["id"]) if revision and revision.get("id") else request.revision_id,
            shot_type="usage",
            source=source,
            options=options,
        )

    # --- step 2: generate ------------------------------------------------

    def generate_art(self, campaign_id: str, request: GenerateArtRequest) -> GenerateArtResponse:
        revision, concept, brand = self._context(campaign_id, request.revision_id)
        revision_id = str(revision["id"]) if revision and revision.get("id") else request.revision_id
        prompt = (request.prompt or "").strip() or _base_subject(concept)

        image_bytes, meta, cost, refined = run_coro(
            self._generate_image(prompt, concept, brand, request.aspect_ratio, campaign_id)
        )
        records = self._optimize(
            image_bytes=image_bytes,
            mime_type=meta.get("mime_type"),
            refined_prompt=refined,
            campaign_id=campaign_id,
            revision_id=revision_id,
            shot_type=request.shot_type,
            background_ref=request.background_ref,
        )
        assets = [_to_asset(r) for r in records]
        primary = _primary_asset(records)
        primary_asset = _to_asset(primary) if primary else None

        composed_html = self._compose(request, primary_asset)
        self._attach_to_revision(revision_id, revision, refined, request, primary, composed_html)

        return GenerateArtResponse(
            campaign_id=campaign_id,
            revision_id=revision_id,
            shot_type=request.shot_type,
            provider=str(meta.get("provider") or ""),
            prompt=refined,
            asset=primary_asset,
            assets=assets,
            background_ref=request.background_ref,
            composed_html=composed_html,
            cost_usd=round(float(cost), 6),
        )

    # --- internals -------------------------------------------------------

    async def _generate_image(self, prompt: str, concept: Any, brand: Any, aspect_ratio: str, campaign_id: str) -> tuple[bytes, dict[str, Any], float, str]:
        from app.services.banners.image_gen import generate_image
        from app.services.gemini.cost_guard import get_default_cost_guard

        refine = _load_runtime_skill("image-prompt-refine")
        refined = await refine.run(prompt, brand_context=brand)
        settings = self.settings or Settings.from_env()
        guard = get_default_cost_guard(settings)
        image_bytes, meta, cost = await generate_image(
            refined, settings=settings, cost_guard=guard, campaign_id=campaign_id, aspect_ratio=aspect_ratio, concept=concept
        )
        return image_bytes, meta, cost, refined

    def _optimize(
        self,
        *,
        image_bytes: bytes,
        mime_type: str | None,
        refined_prompt: str,
        campaign_id: str,
        revision_id: str | None,
        shot_type: str,
        background_ref: str | None,
    ) -> list[dict[str, Any]]:
        # Map to the banner_assets.asset_kind CHECK enum: usage/model shots are
        # product imagery; hero shots are generated backgrounds.
        asset_kind = "product_image" if shot_type == "usage" else "generated_background"
        if self.asset_service is not None and revision_id:
            try:
                stored = self.asset_service.optimize_upload_and_record(
                    image_bytes=image_bytes,
                    campaign_id=campaign_id,
                    revision_id=revision_id,
                    alt_text=refined_prompt[:120],
                    image_prompt=refined_prompt,
                    asset_kind=asset_kind,
                    source_metadata={"shot_type": shot_type, "background_ref": background_ref},
                )
                return list(stored.asset_records)
            except Exception:  # noqa: BLE001 — upload failed; degrade to in-memory optimize
                pass
        skill = _load_runtime_skill("image-asset-optimize")
        assets = run_coro(skill.run(image_bytes, refined_prompt[:120], mime_type=mime_type, image_prompt=refined_prompt))
        return list(getattr(assets, "asset_records", []) or [])

    def _compose(self, request: GenerateArtRequest, primary: GeneratedAsset | None) -> str | None:
        if request.shot_type != "usage" or not request.background_css or primary is None:
            return None
        sanitize_css = _load_runtime_skill("background-options-generate").sanitize_css
        css = sanitize_css(request.background_css)
        url = primary.public_url or primary.storage_path or ""
        if not css or not url:
            return None
        return (
            '<section class="aijolot-banner">'
            f"<style>{css}</style>"
            f'<img src="{url}" alt="" loading="lazy" style="width:100%;height:auto;display:block;">'
            "</section>"
        )

    def _attach_to_revision(
        self,
        revision_id: str | None,
        revision: dict[str, Any] | None,
        refined_prompt: str,
        request: GenerateArtRequest,
        primary: dict[str, Any] | None,
        composed_html: str | None,
    ) -> None:
        if self.revisions is None or revision is None or not revision_id:
            return
        concept = dict(revision.get("concept") or {})
        generated = list(concept.get("generated_art") or [])
        generated.append(
            {
                "shot_type": request.shot_type,
                "prompt": refined_prompt,
                "background_ref": request.background_ref,
                "storage_path": (primary or {}).get("storage_path"),
                "public_url": (primary or {}).get("public_url"),
                "composed_html": composed_html,
            }
        )
        concept["generated_art"] = generated
        data: dict[str, Any] = {"concept": concept}
        if primary and primary.get("storage_path"):
            data["preview_storage_path"] = primary["storage_path"]
        self.revisions.update(revision_id=revision_id, data=data)

    def _context(self, campaign_id: str, revision_id: str | None) -> tuple[dict[str, Any] | None, dict[str, Any], Any]:
        campaign = self._get_campaign(campaign_id)
        revision = self._resolve_revision(campaign_id, revision_id)
        concept = (revision or {}).get("concept") or {}
        brand = resolve_brand_context(campaign or {"id": campaign_id})
        return revision, concept, brand

    def _get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        if self.campaigns is None:
            return None
        campaign = self.campaigns.get(campaign_id=campaign_id, team_id=self.team_id)
        if campaign is None:
            raise CampaignNotFound(campaign_id)
        return campaign

    def _resolve_revision(self, campaign_id: str, revision_id: str | None) -> dict[str, Any] | None:
        if self.revisions is None:
            return None
        if revision_id:
            revision = self.revisions.get(revision_id=revision_id)
            if revision is None or str(revision.get("campaign_id")) != campaign_id:
                raise RevisionNotFound(revision_id)
            return revision
        return self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id)


def _base_subject(concept: Any) -> str:
    copy = concept.get("copy", {}) if isinstance(concept, dict) else {}
    headline = copy.get("headline", "") if isinstance(copy, dict) else ""
    image_prompt = concept.get("image_prompt", "") if isinstance(concept, dict) else ""
    return str(image_prompt or headline or "featured product scene")


def _primary_asset(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    webp = [r for r in records if str(r.get("format") or "").lower() == "webp"]
    pool = webp or records
    return max(pool, key=lambda r: int(r.get("size_key") or r.get("width") or 0))


def _to_asset(record: dict[str, Any]) -> GeneratedAsset:
    return GeneratedAsset(
        storage_path=record.get("storage_path"),
        public_url=record.get("public_url"),
        width=record.get("width"),
        height=record.get("height"),
        format=record.get("format"),
        size_key=record.get("size_key"),
        bytes=record.get("bytes"),
    )


def _configured_service_for_team(team_id_override: str | None = None) -> ArtService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    has_supabase = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    team_id = team_id_override or settings.supabase_team_id or settings.brand_context_team_id
    if not has_supabase_signal:
        return ArtService(settings=settings, team_id=team_id)
    if not has_supabase:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID", "BRAND_CONTEXT_TEAM_ID"))
    client = SupabaseClientFactory(settings).service_role_client()
    return ArtService.from_supabase_client(client, settings=settings, team_id=team_id)


def configured_service() -> ArtService:
    return _configured_service_for_team()


def configured_service_for_team(team_id: str) -> ArtService:
    return _configured_service_for_team(team_id)
