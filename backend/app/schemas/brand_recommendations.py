"""Apply-discovery-recommendations request contract (Task 7).

The user is the approval gate: this request body lists ONLY the recommendations
the user explicitly accepted. Anything not listed must stay exactly as it is on
the active ``BrandContext`` (the merge itself lives in
``app.services.brands.apply_recommendations``).

Schema-only module: keep it import-light (no service imports).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.brand import FontCandidate
from app.schemas.brand_discovery import BrandColorRecommendation


class ApplyDiscoveryRecommendationsRequest(BaseModel):
    """Accepted discovery recommendations to merge into the active BrandContext.

    Field semantics (anything omitted means "not accepted -> keep current value"):

    - ``run_id``: provenance only — which discovery run the user reviewed.
    - ``colors``: accepted color roles, FULL payload including ONLY the variants
      the user accepted. Roles not listed stay exactly as they are.
    - ``logo_url``: accepted logo URL; ``None`` or empty string means not accepted.
    - ``image_style_directives``: ``None`` keeps the current list; a list (even an
      empty one) replaces it.
    - ``approved_fonts`` / ``discarded_fonts``: font candidates the user settled.
      The same family in both lists is a user error (422 at the route layer).
    - ``typography_roles``: role key (``display|headline|body|accent``) -> approved
      family name. The family must be approved after this request is merged.

    The response is the saved ``BrandContext`` itself (same as ``PUT /brands/{id}``).
    """

    run_id: str | None = None
    colors: list[BrandColorRecommendation] = Field(default_factory=list)
    logo_url: str | None = None
    image_style_directives: list[str] | None = None
    approved_fonts: list[FontCandidate] = Field(default_factory=list)
    discarded_fonts: list[FontCandidate] = Field(default_factory=list)
    typography_roles: dict[str, str] | None = None
