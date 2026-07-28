from datetime import datetime

from pydantic import Field, field_validator, model_validator

from workalmanac.core import WorkAlmanacModel
from workalmanac.services.curators.models import ContentAccess


class AutoDistillSettings(WorkAlmanacModel):
    interval_minutes: int = Field(ge=1, le=1439)
    limit: int = Field(ge=1, le=20)
    runtime: str
    model: str | None = None
    content_access: ContentAccess
    installed_at: datetime | None = None
    expires_at: datetime
    max_sessions_total: int = Field(ge=1, le=100)
    sessions_reserved: int = Field(default=0, ge=0)

    @field_validator("runtime")
    @classmethod
    def require_runtime(cls, value: str) -> str:
        runtime = value.strip()
        if not runtime:
            raise ValueError("automatic distill runtime must not be empty")
        return runtime

    @field_validator("expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("automatic distill expiry must include a timezone")
        return value

    @model_validator(mode="after")
    def require_standing_content_grant(self) -> "AutoDistillSettings":
        if self.content_access is ContentAccess.METADATA_ONLY:
            raise ValueError(
                "automatic distill requires an explicit local or remote content grant"
            )
        if self.sessions_reserved > self.max_sessions_total:
            raise ValueError(
                "automatic distill reserved count exceeds its standing grant"
            )
        return self


class AutoDistillStatus(WorkAlmanacModel):
    available: bool
    installed: bool
    task_name: str
    message: str
    settings: AutoDistillSettings | None = None
