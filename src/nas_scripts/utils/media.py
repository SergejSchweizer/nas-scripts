"""Media-related helpers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaStream:
    index: int
    codec_type: str
    language: str | None


def is_media_file(path: Path, extensions: tuple[str, ...]) -> bool:
    return path.suffix.lower().lstrip(".") in {ext.lower() for ext in extensions}


def collect_relative_media_files(root: Path, extensions: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and is_media_file(path, extensions):
            matches.append(path.relative_to(root).as_posix())
    return matches


def collect_relative_files(root: Path) -> list[str]:
    matches: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            matches.append(path.relative_to(root).as_posix())
    return matches


def copy_file_with_metadata(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def remove_empty_directories(root: Path) -> list[Path]:
    removed: list[Path] = []
    for directory in sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            continue
        removed.append(directory)
    return removed


def probe_streams(file_path: Path) -> list[MediaStream]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type:stream_tags=language",
            "-of",
            "csv=p=0",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    streams: list[MediaStream] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(",")]
        index = int(parts[0])
        codec_type = parts[1] if len(parts) > 1 else ""
        language = parts[2] if len(parts) > 2 and parts[2] else None
        streams.append(MediaStream(index=index, codec_type=codec_type, language=language))
    return streams


def is_english_language(language: str | None) -> bool:
    if language is None:
        return False
    return language.lower() in {"eng", "en"}


def find_non_english_audio_subtitle_streams(streams: list[MediaStream]) -> list[int]:
    indexes: list[int] = []
    for stream in streams:
        if stream.codec_type not in {"audio", "subtitle"}:
            continue
        if not is_english_language(stream.language):
            indexes.append(stream.index)
    return indexes


def build_stream_map_args(streams: list[MediaStream]) -> list[str]:
    map_args: list[str] = []
    for stream in streams:
        if stream.codec_type in {"audio", "subtitle"}:
            if not is_english_language(stream.language):
                continue
        map_args.extend(["-map", f"0:{stream.index}"])
    return map_args


def filter_to_english_audio_and_subtitles(
    file_path: Path,
    *,
    ffmpeg_threads: int,
) -> bool:
    streams = probe_streams(file_path)
    map_args = build_stream_map_args(streams)

    temp_file = file_path.with_name(f"temp.{file_path.suffix.lstrip('.')}")
    result = subprocess.run(
        [
            "ffmpeg",
            "-threads",
            str(ffmpeg_threads),
            "-i",
            str(file_path),
            *map_args,
            "-c",
            "copy",
            str(temp_file),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        temp_file.unlink(missing_ok=True)
        return False
    temp_file.replace(file_path)
    return True


def remove_leftover_temp_files(root: Path) -> list[Path]:
    removed: list[Path] = []
    for path in root.rglob("temp.*"):
        if path.is_file():
            path.unlink(missing_ok=True)
            removed.append(path)
    return removed
