from enum import StrEnum

from agentworkmemory.core import AgentWorkMemoryModel


class DiagnosticStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticCheck(AgentWorkMemoryModel):
    name: str
    status: DiagnosticStatus
    message: str
