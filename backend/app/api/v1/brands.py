"""/api/v1 brand routes.

These routes intentionally reuse the prototype brand router so the canonical
namespace stays behavior-compatible without duplicating endpoint logic.
"""

from __future__ import annotations

from app.api.brands import router

__all__ = ["router"]
