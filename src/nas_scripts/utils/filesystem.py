"""Filesystem helpers for NAS jobs."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    mtime: float
    sha256: str

    def to_state(self) -> dict[str, str | int | float]:
        return asdict(self)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def is_supported_file(
    path: Path,
    *,
    supported_extensions: set[str],
    ignored_names: set[str],
) -> bool:
    if not path.is_file():
        return False
    if path.name in ignored_names:
        return False
    return path.suffix.lower() in supported_extensions


def collect_files(
    root: Path,
    *,
    supported_extensions: set[str],
    ignored_names: set[str],
) -> dict[str, FileRecord]:
    found: dict[str, FileRecord] = {}
    for path in sorted(root.rglob("*")):
        if not is_supported_file(
            path,
            supported_extensions=supported_extensions,
            ignored_names=ignored_names,
        ):
            continue
        stat = path.stat()
        rel_path = path.relative_to(root).as_posix()
        found[rel_path] = FileRecord(
            path=str(path),
            size=stat.st_size,
            mtime=stat.st_mtime,
            sha256=sha256_file(path),
        )
    return found
