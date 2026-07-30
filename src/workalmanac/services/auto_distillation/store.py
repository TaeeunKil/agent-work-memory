from pathlib import Path

from workalmanac.services.auto_distillation.models import AutoDistillSettings


class AutoDistillStore:
    def __init__(self, path: Path):
        self.path = path

    def save(self, settings: AutoDistillSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            settings.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def load(self) -> AutoDistillSettings | None:
        if not self.path.is_file():
            return None
        return AutoDistillSettings.model_validate_json(
            self.path.read_text(encoding="utf-8")
        )

    def remove(self) -> None:
        self.path.unlink(missing_ok=True)
