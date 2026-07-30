from enum import StrEnum


class RemoteAccessErrorKind(StrEnum):
    UNAVAILABLE = "unavailable"
    PROTOCOL = "protocol"
    LIMIT = "limit"


class RemoteAccessError(RuntimeError):
    def __init__(
        self,
        kind: RemoteAccessErrorKind,
        message: str = "remote snapshot failed",
    ):
        self.kind = kind
        super().__init__(f"{message} ({kind.value})")
