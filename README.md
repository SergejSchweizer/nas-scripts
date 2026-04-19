# NAS Scripts

Python automation scripts for a UGREEN NASync DXP4800 Plus.

## Table of Contents

- [Purpose](#purpose)
- [Project Layout](#project-layout)
- [Setup](#setup)
- [Run](#run)
- [System Dependencies](#system-dependencies)
- [Dependency Management](#dependency-management)
- [Development Rules](#development-rules)
- [OOP and Design](#oop-and-design)
- [Scripts](#scripts)
  - [ingest_crypto_documents](#ingest_crypto_documents)
  - [sync_media_library](#sync_media_library)
  - [organize_temp_media](#organize_temp_media)
- [Current Status](#current-status)

## Purpose

This repository is the Python home for NAS jobs such as ingestion, sync, backup, and media automation.

## Code Map

The code is organized so each concern has one clear home:

- `src/nas_scripts/cli.py`: command-line parsing and job dispatch
- `src/nas_scripts/__main__.py`: `python -m nas_scripts` entrypoint
- `src/nas_scripts/config/`: environment-driven configuration objects
- `src/nas_scripts/jobs/`: the actual job workflows
- `src/nas_scripts/utils/`: reusable helpers for logging, locking, files, media, text, and API calls
- `scripts/`: thin wrappers for users who prefer direct script execution

Most jobs follow the same lifecycle: load config, create a per-script logger, take a lock, do the work, and write a clear completion or failure message.

## Design Patterns

The code deliberately uses a few simple patterns instead of a lot of framework
abstraction:

- Command dispatcher: `src/nas_scripts/cli.py` routes a CLI command to the matching job.
- Factory plus value object: each `config/*.py` module builds one immutable config object from environment variables.
- Facade: each `jobs/*.py` module presents one job-level workflow and hides the helper calls underneath it.
- Adapter: `src/nas_scripts/utils/onyx.py` translates local files into the FlowRAG API request shape.
- Strategy hook: `ingest_crypto_documents.run_job(..., ingest_func=...)` lets tests or alternate callers swap the ingestion action.
- Persistence layer: `src/nas_scripts/utils/state.py` owns the incremental ingestion state format.
- Concurrency control: `src/nas_scripts/utils/locking.py` keeps overlapping cron runs from stepping on each other.

## Project Layout

- `src/nas_scripts/`: main Python package
- `src/nas_scripts/jobs/`: job modules and task entrypoints
- `src/nas_scripts/utils/`: shared helpers for filesystem, APIs, parsing, logging, and common logic
- `src/nas_scripts/config/`: one dedicated config module per script
- `scripts/`: thin wrappers that call package code
- `tests/unit/`: fast unit tests
- `tests/integration/`: integration-level tests
- `tests/unit/<script_name>/`: unit tests grouped per script
- `tests/integration/<script_name>/`: integration tests grouped per script
- `tests/data/<script_name>/`: local test fixtures grouped per script and excluded from Git
- `config/ingest_crypto_documents.env.example`: local configuration template
- `config/ingest_crypto_documents.env`: local runtime configuration file, excluded from git

## Setup

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
pytest
```

Run live integration tests only:

```powershell
$env:RUN_LIVE_FLOWRAG_TESTS="1"
$env:FLOWRAG_BASE_URL="http://your-flowrag-host:18080"
$env:FLOWRAG_API_KEY="your-api-key"
$env:FLOWRAG_DATASET_ID="your-dataset-id"
python -m pytest tests/integration -m "integration and live"
```

## System Dependencies

Python packages are installed from `requirements.txt`, but some scripts also need OS-level tools.

On Debian/Ubuntu-style systems with `apt`, install:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

This provides both:

- `ffmpeg`
- `ffprobe`

These tools are required by `sync_media_library`.

## Run

Base CLI:

```powershell
python -m nas_scripts
```

Crypto RAG ingestion:

```powershell
python -m nas_scripts ingest-crypto-documents
python -m nas_scripts ingest-crypto-documents --max-files-per-run 1
python scripts/ingest_crypto_documents.py --max-files-per-run 1
python scripts/ingest_crypto_documents.py
```

The ingest job uploads into the FlowRAG dataset you point `FLOWRAG_DATASET_ID`
at.

The ingest job reads its runtime settings from `config/ingest_crypto_documents.env` by default. You can
override that path with `INGEST_CONFIG_FILE` if needed.

Media library sync:

```powershell
python -m nas_scripts sync-media-library
python scripts/sync_media_library.py
```

Sort temp images:

```powershell
python -m nas_scripts organize-temp-media
python scripts/organize_temp_media.py
```

## Dependency Management

- Keep Python dependencies in `pyproject.toml`.
- Use `requirements.txt` as the install entrypoint for local development.
- Keep `requirements.txt` aligned with `pyproject.toml` after dependency changes.

## Development Rules

- Put job-specific behavior in `src/nas_scripts/jobs/`.
- Put reusable logic in `src/nas_scripts/utils/`.
- Keep scripts in `scripts/` thin.
- Keep each script functionally isolated from the others.
  A job module must not call another job module, import another script's config module, or absorb another script's workflow.
- Move code into `src/nas_scripts/utils/` only when it is truly generic.
  If logic is specific to one script's domain, keep it owned by that script's job or domain utility module.
- Ensure every script writes to its own log file through the shared logging helper.
- Script logs rotate weekly and keep the current file plus the last 3 weekly archives.
- Keep log output expressive and consistent.
  Log lines should include timestamp, level, script identity, process id, and a meaningful action-oriented message.
- Add or update tests for behavior changes.
- Keep secrets out of source control and use environment variables or local `.env` files.
## OOP and Design

This project uses light OOP rather than deep class hierarchies.

Why:

- NAS automation scripts usually need clarity, reliability, and easy debugging more than heavy abstraction.
- Most behavior here is workflow-oriented, so small focused modules and simple data objects are easier to maintain.
- Classes are used when state or lifecycle management is clearer as an object.

Design rules for scripts:

- Each script gets its own job module in `src/nas_scripts/jobs/`.
- Each script gets its own config module in `src/nas_scripts/config/`.
- Shared behavior belongs in `src/nas_scripts/utils/`.
- Entry scripts in `scripts/` stay thin and only call package code.
- Prefer small composable functions for workflow steps.
- Use dataclasses for structured configuration and immutable records.
- Use classes only when they improve lifecycle control or encapsulate stateful behavior.

Patterns used in this repo:

- `Dataclass`: explicit typed config and record objects
- `Facade`: each job module orchestrates lower-level helpers
- `Single Responsibility`: scanning, extraction, locking, state, logging, and API ingestion are split into focused modules
- `Dependency Injection`: `run_job()` accepts injectable behavior for testability
- `Wrapper/Adapter`: CLI and script entrypoints stay thin
- `Context Manager`: `FileLock` manages acquire/release safely

General hierarchy:

```text
Script
|- Config module
|  |- ScriptConfig dataclass
|- Job module
|  |- main()
|  |- run_job()
|- Utility modules
|  |- immutable data objects
|  |- stateful helper classes when needed
|  |- pure helper functions
|- Thin script entrypoint
```

## Scripts

### `ingest_crypto_documents`

Purpose:
Ingest supported crypto RAG documents into FlowRAG from a configured scan directory.

What this script does:

- scans the configured crypto document folder for supported files
- compares current files against the saved ingestion state
- ingests only new or changed documents into FlowRAG
- writes progress to a per-script log file
- prevents overlapping runs with a lock file
- limits each run to a configurable number of documents

Entrypoints:
- `python -m nas_scripts ingest-crypto-documents`
- `python scripts/ingest_crypto_documents.py`

Modules:
- `src/nas_scripts/jobs/ingest_crypto_documents.py`
- `src/nas_scripts/config/ingest_crypto_documents.py`
- `src/nas_scripts/utils/filesystem.py`
- `src/nas_scripts/utils/locking.py`
- `src/nas_scripts/utils/logging.py`
- `src/nas_scripts/utils/onyx.py`
- `src/nas_scripts/utils/state.py`
- `src/nas_scripts/utils/text.py`

Config:

Required environment variables:
- `FLOWRAG_DATASET_ID`

Optional environment variables:
- `FLOWRAG_BASE_URL`
- `FLOWRAG_API_KEY`
- `SCAN_DIR`
- `STATE_FILE`
- `LOCK_FILE`
- `LOG_DIR`
- `MAX_FILES_PER_RUN`
- `REQUEST_TIMEOUT`
- `INGEST_CONFIG_FILE`

Behavior:

- Single-instance protection is enforced through `LOCK_FILE`.
- If a second run starts while another instance is active, it exits immediately.
- Logs are written per script.
  Default log path: `/volume1/Temp/logs/ingest_crypto_documents.log`
- `MAX_FILES_PER_RUN` limits how many changed files are ingested in one run.
  Default: `3`
  `0` or lower means skip ingestion for that run.

Program flow:

```text
start
  |
  v
load config
  |
  v
setup logger
  |
  v
validate required settings and scan path
  |
  v
acquire lock
  |
  v
scan supported files
  |
  v
load previous state
  |
  v
detect new or changed files
  |
  +--> no changes --> log "nothing to do" --> exit
  |
  v
apply MAX_FILES_PER_RUN limit
  |
  v
extract text and build payload per file
  |
  v
send document to FlowRAG document upload API
  |
  v
save successful state
  |
  v
release lock
  |
  v
end
```

Cron job:

- Example:
  `0 * * * * export LOG_DIR=/volume1/Temp/logs MAX_FILES_PER_RUN=3 && cd /path/to/nas-scripts && /path/to/nas-scripts/.venv/bin/python -m nas_scripts ingest-crypto-documents`
- Use the project virtual environment Python, not the system default interpreter.
- Set required environment variables in the cron environment or source them before the command runs.
- Avoid overlapping schedules even though the script has locking.

Design notes:

- Uses `IngestCryptoDocumentsConfig` as the top configuration object for stable runtime settings.
- Uses `FileRecord` as a dataclass instead of loose dictionaries.
- Uses `FileLock` as a stateful class because lock lifecycle is clearer with `__enter__` and `__exit__`.
- Keeps orchestration in the job module and low-level details in utilities.
- Keeps logger setup separate from core workflow so per-script logging stays reusable.
- Uses dependency injection in `run_job(..., ingest_func=...)` so ingestion can be tested without real HTTP requests.

Applied hierarchy:

```text
ingest_crypto_documents
|- Config
|  |- IngestCryptoDocumentsConfig
|     file: src/nas_scripts/config/ingest_crypto_documents.py
|- Job orchestration
|  |- main()
|  |- run_job()
|  |- _partition_files()
|     file: src/nas_scripts/jobs/ingest_crypto_documents.py
|- Utility layer
|  |- FileRecord / collect_files() / sha256_file()
|     file: src/nas_scripts/utils/filesystem.py
|  |- FileLock / AlreadyLockedError
|     file: src/nas_scripts/utils/locking.py
|  |- setup_script_logger()
|     file: src/nas_scripts/utils/logging.py
|  |- build_payload() / build_headers() / ingest_file()
|     file: src/nas_scripts/utils/onyx.py
|  |- load_state() / save_state()
|     file: src/nas_scripts/utils/state.py
|  |- extract_text() / extract_pdf_text()
|     file: src/nas_scripts/utils/text.py
|- Entrypoints
|  |- python -m nas_scripts ingest-crypto-documents
|  |- python scripts/ingest_crypto_documents.py
```

Testing:

- Unit tests cover CLI smoke behavior for `python -m nas_scripts`.
- Unit tests cover supported file discovery and filtering.
- Unit tests cover change detection between current files and saved state.
- Unit tests cover payload and request header construction.
- Unit tests cover job execution flow and state persistence.
- Unit tests cover validation failure when `FLOWRAG_DATASET_ID` is missing.
- Unit tests cover single-instance lock behavior.
- Unit tests cover per-script log file creation and job log output.
- Unit tests cover max-files-per-run throttling and zero-file runs.
- Live integration test `tests/integration/ingest_crypto_documents/test_live.py` uses `tests/data/ingest_crypto_documents/09_Dergileva_Dobrynskaja_Gurov_Sokolova.pdf`.
- The live test confirms the upload/parsing flow against the FlowRAG API and verifies local state updates.

Current testing gaps:

- concurrent lock behavior across multiple processes
- retry behavior and partial-failure recovery
- end-to-end execution on the real NAS scheduler
- assertions against downstream indexed content inside FlowRAG after ingestion

### `sync_media_library`

Purpose:
Sync video files from the configured source folder into the media library, remove stale destination files, clean empty directories, and keep only English audio and subtitle tracks in matching media files.

What this script does:

- finds supported media files in the configured source folder
- copies new files into the media destination while preserving metadata
- deletes destination files that no longer exist in the source
- removes empty directories left after cleanup
- inspects media streams with `ffprobe`
- rewrites media files with `ffmpeg` so only English audio and English subtitle streams remain
- stores a checksum cache so files that were already verified can be skipped on later runs
- cleans up leftover temporary media files
- writes progress to a per-script log file
- prevents overlapping runs with a lock file

Entrypoints:
- `python -m nas_scripts sync-media-library`
- `python scripts/sync_media_library.py`

Modules:
- `src/nas_scripts/jobs/sync_media_library.py`
- `src/nas_scripts/config/sync_media_library.py`
- `src/nas_scripts/utils/media.py`
- `src/nas_scripts/utils/locking.py`
- `src/nas_scripts/utils/logging.py`

Config:

Optional environment variables:
- `SOURCE_DIR`
- `DEST_DIR`
- `LOCK_FILE`
- `LOG_DIR`
- `MEDIA_EXTENSIONS`
- `FFMPEG_THREADS`

Behavior:

- Copies new media files from `SOURCE_DIR` to `DEST_DIR` while preserving metadata.
- Removes destination files that no longer exist in the source tree.
- Deletes empty directories left behind in the destination tree.
- Uses `ffprobe` to inspect streams and `ffmpeg` to keep only English audio and subtitle streams.
- Verifies the rewritten file still contains only English audio and subtitle streams before replacing the original.
- Cleans up leftover `temp.*` media files after processing.
- Uses single-instance locking through `LOCK_FILE`.
- Writes logs per script.
  Default log path: `/volume1/Temp/logs/sync_media_library.log`

Program flow:

```text
start
  |
  v
load config
  |
  v
setup logger
  |
  v
validate source and destination paths
  |
  v
acquire lock
  |
  v
scan source media files
  |
  v
scan destination files
  |
  v
copy new files to media library
  |
  v
delete stale destination files
  |
  v
remove empty directories
  |
  v
scan destination media files
  |
  v
probe streams with ffprobe
  |
  +--> only English audio/subtitles already present --> keep file
  |
  v
rewrite file keeping only English audio/subtitle streams
  |
  v
remove leftover temp.* files
  |
  v
release lock
  |
  v
end
```

Cron job:

- Example:
  `*/5 * * * * export LOG_DIR=/volume1/Temp/logs && cd /path/to/nas-scripts && /path/to/nas-scripts/.venv/bin/python -m nas_scripts sync-media-library`
- On apt-based Linux systems, install them with `sudo apt install -y ffmpeg`.
- `ffprobe` and `ffmpeg` must be available on the NAS `PATH`.
- Use the project virtual environment Python, not the system default interpreter.
- Avoid overlapping schedules even though the script has locking.

Design notes:

- Keeps sync orchestration and media-stream cleanup in one job because the legacy behavior was operationally coupled.
- Uses a dedicated config object so path and tool settings stay script-specific.
- Pushes media inspection and file operations into `src/nas_scripts/utils/media.py` so the job module stays readable.
- Uses subprocess-based helpers for `ffprobe` and `ffmpeg` to preserve the original shell-script behavior closely.

Applied hierarchy:

```text
sync_media_library
|- Config
|  |- SyncMediaLibraryConfig
|     file: src/nas_scripts/config/sync_media_library.py
|- Job orchestration
|  |- main()
|  |- run_job()
|  |- sync_media_files()
|  |- keep_only_english_audio_and_subtitles()
|     file: src/nas_scripts/jobs/sync_media_library.py
|- Utility layer
|  |- MediaStream
|  |- collect_relative_media_files()
|  |- collect_relative_files()
|  |- probe_streams()
|  |- find_non_english_audio_subtitle_streams()
|  |- build_stream_map_args()
|  |- filter_to_english_audio_and_subtitles()
|  |- remove_empty_directories()
|  |- remove_leftover_temp_files()
|     file: src/nas_scripts/utils/media.py
|  |- FileLock / AlreadyLockedError
|     file: src/nas_scripts/utils/locking.py
|  |- setup_script_logger()
|     file: src/nas_scripts/utils/logging.py
|- Entrypoints
|  |- python -m nas_scripts sync-media-library
|  |- python scripts/sync_media_library.py
```

Testing:

- Unit tests cover media file discovery and relative-path collection.
- Unit tests cover discovery against the real media fixture filenames in `tests/data/sync_media_library/`.
- Unit tests cover stale-file deletion and copy behavior during sync.
- Unit tests cover sync behavior against the real media fixture set without copying the large media payloads.
- Unit tests cover non-English audio/subtitle detection.
- Unit tests cover source/destination validation failures.
- Unit tests cover English-only stream filtering orchestration with mocked media-tool calls.
- Unit tests opportunistically probe a real local media fixture with `ffprobe` when the tool is available.

Current testing gaps:

- live execution with real `ffprobe` and `ffmpeg`
- NAS filesystem permission edge cases
- large-library performance behavior

### `organize_temp_media`

Purpose:
Sort temporary image and media files from the temp folder into dated `YYYY-MM` folders, and place raw files into `raw/`, images into `img/`, and videos into `vid/`.

What this script does:

- scans the configured temp folder for matching image and media extensions
- derives a `YYYY-MM` target folder from each file timestamp
- moves raw files into `YYYY-MM/raw/`
- moves images into `YYYY-MM/img/`
- moves videos into `YYYY-MM/vid/`
- preserves timestamps on the moved file and destination folder
- attempts to apply configured ownership when the platform supports it
- writes progress to a per-script log file
- prevents overlapping runs with a lock file
- can optionally reorganize files already stored in legacy month folders when `--reorganize-existing` is enabled

Entrypoints:
- `python -m nas_scripts organize-temp-media`
- `python -m nas_scripts organize-temp-media --reorganize-existing`
- `python scripts/organize_temp_media.py`

Modules:
- `src/nas_scripts/jobs/organize_temp_media.py`
- `src/nas_scripts/config/organize_temp_media.py`
- `src/nas_scripts/utils/images.py`
- `src/nas_scripts/utils/locking.py`
- `src/nas_scripts/utils/logging.py`

Config:

Optional environment variables:
- `TEMP_DIR`
- `LOCK_FILE`
- `LOG_DIR`
- `REORGANIZE_EXISTING`
- `FILE_EXTENSIONS`
- `RAW_EXTENSIONS`
- `VIDEO_EXTENSIONS`
- `OWNER_USER`
- `OWNER_GROUP`

Behavior:

- Uses file timestamps to derive the `YYYY-MM` target folder.
- Files with raw extensions go into a `raw/` subfolder.
- Files with video extensions go into a `vid/` subfolder.
- Files with other matching extensions go into an `img/` subfolder.
- By default, only files at the top level of `TEMP_DIR` are organized.
- When `REORGANIZE_EXISTING=1` or `--reorganize-existing` is used, nested legacy folders are scanned too and files are moved into the new folder layout.
- Writes logs per script.
  Default log path: `/volume1/Temp/logs/organize_temp_media.log`
- If the configured NAS log directory cannot be created, it falls back to `./logs/organize_temp_media.log` and warns on the console.
- Uses single-instance locking through `LOCK_FILE`.

Program flow:

```text
start
  |
  v
load config
  |
  v
setup logger
  |
  v
validate temp path
  |
  v
acquire lock
  |
  v
scan matching files
  |
  v
build YYYY-MM target folder
  |
  +--> raw extension --> append /raw
  |
  +--> video extension --> append /vid
  |
  +--> otherwise --> append /img
  |
  v
create destination folder
  |
  v
move file
  |
  v
preserve timestamps
  |
  v
apply ownership when supported
  |
  v
release lock
  |
  v
end
```

Cron job:

- Example:
  `15 23 * * * export LOG_DIR=/volume1/Temp/logs && cd /path/to/nas-scripts && /path/to/nas-scripts/.venv/bin/python -m nas_scripts organize-temp-media`
- Use the project virtual environment Python, not the system default interpreter.
- Avoid overlapping schedules even though the script has locking.

Design notes:

- Uses a dedicated config object so extension lists and ownership settings stay script-specific.
- Keeps timestamp/folder logic in `src/nas_scripts/utils/images.py` so the job module stays simple.
- Keeps lock and logging behavior aligned with the other scripts in the repo.

Applied hierarchy:

```text
organize_temp_media
|- Config
|  |- OrganizeTempMediaConfig
|     file: src/nas_scripts/config/organize_temp_media.py
|- Job orchestration
|  |- main()
|  |- organize_files()
|     file: src/nas_scripts/jobs/organize_temp_media.py
|- Utility layer
|  |- collect_matching_files()
|  |- build_destination_dir()
|  |- month_folder_name()
|  |- set_path_timestamp_from_source()
|  |- apply_ownership()
|     file: src/nas_scripts/utils/images.py
|  |- FileLock / AlreadyLockedError
|     file: src/nas_scripts/utils/locking.py
|  |- setup_script_logger()
|     file: src/nas_scripts/utils/logging.py
|- Entrypoints
|  |- python -m nas_scripts organize-temp-media
|  |- python scripts/organize_temp_media.py
```

Testing:

- Unit tests cover extension filtering.
- Unit tests cover destination-folder building for regular, raw, and video files.
- Unit tests cover moving files into dated folders with `raw/img/vid` routing.
- Unit tests cover overwrite behavior and the opt-in reorganization mode.
- Unit tests cover per-script log output.

Current testing gaps:

- ownership changes on the real NAS
- edge cases around duplicate filenames in the same target month

## Current Status

- Local Python 3.11 virtual environment is set up in `.venv/`.
- Project packaging is configured through `pyproject.toml`.
- Runtime dependencies currently include `requests` and `pypdf`.
- `ingest_crypto_documents` has been migrated into the Python package structure.
- The current automated test suite is passing.
