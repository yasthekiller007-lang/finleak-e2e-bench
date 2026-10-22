from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IntakeLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    profile: Literal["pilot-intake/1"] = "pilot-intake/1"
    upload_slots: int = Field(default=2, ge=1, le=4)
    process_slots: int = Field(default=1, ge=1, le=4)
    actor_operations_per_minute: int = Field(default=10, ge=1, le=1000)
