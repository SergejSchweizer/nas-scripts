"""Configuration for the ingest_crypto_documents job."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SCAN_DIR = Path("/volume1/RAG/crypto")
DEFAULT_LOG_DIR = Path("/volume1/Temp/logs")
DEFAULT_MAX_FILES_PER_RUN = 3


@dataclass(frozen=True)
class IngestCryptoDocumentsConfig:
    script_name: str
    onyx_base_url: str
    onyx_api_key: str | None
    onyx_cc_pair_id: int | None
    scan_dir: Path
    state_file: Path
    lock_file: Path
    log_dir: Path
    max_files_per_run: int | None
    request_timeout: int = 300

    @property
    def ingest_endpoint(self) -> str:
        return f"{self.onyx_base_url.rstrip('/')}/api/onyx-api/ingestion"

    @property
    def log_file(self) -> Path:
        return self.log_dir / f"{self.script_name}.log"


def _parse_optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)


def load_ingest_crypto_documents_config() -> IngestCryptoDocumentsConfig:
    scan_dir = Path(os.environ.get("SCAN_DIR", str(DEFAULT_SCAN_DIR)))
    state_file = Path(
        os.environ.get("STATE_FILE", str(scan_dir / ".onyx_ingest_state.json"))
    )
    lock_file = Path(os.environ.get("LOCK_FILE", str(scan_dir / ".onyx_ingest.lock")))

    return IngestCryptoDocumentsConfig(
        script_name="ingest_crypto_documents",
        onyx_base_url=os.environ.get("ONYX_BASE_URL", "http://10.10.10.10:3000"),
        onyx_api_key=os.environ.get("ONYX_API_KEY") or None,
        onyx_cc_pair_id=_parse_optional_int(os.environ.get("ONYX_CC_PAIR_ID")),
        scan_dir=scan_dir,
        state_file=state_file,
        lock_file=lock_file,
        log_dir=Path(os.environ.get("LOG_DIR", str(DEFAULT_LOG_DIR))),
        max_files_per_run=_parse_optional_int(
            os.environ.get("MAX_FILES_PER_RUN", str(DEFAULT_MAX_FILES_PER_RUN))
        ),
        request_timeout=int(os.environ.get("REQUEST_TIMEOUT", "300")),
    )
