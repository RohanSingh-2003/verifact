"""SQLite database backup utility for VeriFact.

Creates consistent snapshots using SQLite's Online Backup API,
verifies integrity via PRAGMA integrity_check, and rotates old backups.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from pathlib import Path
import re
import sqlite3
from urllib.parse import unquote

from app.config import get_settings

logger = logging.getLogger(__name__)

BACKUP_FILENAME_PREFIX = "verifact_backup_"
BACKUP_FILENAME_PATTERN = re.compile(r"^verifact_backup_\d{8}_\d{6}(?:_\d+)?\.db$")
DEFAULT_RETENTION_COUNT = 7


def get_backend_root() -> Path:
    """Return the absolute path to the backend root directory."""
    return Path(__file__).resolve().parent.parent.parent


def get_default_backup_dir() -> Path:
    """Return the default directory for storing database backups."""
    return get_backend_root() / "data" / "backups"


def resolve_database_path(db_url_or_path: str | Path | None = None) -> Path:
    """Resolve an SQLite database file path from a URL, Path, or settings.

    Resolves relative paths relative to the backend root directory,
    making database location independent of the current working directory.
    """
    if db_url_or_path is None:
        db_url_or_path = get_settings().database_url

    if isinstance(db_url_or_path, Path):
        path = db_url_or_path
    else:
        url_str = str(db_url_or_path).strip()
        if url_str.startswith("sqlite:///"):
            raw_path = unquote(url_str[len("sqlite:///"):])
            if raw_path == ":memory:":
                raise ValueError("Cannot perform file backup on an in-memory SQLite database (:memory:).")
            path = Path(raw_path)
        elif url_str.startswith("sqlite://"):
            raise ValueError("Unsupported or malformed SQLite URL.")
        elif "://" in url_str:
            scheme = url_str.split("://", 1)[0]
            raise ValueError(f"Unsupported database scheme: '{scheme}'. Only SQLite databases are supported.")
        else:
            path = Path(url_str)

    if not path.is_absolute():
        path = (get_backend_root() / path).resolve()
    else:
        path = path.resolve()

    return path


def verify_backup_integrity(backup_path: Path) -> None:
    """Verify an SQLite database file using PRAGMA integrity_check.

    Raises RuntimeError or sqlite3.DatabaseError if the integrity check fails.
    """
    if not backup_path.is_file():
        raise FileNotFoundError(f"Backup file not found at {backup_path}")

    conn = sqlite3.connect(f"{backup_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        rows = cursor.fetchall()
        if not rows or len(rows) != 1 or str(rows[0][0]).strip().lower() != "ok":
            error_details = "; ".join(str(r[0]) for r in rows)
            raise RuntimeError(f"Database integrity check failed: {error_details}")
    finally:
        conn.close()


def list_backups(backup_dir: Path) -> list[Path]:
    """List all recognized backup files in backup_dir, sorted newest to oldest."""
    if not backup_dir.is_dir():
        return []
    backups = [p for p in backup_dir.iterdir() if p.is_file() and BACKUP_FILENAME_PATTERN.match(p.name)]
    # Sort descending by filename and modification time
    backups.sort(key=lambda p: (p.name, p.stat().st_mtime), reverse=True)
    return backups


def prune_old_backups(backup_dir: Path, retention_count: int = DEFAULT_RETENTION_COUNT) -> list[Path]:
    """Prune recognized backup files exceeding retention_count.

    Only files matching the recognized backup pattern are considered.
    Returns a list of Paths of pruned files.
    """
    if retention_count < 1:
        return []

    backups = list_backups(backup_dir)
    to_delete = backups[retention_count:]
    deleted: list[Path] = []
    for file_path in to_delete:
        try:
            file_path.unlink()
            deleted.append(file_path)
            logger.info("Pruned old backup: %s", file_path)
        except OSError as e:
            logger.warning("Failed to prune old backup %s: %s", file_path, e)
    return deleted


def create_backup(
    source_db: str | Path | None = None,
    backup_dir: str | Path | None = None,
    retention_count: int = DEFAULT_RETENTION_COUNT,
) -> Path:
    """Create a verified SQLite database snapshot using SQLite Online Backup API.

    Args:
        source_db: Path or SQLite URL of the source database. If None, resolved from settings.
        backup_dir: Directory where backups should be saved. Defaults to backend/data/backups/.
        retention_count: Maximum number of backups to keep (default 7). Set <= 0 to disable pruning.

    Returns:
        Path: The absolute path of the newly created and verified backup file.
    """
    source_path = resolve_database_path(source_db)
    if not source_path.is_file():
        raise FileNotFoundError(f"Source database file does not exist: {source_path}")

    dest_dir = Path(backup_dir).resolve() if backup_dir else get_default_backup_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{BACKUP_FILENAME_PREFIX}{timestamp}.db"
    backup_path = dest_dir / backup_filename

    # Defensive check: ensure backup destination does not resolve to the source database file
    if backup_path.resolve() == source_path.resolve():
        raise ValueError("Backup destination cannot resolve to the source database file.")

    # If a file with the same timestamp exists, append a sequence counter
    counter = 1
    while backup_path.exists():
        backup_filename = f"{BACKUP_FILENAME_PREFIX}{timestamp}_{counter:02d}.db"
        backup_path = dest_dir / backup_filename
        if backup_path.resolve() == source_path.resolve():
            raise ValueError("Backup destination cannot resolve to the source database file.")
        counter += 1

    logger.info("Starting online backup from %s to %s", source_path, backup_path)

    # Use SQLite Online Backup API
    # Source is opened in read-only mode to prevent accidental modifications
    src_conn = sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(str(backup_path))
    try:
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        # Verify integrity of newly created snapshot
        verify_backup_integrity(backup_path)
        logger.info("Backup successfully created and verified: %s", backup_path)

        # Retention pruning is performed strictly AFTER backup is created and verified
        if retention_count > 0:
            pruned = prune_old_backups(dest_dir, retention_count=retention_count)
            if pruned:
                logger.info("Pruned %d old backup(s) based on retention count %d", len(pruned), retention_count)

        return backup_path

    except Exception:
        # Clean up partial or unverified backup file on any failure
        if backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass
        raise
