from workalmanac.core import WorkAlmanacModel


class SearchSourceSignature(WorkAlmanacModel):
    session_count: int
    session_version: str
    event_count: int
    event_rowid: int
    vault_digest: str
