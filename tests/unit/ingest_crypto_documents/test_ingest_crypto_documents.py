from __future__ import annotations

from contextlib import nullcontext
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from nas_scripts.cli import main as cli_main
from nas_scripts.config.ingest_crypto_documents import (
    IngestCryptoDocumentsConfig,
    load_ingest_crypto_documents_config,
)
from nas_scripts.jobs.ingest_crypto_documents import _partition_files, main, run_job
from nas_scripts.utils.filesystem import FileRecord, collect_files
from nas_scripts.utils.locking import AlreadyLockedError
from nas_scripts.utils.logging import LOG_DATE_FORMAT, setup_script_logger
from nas_scripts.utils.flowrag import build_headers, trigger_parsing, upload_file
from nas_scripts.utils.state import load_state


JOB_MODULE = Path("src/nas_scripts/jobs/ingest_crypto_documents.py")


class DummyLogger:
    # These tests only care that the logger interface is accepted, not that
    # messages are emitted somewhere real.
    def info(self, *args, **kwargs) -> None:
        return None

    def warning(self, *args, **kwargs) -> None:
        return None

    def error(self, *args, **kwargs) -> None:
        return None

    def exception(self, *args, **kwargs) -> None:
        return None


def make_config(
    tmp_path: Path, *, dataset_id: str | None = "dataset-123"
) -> IngestCryptoDocumentsConfig:
    scan_dir = tmp_path / "crypto"
    return IngestCryptoDocumentsConfig(
        script_name="ingest_crypto_documents",
        flowrag_base_url="http://localhost:18080",
        flowrag_api_key="token",
        flowrag_dataset_id=dataset_id,
        scan_dir=scan_dir,
        ingested_dir=scan_dir / "ingested",
        state_file=scan_dir / ".flowrag_ingest_state.json",
        lock_file=tmp_path / "ingest_crypto_documents.lock",
        log_dir=tmp_path / "logs",
        max_files_per_run=None,
        request_timeout=30,
    )


def test_collect_files_filters_supported_extensions(tmp_path: Path) -> None:
    root = tmp_path / "crypto"
    root.mkdir()
    (root / "note.txt").write_text("alpha", encoding="utf-8")
    (root / "README.md").write_text("beta", encoding="utf-8")
    (root / "video.mp4").write_text("ignore", encoding="utf-8")
    (root / "ingested" / "old.txt").parent.mkdir(parents=True)
    (root / "ingested" / "old.txt").write_text("ignore", encoding="utf-8")

    files = collect_files(
        root,
        supported_extensions={".txt", ".md"},
        ignored_names={".flowrag_ingest_state.json", "ingest_crypto_documents.lock"},
        ignored_dir_names={"ingested"},
    )

    assert sorted(files) == ["README.md", "note.txt"]


def test_job_module_stays_isolated_from_other_script_modules() -> None:
    source = JOB_MODULE.read_text(encoding="utf-8")

    assert "nas_scripts.jobs.sync_media_library" not in source
    assert "nas_scripts.jobs.organize_temp_media" not in source
    assert "nas_scripts.config.sync_media_library" not in source
    assert "nas_scripts.config.organize_temp_media" not in source
    assert "nas_scripts.utils.media" not in source
    assert "nas_scripts.utils.images" not in source


def test_cli_runs_ingest_crypto_documents_command(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["nas-scripts", "ingest-crypto-documents"])
    monkeypatch.setattr(
        "nas_scripts.cli.ingest_crypto_documents_main",
        lambda max_files_per_run=None: 0,
    )
    assert cli_main() == 0


def test_cli_passes_max_files_per_run_to_ingest_job(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["nas-scripts", "ingest-crypto-documents", "--max-files-per-run", "1"],
    )
    received: list[int | None] = []

    def fake_main(*, max_files_per_run=None):  # type: ignore[no-untyped-def]
        received.append(max_files_per_run)
        return 0

    monkeypatch.setattr("nas_scripts.cli.ingest_crypto_documents_main", fake_main)

    assert cli_main() == 0
    assert received == [1]


def test_partition_files_separates_changed_records() -> None:
    current = {
        "same.txt": FileRecord("same.txt", 1, 1.0, "same"),
        "new.txt": FileRecord("new.txt", 2, 2.0, "new"),
    }
    previous = {"same.txt": {"sha256": "same"}}

    successful_state, changed = _partition_files(current, previous)

    assert successful_state == {"same.txt": current["same.txt"].to_state()}
    assert changed == [("new.txt", current["new.txt"])]


def test_build_headers_includes_bearer_token() -> None:
    assert build_headers("abc")["Authorization"] == "Bearer abc"
    assert build_headers(None) == {}


def test_load_ingest_crypto_documents_config_reads_local_config_file(
    tmp_path: Path, monkeypatch
) -> None:
    config_file = tmp_path / "config.env"
    config_file.write_text(
        "\n".join(
            [
                "FLOWRAG_BASE_URL=http://flowrag.local:18080",
                "FLOWRAG_API_KEY=test-key",
                "FLOWRAG_DATASET_ID=dataset-999",
                "SCAN_DIR=/tmp/crypto",
                "INGESTED_DIR=/tmp/crypto/ingested",
                "STATE_FILE=/tmp/crypto/state.json",
                "LOCK_FILE=/tmp/crypto/lockfile",
                "LOG_DIR=/tmp/logs",
                "MAX_FILES_PER_RUN=7",
                "REQUEST_TIMEOUT=12",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("INGEST_CONFIG_FILE", str(config_file))

    # The loader should prefer the explicit config file path over defaults or
    # any ambient process environment.
    config = load_ingest_crypto_documents_config()

    assert config.flowrag_base_url == "http://flowrag.local:18080"
    assert config.flowrag_api_key == "test-key"
    assert config.flowrag_dataset_id == "dataset-999"
    assert config.scan_dir == Path("/tmp/crypto")
    assert config.ingested_dir == Path("/tmp/crypto/ingested")
    assert config.state_file == Path("/tmp/crypto/state.json")
    assert config.lock_file == Path("/tmp/crypto/lockfile")
    assert config.log_dir == Path("/tmp/logs")
    assert config.max_files_per_run == 7
    assert config.request_timeout == 12


def test_upload_file_returns_document_id(tmp_path: Path) -> None:
    file_path = tmp_path / "market.md"
    file_path.write_text("btc outlook", encoding="utf-8")
    config = make_config(tmp_path)

    class FakeResponse:
        status_code = 200

        def json(self):  # type: ignore[no-untyped-def]
            return {"code": 0, "data": {"id": "doc-123"}}

    class FakeSession:
        def __init__(self) -> None:
            self.calls = []

        # Capture the request so we can assert the multipart payload shape.
        def post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append((args, kwargs))
            return FakeResponse()

    session = FakeSession()
    assert upload_file(file_path, config=config, session=session) == "doc-123"
    assert session.calls[0][1]["files"]["file"][0] == "market.md"


def test_trigger_parsing_posts_document_ids() -> None:
    config = make_config(Path("/tmp/test-flowrag"))

    class FakeResponse:
        status_code = 200

        @property
        def text(self) -> str:
            return ""

    class FakeSession:
        def __init__(self) -> None:
            self.calls = []

        # Capture the request so we can assert the parse trigger body.
        def post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append((args, kwargs))
            return FakeResponse()

    session = FakeSession()
    trigger_parsing("doc-123", config=config, session=session)
    assert session.calls[0][1]["json"] == {"document_ids": ["doc-123"]}


def test_run_job_ingests_changed_files_and_updates_state(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.scan_dir.mkdir(parents=True)
    first = config.scan_dir / "first.txt"
    second = config.scan_dir / "second.md"
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")

    ingested: list[str] = []

    # Inject a fake ingest function so the test stays local and deterministic.
    def fake_ingest(path: Path, rel_path: str) -> None:
        ingested.append(f"{rel_path}:{path.name}")

    exit_code = run_job(config, ingest_func=fake_ingest)
    saved_state = load_state(config.state_file)

    assert exit_code == 0
    assert ingested == ["first.txt:first.txt", "second.md:second.md"]
    assert sorted(saved_state) == ["first.txt", "second.md"]
    assert not (config.scan_dir / "first.txt").exists()
    assert not (config.scan_dir / "second.md").exists()
    assert (config.ingested_dir / "first.txt").exists()
    assert (config.ingested_dir / "second.md").exists()


def test_run_job_fails_when_dataset_id_missing(tmp_path: Path, capsys) -> None:
    config = make_config(tmp_path, dataset_id=None)
    config.scan_dir.mkdir(parents=True)

    assert run_job(config) == 1
    assert "FLOWRAG_DATASET_ID is not set" in capsys.readouterr().err


def test_main_exits_when_another_instance_holds_the_lock(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    config = make_config(tmp_path)
    config.scan_dir.mkdir(parents=True)

    class LockedFileLock:
        def __init__(self, lock_path: Path) -> None:
            self.lock_path = lock_path

        def __enter__(self):
            raise AlreadyLockedError(str(self.lock_path))

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(
        "nas_scripts.jobs.ingest_crypto_documents.load_ingest_crypto_documents_config",
        lambda: config,
    )
    monkeypatch.setattr(
        "nas_scripts.jobs.ingest_crypto_documents.FileLock",
        LockedFileLock,
    )

    assert main() == 0
    assert "Another instance is already running. Exiting." in capsys.readouterr().out


def test_setup_script_logger_writes_to_per_script_log_file(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "ingest_crypto_documents.log"
    logger = setup_script_logger("test_ingest_crypto_documents_logger", log_file)

    logger.info("hello log")

    for handler in logger.handlers:
        handler.flush()

    assert log_file.exists()
    assert "hello log" in log_file.read_text(encoding="utf-8")
    assert any(
        isinstance(handler, TimedRotatingFileHandler) and handler.backupCount == 0
        for handler in logger.handlers
    )


def test_setup_script_logger_uses_expressive_log_format(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "expressive.log"
    logger = setup_script_logger("test_ingest_crypto_documents_format", log_file)

    logger.warning("format check")

    for handler in logger.handlers:
        handler.flush()

    first_line = log_file.read_text(encoding="utf-8").splitlines()[0]
    prefix = first_line.split(" | pid=")[0]

    assert " | WARNING  | script=nas_scripts.test_ingest_crypto_documents_format | pid=" in first_line
    assert first_line.endswith("format check")
    assert len(prefix.split(" | ")[0]) == len("2026-04-19 10:30:45")
    from datetime import datetime
    datetime.strptime(prefix.split(" | ")[0], LOG_DATE_FORMAT)


def test_setup_script_logger_falls_back_to_local_logs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    primary_log = Path("/volume1/Temp/logs/fallback.log")
    original_mkdir = Path.mkdir

    def fake_mkdir(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self == primary_log.parent:
            raise OSError("read-only file system")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir)

    logger = setup_script_logger("test_ingest_crypto_documents_fallback", primary_log)
    logger.info("fallback log message")

    for handler in logger.handlers:
        handler.flush()

    fallback_log = tmp_path / "logs" / primary_log.name
    assert fallback_log.exists()
    assert "fallback log message" in fallback_log.read_text(encoding="utf-8")


def test_run_job_writes_messages_to_log_file(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.scan_dir.mkdir(parents=True)
    sample = config.scan_dir / "first.txt"
    sample.write_text("one", encoding="utf-8")
    logger = setup_script_logger(f"job_test_{tmp_path.name}", config.log_file)

    run_job(config, ingest_func=lambda path, rel_path: None, logger=logger)

    for handler in logger.handlers:
        handler.flush()

    log_content = config.log_file.read_text(encoding="utf-8")
    assert "Scanning:" in log_content
    assert "Ingested: first.txt" in log_content


def test_run_job_limits_ingestion_to_max_files_per_run(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config = IngestCryptoDocumentsConfig(
        script_name=config.script_name,
        flowrag_base_url=config.flowrag_base_url,
        flowrag_api_key=config.flowrag_api_key,
        flowrag_dataset_id=config.flowrag_dataset_id,
        scan_dir=config.scan_dir,
        ingested_dir=config.ingested_dir,
        state_file=config.state_file,
        lock_file=config.lock_file,
        log_dir=config.log_dir,
        max_files_per_run=2,
        request_timeout=config.request_timeout,
    )
    config.scan_dir.mkdir(parents=True)
    for name in ("a.txt", "b.txt", "c.txt"):
        (config.scan_dir / name).write_text(name, encoding="utf-8")

    ingested: list[str] = []

    def fake_ingest(path: Path, rel_path: str) -> None:
        ingested.append(rel_path)

    exit_code = run_job(config, ingest_func=fake_ingest)
    saved_state = load_state(config.state_file)

    assert exit_code == 0
    assert ingested == ["a.txt", "b.txt"]
    assert sorted(saved_state) == ["a.txt", "b.txt"]
    assert not (config.scan_dir / "a.txt").exists()
    assert not (config.scan_dir / "b.txt").exists()
    assert (config.ingested_dir / "a.txt").exists()
    assert (config.ingested_dir / "b.txt").exists()
    assert (config.scan_dir / "c.txt").exists()


def test_main_accepts_cli_override_for_max_files_per_run(
    tmp_path: Path, monkeypatch
) -> None:
    config = make_config(tmp_path)
    config.scan_dir.mkdir(parents=True)

    monkeypatch.setattr(
        "nas_scripts.jobs.ingest_crypto_documents.load_ingest_crypto_documents_config",
        lambda: config,
    )
    monkeypatch.setattr(
        "nas_scripts.jobs.ingest_crypto_documents.setup_script_logger",
        lambda script_name, log_file: DummyLogger(),
    )
    monkeypatch.setattr(
        "nas_scripts.jobs.ingest_crypto_documents.FileLock",
        lambda lock_path: nullcontext(),
    )

    monkeypatch.setattr(
        "nas_scripts.jobs.ingest_crypto_documents.run_job",
        lambda cfg, logger=None: cfg.max_files_per_run,
    )

    assert main(max_files_per_run=1) == 1


def test_run_job_skips_ingestion_when_max_files_per_run_is_zero(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    config = IngestCryptoDocumentsConfig(
        script_name=config.script_name,
        flowrag_base_url=config.flowrag_base_url,
        flowrag_api_key=config.flowrag_api_key,
        flowrag_dataset_id=config.flowrag_dataset_id,
        scan_dir=config.scan_dir,
        ingested_dir=config.ingested_dir,
        state_file=config.state_file,
        lock_file=config.lock_file,
        log_dir=config.log_dir,
        max_files_per_run=0,
        request_timeout=config.request_timeout,
    )
    config.scan_dir.mkdir(parents=True)
    (config.scan_dir / "a.txt").write_text("a", encoding="utf-8")

    ingested: list[str] = []

    exit_code = run_job(
        config,
        ingest_func=lambda path, rel_path: ingested.append(rel_path),
    )
    saved_state = load_state(config.state_file)

    assert exit_code == 0
    assert ingested == []
    assert saved_state == {}
    assert (config.scan_dir / "a.txt").exists()
    assert not (config.ingested_dir / "a.txt").exists()
