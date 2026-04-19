"""FlowRAG ingestion helpers.

This module acts as the adapter layer for the external FlowRAG API. It
translates local files into the multipart upload and parsing requests the
service expects, so the job module can stay focused on workflow orchestration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from nas_scripts.config.ingest_crypto_documents import IngestCryptoDocumentsConfig


def build_headers(api_key: str | None) -> dict[str, str]:
    """Build the HTTP headers required by the FlowRAG adapter."""
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _extract_document_id(response_json: Any) -> str | None:
    """Pull a document id out of a FlowRAG API response body."""
    if not isinstance(response_json, dict):
        return None

    # FlowRAG responses have varied across versions, so accept the common
    # shapes we have seen instead of assuming one strict schema.
    data = response_json.get("data")
    if isinstance(data, dict):
        doc_id = data.get("id")
        if isinstance(doc_id, str) and doc_id.strip():
            return doc_id.strip()
        document_id = data.get("document_id")
        if isinstance(document_id, str) and document_id.strip():
            return document_id.strip()

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                doc_id = item.get("id")
                if isinstance(doc_id, str) and doc_id.strip():
                    return doc_id.strip()

    return None


def upload_file(
    path: Path,
    *,
    config: IngestCryptoDocumentsConfig,
    session: requests.Session | None = None,
) -> str:
    """Upload one file to a FlowRAG dataset and return the new document id."""
    client = session or requests
    with path.open("rb") as handle:
        response = client.post(
            config.dataset_documents_endpoint,
            headers=build_headers(config.flowrag_api_key),
            files={"file": (path.name, handle)},
            timeout=config.request_timeout,
        )

    if response.status_code >= 300:
        raise RuntimeError(
            f"Upload failed for {path} | HTTP {response.status_code} | {response.text[:1500]}"
        )

    try:
        document_id = _extract_document_id(response.json())
    except ValueError:
        document_id = None

    if not document_id:
        raise RuntimeError(f"Upload succeeded but no document id was returned for {path}")

    return document_id


def trigger_parsing(
    document_id: str,
    *,
    config: IngestCryptoDocumentsConfig,
    session: requests.Session | None = None,
) -> None:
    """Ask FlowRAG to parse a previously uploaded document."""
    client = session or requests
    response = client.post(
        config.dataset_chunks_endpoint,
        headers={**build_headers(config.flowrag_api_key), "Content-Type": "application/json"},
        json={"document_ids": [document_id]},
        timeout=config.request_timeout,
    )
    if response.status_code >= 300:
        raise RuntimeError(
            "Parsing failed for document "
            f"{document_id} | HTTP {response.status_code} | {response.text[:1500]}"
        )


def ingest_file(
    path: Path,
    rel_path: str,
    *,
    config: IngestCryptoDocumentsConfig,
    session: requests.Session | None = None,
) -> None:
    """Upload a file to FlowRAG and trigger parsing."""
    # The relative path is part of the job signature for testability and
    # future metadata use, even though the FlowRAG upload itself only needs the
    # file contents and filename today.
    _ = rel_path
    document_id = upload_file(path, config=config, session=session)
    trigger_parsing(document_id, config=config, session=session)
