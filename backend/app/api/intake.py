"""Campaign intake endpoint (GH-27).

POST /campaigns/intake — streams the agent reply token-by-token over SSE, then
a final ``done`` event carrying the updated campaign and completeness state.

SSE event shapes (each line is ``data: <json>\\n\\n``):
    {"type": "token", "text": "..."}                 # streamed reply chunk
    {"type": "done", "campaign": {...},
     "complete": bool, "missing": [...]}              # final state
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.campaign import IntakeRequest
from app.services import campaign_store

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/intake")
def intake(req: IntakeRequest) -> StreamingResponse:
    campaign, reply = campaign_store.intake(req.message, req.campaign_id)

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
