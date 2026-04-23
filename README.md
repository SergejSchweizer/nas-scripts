# NAS Scripts

Python automation for NAS workflows.

This repository contains three small NAS jobs:

- `ingest-crypto-documents`: ingest crypto RAG documents into FlowRAG
- `sync-media-library`: mirror media into a library and filter non-English streams
- `organize-temp-media`: sort temporary photos and videos into dated folders

## Table Of Contents

- [Quick Start](#quick-start)
- [Project Overview](#project-overview)
- [Jobs](#jobs)
- [Configuration](#configuration)
- [Execution](#execution)
- [System Dependencies](#system-dependencies)
- [Testing](#testing)
- [Development Rules](#development-rules)
- [Troubleshooting](#troubleshooting)

## Quick Start

Install dependencies and run the test suite:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.venv/bin/pytest -q
```

Run the CLI:

```powershell
python -m nas_scripts
```

## Project Overview

The codebase is organized by responsibility:

| Path | Responsibility |
| --- | --- |
| `src/nas_scripts/cli.py` | Top-level command parsing and dispatch |
| `src/nas_scripts/__main__.py` | `python -m nas_scripts` entrypoint |
| `src/nas_scripts/config/` | Environment-driven runtime config |
| `src/nas_scripts/jobs/` | Job orchestration and workflow logic |
| `src/nas_scripts/utils/` | Shared helpers for files, logging, locking, media, text, and state |
| `scripts/` | Thin direct-execution wrappers |
| `tests/unit/` | Fast unit tests |
| `tests/integration/` | Integration tests, including live FlowRAG coverage |

Each job follows the same general lifecycle:

1. Load config.
2. Set up a per-script logger.
3. Acquire a file lock.
4. Run the workflow.
5. Persist state if needed.
6. Release the lock.

## Jobs

### `ingest-crypto-documents`

Purpose: ingest supported crypto documents into FlowRAG from a configured scan directory.

Behavior:

| Item | Details |
| --- | --- |
| Input | `.pdf`, `.txt`, and `.md` files under `SCAN_DIR` |
| State | Tracks file path, size, mtime, and SHA-256 hash |
| Output | Uploads documents to FlowRAG and triggers parsing |
| Limits | Supports `MAX_FILES_PER_RUN` |
| Safety | Uses a lock file to prevent overlapping runs |

Entry points:

```powershell
python -m nas_scripts ingest-crypto-documents
python -m nas_scripts ingest-crypto-documents --max-files-per-run 1
python scripts/ingest_crypto_documents.py
```

Important detail:

- The loader reads `config/ingest_crypto_documents.env` by default.
- You can override that file with `INGEST_CONFIG_FILE`.
- Relative paths in that config are resolved against the repository root.
- `FLOWRAG_BASE_URL`, `FLOWRAG_DATASET_ID`, and `FLOWRAG_API_KEY` are required at run time.

### `sync-media-library`

Purpose: sync media from a source tree into a destination library, prune stale files, and keep only English audio and subtitle streams.

Behavior:

| Item | Details |
| --- | --- |
| Input | Media files in `SOURCE_DIR` |
| Output | Copied media in `DEST_DIR` |
| Cleanup | Removes stale files and empty directories |
| Stream filtering | Uses `ffprobe` and `ffmpeg` to remove one non-English audio or subtitle track per run |
| Cache | Stores verification state in a checksum-based JSON file |
| Safety | Uses a lock file to prevent overlapping runs |

Entry points:

```powershell
python -m nas_scripts sync-media-library
python scripts/sync_media_library.py
```

Important detail:

- A file may need multiple runs before all non-English audio/subtitle tracks are removed.
- Already verified files are skipped on later runs unless the policy version changes or the file changes.

### `organize-temp-media`

Purpose: sort temporary photos and videos into dated folders.

Behavior:

| Item | Details |
| --- | --- |
| Input | Matching files in `TEMP_DIR` |
| Output | `YYYY-MM/raw`, `YYYY-MM/img`, or `YYYY-MM/vid` |
| Default scan mode | Top-level files only |
| Optional scan mode | `--reorganize-existing` scans nested legacy folders too |
| Safety | Uses a lock file to prevent overlapping runs |

Entry points:

```powershell
python -m nas_scripts organize-temp-media
python -m nas_scripts organize-temp-media --reorganize-existing
python scripts/organize_temp_media.py
```

## Operational Behavior

Locking:

- Each job uses a dedicated lock file.
- If another instance is already running, the new run exits cleanly.

Logging:

- Each job writes to its own log file under `LOG_DIR`.
- Logs use a shared format with timestamp, level, script name, and process id.
- If the configured log directory cannot be created, the logger falls back to a local `./logs/` directory when possible.

State:

- `ingest-crypto-documents` stores incremental ingestion state in JSON.
- `sync-media-library` stores checksum-based verification state in JSON.
- `organize-temp-media` does not keep a persistent state file.

## Configuration

### Ingest

Configuration source:

- `config/ingest_crypto_documents.env`
- `INGEST_CONFIG_FILE` can point to an alternate file
- Process environment variables override file values

Required settings:

- `FLOWRAG_BASE_URL`
- `SCAN_DIR`
- `INGESTED_DIR`
- `STATE_FILE`
- `LOCK_FILE`
- `LOG_DIR`
- `MAX_FILES_PER_RUN`
- `REQUEST_TIMEOUT`

Runtime-required settings:

- `FLOWRAG_DATASET_ID`
- `FLOWRAG_API_KEY`

### Media Sync

Environment variables:

- `SOURCE_DIR`
- `DEST_DIR`
- `LOCK_FILE`
- `LOG_DIR`
- `STATE_FILE`
- `MEDIA_EXTENSIONS`
- `FFMPEG_THREADS`

Defaults:

- `SOURCE_DIR`: `/volume1/Torrents`
- `DEST_DIR`: `/volume1/Media`
- `LOCK_FILE`: `/tmp/media.lock`
- `LOG_DIR`: `/volume1/Temp/logs`
- `STATE_FILE`: `/volume1/Temp/logs/sync_media_library.state.json`

### Temp Media Organizer

Environment variables:

- `TEMP_DIR`
- `LOCK_FILE`
- `LOG_DIR`
- `REORGANIZE_EXISTING`
- `FILE_EXTENSIONS`
- `RAW_EXTENSIONS`
- `VIDEO_EXTENSIONS`
- `OWNER_USER`
- `OWNER_GROUP`

Defaults:

- `TEMP_DIR`: `/volume1/Temp/Fotos`
- `LOCK_FILE`: `/tmp/organize_temp_media.lock`
- `LOG_DIR`: `/volume1/Temp/logs`

## Execution

### Direct CLI

```powershell
python -m nas_scripts ingest-crypto-documents
python -m nas_scripts sync-media-library
python -m nas_scripts organize-temp-media
```

### Direct Scripts

```powershell
python scripts/ingest_crypto_documents.py
python scripts/sync_media_library.py
python scripts/organize_temp_media.py
```

### Cron Examples

Ingest:

```bash
0 * * * * cd /path/to/nas-scripts && /path/to/nas-scripts/.venv/bin/python -m nas_scripts ingest-crypto-documents
```

Media sync:

```bash
*/5 * * * * cd /path/to/nas-scripts && /path/to/nas-scripts/.venv/bin/python -m nas_scripts sync-media-library
```

Temp organizer:

```bash
15 23 * * * cd /path/to/nas-scripts && /path/to/nas-scripts/.venv/bin/python -m nas_scripts organize-temp-media
```

## System Dependencies

Python dependencies live in `requirements.txt` and `pyproject.toml`.

The media sync job also needs:

- `ffmpeg`
- `ffprobe`

On Debian and Ubuntu systems:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

## Testing

Run all tests:

```powershell
.venv/bin/pytest -q
```

Run only the unit suites:

```powershell
.venv/bin/pytest -q tests/unit
```

Run the live FlowRAG integration test:

```powershell
$env:RUN_LIVE_FLOWRAG_TESTS="1"
$env:FLOWRAG_BASE_URL="http://your-flowrag-host:18080"
$env:FLOWRAG_API_KEY="your-api-key"
$env:FLOWRAG_DATASET_ID="your-dataset-id"
.venv/bin/pytest -q tests/integration -m "integration and live"
```

The repository currently includes unit coverage for:

- CLI dispatch
- config loading
- file discovery and incremental state
- FlowRAG upload and parsing helpers
- media copy and stream filtering
- temp-file organization and destination routing
- logger setup and file locking

## Development Rules

- Keep job-specific behavior in `src/nas_scripts/jobs/`.
- Keep reusable logic in `src/nas_scripts/utils/`.
- Keep `scripts/` thin.
- Keep jobs isolated from each other.
- Use environment variables or local config files for secrets.
- Update or add tests when behavior changes.
- Keep log output expressive and consistent.

## Troubleshooting

If a job exits immediately:

- Check the lock file for a stale or active run.
- Verify the configured directories exist.
- Confirm the log directory is writable.

If media sync fails:

- Confirm `ffmpeg` and `ffprobe` are installed and on `PATH`.
- Check whether the file has more than one non-English track and needs another run.

If ingest fails:

- Confirm `FLOWRAG_BASE_URL`, `FLOWRAG_DATASET_ID`, and `FLOWRAG_API_KEY` are set correctly.
- Confirm the scan directory exists and contains supported files.
- Check the per-script log file for the HTTP response details.

If live tests skip:

- Set `RUN_LIVE_FLOWRAG_TESTS=1`.
- Provide the FlowRAG environment variables required by the integration test.
