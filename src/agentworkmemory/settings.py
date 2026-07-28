import json
import os
from pathlib import Path

from pydantic import field_validator

from agentworkmemory.core import AgentWorkMemoryModel

CONFIG_FILE_NAME = "config.json"
DATABASE_FILE_NAME = "agentworkmemory.db"


class AgentWorkMemoryConfig(AgentWorkMemoryModel):
    state_dir: Path
    vault_path: Path | None = None

    @field_validator("state_dir", "vault_path")
    @classmethod
    def absolute_paths(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        return value.expanduser().resolve()

    @property
    def database_path(self) -> Path:
        return self.state_dir / DATABASE_FILE_NAME

    @property
    def config_path(self) -> Path:
        return self.state_dir / CONFIG_FILE_NAME


def default_state_dir() -> Path:
    configured = os.environ.get("AGENTWORKMEMORY_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local_app_data:
        return (Path(local_app_data) / "AgentWorkMemory").resolve()
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return (Path(xdg_state_home) / "agentworkmemory").expanduser().resolve()
    return (Path.home() / ".local" / "state" / "agentworkmemory").resolve()


def load_config(state_dir: Path | None = None) -> AgentWorkMemoryConfig:
    resolved_state = (state_dir or default_state_dir()).expanduser().resolve()
    config_path = resolved_state / CONFIG_FILE_NAME
    vault_path: Path | None = None
    if config_path.is_file():
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        configured_vault = raw.get("vault_path")
        if isinstance(configured_vault, str) and configured_vault.strip():
            vault_path = Path(configured_vault)
    return AgentWorkMemoryConfig(state_dir=resolved_state, vault_path=vault_path)


def save_config(config: AgentWorkMemoryConfig) -> None:
    config.state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "vault_path": str(config.vault_path) if config.vault_path is not None else None
    }
    config.config_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
