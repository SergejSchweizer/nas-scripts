"""Configuration for the sync_media_library job."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SOURCE_DIR = Path("/volume1/Torrents")
DEFAULT_DEST_DIR = Path("/volume1/Media")
DEFAULT_LOCK_FILE = Path("/tmp/media.lock")
DEFAULT_LOG_DIR = Path("/volume1/Temp/logs")
DEFAULT_EXTENSIONS = ("mpg", "avi", "mp4", "mkv")


@dataclass(frozen=True)
class SyncMediaLibraryConfig:
    script_name: str
    source_dir: Path
    dest_dir: Path
    lock_file: Path
    log_dir: Path
    extensions: tuple[str, ...]
    ffmpeg_threads: int

    @property
    def log_file(self) -> Path:
        return self.log_dir / f"{self.script_name}.log"


def load_sync_media_library_config() -> SyncMediaLibraryConfig:
    extensions_raw = os.environ.get("MEDIA_EXTENSIONS")
    extensions = (
        tuple(part.strip().lower() for part in extensions_raw.split(",") if part.strip())
        if extensions_raw
        else DEFAULT_EXTENSIONS
    )

    return SyncMediaLibraryConfig(
        script_name="sync_media_library",
        source_dir=Path(os.environ.get("SOURCE_DIR", str(DEFAULT_SOURCE_DIR))),
        dest_dir=Path(os.environ.get("DEST_DIR", str(DEFAULT_DEST_DIR))),
        lock_file=Path(os.environ.get("LOCK_FILE", str(DEFAULT_LOCK_FILE))),
        log_dir=Path(os.environ.get("LOG_DIR", str(DEFAULT_LOG_DIR))),
        extensions=extensions,
        ffmpeg_threads=int(os.environ.get("FFMPEG_THREADS", "1")),
    )
