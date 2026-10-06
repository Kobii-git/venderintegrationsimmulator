from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReplayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str
    loop: bool = False
    timing: Literal["fixed", "original"] = "fixed"
    rewrite_timestamps: bool = False
    timestamp_fields: list[str] = Field(default_factory=list)
    max_original_gap_seconds: float = Field(default=3600, ge=0, le=86400)
