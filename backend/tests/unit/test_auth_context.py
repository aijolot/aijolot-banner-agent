from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

from app.core.auth import UserContext, parse_user_context_headers, require_team_match
from app.services.auth.user_context import filter_records_for_team


def test_parse_demo_headers_builds_user_context_without_token_leakage() -> None:
    context = parse_user_context_headers(
        Headers(
            {
                "authorization": "Bearer super-secret-token",
                "x-aijolot-user-id": "user-1",
                "x-aijolot-team-id": "team-a",
                "x-aijolot-store-id": "store-1",
            }
        )
    )

    assert context == UserContext(user_id="user-1", team_id="team-a", store_id="store-1", source="demo-headers")
    assert "secret" not in repr(context)


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"x-aijolot-user-id": "user-1"},
        {"x-aijolot-team-id": "team-a"},
        {"x-aijolot-user-id": "", "x-aijolot-team-id": "team-a"},
    ],
)
def test_parse_context_fails_closed_when_identity_or_team_missing(headers: dict[str, str]) -> None:
    with pytest.raises(HTTPException) as exc_info:
        parse_user_context_headers(Headers(headers))

    assert exc_info.value.status_code == 401


def test_parse_demo_bearer_token_supports_mvp_without_service_role_secret() -> None:
    context = parse_user_context_headers(Headers({"authorization": "Bearer demo:user-1:team-a:store-1"}))

    assert context.user_id == "user-1"
    assert context.team_id == "team-a"
    assert context.store_id == "store-1"
    assert context.source == "demo-token"


@pytest.mark.parametrize("authorization", ["Bearer", "Bearer demo:user-only", "Basic abc", "Bearer not-demo-token"])
def test_malformed_bearer_token_fails_closed(authorization: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        parse_user_context_headers(Headers({"authorization": authorization}))

    assert exc_info.value.status_code == 401


def test_require_team_match_allows_matching_records_and_hides_cross_team_records() -> None:
    context = UserContext(user_id="user-1", team_id="team-a")

    assert require_team_match({"id": "row-1", "team_id": "team-a"}, context) == {"id": "row-1", "team_id": "team-a"}

    with pytest.raises(HTTPException) as exc_info:
        require_team_match({"id": "row-2", "team_id": "team-b"}, context)

    assert exc_info.value.status_code == 404
    assert "team-b" not in str(exc_info.value.detail)


def test_require_team_match_fails_closed_when_record_team_missing() -> None:
    context = UserContext(user_id="user-1", team_id="team-a")

    with pytest.raises(HTTPException) as exc_info:
        require_team_match({"id": "row-1"}, context)

    assert exc_info.value.status_code == 404


def test_filter_records_for_team_does_not_swallow_programmer_errors() -> None:
    class BrokenRecord:
        @property
        def team_id(self) -> str:
            raise RuntimeError("schema bug")

    with pytest.raises(RuntimeError, match="schema bug"):
        filter_records_for_team([BrokenRecord()], UserContext(user_id="user-1", team_id="team-a"))
