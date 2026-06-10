"""Campaign intake endpoint (GH-27).

POST /campaigns/intake — streams the agent reply token-by-token over SSE, then
a final ``done`` event carrying the updated campaign and completeness state.

The root route preserves prototype unauthenticated behavior. When mounted under
`/api/v1`, intake requires request user/team context and uses a request-scoped
campaign service.

SSE event shapes (each line is ``data: <json>\\n\\n``):
    {"type": "token", "text": "..."}                 # streamed reply chunk
    {"type": "done", "campaign": {...},
     "complete": bool, "missing": [...]}              # final state
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.schemas.campaign import IntakeRequest
from app.core.auth import require_user_context
from app.core.settings import MissingSettingsError
from app.services import campaign_store
from app.services.banners.campaign_service import CampaignNotEditable

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/intake")
def intake(req: IntakeRequest, request: Request) -> StreamingResponse:
    try:
        from app.core.i18n import request_lang

        lang = req.language or request_lang(request)
        if request.url.path.startswith("/api/v1/"):
            context = require_user_context(request)
            campaign, reply = campaign_store.intake_for_context(context, req.message, req.campaign_id, lang=lang)
        else:
            campaign, reply = campaign_store.intake(req.message, req.campaign_id, lang=lang)
    except CampaignNotEditable as exc:
        raise HTTPException(status_code=409, detail=f"campaign '{exc.args[0]}' is not editable")
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None

    def stream():
        # stream the reply word-by-word so the UI can render it live
        words = reply.split(" ")
        for i, w in enumerate(words):
            yield _sse({"type": "token", "text": (" " if i else "") + w})
        yield _sse({
            "type": "done",
            "campaign": campaign.model_dump(),
            "complete": campaign.structured_brief.is_complete(),
            "missing": campaign.structured_brief.missing(),
        })

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
