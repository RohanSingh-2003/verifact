"""Unit tests for SQLite database backup, integrity verification, and retention."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from unittest.mock import Mock

import pytest

from app.database.backup import (
    BACKUP_FILENAME_PATTERN,
    create_backup,
    get_backend_root,
    get_default_backup_dir,
    list_backups,
    prune_old_backups,
    resolve_database_path,
    verify_backup_integrity,
)
from scripts.backup_db import main as cli_main


def _create_sample_db(db_path: Path) -> None:
    """Create a sample SQLite database with representative VeriFact tables and data."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute(
            """
            CREATE TABLE experiments (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(128) NOT NULL,
                dataset_version VARCHAR(64) DEFAULT '1.0',
                threshold FLOAT DEFAULT 0.5,
                config_json TEXT DEFAULT '{}'
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE runs (
                id VARCHAR(36) PRIMARY KEY,
                experiment_id VARCHAR(36),
                question TEXT NOT NULL,
                status VARCHAR(32) DEFAULT 'completed',
                llm_mode VARCHAR(16) DEFAULT 'mock',
                answer_ms FLOAT,
                total_ms FLOAT,
                FOREIGN KEY (experiment_id) REFERENCES experiments (id)
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE mutations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id VARCHAR(36) NOT NULL,
                operator VARCHAR(64) NOT NULL,
                mutated_text TEXT NOT NULL,
                verified BOOLEAN DEFAULT 1,
                verdicts_json TEXT DEFAULT '[]',
                FOREIGN KEY (run_id) REFERENCES runs (id)
            );
            """
        )

        cursor.execute(
            "INSERT INTO experiments VALUES (?, ?, ?, ?, ?)",
            ("exp-001", "Pilot Experiment", "1.0", 0.5, json.dumps({"trials": 3})),
        )
        cursor.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-101", "exp-001", "Is Paris the capital of France?", "completed", "mock", 125.4, 350.2),
        )
        cursor.execute(
            "INSERT INTO mutations (run_id, operator, mutated_text, verified, verdicts_json) VALUES (?, ?, ?, ?, ?)",
            ("run-101", "synonym_swap", "Is Paris the chief city of France?", 1, json.dumps(["CONSISTENT"])),
        )
        conn.commit()
    finally:
        conn.close()


def test_resolve_database_path_absolute(tmp_path: Path):
    abs_file = tmp_path / "custom.db"
    resolved = resolve_database_path(abs_file)
    assert resolved == abs_file.resolve()

    resolved_from_url = resolve_database_path(f"sqlite:///{abs_file.resolve().as_posix()}")
    assert resolved_from_url == abs_file.resolve()


def test_resolve_database_path_relative():
    resolved = resolve_database_path("data/test_rel.db")
    expected = (get_backend_root() / "data" / "test_rel.db").resolve()
    assert resolved == expected

    resolved_url = resolve_database_path("sqlite:///./data/test_rel.db")
    assert resolved_url == expected


def test_resolve_database_path_in_memory():
    with pytest.raises(ValueError, match="in-memory"):
        resolve_database_path("sqlite:///:memory:")


def test_resolve_database_path_malformed():
    with pytest.raises(ValueError, match="Unsupported or malformed"):
        resolve_database_path("sqlite://invalid_url")


def test_resolve_database_path_unsupported_scheme_does_not_leak_secrets():
    fake_url = "postgresql://secret_user:super_secret_password_123@db.prod.internal:5432/maindb"
    with pytest.raises(ValueError) as exc_info:
        resolve_database_path(fake_url)

    err_msg = str(exc_info.value)
    assert "Unsupported database scheme: 'postgresql'" in err_msg
    # Ensure no credentials, hosts, or full URLs are leaked in the error message
    assert "secret_user" not in err_msg
    assert "super_secret_password_123" not in err_msg
    assert "db.prod.internal" not in err_msg
    assert fake_url not in err_msg


def test_resolve_database_path_percent_encoded_spaces(tmp_path: Path):
    space_db = tmp_path / "my database.db"
    space_db.touch()
    encoded_url = f"sqlite:///{space_db.resolve().as_posix().replace(' ', '%20')}"
    resolved = resolve_database_path(encoded_url)
    assert resolved == space_db.resolve()


def test_get_default_backup_dir():
    backup_dir = get_default_backup_dir()
    assert backup_dir == (get_backend_root() / "data" / "backups").resolve()


def test_create_backup_success_and_integrity(tmp_path: Path):
    source_db = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    _create_sample_db(source_db)

    backup_file = create_backup(source_db=source_db, backup_dir=backup_dir, retention_count=7)

    assert backup_file.is_file()
    assert backup_file.parent == backup_dir
    assert BACKUP_FILENAME_PATTERN.match(backup_file.name)

    # Integrity verification
    verify_backup_integrity(backup_file)


def test_preservation_of_representative_database_records(tmp_path: Path):
    source_db = tmp_path / "records_source.db"
    backup_dir = tmp_path / "backups"
    _create_sample_db(source_db)

    backup_file = create_backup(source_db=source_db, backup_dir=backup_dir)

    conn = sqlite3.connect(backup_file)
    try:
        cursor = conn.cursor()
        exp_row = cursor.execute("SELECT id, name, threshold FROM experiments").fetchone()
        assert exp_row == ("exp-001", "Pilot Experiment", 0.5)

        run_row = cursor.execute("SELECT id, question, status, llm_mode FROM runs").fetchone()
        assert run_row == ("run-101", "Is Paris the capital of France?", "completed", "mock")

        mutation_row = cursor.execute("SELECT run_id, operator, verified FROM mutations").fetchone()
        assert mutation_row == ("run-101", "synonym_swap", 1)
    finally:
        conn.close()


def test_online_backup_during_active_connection(tmp_path: Path):
    source_db = tmp_path / "active_source.db"
    backup_dir = tmp_path / "backups"
    _create_sample_db(source_db)

    # Open persistent connection to simulate ongoing application operations
    active_conn = sqlite3.connect(source_db)
    try:
        active_conn.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("run-102", "exp-001", "What is water made of?", "completed", "mock", 100.0, 200.0),
        )
        active_conn.commit()

        # Create backup while active connection remains open
        backup_file = create_backup(source_db=source_db, backup_dir=backup_dir)
        assert backup_file.is_file()
        verify_backup_integrity(backup_file)

        # Confirm the new record is present in the backup
        b_conn = sqlite3.connect(backup_file)
        try:
            row = b_conn.execute("SELECT id FROM runs WHERE id = 'run-102'").fetchone()
            assert row is not None and row[0] == "run-102"
        finally:
            b_conn.close()
    finally:
        active_conn.close()


def test_safe_retention_and_protection_of_other_files(tmp_path: Path):
    source_db = tmp_path / "retention_source.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    _create_sample_db(source_db)

    # Create dummy recognized backups with older timestamps
    old_names = [
        "verifact_backup_20261001_100000.db",
        "verifact_backup_20261002_100000.db",
        "verifact_backup_20261003_100000.db",
        "verifact_backup_20261004_100000.db",
    ]
    for name in old_names:
        _create_sample_db(backup_dir / name)

    # Create non-backup files that must NOT be touched or pruned
    gitkeep = backup_dir / ".gitkeep"
    gitkeep.write_text("keep this directory", encoding="utf-8")
    custom_db = backup_dir / "custom_unrelated.db"
    _create_sample_db(custom_db)
    readme = backup_dir / "README.txt"
    readme.write_text("important backup notes", encoding="utf-8")

    # We currently have 4 recognized backups.
    # Set retention to 3. Creating 1 new backup brings total recognized backups to 5.
    # Retention 3 must keep the 3 newest and prune the 2 oldest (20261001 and 20261002).
    new_backup = create_backup(source_db=source_db, backup_dir=backup_dir, retention_count=3)

    remaining_backups = list_backups(backup_dir)
    assert len(remaining_backups) == 3
    assert new_backup in remaining_backups
    assert (backup_dir / "verifact_backup_20261004_100000.db") in remaining_backups
    assert (backup_dir / "verifact_backup_20261003_100000.db") in remaining_backups

    # Verify oldest 2 backups were pruned
    assert not (backup_dir / "verifact_backup_20261001_100000.db").exists()
    assert not (backup_dir / "verifact_backup_20261002_100000.db").exists()

    # Verify unrelated files remain completely untouched
    assert gitkeep.exists() and gitkeep.read_text(encoding="utf-8") == "keep this directory"
    assert custom_db.exists()
    assert readme.exists() and readme.read_text(encoding="utf-8") == "important backup notes"


def test_retention_zero_or_negative_disables_pruning(tmp_path: Path):
    source_db = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    _create_sample_db(source_db)

    _create_sample_db(backup_dir / "verifact_backup_20261001_100000.db")
    _create_sample_db(backup_dir / "verifact_backup_20261002_100000.db")

    pruned = prune_old_backups(backup_dir, retention_count=0)
    assert pruned == []
    assert len(list_backups(backup_dir)) == 2


def test_filename_collision_handling(tmp_path: Path):
    source_db = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    _create_sample_db(source_db)

    # Creating two backups rapidly in succession
    backup1 = create_backup(source_db=source_db, backup_dir=backup_dir, retention_count=10)
    backup2 = create_backup(source_db=source_db, backup_dir=backup_dir, retention_count=10)

    assert backup1.exists()
    assert backup2.exists()
    assert backup1 != backup2
    assert BACKUP_FILENAME_PATTERN.match(backup1.name)
    assert BACKUP_FILENAME_PATTERN.match(backup2.name)


def test_create_backup_rejects_source_destination_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Freeze timestamp deterministically to match candidate filename
    fixed_now = datetime(2026, 10, 13, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.database.backup.datetime",
        Mock(now=Mock(return_value=fixed_now)),
    )

    source_db = backup_dir / "verifact_backup_20261013_120000.db"
    _create_sample_db(source_db)
    original_bytes = source_db.read_bytes()

    with pytest.raises(ValueError, match="Backup destination cannot resolve to the source database file"):
        create_backup(source_db=source_db, backup_dir=backup_dir)

    # Confirm the active source database remains completely unchanged
    assert source_db.exists()
    assert source_db.read_bytes() == original_bytes


def test_create_backup_with_spaces_in_path(tmp_path: Path):
    source_db = tmp_path / "my database.db"
    backup_dir = tmp_path / "my backups"
    _create_sample_db(source_db)

    backup_file = create_backup(source_db=source_db, backup_dir=backup_dir)
    assert backup_file.is_file()
    assert backup_file.parent == backup_dir
    verify_backup_integrity(backup_file)


def test_backup_failure_on_nonexistent_source(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist.db"
    backup_dir = tmp_path / "backups"

    with pytest.raises(FileNotFoundError, match="does not exist"):
        create_backup(source_db=nonexistent, backup_dir=backup_dir)


def test_backup_failure_on_corrupted_database_cleans_up_candidate(tmp_path: Path):
    corrupt_db = tmp_path / "corrupt.db"
    # Write invalid / corrupted binary content
    corrupt_db.write_bytes(b"SQLite format 3\x00corrupted junk data" + b"\xff" * 2048)

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Add an existing valid backup
    existing_backup = backup_dir / "verifact_backup_20261001_100000.db"
    _create_sample_db(existing_backup)

    with pytest.raises((sqlite3.DatabaseError, RuntimeError)):
        create_backup(source_db=corrupt_db, backup_dir=backup_dir, retention_count=1)

    # Verify candidate file was unlinked and cleaned up
    all_files = list(backup_dir.iterdir())
    assert all_files == [existing_backup], "Partial/corrupt backup file must not be left behind"

    # Existing backup must NOT be pruned on failure
    assert existing_backup.exists()


def test_verify_backup_integrity_raises_on_corrupt(tmp_path: Path):
    corrupt_db = tmp_path / "bad.db"
    corrupt_db.write_bytes(b"SQLite format 3\x00bad header" + b"\x00" * 1024)

    with pytest.raises((sqlite3.DatabaseError, RuntimeError)):
        verify_backup_integrity(corrupt_db)

    with pytest.raises(FileNotFoundError):
        verify_backup_integrity(tmp_path / "missing.db")


def test_cli_backup_db_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    source_db = tmp_path / "cli_source.db"
    backup_dir = tmp_path / "cli_backups"
    _create_sample_db(source_db)

    exit_code = cli_main([
        "--source", str(source_db),
        "--dest-dir", str(backup_dir),
        "--retention", "5",
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "SUCCESS: Created and verified backup" in captured.out

    backups = list_backups(backup_dir)
    assert len(backups) == 1
    assert backups[0].exists()


def test_cli_backup_db_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    nonexistent = tmp_path / "absent.db"
    backup_dir = tmp_path / "cli_backups"

    exit_code = cli_main([
        "--source", str(nonexistent),
        "--dest-dir", str(backup_dir),
    ])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "ERROR: Backup failed" in captured.err
