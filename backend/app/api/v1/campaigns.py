"""/api/v1 campaign CRUD routes.

These routes intentionally reuse the prototype campaign router so the canonical
namespace stays behavior-compatible without duplicating endpoint logic.
"""

from __future__ import annotations

from app.api.campaigns import router

__all__ = ["router"]
