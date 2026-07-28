from dataclasses import dataclass
from pathlib import Path

MAX_SNAPSHOT_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class VaultSnapshot:
    root: Path
    files: dict[Path, bytes]
    ignored_roots: frozenset[str] = frozenset()

    @classmethod
    def capture(
        cls,
        root: Path,
        *,
        ignored_roots: frozenset[str] = frozenset(),
    ) -> "VaultSnapshot":
        resolved_root = root.resolve()
        files: dict[Path, bytes] = {}
        total_bytes = 0
        for path in vault_files(resolved_root, ignored_roots=ignored_roots):
            relative = path.relative_to(resolved_root)
            content = path.read_bytes()
            total_bytes += len(content)
            if total_bytes > MAX_SNAPSHOT_BYTES:
                raise ValueError(
                    "Vault is too large for safe foreground distillation "
                    f"(limit: {MAX_SNAPSHOT_BYTES} bytes)"
                )
            files[relative] = content
        return cls(
            root=resolved_root,
            files=files,
            ignored_roots=ignored_roots,
        )

    def changed_files(self) -> tuple[Path, ...]:
        current = {
            path.relative_to(self.root): path.read_bytes()
            for path in vault_files(
                self.root,
                ignored_roots=self.ignored_roots,
            )
        }
        changed = {
            relative
            for relative in self.files.keys() | current.keys()
            if self.files.get(relative) != current.get(relative)
        }
        return tuple(sorted(changed, key=lambda path: path.as_posix()))

    def restore(self) -> None:
        current = {
            path.relative_to(self.root): path
            for path in vault_files(
                self.root,
                ignored_roots=self.ignored_roots,
            )
        }
        for relative, path in current.items():
            if relative not in self.files:
                path.unlink()
        for relative, content in self.files.items():
            target = (self.root / relative).resolve()
            ensure_inside(self.root, target)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


def vault_files(
    root: Path,
    *,
    ignored_roots: frozenset[str] = frozenset(),
) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in ignored_roots | {".git"}:
            continue
        if path.is_symlink():
            raise ValueError(
                f"Vault symlinks are not allowed during distill: {relative}"
            )
        if path.is_file():
            ensure_inside(root, path.resolve())
            files.append(path)
    return tuple(sorted(files))


def ensure_inside(root: Path, target: Path) -> None:
    try:
        target.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"Vault path escapes configured root: {target}") from error
