from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from nas_scripts.config.ingest_crypto_documents import IngestCryptoDocumentsConfig
from nas_scripts.jobs.ingest_crypto_documents import run_job
from nas_scripts.utils.state import load_state
from nas_scripts.utils.text import extract_text


PDF_FIXTURE = Path(
    "tests/data/ingest_crypto_documents/09_Dergileva_Dobrynskaja_Gurov_Sokolova.pdf"
)


def _require_live_env() -> tuple[str, str, int]:
    if os.environ.get("RUN_LIVE_ONYX_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_ONYX_TESTS=1 to enable live Onyx integration tests.")

    base_url = os.environ.get("ONYX_BASE_URL")
    api_key = os.environ.get("ONYX_API_KEY")
    cc_pair_id_raw = os.environ.get("ONYX_CC_PAIR_ID")

    missing = [
        name
        for name, value in (
            ("ONYX_BASE_URL", base_url),
            ("ONYX_API_KEY", api_key),
            ("ONYX_CC_PAIR_ID", cc_pair_id_raw),
        )
        if not value
    ]
    if missing:
        pytest.skip(f"Missing live Onyx env vars: {', '.join(missing)}")

    return base_url or "", api_key or "", int(cc_pair_id_raw or "0")


@pytest.mark.integration
@pytest.mark.live
def test_ingest_crypto_documents_pdf_against_real_api(tmp_path: Path) -> None:
    base_url, api_key, cc_pair_id = _require_live_env()

    assert PDF_FIXTURE.exists(), f"Missing PDF fixture: {PDF_FIXTURE}"
    assert extract_text(PDF_FIXTURE), "PDF fixture did not yield extractable text"

    scan_dir = tmp_path / "scan"
    scan_dir.mkdir(parents=True)
    target_pdf = scan_dir / PDF_FIXTURE.name
    shutil.copy2(PDF_FIXTURE, target_pdf)

    config = IngestCryptoDocumentsConfig(
        script_name="ingest_crypto_documents",
        onyx_base_url=base_url,
        onyx_api_key=api_key,
        onyx_cc_pair_id=cc_pair_id,
        scan_dir=scan_dir,
        state_file=tmp_path / "state" / ".onyx_ingest_state.json",
        lock_file=tmp_path / "locks" / ".onyx_ingest.lock",
        log_dir=tmp_path / "logs",
        max_files_per_run=1,
        request_timeout=int(os.environ.get("REQUEST_TIMEOUT", "300")),
    )

    exit_code = run_job(config)
    saved_state = load_state(config.state_file)

    assert exit_code == 0
    assert list(saved_state) == [PDF_FIXTURE.name]
    assert saved_state[PDF_FIXTURE.name]["sha256"]
