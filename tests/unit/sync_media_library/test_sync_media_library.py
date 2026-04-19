from __future__ import annotations

import shutil
from pathlib import Path

from nas_scripts.cli import main as cli_main
from nas_scripts.config.sync_media_library import SyncMediaLibraryConfig
from nas_scripts.jobs.sync_media_library import (
    keep_only_english_audio_and_subtitles,
    run_job,
    sync_media_files,
)
from nas_scripts.utils.logging import setup_script_logger
from nas_scripts.utils.media import (
    build_stream_map_args,
    MediaStream,
    collect_relative_files,
    collect_relative_media_files,
    find_non_english_audio_subtitle_streams,
)

MEDIA_FIXTURE_ROOT = Path("tests/data/sync_media_library")
JOB_MODULE = Path("src/nas_scripts/jobs/sync_media_library.py")


def make_config(tmp_path: Path) -> SyncMediaLibraryConfig:
    return SyncMediaLibraryConfig(
        script_name="sync_media_library",
        source_dir=tmp_path / "source",
        dest_dir=tmp_path / "dest",
        lock_file=tmp_path / "media.lock",
        log_dir=tmp_path / "logs",
        extensions=("mpg", "avi", "mp4", "mkv"),
        ffmpeg_threads=1,
    )


class DummyLogger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
        return None


def test_collect_relative_media_files_filters_extensions(tmp_path: Path) -> None:
    root = tmp_path / "media"
    root.mkdir()
    (root / "movie.mkv").write_text("a", encoding="utf-8")
    (root / "clip.mp4").write_text("b", encoding="utf-8")
    (root / "note.txt").write_text("c", encoding="utf-8")

    result = collect_relative_media_files(root, ("mkv", "mp4"))

    assert result == ["clip.mp4", "movie.mkv"]


def test_job_module_stays_isolated_from_other_script_modules() -> None:
    source = JOB_MODULE.read_text(encoding="utf-8")

    assert "nas_scripts.jobs.ingest_crypto_documents" not in source
    assert "nas_scripts.jobs.organize_temp_media" not in source
    assert "nas_scripts.config.ingest_crypto_documents" not in source
    assert "nas_scripts.config.organize_temp_media" not in source
    assert "nas_scripts.utils.onyx" not in source
    assert "nas_scripts.utils.images" not in source


def test_cli_runs_sync_media_library_command(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["nas-scripts", "sync-media-library"])
    monkeypatch.setattr(
        "nas_scripts.cli.sync_media_library_main",
        lambda: 0,
    )
    assert cli_main() == 0


def test_sync_media_files_copies_new_and_deletes_stale(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.source_dir.mkdir(parents=True)
    config.dest_dir.mkdir(parents=True)
    (config.source_dir / "movie.mkv").write_text("source", encoding="utf-8")
    (config.dest_dir / "old.mkv").write_text("old", encoding="utf-8")

    copied = sync_media_files(config, logger=DummyLogger())

    assert [path.name for path in copied] == ["movie.mkv"]
    assert (config.dest_dir / "movie.mkv").exists()
    assert not (config.dest_dir / "old.mkv").exists()


def test_find_non_english_audio_subtitle_streams_returns_matching_indexes() -> None:
    streams = [
        MediaStream(index=0, codec_type="video", language=None),
        MediaStream(index=1, codec_type="audio", language="eng"),
        MediaStream(index=2, codec_type="audio", language="rus"),
        MediaStream(index=3, codec_type="subtitle", language="spa"),
        MediaStream(index=4, codec_type="subtitle", language="en"),
    ]

    assert find_non_english_audio_subtitle_streams(streams) == [2, 3]


def test_build_stream_map_args_keeps_only_english_audio_and_subtitles() -> None:
    streams = [
        MediaStream(index=0, codec_type="video", language=None),
        MediaStream(index=1, codec_type="audio", language="eng"),
        MediaStream(index=2, codec_type="audio", language="rus"),
        MediaStream(index=3, codec_type="subtitle", language="en"),
        MediaStream(index=4, codec_type="subtitle", language="spa"),
    ]

    assert build_stream_map_args(streams) == [
        "-map",
        "0:0",
        "-map",
        "0:1",
        "-map",
        "0:3",
    ]


def test_run_job_fails_when_source_missing(tmp_path: Path, capsys) -> None:
    config = make_config(tmp_path)
    config.dest_dir.mkdir(parents=True)

    assert run_job(config, logger=DummyLogger()) == 1
    assert "source directory does not exist" in capsys.readouterr().err


def test_run_job_fails_when_dest_missing(tmp_path: Path, capsys) -> None:
    config = make_config(tmp_path)
    config.source_dir.mkdir(parents=True)

    assert run_job(config, logger=DummyLogger()) == 1
    assert "destination directory does not exist" in capsys.readouterr().err


def test_collect_relative_files_lists_all_files(tmp_path: Path) -> None:
    root = tmp_path / "dest"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "movie.mkv").write_text("x", encoding="utf-8")
    (root / "note.txt").write_text("y", encoding="utf-8")

    assert collect_relative_files(root) == ["note.txt", "sub/movie.mkv"]


def test_run_job_writes_messages_to_log_file(tmp_path: Path, monkeypatch) -> None:
    config = make_config(tmp_path)
    config.source_dir.mkdir(parents=True)
    config.dest_dir.mkdir(parents=True)
    logger = setup_script_logger(f"sync_job_test_{tmp_path.name}", config.log_file)

    monkeypatch.setattr(
        "nas_scripts.jobs.sync_media_library.sync_media_files",
        lambda config, logger: [],
    )
    monkeypatch.setattr(
        "nas_scripts.jobs.sync_media_library.keep_only_english_audio_and_subtitles",
        lambda config, logger: None,
    )

    assert run_job(config, logger=logger) == 0

    for handler in logger.handlers:
        handler.flush()

    log_content = config.log_file.read_text(encoding="utf-8")
    assert "Starting media sync" in log_content
    assert "Media sync completed." in log_content


def test_keep_only_english_audio_and_subtitles_updates_matching_files(
    tmp_path: Path, monkeypatch
) -> None:
    config = make_config(tmp_path)
    config.dest_dir.mkdir(parents=True)
    target = config.dest_dir / "movie.mkv"
    target.write_text("media", encoding="utf-8")

    monkeypatch.setattr(
        "nas_scripts.jobs.sync_media_library.collect_relative_media_files",
        lambda root, extensions: ["movie.mkv"],
    )
    monkeypatch.setattr(
        "nas_scripts.jobs.sync_media_library.probe_streams",
        lambda file_path: [
            MediaStream(index=0, codec_type="video", language=None),
            MediaStream(index=1, codec_type="audio", language="eng"),
            MediaStream(index=2, codec_type="audio", language="rus"),
            MediaStream(index=3, codec_type="subtitle", language="spa"),
        ],
    )
    filtered: list[Path] = []
    monkeypatch.setattr(
        "nas_scripts.jobs.sync_media_library.filter_to_english_audio_and_subtitles",
        lambda file_path, ffmpeg_threads: filtered.append(file_path) or True,
    )
    monkeypatch.setattr(
        "nas_scripts.jobs.sync_media_library.remove_leftover_temp_files",
        lambda root: [],
    )

    keep_only_english_audio_and_subtitles(config, logger=DummyLogger())

    assert filtered == [target]


def test_collect_relative_media_files_uses_real_media_fixtures() -> None:
    result = collect_relative_media_files(MEDIA_FIXTURE_ROOT, ("mkv", "mp4", "avi", "mpg"))

    assert "09_Dergileva_Dobrynskaja_Gurov_Sokolova.pdf" not in result
    assert "Avatar.Fire.and.Ash.2025.x265.WEB-DL.2160p.HDR-DV.mkv" in result
    assert "Balls.Up.2026.2160p.AMZN.WEB-DL.DDP5.1.DV.HDR.H.265.mkv" in result
    assert "Mike.and.Nick.and.Nick.and.Alice.2026.x265.WEB-DL.2160p.HDR-DV.mkv" in result
    assert "Podlasie.2026.x265.WEB-DL.2160p.SDR.mkv" in result


def test_sync_media_files_with_real_fixture_names_without_copying_large_files(
    tmp_path: Path, monkeypatch
) -> None:
    config = SyncMediaLibraryConfig(
        script_name="sync_media_library",
        source_dir=MEDIA_FIXTURE_ROOT,
        dest_dir=tmp_path / "dest",
        lock_file=tmp_path / "media.lock",
        log_dir=tmp_path / "logs",
        extensions=("mpg", "avi", "mp4", "mkv"),
        ffmpeg_threads=1,
    )
    config.dest_dir.mkdir(parents=True)
    (config.dest_dir / "stale_file.mkv").write_text("stale", encoding="utf-8")

    copied: list[str] = []

    def fake_copy(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source.name, encoding="utf-8")
        copied.append(destination.name)

    monkeypatch.setattr(
        "nas_scripts.jobs.sync_media_library.copy_file_with_metadata",
        fake_copy,
    )

    sync_media_files(config, logger=DummyLogger())

    assert "stale_file.mkv" not in collect_relative_files(config.dest_dir)
    assert "Avatar.Fire.and.Ash.2025.x265.WEB-DL.2160p.HDR-DV.mkv" in copied
    assert "Podlasie.2026.x265.WEB-DL.2160p.SDR.mkv" in copied


def test_probe_streams_on_real_fixture_if_ffprobe_is_available() -> None:
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        return

    media_files = collect_relative_media_files(MEDIA_FIXTURE_ROOT, ("mkv",))
    assert media_files, "Expected at least one MKV fixture in tests/data/sync_media_library"

    from nas_scripts.utils.media import probe_streams

    streams = probe_streams(MEDIA_FIXTURE_ROOT / media_files[0])

    assert streams
