"""Command-line interface to restore the VeriFact SQLite database from a backup.

Usage:
    python backend/scripts/restore_db.py (--backup PATH | --latest) [--target PATH] [--yes]
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

from app.database.backup import resolve_database_path
from app.database.restore import (
    get_latest_backup,
    restore_database,
    validate_candidate_backup,
)


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely restore the VeriFact SQLite database from a validated backup."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--backup",
        "-b",
        type=str,
        help="Path to the candidate backup file to restore from.",
    )
    group.add_argument(
        "--latest",
        "-l",
        action="store_true",
        help="Automatically select the newest valid backup from the backups directory.",
    )

    parser.add_argument(
        "--target",
        "-t",
        type=str,
        default=None,
        help="Path or SQLite URL of target database to replace (defaults to configured database_url).",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Bypass interactive operator confirmation.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    parsed = parse_args(args)
    log_level = logging.DEBUG if parsed.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        # Resolve candidate backup
        if parsed.latest:
            candidate_path = get_latest_backup()
        else:
            candidate_path = Path(parsed.backup).resolve()

        # Validate candidate backup before prompting or acting
        metadata = validate_candidate_backup(candidate_path)
        resolved_target = resolve_database_path(parsed.target)

        target_status = "Exists" if resolved_target.is_file() else "New file (does not exist)"
        target_size = (
            f"{resolved_target.stat().st_size / 1024.0:.1f} KB"
            if resolved_target.is_file()
            else "N/A"
        )
        cand_size = f"{metadata['size_bytes'] / 1024.0:.1f} KB"

        print("=======================================================")
        print("VeriFact SQLite Database Recovery")
        print("=======================================================")
        print(f"Candidate Backup: {candidate_path} ({cand_size})")
        print(f"Target Database:  {resolved_target} ({target_status}, {target_size})")
        print(f"Verified Tables:  {metadata['table_counts']}")
        print("=======================================================")
        print("WARNING: Restoring will overwrite/replace the target database!")
        print("CRITICAL: The VeriFact application server MUST be stopped before proceeding.")

        if not parsed.yes:
            prompt = input("Proceed with database restoration? [y/N]: ").strip().lower()
            if prompt not in {"y", "yes"}:
                print("Restoration cancelled by user.", file=sys.stderr)
                return 1

        restored_path, safety_snapshot = restore_database(
            candidate_backup=candidate_path,
            target_db=parsed.target,
        )

        print(f"SUCCESS: Database restored to {restored_path}")
        if safety_snapshot:
            print(f"Safety snapshot preserved at: {safety_snapshot}")
        return 0

    except Exception as exc:  # noqa: BLE001 - Top-level CLI handler reports all unexpected failures cleanly
        print(f"ERROR: Restoration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
