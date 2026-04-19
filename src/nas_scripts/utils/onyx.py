"""Onyx ingestion helpers.

This module acts as the adapter layer for the external Onyx API. It translates
local file content and job settings into the request shape the service expects,
so the job module can stay focused on workflow orchestration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from nas_scripts.config.ingest_crypto_documents import IngestCryptoDocumentsConfig
from nas_scripts.utils.text import extract_text


def build_headers(api_key: str | None) -> dict[str, str]:
    """Build the HTTP headers required by the Onyx adapter."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def build_payload(
    path: Path,
    rel_path: str,
    *,
    cc_pair_id: int,
) -> dict[str, Any]:
    """Translate one local file into the JSON payload expected by Onyx."""
    text = extract_text(path)
    if not text:
        raise ValueError(f"No extractable text found in {path}")

    return {
        "document": {
            "id": f"crypto::{rel_path}",
            "semantic_identifier": path.name,
            "title": path.name,
            "sections": [{"text": text}],
            "source": "file",
            "from_ingestion_api": True,
            "metadata": {
                "source_folder": str(path.parent),
                "relative_path": rel_path,
                "filename": path.name,
            },
        },
        "cc_pair_id": cc_pair_id,
    }


def ingest_file(
    path: Path,
    rel_path: str,
    *,
    config: IngestCryptoDocumentsConfig,
    session: requests.Session | None = None,
) -> None:
    """Send the payload to Onyx and raise when the adapter call fails."""
    client = session or requests
    payload = build_payload(path, rel_path, cc_pair_id=config.onyx_cc_pair_id or 0)
    response = client.post(
        config.ingest_endpoint,
        headers=build_headers(config.onyx_api_key),
        json=payload,
        timeout=config.request_timeout,
    )
    if response.status_code >= 300:
        raise RuntimeError(
            f"Upload failed for {path} | HTTP {response.status_code} | {response.text[:1500]}"
        )
