"""State file helpers.

This module acts as the persistence layer for the incremental ingestion flow:
it stores and restores the compact JSON state that tells the job whether a
document is new, changed, or already processed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_state(state_file: Path) -> dict[str, dict[str, Any]]:
    """Load the persisted state map for the incremental ingestion flow."""
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state_file: Path, state: dict[str, dict[str, Any]]) -> None:
    """Persist the incremental ingestion state atomically."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = state_file.with_suffix(f"{state_file.suffix}.tmp")
    tmp_file.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    tmp_file.replace(state_file)
