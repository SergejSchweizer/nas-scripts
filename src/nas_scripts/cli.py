"""Command-line entrypoints for NAS scripts.

The CLI stays intentionally thin: it parses a command, maps it to a job
module, and lets the job own the actual workflow and logging.
"""

from __future__ import annotations

import argparse

from nas_scripts.jobs.ingest_crypto_documents import main as ingest_crypto_documents_main
from nas_scripts.jobs.organize_temp_media import main as organize_temp_media_main
from nas_scripts.jobs.sync_media_library import main as sync_media_library_main


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser for all NAS jobs."""
    parser = argparse.ArgumentParser(
        prog="nas-scripts",
        description="Python automation scripts for NAS workflows.",
    )
    subparsers = parser.add_subparsers(dest="command")

    ingest_parser = subparsers.add_parser(
        "ingest-crypto-documents",
        help="Ingest supported files from the crypto RAG directory into Onyx.",
    )
    ingest_parser.add_argument(
        "--max-files-per-run",
        type=int,
        help="Limit this run to the first N changed or new files.",
    )
    ingest_parser.set_defaults(
        handler=lambda args: ingest_crypto_documents_main(
            max_files_per_run=args.max_files_per_run,
        )
    )

    sync_parser = subparsers.add_parser(
        "sync-media-library",
        help="Sync media files into the media library and keep only English audio/subtitle streams.",
    )
    sync_parser.set_defaults(handler=lambda args: sync_media_library_main())

    organize_parser = subparsers.add_parser(
        "organize-temp-media",
        help="Sort temporary image and media files into dated folders.",
    )
    organize_parser.add_argument(
        "--reorganize-existing",
        action="store_true",
        help="Also scan existing subdirectories and reorganize older folder layouts into raw/img/vid.",
    )
    organize_parser.set_defaults(
        handler=lambda args: organize_temp_media_main(
            reorganize_existing=args.reorganize_existing,
        )
    )

    return parser


def main() -> int:
    """Parse CLI arguments and dispatch to the selected job."""
    parser = build_parser()
    args = parser.parse_args()
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return int(handler(args))
