"""Configuration for the ingest_crypto_documents job.

This module applies a factory plus value-object pattern: the loader builds one
immutable config object from environment variables, and the job consumes that
object as its single source of truth.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SCAN_DIR = Path("/volume1/RAG/crypto")
DEFAULT_LOG_DIR = Path("/volume1/Temp/logs")
DEFAULT_FLOWRAG_BASE_URL = "http://10.10.10.10:18080"
DEFAULT_MAX_FILES_PER_RUN = 3
DEFAULT_CONFIG_FILE = Path("config/ingest_crypto_documents.env")
LEGACY_CONFIG_FILES = (Path("config/.env"), Path("config/.env.example"))


@dataclass(frozen=True)
class IngestCryptoDocumentsConfig:
    """Immutable value object for the crypto document ingestion workflow."""

    script_name: str
    flowrag_base_url: str
    flowrag_api_key: str | None
    flowrag_dataset_id: str | None
    scan_dir: Path
    state_file: Path
    lock_file: Path
    log_dir: Path
    max_files_per_run: int | None
    request_timeout: int = 300

    @property
    def dataset_documents_endpoint(self) -> str:
        """Return the FlowRAG document upload endpoint."""
        if self.flowrag_dataset_id is None:
            return f"{self.flowrag_base_url.rstrip('/')}/api/v1/datasets/<dataset_id>/documents"
        return f"{self.flowrag_base_url.rstrip('/')}/api/v1/datasets/{self.flowrag_dataset_id}/documents"

    @property
    def dataset_chunks_endpoint(self) -> str:
        """Return the FlowRAG chunk parsing endpoint."""
        if self.flowrag_dataset_id is None:
            return f"{self.flowrag_base_url.rstrip('/')}/api/v1/datasets/<dataset_id>/chunks"
        return f"{self.flowrag_base_url.rstrip('/')}/api/v1/datasets/{self.flowrag_dataset_id}/chunks"

    @property
    def log_file(self) -> Path:
        """Return the per-script log file path."""
        return self.log_dir / f"{self.script_name}.log"


def _parse_optional_int(value: str | None) -> int | None:
    """Parse an optional integer environment variable."""
    if value is None or not value.strip():
        return None
    return int(value)


def _first_env(*names: str) -> str | None:
    """Return the first populated environment variable from a list of names."""
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def _load_env_file(path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from a local config file."""
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip("\"'")
    return values


def _config_value(file_values: dict[str, str], name: str, default: str | None = None) -> str | None:
    """Resolve a value from process env, then local config, then a default."""
    env_value = _first_env(name)
    if env_value is not None:
        return env_value
    file_value = file_values.get(name)
    if file_value is not None and file_value.strip():
        return file_value.strip()
    return default


def load_ingest_crypto_documents_config() -> IngestCryptoDocumentsConfig:
    """Factory function that builds the ingestion runtime configuration."""
    config_file = Path(os.environ.get("INGEST_CONFIG_FILE", str(DEFAULT_CONFIG_FILE)))
    file_values = _load_env_file(config_file)
    if not file_values:
        for legacy_file in LEGACY_CONFIG_FILES:
            if legacy_file == config_file:
                continue
            file_values = _load_env_file(legacy_file)
            if file_values:
                break
    scan_dir = Path(_config_value(file_values, "SCAN_DIR", str(DEFAULT_SCAN_DIR)) or DEFAULT_SCAN_DIR)
    state_file = Path(
        _config_value(
            file_values,
            "STATE_FILE",
            str(scan_dir / ".flowrag_ingest_state.json"),
        )
        or scan_dir / ".flowrag_ingest_state.json"
    )
    lock_file = Path(
        _config_value(
            file_values,
            "LOCK_FILE",
            str(scan_dir / ".flowrag_ingest.lock"),
        )
        or scan_dir / ".flowrag_ingest.lock"
    )

    return IngestCryptoDocumentsConfig(
        script_name="ingest_crypto_documents",
        flowrag_base_url=_config_value(
            file_values,
            "FLOWRAG_BASE_URL",
            DEFAULT_FLOWRAG_BASE_URL,
        )
        or DEFAULT_FLOWRAG_BASE_URL,
        flowrag_api_key=_config_value(file_values, "FLOWRAG_API_KEY"),
        flowrag_dataset_id=_config_value(file_values, "FLOWRAG_DATASET_ID"),
        scan_dir=scan_dir,
        state_file=state_file,
        lock_file=lock_file,
        log_dir=Path(
            _config_value(file_values, "LOG_DIR", str(DEFAULT_LOG_DIR)) or DEFAULT_LOG_DIR
        ),
        max_files_per_run=_parse_optional_int(
            _config_value(file_values, "MAX_FILES_PER_RUN", str(DEFAULT_MAX_FILES_PER_RUN))
        ),
        request_timeout=int(
            _config_value(file_values, "REQUEST_TIMEOUT", "300") or "300"
        ),
    )
