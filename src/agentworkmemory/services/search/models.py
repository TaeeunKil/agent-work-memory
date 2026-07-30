from agentworkmemory.core import AgentWorkMemoryModel


class SearchSourceSignature(AgentWorkMemoryModel):
    session_count: int
    session_version: str
    event_count: int
    event_rowid: int
    vault_digest: str
