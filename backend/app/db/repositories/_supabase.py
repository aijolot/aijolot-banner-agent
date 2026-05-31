from __future__ import annotations

from typing import Any, Protocol


class SupabaseQueryResult(Protocol):
    data: Any


class SupabaseTable(Protocol):
    def select(self, *args: Any, **kwargs: Any) -> Any: ...
    def insert(self, *args: Any, **kwargs: Any) -> Any: ...
    def upsert(self, *args: Any, **kwargs: Any) -> Any: ...
    def update(self, *args: Any, **kwargs: Any) -> Any: ...
    def delete(self, *args: Any, **kwargs: Any) -> Any: ...


class SupabaseClient(Protocol):
    def table(self, table_name: str) -> SupabaseTable: ...


def execute_data(query: Any) -> Any:
    result = query.execute()
    return getattr(result, "data", result)
