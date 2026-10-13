"""Command-line interface to create an SQLite database backup for VeriFact.

Usage:
    python backend/scripts/backup_db.py [--source PATH] [--dest-dir PATH] [--retention N]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

# Ensure backend root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.backup import (
    DEFAULT_RETENTION_COUNT,
    create_backup,
    get_default_backup_dir,
    resolve_database_path,
)


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a verified snapshot of the VeriFact SQLite database."
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=None,
        help="Path or SQLite URL to source database (defaults to configured database_url).",
    )
    parser.add_argument(
        "--dest-dir",
        "-d",
        type=str,
        default=None,
        help="Destination directory for backups (defaults to backend/data/backups/).",
    )
    parser.add_argument(
        "--retention",
        "-r",
        type=int,
        default=DEFAULT_RETENTION_COUNT,
        help=f"Number of backups to retain (default: {DEFAULT_RETENTION_COUNT}). Set <= 0 to disable pruning.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    parsed = parse_args(args)
    log_level = logging.DEBUG if parsed.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        resolved_source = resolve_database_path(parsed.source)
        dest_dir = Path(parsed.dest_dir).resolve() if parsed.dest_dir else get_default_backup_dir()

        print("VeriFact SQLite Backup")
        print(f"Source database: {resolved_source}")
        print(f"Destination:     {dest_dir}")
        print(f"Retention limit: {parsed.retention}")

        backup_file = create_backup(
            source_db=parsed.source,
            backup_dir=parsed.dest_dir,
            retention_count=parsed.retention,
        )

        size_kb = backup_file.stat().st_size / 1024.0
        print(f"SUCCESS: Created and verified backup: {backup_file} ({size_kb:.1f} KB)")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI top-level handler prints failure message to stderr
        print(f"ERROR: Backup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
