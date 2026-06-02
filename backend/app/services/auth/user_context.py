"""Reusable request user/team context service helpers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core.auth import UserContext, require_team_match


def filter_records_for_team(records: list[Any], context: UserContext) -> list[Any]:
    """Return only records explicitly owned by the request team."""

    scoped: list[Any] = []
    for record in records:
        try:
            scoped.append(require_team_match(record, context))
        except HTTPException:
            continue
    return scoped


def user_metadata(context: UserContext) -> dict[str, str]:
    data = {"user_id": context.user_id, "team_id": context.team_id}
    if context.store_id:
        data["store_id"] = context.store_id
    return data
