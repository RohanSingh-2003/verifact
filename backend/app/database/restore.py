"""SQLite database recovery and restoration utility for VeriFact.

Restores the database from a validated backup using atomic staging replacement,
creates verified pre-restore safety snapshots, and prevents active-connection corruption.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any

from app.database.backup import (
    get_default_backup_dir,
    list_backups,
    resolve_database_path,
    verify_backup_integrity,
)

logger = logging.getLogger(__name__)

REQUIRED_VERIFACT_TABLES = frozenset({"runs", "mutations", "experiments"})
PRE_RESTORE_SNAPSHOT_PREFIX = "verifact_pre_restore_"
STAGING_FILE_SUFFIX = ".restore_staging.tmp"


def check_database_unlocked(db_path: Path) -> None:
    """Probe whether the target database is locked by another process.

    Note: A successful probe is an additional safeguard, not proof that all
    background server processes or connection pools have stopped.
    The VeriFact application server must be stopped before performing a restore.
    """
    if not db_path.is_file():
        return
    try:
        conn = sqlite3.connect(str(db_path), timeout=0.5)
        try:
            conn.execute("BEGIN EXCLUSIVE;")
            conn.rollback()
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        raise RuntimeError(
            f"Target database '{db_path.name}' is locked by another process (e.g. running server). "
            "Please stop VeriFact before performing a restore."
        ) from exc


def validate_candidate_backup(candidate_path: Path) -> dict[str, Any]:
    """Validate a candidate backup file before attempting restoration.

    Checks:
    1. File exists and is a regular file (not a symlink).
    2. Physical SQLite integrity check passes (`PRAGMA integrity_check`).
    3. Contains required VeriFact schema tables (runs, mutations, experiments).

    Returns:
        dict: Inspection metadata containing path, size, and table row counts.
    """
    if not candidate_path.is_file():
        raise FileNotFoundError(f"Candidate backup file does not exist: {candidate_path}")
    if candidate_path.is_symlink():
        raise ValueError("Candidate backup path cannot be a symbolic link.")

    conn = sqlite3.connect(f"{candidate_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        rows = cursor.fetchall()
        if not rows or len(rows) != 1 or str(rows[0][0]).strip().lower() != "ok":
            details = "; ".join(str(r[0]) for r in rows)
            raise RuntimeError(f"Candidate backup failed integrity check: {details}")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        missing = REQUIRED_VERIFACT_TABLES - tables
        if missing:
            raise ValueError(
                f"Candidate backup is missing required VeriFact tables: {sorted(missing)}. "
                "Unrelated or empty SQLite databases cannot be restored."
            )

        counts: dict[str, int] = {}
        for tbl in sorted(REQUIRED_VERIFACT_TABLES):
            cursor.execute(f"SELECT count(*) FROM {tbl};")
            counts[tbl] = int(cursor.fetchone()[0])

        return {
            "path": candidate_path.resolve(),
            "size_bytes": candidate_path.stat().st_size,
            "table_counts": counts,
        }
    finally:
        conn.close()


def get_latest_backup(backup_dir: Path | None = None) -> Path:
    """Find and return the latest valid backup file from the backup directory."""
    b_dir = backup_dir.resolve() if backup_dir else get_default_backup_dir()
    backups = list_backups(b_dir)
    primary_backups = [b for b in backups if not b.name.startswith(PRE_RESTORE_SNAPSHOT_PREFIX)]
    if not primary_backups:
        raise FileNotFoundError(f"No valid backups found in {b_dir}")
    return primary_backups[0]


def create_pre_restore_snapshot(target_path: Path, backup_dir: Path | None = None) -> Path:
    """Create a verified safety snapshot of the target database before replacement."""
    if not target_path.is_file() or target_path.stat().st_size == 0:
        raise ValueError(f"Target database {target_path} does not exist or is empty.")

    b_dir = backup_dir.resolve() if backup_dir else get_default_backup_dir()
    b_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    snapshot_filename = f"{PRE_RESTORE_SNAPSHOT_PREFIX}{timestamp}.db"
    snapshot_path = b_dir / snapshot_filename

    counter = 1
    while snapshot_path.exists():
        snapshot_filename = f"{PRE_RESTORE_SNAPSHOT_PREFIX}{timestamp}_{counter:02d}.db"
        snapshot_path = b_dir / snapshot_filename
        counter += 1

    logger.info("Creating pre-restore safety snapshot from %s to %s", target_path, snapshot_path)

    src_conn = sqlite3.connect(f"{target_path.resolve().as_uri()}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(str(snapshot_path))
    try:
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        verify_backup_integrity(snapshot_path)
        logger.info("Pre-restore safety snapshot verified: %s", snapshot_path)
        return snapshot_path
    except Exception:
        if snapshot_path.exists():
            try:
                snapshot_path.unlink()
            except OSError:
                pass
        raise


def restore_database(
    candidate_backup: str | Path,
    target_db: str | Path | None = None,
    backup_dir: str | Path | None = None,
) -> tuple[Path, Path | None]:
    """Safely restore the SQLite database from a candidate backup.

    Args:
        candidate_backup: Path to candidate backup file.
        target_db: Path or URL of the target database. If None, resolved from settings.
        backup_dir: Directory where safety snapshots are stored. Defaults to backend/data/backups/.

    Returns:
        tuple[Path, Path | None]: (restored target path, safety snapshot path if one was created).
    """
    candidate_path = Path(candidate_backup).resolve()
    target_path = resolve_database_path(target_db)

    # Path validations
    if candidate_path.resolve() == target_path.resolve():
        raise ValueError("Candidate backup and target database cannot be the same file.")
    if target_path.is_symlink():
        raise ValueError("Target database path cannot be a symbolic link.")

    # 1. Candidate validation
    validate_candidate_backup(candidate_path)

    # 2. Probe whether target is locked by active connections
    check_database_unlocked(target_path)

    # Ensure target parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)
    b_dir = Path(backup_dir).resolve() if backup_dir else get_default_backup_dir()

    # 3. Create pre-restore safety snapshot if target exists and is non-empty
    safety_snapshot: Path | None = None
    if target_path.is_file() and target_path.stat().st_size > 0:
        try:
            safety_snapshot = create_pre_restore_snapshot(target_path, backup_dir=b_dir)
        except Exception as snap_exc:
            raise RuntimeError(
                f"Failed to secure pre-restore safety snapshot: {snap_exc}. "
                "Restoration aborted without modifying target database."
            ) from snap_exc

    # 4. Stage restored database in target directory
    staging_path = target_path.parent / f"{target_path.name}{STAGING_FILE_SUFFIX}"
    if staging_path.exists():
        try:
            staging_path.unlink()
        except OSError:
            pass

    logger.info("Staging restored database at %s", staging_path)
    src_conn = sqlite3.connect(f"{candidate_path.resolve().as_uri()}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(str(staging_path))
    try:
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        # Verify staging file before replacement
        validate_candidate_backup(staging_path)

        # 5. Atomic replacement
        try:
            os.replace(staging_path, target_path)
        except Exception as replace_exc:
            logger.error("Atomic replacement failed: %s", replace_exc)
            raise

        # 6. Post-replacement verification
        try:
            validate_candidate_backup(target_path)
        except Exception as post_exc:
            logger.critical(
                "Post-replacement verification failed: %s. Initiating emergency rollback.", post_exc
            )
            # Emergency rollback from safety snapshot if available
            if safety_snapshot and safety_snapshot.is_file():
                try:
                    rollback_staging = target_path.parent / f"{target_path.name}.rollback_staging.tmp"
                    r_src = sqlite3.connect(f"{safety_snapshot.resolve().as_uri()}?mode=ro", uri=True)
                    r_dst = sqlite3.connect(str(rollback_staging))
                    try:
                        r_src.backup(r_dst)
                    finally:
                        r_dst.close()
                        r_src.close()
                    os.replace(rollback_staging, target_path)
                    logger.info("Successfully rolled back target database from safety snapshot %s", safety_snapshot)
                except Exception as rollback_err:  # noqa: BLE001 - Critical emergency handler logs all errors
                    logger.critical(
                        "Emergency rollback failed: %s. Safety snapshot is preserved at %s",
                        rollback_err,
                        safety_snapshot,
                    )
            raise RuntimeError(f"Restored database failed verification: {post_exc}") from post_exc

        logger.info("Successfully restored database to %s", target_path)
        return target_path, safety_snapshot

    finally:
        # Clean up staging file
        if staging_path.exists():
            try:
                staging_path.unlink()
            except OSError:
                pass
