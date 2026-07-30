import base64
import io
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

PREFIXES = (".codex/sessions/", ".claude/projects/")


def safe_path(value):
    normalized = value.strip().replace("\\", "/")
    relative = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or relative.is_absolute()
        or ".." in relative.parts
        or ":" in normalized
        or "\0" in normalized
        or not normalized.endswith(".jsonl")
        or not normalized.startswith(PREFIXES)
    ):
        raise ValueError("unsafe transcript path")
    return normalized


def main():
    requested = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
    home = Path.home().resolve()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in requested:
            relative = safe_path(item)
            unresolved = home / Path(relative)
            candidate = unresolved
            while candidate != home:
                if candidate.is_symlink():
                    raise ValueError("transcript path contains a symbolic link")
                candidate = candidate.parent
            source = unresolved.resolve()
            source.relative_to(home)
            if not source.is_file():
                raise ValueError("transcript changed during snapshot")
            archive.write(source, relative)
    sys.stdout.buffer.write(buffer.getvalue())


if __name__ == "__main__":
    main()
