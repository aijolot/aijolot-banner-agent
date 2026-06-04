from __future__ import annotations

import itertools
from collections.abc import Sequence
from typing import Any, Protocol
from uuid import uuid4

from app.db.repositories.campaign_messages import CampaignMessageRepository
from app.db.repositories.campaigns import CampaignRepository
from app.schemas.campaign import Campaign, CampaignMessage, StructuredBrief
from app.services.banners.status_machine import can_patch_brief, status_for_brief


class CampaignNotFound(KeyError):
    pass


class CampaignNotEditable(ValueError):
    pass


class CampaignRepositoryProtocol(Protocol):
    def list(self, *, team_id: str, limit: int = 100) -> list[dict[str, Any]]: ...
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...
    def create(
        self,
        *,
        team_id: str,
        store_id: str,
        title: str,
        raw_brief: str = "",
        structured_brief: dict[str, Any] | None = None,
        status: str = "draft",
        created_by: str | None = None,
        brand_context_id: str | None = None,
    ) -> dict[str, Any]: ...
    def update(self, *, campaign_id: str, data: dict[str, Any], team_id: str | None = None) -> dict[str, Any] | None: ...


class CampaignMessageRepositoryProtocol(Protocol):
    def list_for_campaign(self, *, campaign_id: str) -> list[dict[str, Any]]: ...
    def create(
        self,
        *,
        campaign_id: str,
        author_type: str,
        body: str,
        metadata: dict[str, Any] | None = None,
        author_id: str | None = None,
    ) -> dict[str, Any]: ...


class CampaignService:
    """Runtime campaign service.

    Supabase repositories are authoritative when configured. The in-memory path
    preserves prototype IDs and keeps unit/API tests independent of Supabase.
    """

    def __init__(
        self,
        *,
        campaign_repository: CampaignRepositoryProtocol | None = None,
        message_repository: CampaignMessageRepositoryProtocol | None = None,
        team_id: str | None = None,
        store_id: str | None = None,
        uuid_ids: bool = False,
    ) -> None:
        self.campaign_repository = campaign_repository
        self.message_repository = message_repository
        self.team_id = team_id
        self.store_id = store_id
        self.uuid_ids = uuid_ids
        self._campaigns: dict[str, Campaign] = {}
        self._ids = itertools.count(1)

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str, store_id: str) -> "CampaignService":
        return cls(
            campaign_repository=CampaignRepository(client),
            message_repository=CampaignMessageRepository(client),
            team_id=team_id,
            store_id=store_id,
        )

    @property
    def supabase_enabled(self) -> bool:
        return self.campaign_repository is not None and self.message_repository is not None and bool(self.team_id and self.store_id)

    def list_campaigns(self, *, limit: int = 100) -> list[Campaign]:
        if self.supabase_enabled:
            assert self.campaign_repository is not None and self.team_id is not None
            return [self._campaign_from_record(row, []) for row in self.campaign_repository.list(team_id=self.team_id, limit=limit)]
        return list(self._campaigns.values())[-limit:]

    def create_campaign(self, *, title: str = "", raw_brief: str = "", structured_brief: StructuredBrief | None = None) -> Campaign:
        brief = structured_brief or StructuredBrief()
        status = status_for_brief(brief)
        if self.supabase_enabled:
            assert self.campaign_repository is not None and self.team_id is not None and self.store_id is not None
            row = self.campaign_repository.create(
                team_id=self.team_id,
                store_id=self.store_id,
                title=title or "Nueva campaña",
                raw_brief=raw_brief,
                structured_brief=brief.model_dump(),
                status=status,
            )
            return self._campaign_from_record(row, [])
        cid = str(uuid4()) if self.uuid_ids else f"cmp_{next(self._ids):04d}"
        campaign = Campaign(id=cid, title=title, raw_brief=raw_brief, structured_brief=brief, status=status)
        self._campaigns[cid] = campaign
        return campaign

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        if self.supabase_enabled:
            assert self.campaign_repository is not None and self.message_repository is not None and self.team_id is not None
            row = self.campaign_repository.get(campaign_id=campaign_id, team_id=self.team_id)
            if not row:
                return None
            messages = self.message_repository.list_for_campaign(campaign_id=campaign_id)
            return self._campaign_from_record(row, messages)
        return self._campaigns.get(campaign_id)

    def apply_patch(self, campaign_id: str, fields: dict[str, Any]) -> Campaign | None:
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return None
        if not can_patch_brief(campaign.status):
            raise CampaignNotEditable(campaign_id)
        brief_data = campaign.structured_brief.model_dump()
        for key in ("goal", "audience", "cta", "tone", "urgency", "placement", "deadline",
                    "personalization_dimension", "personalization_variants"):
            if key in fields and fields[key] is not None:
                brief_data[key] = fields[key]
        campaign.structured_brief = StructuredBrief(**brief_data)
        if fields.get("title"):
            campaign.title = fields["title"]
        campaign.status = status_for_brief(campaign.structured_brief, campaign.status)
        if self.supabase_enabled:
            assert self.campaign_repository is not None and self.team_id is not None
            row = self.campaign_repository.update(
                campaign_id=campaign_id,
                team_id=self.team_id,
                data={
                    "title": campaign.title or "Nueva campaña",
                    "structured_brief": campaign.structured_brief.model_dump(),
                    "status": campaign.status,
                },
            )
            if not row:
                return None
            return self._campaign_from_record(row, campaign.messages)
        self._campaigns[campaign_id] = campaign
        return campaign

    def intake(self, message: str, campaign_id: str | None, *, extractor, title_builder, reply_builder) -> tuple[Campaign, str]:
        campaign = self.get_campaign(campaign_id) if campaign_id else None
        if campaign is None:
            campaign = self.create_campaign()
        elif not can_patch_brief(campaign.status):
            raise CampaignNotEditable(campaign.id)
        user_message = CampaignMessage(author_type="user", body=message)
        campaign.messages.append(user_message)
        if self.supabase_enabled:
            assert self.message_repository is not None
            self.message_repository.create(campaign_id=campaign.id, author_type="user", body=message)
        if not campaign.raw_brief:
            campaign.raw_brief = message
        campaign.structured_brief = extractor(campaign.structured_brief, message)
        if not campaign.title:
            campaign.title = title_builder(campaign.structured_brief, message)
        campaign.status = status_for_brief(campaign.structured_brief, campaign.status)
        reply = reply_builder(campaign.structured_brief)
        agent_message = CampaignMessage(author_type="agent", body=reply)
        campaign.messages.append(agent_message)
        if self.supabase_enabled:
            assert self.campaign_repository is not None and self.message_repository is not None and self.team_id is not None
            self.campaign_repository.update(
                campaign_id=campaign.id,
                team_id=self.team_id,
                data={
                    "title": campaign.title or "Nueva campaña",
                    "raw_brief": campaign.raw_brief,
                    "structured_brief": campaign.structured_brief.model_dump(),
                    "status": campaign.status,
                },
            )
            self.message_repository.create(campaign_id=campaign.id, author_type="agent", body=reply)
            refreshed = self.get_campaign(campaign.id)
            return (refreshed or campaign), reply
        self._campaigns[campaign.id] = campaign
        return campaign, reply

    def _campaign_from_record(self, row: dict[str, Any], messages: Sequence[dict[str, Any] | CampaignMessage]) -> Campaign:
        structured = row.get("structured_brief") or {}
        brief = structured if isinstance(structured, StructuredBrief) else StructuredBrief(**structured)
        return Campaign(
            id=str(row.get("id", "")),
            title=row.get("title") or "",
            raw_brief=row.get("raw_brief") or "",
            structured_brief=brief,
            status=row.get("status") or "draft",
            messages=[self._message_from_record(m) for m in messages],
        )

    @staticmethod
    def _message_from_record(row: dict[str, Any] | CampaignMessage) -> CampaignMessage:
        if isinstance(row, CampaignMessage):
            return row
        return CampaignMessage(author_type=row.get("author_type", "system"), body=row.get("body", ""), metadata=row.get("metadata") or {})
