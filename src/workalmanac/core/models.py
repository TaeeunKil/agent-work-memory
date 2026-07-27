from pydantic import BaseModel, ConfigDict


class WorkAlmanacModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
