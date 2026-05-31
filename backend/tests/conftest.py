from __future__ import annotations

import pytest

from app.services import campaign_store
from app.services.banners.campaign_service import CampaignService


@pytest.fixture(autouse=True)
def _use_in_memory_campaign_service():
    campaign_store.set_service(CampaignService())
    yield
    campaign_store.set_service(None)
