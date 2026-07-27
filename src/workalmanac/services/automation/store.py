import json
from pathlib import Path

from workalmanac.services.automation.models import AutoSyncSettings


class AutomationStore:
    def __init__(self, path: Path):
        self.path = path

    def save(self, settings: AutoSyncSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(settings.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )

    def load(self) -> AutoSyncSettings | None:
        if not self.path.is_file():
            return None
        return AutoSyncSettings.model_validate_json(
            self.path.read_text(encoding="utf-8")
        )

    def remove(self) -> None:
        if self.path.is_file():
            self.path.unlink()
