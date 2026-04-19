"""Filesystem helpers for NAS jobs.

This module provides the low-level file discovery and checksum support used by
the incremental ingestion workflow. It sits below the job facade and above the
raw filesystem calls.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileRecord:
    """A file metadata snapshot used by the incremental ingestion state."""

    path: str
    size: int
    mtime: float
    sha256: str

    def to_state(self) -> dict[str, str | int | float]:
        """Serialize the file snapshot into the persistence-layer format."""
        return asdict(self)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute the content hash used by the incremental-sync strategy."""
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
    """Decide whether a path belongs in the ingestion candidate set."""
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
    """Collect the filesystem snapshot that the ingestion facade consumes."""
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
