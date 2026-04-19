"""Image-sorting helpers."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

try:
    import grp
    import pwd
except ImportError:  # pragma: no cover - platform-specific
    grp = None
    pwd = None


def has_extension(path: Path, extensions: tuple[str, ...]) -> bool:
    return path.suffix.lstrip(".") in set(extensions)


def collect_matching_files(root: Path, extensions: tuple[str, ...]) -> list[Path]:
    matches: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and has_extension(path, extensions):
            matches.append(path)
    return matches


def collect_top_level_matching_files(root: Path, extensions: tuple[str, ...]) -> list[Path]:
    matches: list[Path] = []
    for path in sorted(root.iterdir()):
        if path.is_file() and has_extension(path, extensions):
            matches.append(path)
    return matches


def timestamp_for_path(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime)


def month_folder_name(path: Path) -> str:
    return timestamp_for_path(path).strftime("%Y-%m")


def build_destination_dir(
    path: Path,
    *,
    temp_dir: Path,
    raw_extensions: tuple[str, ...],
    video_extensions: tuple[str, ...],
) -> Path:
    destination = temp_dir / month_folder_name(path)
    if has_extension(path, raw_extensions):
        return destination / "raw"
    if has_extension(path, video_extensions):
        return destination / "vid"
    return destination / "img"


def set_path_timestamp_from_source(target: Path, source: Path) -> None:
    stat = source.stat()
    os.utime(target, (stat.st_atime, stat.st_mtime))


def apply_ownership(path: Path, *, owner_user: str | None, owner_group: str | None) -> None:
    if not owner_user or not owner_group or pwd is None or grp is None:
        return
    uid = pwd.getpwnam(owner_user).pw_uid
    gid = grp.getgrnam(owner_group).gr_gid
    os.chown(path, uid, gid)
