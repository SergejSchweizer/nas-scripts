"""Thin script wrapper for the ingest_crypto_documents job."""

import argparse

from nas_scripts.jobs.ingest_crypto_documents import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--max-files-per-run",
        type=int,
        help="Limit this run to the first N changed or new files.",
    )
    args = parser.parse_args()
    raise SystemExit(main(max_files_per_run=args.max_files_per_run))
