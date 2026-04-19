"""Sync media files into the library and keep only English audio/subtitles."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from nas_scripts.config.sync_media_library import (
    SyncMediaLibraryConfig,
    load_sync_media_library_config,
)
from nas_scripts.utils.locking import AlreadyLockedError, FileLock
from nas_scripts.utils.logging import setup_script_logger
from nas_scripts.utils.media import (
    build_stream_map_args,
    collect_relative_files,
    collect_relative_media_files,
    copy_file_with_metadata,
    find_non_english_audio_subtitle_streams,
    is_media_file,
    probe_streams,
    filter_to_english_audio_and_subtitles,
    remove_empty_directories,
    remove_leftover_temp_files,
)


def sync_media_files(
    config: SyncMediaLibraryConfig,
    *,
    logger: logging.Logger,
) -> list[Path]:
    source_files = collect_relative_media_files(config.source_dir, config.extensions)
    dest_files = collect_relative_files(config.dest_dir)

    logger.info("Found %s source media file(s).", len(source_files))
    logger.info("Found %s destination file(s).", len(dest_files))

    copied_files: list[Path] = []
    source_set = set(source_files)
    dest_set = set(dest_files)

    for relpath in source_files:
        source_path = config.source_dir / relpath
        dest_path = config.dest_dir / relpath
        if not dest_path.exists():
            copy_file_with_metadata(source_path, dest_path)
            copied_files.append(dest_path)
            logger.info("Copied: %s", relpath)

    for relpath in sorted(dest_set - source_set):
        full_path = config.dest_dir / relpath
        if full_path.is_file():
            full_path.unlink()
            logger.info("Deleted stale file: %s", relpath)

    for removed_dir in remove_empty_directories(config.dest_dir):
        logger.info("Deleted empty directory: %s", removed_dir)

    return copied_files


def keep_only_english_audio_and_subtitles(
    config: SyncMediaLibraryConfig,
    *,
    logger: logging.Logger,
) -> None:
    media_files = collect_relative_media_files(config.dest_dir, config.extensions)
    logger.info(
        "Checking %s media file(s) for non-English audio/subtitle streams.",
        len(media_files),
    )

    for relpath in media_files:
        file_path = config.dest_dir / relpath
        if not is_media_file(file_path, config.extensions):
            continue
        try:
            streams = probe_streams(file_path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ffprobe failed for %s: %s", file_path, exc)
            continue

        non_english_indexes = find_non_english_audio_subtitle_streams(streams)
        if not non_english_indexes:
            continue

        kept_map_count = len(build_stream_map_args(streams)) // 2
        logger.info(
            "Filtering %s to English audio/subtitle streams only. Removing stream(s): %s",
            file_path,
            ",".join(str(index) for index in non_english_indexes),
        )
        if kept_map_count == 0:
            logger.error(
                "Skipping %s because filtering would remove all mapped streams.", file_path
            )
            continue
        if filter_to_english_audio_and_subtitles(
            file_path,
            ffmpeg_threads=config.ffmpeg_threads,
        ):
            logger.info("Updated file: %s", file_path)
        else:
            logger.error("Failed to process %s", file_path)

    for temp_file in remove_leftover_temp_files(config.dest_dir):
        logger.info("Removed leftover temp file: %s", temp_file)


def run_job(config: SyncMediaLibraryConfig, *, logger: logging.Logger) -> int:
    if not config.source_dir.exists():
        message = f"Error: source directory does not exist: {config.source_dir}"
        print(message, file=sys.stderr)
        logger.error(message)
        return 1

    if not config.dest_dir.exists():
        message = f"Error: destination directory does not exist: {config.dest_dir}"
        print(message, file=sys.stderr)
        logger.error(message)
        return 1

    logger.info("Starting media sync from %s to %s", config.source_dir, config.dest_dir)
    sync_media_files(config, logger=logger)
    keep_only_english_audio_and_subtitles(config, logger=logger)
    logger.info("Media sync completed.")
    return 0


def main() -> int:
    config = load_sync_media_library_config()
    logger = setup_script_logger(config.script_name, config.log_file)
    logger.info("Starting %s", config.script_name)
    if not config.source_dir.exists() or not config.dest_dir.exists():
        return run_job(config, logger=logger)
    try:
        with FileLock(config.lock_file):
            return run_job(config, logger=logger)
    except AlreadyLockedError:
        print("Another instance is already running. Exiting.")
        logger.warning("Another instance is already running. Exiting.")
        return 0
