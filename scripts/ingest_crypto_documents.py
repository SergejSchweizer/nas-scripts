"""Thin script wrapper for the ingest_crypto_documents job."""

from nas_scripts.jobs.ingest_crypto_documents import main


if __name__ == "__main__":
    raise SystemExit(main())
