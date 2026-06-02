"""/api/v1 campaign intake routes.

These routes intentionally reuse the prototype intake router so the canonical
namespace stays behavior-compatible without duplicating endpoint logic.
"""

from __future__ import annotations

from app.api.intake import router

__all__ = ["router"]
