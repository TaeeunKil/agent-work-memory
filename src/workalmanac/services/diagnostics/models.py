from enum import StrEnum

from workalmanac.core import WorkAlmanacModel


class DiagnosticStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticCheck(WorkAlmanacModel):
    name: str
    status: DiagnosticStatus
    message: str
