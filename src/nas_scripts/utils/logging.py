"""Logging helpers for NAS jobs."""

from __future__ import annotations

import logging
from pathlib import Path


LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | script=%(name)s | pid=%(process)d | %(message)s"
)
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_script_logger(script_name: str, log_file: Path) -> logging.Logger:
    logger = logging.getLogger(f"nas_scripts.{script_name}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    candidate_files = [log_file, Path.cwd() / "logs" / log_file.name]
    for candidate in candidate_files:
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(candidate, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            if candidate != log_file:
                logger.warning(
                    "Unable to open log file: %s. Falling back to %s",
                    log_file,
                    candidate,
                )
            break
        except OSError:
            continue
    else:
        logger.error("Unable to open any log file for %s", log_file)

    return logger
