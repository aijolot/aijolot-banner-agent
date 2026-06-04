from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PlacementMode = Literal["existing_section", "new_section"]
PlacementTargetType = Literal["home", "collection", "product", "page", "search", "store"]

DEFAULT_LAYOUT_JSON: dict[str, Any] = {"cols": [{"rows": 1, "w": 1, "align": "center"}]}
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class PlacementTypeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    key: str
    label: str
    description: str | None = None
    supported_targets: list[PlacementTargetType] = Field(default_factory=list)
    supported_slots: list[dict[str, Any]] = Field(default_factory=list)
    default_dimensions: dict[str, Any] = Field(default_factory=dict)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    anchor_key: str | None = None
    is_active: bool = True


class PlacementTargetMap(BaseModel):
    model_config = ConfigDict(extra="ignore")

    home: list[Any] = Field(default_factory=list)
    collection: list[Any] = Field(default_factory=list)
    product: list[Any] = Field(default_factory=list)
    page: list[Any] = Field(default_factory=list)
    search: list[Any] = Field(default_factory=list)
    store: list[Any] = Field(default_factory=list)

    def keys(self):
        return self.as_supported_dict().keys()

    def __getitem__(self, key: str) -> list[Any]:
        return getattr(self, key)

    def as_supported_dict(self) -> dict[str, list[Any]]:
        return {key: value for key, value in self.model_dump().items() if value}


class NormalizedPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: str = Field(..., pattern=UUID_PATTERN)
    placement_type_id: str | None = None
    placement_type_key: str
    mode: PlacementMode
    target_type: PlacementTargetType
    target_resource_gid: str | None = None
    target_handle: str | None = None
    target_title: str | None = None
    existing_placement_key: str | None = None
    existing_placement_label: str | None = None
    existing_placement_size: str | None = None
    slot: str | None = None
    slot_order: int = 0
    scope_rule: dict[str, Any] = Field(default_factory=dict)
    layout_json: dict[str, Any] = Field(default_factory=lambda: DEFAULT_LAYOUT_JSON.copy())


class PlacementValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: str = Field(..., pattern=UUID_PATTERN)
    placement_type_key: str
    mode: PlacementMode
    target_type: PlacementTargetType
    target_resource_gid: str | None = None
    target_handle: str | None = None
    target_title: str | None = None
    existing_placement_key: str | None = None
    existing_placement_label: str | None = None
    existing_placement_size: str | None = None
    slot: str | None = None
    slot_order: int = 0
    scope_rule: dict[str, Any] = Field(default_factory=dict)
    layout_json: dict[str, Any] = Field(default_factory=lambda: DEFAULT_LAYOUT_JSON.copy())

    @model_validator(mode="after")
    def _normalize_blank_strings(self) -> "PlacementValidateRequest":
        for field_name in (
            "target_resource_gid",
            "target_handle",
            "target_title",
            "existing_placement_key",
            "existing_placement_label",
            "existing_placement_size",
            "slot",
        ):
            value = getattr(self, field_name)
            if isinstance(value, str):
                stripped = value.strip()
                setattr(self, field_name, stripped or None)
        self.placement_type_key = self.placement_type_key.strip()
        return self

    def to_normalized(self, *, placement_type_id: str | None = None) -> NormalizedPlacement:
        return NormalizedPlacement(placement_type_id=placement_type_id, **self.model_dump())


class CampaignPlacementUpsert(PlacementValidateRequest):
    pass


class PlacementValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    placement: NormalizedPlacement
    errors: list[str] = Field(default_factory=list)


class CampaignPlacementResponse(NormalizedPlacement):
    id: str
    campaign_id: str
    placement_type_id: str | None = None
