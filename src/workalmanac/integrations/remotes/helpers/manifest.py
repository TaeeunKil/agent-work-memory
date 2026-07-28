import json
from pathlib import Path

ROOTS = (
    ("codex", Path(".codex") / "sessions"),
    ("claude", Path(".claude") / "projects"),
)


def main():
    home = Path.home()
    files = []
    for provider, relative_root in ROOTS:
        root = home / relative_root
        if not root.is_dir() or root.is_symlink():
            continue
        for path in root.rglob("*.jsonl"):
            if not path.is_file() or path.is_symlink():
                continue
            stat = path.stat()
            files.append(
                {
                    "path": path.relative_to(home).as_posix(),
                    "provider": provider,
                    "size_bytes": stat.st_size,
                    "modified_ns": stat.st_mtime_ns,
                }
            )
    print(json.dumps({"files": sorted(files, key=lambda item: item["path"])}))


if __name__ == "__main__":
    main()
