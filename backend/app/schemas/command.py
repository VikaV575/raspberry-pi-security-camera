from typing import Literal

from pydantic import BaseModel, Field


class CommandCreate(BaseModel):
    type: Literal["snapshot", "record", "start_live", "stop_live"]
    seconds: int | None = Field(default=None, ge=1, le=60)
