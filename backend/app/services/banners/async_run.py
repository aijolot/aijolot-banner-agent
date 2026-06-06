"""Run an async coroutine from sync service code, even under a live event loop.

FastAPI sync route handlers run in a threadpool (no running loop), so
``asyncio.run`` works directly. If a loop *is* running (async caller/test), the
coroutine is offloaded to a fresh thread to avoid the event-loop-reentry trap.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, TypeVar, cast

_T = TypeVar("_T")


def run_coro(coro: Coroutine[Any, Any, _T]) -> _T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    box: dict[str, Any] = {}

    def _runner() -> None:
        try:
            box["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 — re-raised on the caller thread
            box["error"] = exc

    thread = threading.Thread(target=_runner)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return cast(_T, box["value"])
