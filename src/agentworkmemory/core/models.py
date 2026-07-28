from pydantic import BaseModel, ConfigDict


class AgentWorkMemoryModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
