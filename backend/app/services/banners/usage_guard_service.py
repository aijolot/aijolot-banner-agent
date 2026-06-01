"""Soft usage guard for image generation cost visibility."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any, Protocol
from uuid import UUID

from app.core.settings import Settings


class UsageEventRepository(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...
    def count_since(self, *, user_id: str, event_type: str, since: datetime) -> int: ...


@dataclass(frozen=True, slots=True)
class UsageGuardResult:
    user_id: str
    event_type: str
    count: int
    limit: int
    window_minutes: int
    warning: bool
    message: str | None = None

    def to_metadata(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "event_type": self.event_type,
            "count": self.count,
            "limit": self.limit,
            "window_minutes": self.window_minutes,
            "warning": self.warning,
            "message": self.message,
        }


class InMemoryUsageEventStore:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], list[datetime]] = defaultdict(list)
        self._lock = Lock()

    def record_and_count(self, *, user_id: str, event_type: str, now: datetime, window: timedelta) -> int:
        cutoff = now - window
        key = (user_id, event_type)
        with self._lock:
            kept = [created_at for created_at in self._events[key] if created_at >= cutoff]
            kept.append(now)
            self._events[key] = kept
            return len(kept)

    def count_since(self, *, user_id: str, event_type: str, since: datetime) -> int:
        key = (user_id, event_type)
        with self._lock:
            return sum(1 for created_at in self._events.get(key, []) if created_at >= since)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


class UsageGuardService:
    event_type_image_generation = "image_generation"

    def __init__(
        self,
        *,
        repository: UsageEventRepository | None = None,
        memory_store: InMemoryUsageEventStore | None = None,
        settings: Settings | None = None,
        limit: int | None = None,
        window: timedelta = timedelta(minutes=15),
    ) -> None:
        self.repository = repository
        self.memory_store = memory_store or InMemoryUsageEventStore()
        self.settings = settings or Settings.from_env()
        self.limit = self.settings.soft_image_generation_limit_per_15_minutes if limit is None else limit
        self.window = window

    def record_image_generation(
        self,
        *,
        user_id: str | None,
        team_id: str | None = None,
        campaign_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        estimated_cost_usd: float | None = None,
        metadata: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> UsageGuardResult:
        normalized_user_id = (user_id or "anonymous").strip() or "anonymous"
        event_type = self.event_type_image_generation
        timestamp = _ensure_aware_utc(now or datetime.now(UTC))
        cutoff = timestamp - self.window

        memory_count = self.memory_store.record_and_count(
            user_id=normalized_user_id,
            event_type=event_type,
            now=timestamp,
            window=self.window,
        )
        count = memory_count

        # The current Supabase schema requires a real profile UUID, team_id, and
        # RLS team membership. Keep the per-user soft guard reliable in memory
        # for all calls, and persist/count through Supabase only when the caller
        # has enough authenticated team context for the insert to be valid.
        if self.repository is not None and _can_persist(normalized_user_id, team_id, campaign_id):
            self.repository.create(
                data={
                    "user_id": normalized_user_id,
                    "team_id": team_id,
                    "campaign_id": campaign_id,
                    "event_type": event_type,
                    "provider": provider,
                    "model": model,
                    "estimated_cost_usd": estimated_cost_usd,
                    "metadata": metadata or {},
                    "created_at": timestamp,
                }
            )
            persistent_count = self.repository.count_since(user_id=normalized_user_id, event_type=event_type, since=cutoff)
            count = max(memory_count, persistent_count)

        warning = self.limit > 0 and count >= self.limit
        message = None
        if warning:
            message = (
                f"Soft image generation guard: {count} image generations for user "
                f"{normalized_user_id} in {self.window_minutes} minutes (limit {self.limit})."
            )
        return UsageGuardResult(
            user_id=normalized_user_id,
            event_type=event_type,
            count=count,
            limit=self.limit,
            window_minutes=self.window_minutes,
            warning=warning,
            message=message,
        )

    @property
    def window_minutes(self) -> int:
        return int(self.window.total_seconds() // 60)


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except (TypeError, ValueError):
        return False
    return True


def _can_persist(user_id: str, team_id: str | None, campaign_id: str | None) -> bool:
    if not team_id:
        return False
    if not _is_uuid(user_id) or not _is_uuid(team_id):
        return False
    return campaign_id is None or _is_uuid(campaign_id)


_DEFAULT_MEMORY_STORE = InMemoryUsageEventStore()
_DEFAULT_SERVICE: UsageGuardService | None = None


def get_default_usage_guard_service() -> UsageGuardService:
    global _DEFAULT_SERVICE
    if _DEFAULT_SERVICE is None:
        _DEFAULT_SERVICE = UsageGuardService(memory_store=_DEFAULT_MEMORY_STORE)
    return _DEFAULT_SERVICE


def reset_default_usage_guard_service() -> None:
    """Clear process-local usage guard state for deterministic tests/demos."""

    global _DEFAULT_SERVICE
    _DEFAULT_MEMORY_STORE.clear()
    _DEFAULT_SERVICE = None
