"""Request-scoped MVP auth/team context helpers.

This module intentionally supports only safe, explicit demo identity signals for
MVP API scoping. It never accepts or exposes service-role credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException, Request
from starlette.datastructures import Headers

DEMO_USER_HEADER = "x-aijolot-user-id"
DEMO_TEAM_HEADER = "x-aijolot-team-id"
DEMO_STORE_HEADER = "x-aijolot-store-id"


@dataclass(frozen=True)
class UserContext:
    user_id: str
    team_id: str
    store_id: str | None = None
    source: str = "demo-headers"

    def __repr__(self) -> str:
        return (
            f"UserContext(user_id={self.user_id!r}, team_id={self.team_id!r}, "
            f"store_id={self.store_id!r}, source={self.source!r})"
        )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _unauthorized(detail: str = "Request user/team context is required") -> HTTPException:
    return HTTPException(status_code=401, detail=detail)


def _parse_demo_token(token: str) -> UserContext:
    # MVP-only local/demo token: demo:<user_id>:<team_id>[:<store_id>].
    # Any real Supabase/JWT bearer is intentionally not decoded here; RLS routes
    # can pass it to Supabase anon clients without logging or service-role use.
    parts = token.split(":")
    if len(parts) not in (3, 4) or parts[0] != "demo":
        raise _unauthorized()
    user_id = _clean(parts[1])
    team_id = _clean(parts[2])
    store_id = _clean(parts[3]) if len(parts) == 4 else None
    if not user_id or not team_id:
        raise _unauthorized()
    return UserContext(user_id=user_id, team_id=team_id, store_id=store_id, source="demo-token")


def parse_user_context_headers(headers: Headers) -> UserContext:
    """Parse explicit MVP identity headers or a local demo bearer token.

    Fails closed with 401 when no complete request-scoped user/team identity is
    present. Error messages never echo bearer token/header values.
    """

    user_id = _clean(headers.get(DEMO_USER_HEADER))
    team_id = _clean(headers.get(DEMO_TEAM_HEADER))
    store_id = _clean(headers.get(DEMO_STORE_HEADER))
    if user_id or team_id or store_id:
        if not user_id or not team_id:
            raise _unauthorized()
        return UserContext(user_id=user_id, team_id=team_id, store_id=store_id, source="demo-headers")

    authorization = _clean(headers.get("authorization"))
    if authorization:
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() != "bearer" or not credentials.strip():
            raise _unauthorized()
        return _parse_demo_token(credentials.strip())

    raise _unauthorized()


def require_user_context(request: Request) -> UserContext:
    return parse_user_context_headers(request.headers)


def optional_user_context(request: Request) -> UserContext | None:
    try:
        return parse_user_context_headers(request.headers)
    except HTTPException:
        return None


def get_bearer_token(authorization: str | None = Header(default=None)) -> str:
    value = _clean(authorization)
    if not value:
        raise _unauthorized("Bearer token required")
    scheme, _, credentials = value.partition(" ")
    if scheme.lower() != "bearer" or not credentials.strip():
        raise _unauthorized("Bearer token required")
    return credentials.strip()


def get_record_team_id(record: Any) -> str | None:
    if isinstance(record, dict):
        return _clean(str(record.get("team_id"))) if record.get("team_id") is not None else None
    team_id = getattr(record, "team_id", None)
    return _clean(str(team_id)) if team_id is not None else None


def require_team_match(record: Any, context: UserContext) -> Any:
    """Return record only when it is explicitly owned by the request team.

    Missing or mismatched ownership is hidden as 404 to avoid cross-team
    enumeration/leakage through API responses.
    """

    if get_record_team_id(record) != context.team_id:
        raise HTTPException(status_code=404, detail="resource not found")
    return record
