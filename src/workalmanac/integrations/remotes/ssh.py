import base64
import json
import os
import shlex
import shutil
import stat
import tempfile
import zipfile
from importlib import resources
from pathlib import Path

from pydantic import ValidationError

from workalmanac.integrations.remotes.process import OpenSshRunner, SshRunner
from workalmanac.services.remotes.errors import (
    RemoteAccessError,
    RemoteAccessErrorKind,
)
from workalmanac.services.remotes.models import (
    RemoteFileObservation,
    RemoteHost,
    RemoteManifest,
    RemoteSnapshot,
)

MAX_MANIFEST_BYTES = 20 * 1024 * 1024
MAX_FILES = 50_000
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_BYTES = MAX_DOWNLOAD_BYTES + MAX_MANIFEST_BYTES


class SshRemoteSnapshotAdapter:
    def __init__(self, runner: SshRunner | None = None):
        self.runner = runner or OpenSshRunner()

    def snapshot(
        self,
        host: RemoteHost,
        previous: RemoteManifest,
        cache_root: Path,
    ) -> RemoteSnapshot:
        raw_manifest = self.runner.capture(
            host.target,
            helper_command("manifest.py"),
            timeout_seconds=60,
        )
        manifest = parse_manifest(raw_manifest, host)
        home = cache_root / "home"
        home.mkdir(parents=True, exist_ok=True)
        remove_deleted_files(home, previous, manifest)
        changed = changed_files(previous, manifest, home)
        if not changed:
            return RemoteSnapshot(
                local_home=home,
                manifest=manifest,
                files_downloaded=0,
                bytes_downloaded=0,
            )
        requested = [observation.path for observation in changed]
        encoded = base64.b64encode(json.dumps(requested).encode()).decode()
        cache_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="wa-remote-",
            dir=cache_root,
        ) as temporary:
            archive_path = Path(temporary) / "snapshot.zip"
            self.runner.download(
                host.target,
                helper_command("bundle.py", encoded),
                archive_path,
                timeout_seconds=300,
                max_bytes=MAX_ARCHIVE_BYTES,
            )
            extract_snapshot(archive_path, home, changed)
        return RemoteSnapshot(
            local_home=home,
            manifest=manifest,
            files_downloaded=len(changed),
            bytes_downloaded=sum(item.size_bytes for item in changed),
        )


def helper_command(name: str, *arguments: str) -> str:
    package = resources.files("workalmanac.integrations.remotes.helpers")
    source = package.joinpath(name).read_text(encoding="utf-8")
    encoded = base64.b64encode(source.encode()).decode()
    loader = (
        "import base64;"
        f"exec(compile(base64.b64decode('{encoded}'),"
        "'wa_remote_helper','exec'))"
    )
    return shlex.join(("python3", "-c", loader, *arguments))


def parse_manifest(raw: bytes, host: RemoteHost) -> RemoteManifest:
    if len(raw) > MAX_MANIFEST_BYTES:
        raise limit_error("remote transcript manifest is too large")
    try:
        manifest = RemoteManifest.model_validate_json(raw)
    except ValidationError as error:
        raise protocol_error("remote transcript manifest is invalid") from error
    if len(manifest.files) > MAX_FILES:
        raise limit_error("remote transcript manifest contains too many files")
    allowed = set(host.providers)
    paths: set[str] = set()
    total_bytes = 0
    for observation in manifest.files:
        if observation.provider not in allowed:
            continue
        if observation.path in paths:
            raise protocol_error("remote transcript manifest contains duplicate paths")
        paths.add(observation.path)
        if observation.size_bytes > MAX_FILE_BYTES:
            raise limit_error("a remote transcript exceeds the per-file limit")
        total_bytes += observation.size_bytes
        if total_bytes > MAX_DOWNLOAD_BYTES * 10:
            raise limit_error("remote transcript store exceeds the safety limit")
    return RemoteManifest(
        files=tuple(
            observation
            for observation in manifest.files
            if observation.provider in allowed
        )
    )


def changed_files(
    previous: RemoteManifest,
    current: RemoteManifest,
    home: Path,
) -> tuple[RemoteFileObservation, ...]:
    prior = {
        item.path: (item.size_bytes, item.modified_ns) for item in previous.files
    }
    changed = tuple(
        item
        for item in current.files
        if (
            prior.get(item.path) != (item.size_bytes, item.modified_ns)
            or not safe_local_target(home, item.path).is_file()
        )
    )
    if sum(item.size_bytes for item in changed) > MAX_DOWNLOAD_BYTES:
        raise limit_error("changed remote transcripts exceed the download limit")
    return changed


def remove_deleted_files(
    home: Path,
    previous: RemoteManifest,
    current: RemoteManifest,
) -> None:
    current_paths = {item.path for item in current.files}
    for observation in previous.files:
        if observation.path in current_paths:
            continue
        target = safe_local_target(home, observation.path)
        if target.is_file() and not target.is_symlink():
            target.unlink()


def extract_snapshot(
    archive_path: Path,
    home: Path,
    expected: tuple[RemoteFileObservation, ...],
) -> None:
    observations = {item.path: item for item in expected}
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) != len(observations):
                raise protocol_error("remote snapshot contains unexpected files")
            names: set[str] = set()
            expanded = 0
            for member in members:
                if (
                    member.is_dir()
                    or member.filename not in observations
                    or member.filename in names
                    or stat.S_ISLNK(member.external_attr >> 16)
                ):
                    raise protocol_error("remote snapshot contains an unsafe member")
                observation = observations[member.filename]
                if member.file_size != observation.size_bytes:
                    raise protocol_error("remote snapshot file size changed")
                expanded += member.file_size
                if expanded > MAX_DOWNLOAD_BYTES:
                    raise limit_error("remote snapshot exceeds the extraction limit")
                names.add(member.filename)
            for member in members:
                observation = observations[member.filename]
                target = safe_local_target(home, observation.path)
                target.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=".wa-",
                    suffix=".tmp",
                    dir=target.parent,
                )
                os.close(descriptor)
                temporary = Path(temporary_name)
                try:
                    with archive.open(member) as source, temporary.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    temporary.replace(target)
                    os.utime(
                        target,
                        ns=(observation.modified_ns, observation.modified_ns),
                    )
                finally:
                    temporary.unlink(missing_ok=True)
    except (OSError, zipfile.BadZipFile) as error:
        raise protocol_error("remote snapshot archive is invalid") from error


def safe_local_target(home: Path, relative: str) -> Path:
    root = home.resolve()
    target = (root / Path(relative)).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise protocol_error("remote snapshot path escaped its cache") from error
    return target


def protocol_error(message: str) -> RemoteAccessError:
    return RemoteAccessError(RemoteAccessErrorKind.PROTOCOL, message)


def limit_error(message: str) -> RemoteAccessError:
    return RemoteAccessError(RemoteAccessErrorKind.LIMIT, message)
