"""Ingest crypto documents into FlowRAG.

This module is the workflow facade for the ingestion feature. It coordinates
file discovery, incremental state tracking, locking, and API calls while
keeping the CLI and tests insulated from those details. The optional
`ingest_func` parameter acts like a strategy hook for tests or alternate
ingestion behavior.
"""

from __future__ import annotations

from dataclasses import replace
import logging
import sys
from pathlib import Path
from typing import Callable

from nas_scripts.config.ingest_crypto_documents import (
    IngestCryptoDocumentsConfig,
    load_ingest_crypto_documents_config,
)
from nas_scripts.utils.filesystem import FileRecord, collect_files
from nas_scripts.utils.locking import AlreadyLockedError, FileLock
from nas_scripts.utils.logging import setup_script_logger
from nas_scripts.utils.onyx import ingest_file
from nas_scripts.utils.state import load_state, save_state

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


def _partition_files(
    current_files: dict[str, FileRecord],
    previous_state: dict[str, dict[str, object]],
) -> tuple[dict[str, dict[str, object]], list[tuple[str, FileRecord]]]:
    """Split files into the persisted state set and the ingest queue."""
    successful_state: dict[str, dict[str, object]] = {}
    changed_or_new: list[tuple[str, FileRecord]] = []

    for rel_path, record in current_files.items():
        previous = previous_state.get(rel_path)
        if previous is None or previous.get("sha256") != record.sha256:
            changed_or_new.append((rel_path, record))
        else:
            successful_state[rel_path] = record.to_state()

    return successful_state, changed_or_new


def run_job(
    config: IngestCryptoDocumentsConfig,
    *,
    ingest_func: Callable[[Path, str], None] | None = None,
    logger: logging.Logger | None = None,
) -> int:
    """Run the ingestion facade once and return an exit status."""
    logger = logger or logging.getLogger(f"nas_scripts.{config.script_name}")

    if config.flowrag_api_key is None:
        message = "Error: FLOWRAG_API_KEY is not set."
        print(message, file=sys.stderr)
        logger.error(message)
        return 1

    if config.flowrag_dataset_id is None:
        message = "Error: FLOWRAG_DATASET_ID is not set."
        print(message, file=sys.stderr)
        logger.error(message)
        return 1

    if not config.scan_dir.exists():
        message = f"Error: scan directory does not exist: {config.scan_dir}"
        print(message, file=sys.stderr)
        logger.error(message)
        return 1

    print(f"Scanning: {config.scan_dir}")
    print(f"FlowRAG upload endpoint: {config.dataset_documents_endpoint}")
    logger.info("Scanning: %s", config.scan_dir)
    logger.info("FlowRAG upload endpoint: %s", config.dataset_documents_endpoint)

    previous_state = load_state(config.state_file)
    current_files = collect_files(
        config.scan_dir,
        supported_extensions=SUPPORTED_EXTENSIONS,
        ignored_names={config.state_file.name, config.lock_file.name},
    )

    successful_state, changed_or_new = _partition_files(current_files, previous_state)

    if not changed_or_new:
        print("No new or changed files found.")
        logger.info("No new or changed files found.")
        return 0

    if config.max_files_per_run is not None:
        if config.max_files_per_run <= 0:
            print("MAX_FILES_PER_RUN is 0 or less. Nothing will be ingested this run.")
            logger.info(
                "MAX_FILES_PER_RUN is %s. Nothing will be ingested this run.",
                config.max_files_per_run,
            )
            save_state(config.state_file, successful_state)
            return 0
        if len(changed_or_new) > config.max_files_per_run:
            print(f"Limiting this run to {config.max_files_per_run} changed file(s).")
            logger.info(
                "Limiting this run to %s changed file(s) out of %s.",
                config.max_files_per_run,
                len(changed_or_new),
            )
            changed_or_new = changed_or_new[: config.max_files_per_run]

    ingest = ingest_func or (
        lambda path, rel_path: ingest_file(path, rel_path, config=config)
    )

    for rel_path, record in changed_or_new:
        print(f"NEW/CHANGED: {rel_path}")
        logger.info("NEW/CHANGED: %s", rel_path)
        try:
            ingest(Path(record.path), rel_path)
            successful_state[rel_path] = record.to_state()
            print(f"Ingested: {rel_path}")
            logger.info("Ingested: %s", rel_path)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR ingesting {rel_path}: {exc}", file=sys.stderr)
            logger.exception("ERROR ingesting %s: %s", rel_path, exc)

    save_state(config.state_file, successful_state)
    print("Done.")
    logger.info("Done.")
    return 0


def main(*, max_files_per_run: int | None = None) -> int:
    """Compose the ingestion workflow from config, logging, and locking."""
    config = load_ingest_crypto_documents_config()
    if max_files_per_run is not None:
        config = replace(config, max_files_per_run=max_files_per_run)
    logger = setup_script_logger(config.script_name, config.log_file)
    logger.info("Starting %s", config.script_name)
    if config.flowrag_dataset_id is None or not config.scan_dir.exists():
        return run_job(config, logger=logger)
    try:
        with FileLock(config.lock_file):
            return run_job(config, logger=logger)
    except AlreadyLockedError:
        print("Another instance is already running. Exiting.")
        logger.warning("Another instance is already running. Exiting.")
        return 0
