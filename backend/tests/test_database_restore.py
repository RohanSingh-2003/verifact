"""Unit tests for SQLite database recovery and restoration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3

import pytest

from app.database.restore import (
    PRE_RESTORE_SNAPSHOT_PREFIX,
    STAGING_FILE_SUFFIX,
    check_database_unlocked,
    get_latest_backup,
    restore_database,
    validate_candidate_backup,
)
from scripts.restore_db import main as cli_main


def _create_sample_db(db_path: Path, run_id: str = "run-101", question: str = "Is Paris in France?") -> None:
    """Create a sample SQLite database containing required VeriFact schema and records."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
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
            ("exp-001", "Pilot Experiment", "1.0", 0.5, json.dumps({"trials": 1})),
        )
        cursor.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, "exp-001", question, "completed", "mock", 120.0, 300.0),
        )
        cursor.execute(
            "INSERT INTO mutations (run_id, operator, mutated_text, verified, verdicts_json) VALUES (?, ?, ?, ?, ?)",
            (run_id, "synonym_swap", "Mutated question", 1, json.dumps(["CONSISTENT"])),
        )
        conn.commit()
    finally:
        conn.close()


def test_validate_candidate_backup_success(tmp_path: Path):
    backup_file = tmp_path / "valid_backup.db"
    _create_sample_db(backup_file)

    meta = validate_candidate_backup(backup_file)
    assert meta["path"] == backup_file.resolve()
    assert meta["size_bytes"] > 0
    assert meta["table_counts"] == {"experiments": 1, "runs": 1, "mutations": 1}


def test_validate_candidate_backup_missing_file(tmp_path: Path):
    nonexistent = tmp_path / "absent.db"
    with pytest.raises(FileNotFoundError, match="does not exist"):
        validate_candidate_backup(nonexistent)


def test_validate_candidate_backup_corrupted_file(tmp_path: Path):
    corrupt_file = tmp_path / "corrupt.db"
    corrupt_file.write_bytes(b"SQLite format 3\x00junk data" + b"\xff" * 1024)

    with pytest.raises((sqlite3.DatabaseError, RuntimeError)):
        validate_candidate_backup(corrupt_file)


def test_validate_candidate_backup_unrelated_sqlite_database(tmp_path: Path):
    unrelated_file = tmp_path / "unrelated.db"
    conn = sqlite3.connect(unrelated_file)
    conn.execute("CREATE TABLE other_project (id INT, note TEXT);")
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="missing required VeriFact tables"):
        validate_candidate_backup(unrelated_file)


def test_validate_candidate_backup_rejects_symlink(tmp_path: Path):
    real_db = tmp_path / "real.db"
    _create_sample_db(real_db)

    link_db = tmp_path / "link.db"
    try:
        link_db.symlink_to(real_db)
    except OSError:
        pytest.skip("Symlinks not supported in current environment/permissions")

    with pytest.raises(ValueError, match="symbolic link"):
        validate_candidate_backup(link_db)


def test_check_database_unlocked_locked_rejection(tmp_path: Path):
    target_db = tmp_path / "locked_target.db"
    _create_sample_db(target_db)

    # Hold an active exclusive write lock on target_db
    conn = sqlite3.connect(target_db)
    conn.execute("BEGIN EXCLUSIVE;")
    try:
        with pytest.raises(RuntimeError, match="locked by another process"):
            check_database_unlocked(target_db)
    finally:
        conn.rollback()
        conn.close()


def test_restore_database_successful_records_restoration(tmp_path: Path):
    backup_file = tmp_path / "backup.db"
    _create_sample_db(backup_file, run_id="run-original", question="Original Question?")

    target_db = tmp_path / "data" / "target.db"
    # Create target with different, stale records
    _create_sample_db(target_db, run_id="run-stale", question="Stale Question?")

    backups_dir = tmp_path / "backups"

    restored_path, safety_snapshot = restore_database(
        candidate_backup=backup_file,
        target_db=target_db,
        backup_dir=backups_dir,
    )

    assert restored_path == target_db.resolve()
    assert safety_snapshot is not None
    assert safety_snapshot.is_file()
    assert safety_snapshot.name.startswith(PRE_RESTORE_SNAPSHOT_PREFIX)

    # Verify that restored target now has the backup's records
    conn = sqlite3.connect(target_db)
    try:
        row = conn.execute("SELECT id, question FROM runs").fetchone()
        assert row == ("run-original", "Original Question?")
    finally:
        conn.close()

    # Verify that the safety snapshot preserved the stale records
    s_conn = sqlite3.connect(safety_snapshot)
    try:
        s_row = s_conn.execute("SELECT id, question FROM runs").fetchone()
        assert s_row == ("run-stale", "Stale Question?")
    finally:
        s_conn.close()


def test_restore_database_to_new_nonexistent_target(tmp_path: Path):
    backup_file = tmp_path / "backup.db"
    _create_sample_db(backup_file, run_id="run-fresh")

    new_target = tmp_path / "new_target.db"
    assert not new_target.exists()

    restored_path, safety_snapshot = restore_database(
        candidate_backup=backup_file,
        target_db=new_target,
    )

    assert restored_path == new_target.resolve()
    assert safety_snapshot is None  # No prior file to snapshot
    assert new_target.is_file()

    conn = sqlite3.connect(new_target)
    try:
        row = conn.execute("SELECT id FROM runs").fetchone()
        assert row == ("run-fresh",)
    finally:
        conn.close()


def test_restore_rejects_identical_candidate_and_target(tmp_path: Path):
    same_db = tmp_path / "same.db"
    _create_sample_db(same_db)

    with pytest.raises(ValueError, match="cannot be the same file"):
        restore_database(candidate_backup=same_db, target_db=same_db)


def test_restore_rejection_of_corrupt_candidate_leaves_target_untouched(tmp_path: Path):
    corrupt_candidate = tmp_path / "corrupt.db"
    corrupt_candidate.write_bytes(b"SQLite format 3\x00junk data" + b"\xff" * 1024)

    target_db = tmp_path / "target.db"
    _create_sample_db(target_db, run_id="run-untouched")
    original_bytes = target_db.read_bytes()

    with pytest.raises((sqlite3.DatabaseError, RuntimeError)):
        restore_database(candidate_backup=corrupt_candidate, target_db=target_db)

    # Target database remains completely unaltered
    assert target_db.read_bytes() == original_bytes


def test_restore_rejection_when_target_locked_leaves_target_untouched(tmp_path: Path):
    backup_file = tmp_path / "backup.db"
    _create_sample_db(backup_file)

    target_db = tmp_path / "target.db"
    _create_sample_db(target_db, run_id="run-held")
    original_bytes = target_db.read_bytes()

    conn = sqlite3.connect(target_db)
    conn.execute("BEGIN EXCLUSIVE;")
    try:
        with pytest.raises(RuntimeError, match="locked by another process"):
            restore_database(candidate_backup=backup_file, target_db=target_db)
    finally:
        conn.rollback()
        conn.close()

    assert target_db.read_bytes() == original_bytes


def test_restore_aborts_if_pre_restore_snapshot_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    backup_file = tmp_path / "backup.db"
    _create_sample_db(backup_file)

    target_db = tmp_path / "target.db"
    _create_sample_db(target_db, run_id="run-original")
    original_bytes = target_db.read_bytes()

    # Simulate snapshot creation failure (e.g. disk failure)
    def _failing_snapshot(*args, **kwargs):
        raise OSError("Disk full during safety snapshot")

    monkeypatch.setattr("app.database.restore.create_pre_restore_snapshot", _failing_snapshot)

    with pytest.raises(RuntimeError, match="Failed to secure pre-restore safety snapshot"):
        restore_database(candidate_backup=backup_file, target_db=target_db)

    # Target database must be untouched
    assert target_db.read_bytes() == original_bytes


def test_restore_atomic_replacement_failure_cleans_up_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    backup_file = tmp_path / "backup.db"
    _create_sample_db(backup_file)

    target_db = tmp_path / "target.db"
    _create_sample_db(target_db, run_id="run-original")
    original_bytes = target_db.read_bytes()

    staging_path = target_db.parent / f"{target_db.name}{STAGING_FILE_SUFFIX}"

    # Simulate failure during os.replace
    def _failing_replace(src, dst):
        raise OSError("Simulated atomic replace failure")

    monkeypatch.setattr(os, "replace", _failing_replace)

    with pytest.raises(OSError, match="Simulated atomic replace failure"):
        restore_database(candidate_backup=backup_file, target_db=target_db)

    # Target database remains untouched
    assert target_db.read_bytes() == original_bytes
    # Staging file is cleaned up
    assert not staging_path.exists()


def test_restore_post_verification_failure_triggers_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    backup_file = tmp_path / "backup.db"
    _create_sample_db(backup_file, run_id="run-from-backup")

    target_db = tmp_path / "target.db"
    _create_sample_db(target_db, run_id="run-pre-restore")

    # Track validate_candidate_backup calls: allow candidate & staging to pass, but fail on post-replacement
    original_validate = validate_candidate_backup
    call_count = 0

    def _conditional_validate(path):
        nonlocal call_count
        call_count += 1
        # Call 1: candidate validation
        # Call 2: staging validation
        # Call 3: post-replacement validation on target_db -> simulate unexpected corruption
        if call_count == 3:
            raise RuntimeError("Simulated post-replacement validation failure")
        return original_validate(path)

    monkeypatch.setattr("app.database.restore.validate_candidate_backup", _conditional_validate)

    with pytest.raises(RuntimeError, match="Restored database failed verification"):
        restore_database(candidate_backup=backup_file, target_db=target_db, backup_dir=tmp_path / "backups")

    # Target database must have been rolled back to the pre-restore state!
    conn = sqlite3.connect(target_db)
    try:
        row = conn.execute("SELECT id FROM runs").fetchone()
        assert row == ("run-pre-restore",), "Target database should have been rolled back"
    finally:
        conn.close()


def test_get_latest_backup_selection(tmp_path: Path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    b1 = backup_dir / "verifact_backup_20261001_100000.db"
    b2 = backup_dir / "verifact_backup_20261002_100000.db"
    # Also add a pre-restore snapshot which must NOT be selected as --latest primary backup
    snap = backup_dir / "verifact_pre_restore_20261003_100000.db"

    _create_sample_db(b1)
    _create_sample_db(b2)
    _create_sample_db(snap)

    latest = get_latest_backup(backup_dir)
    assert latest == b2.resolve()


def test_cli_restore_with_explicit_backup_and_yes(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    backup_file = tmp_path / "backup.db"
    _create_sample_db(backup_file, run_id="run-cli-explicit")

    target_db = tmp_path / "target.db"
    _create_sample_db(target_db, run_id="run-cli-old")

    exit_code = cli_main([
        "--backup", str(backup_file),
        "--target", str(target_db),
        "--yes",
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "SUCCESS: Database restored" in captured.out

    conn = sqlite3.connect(target_db)
    try:
        row = conn.execute("SELECT id FROM runs").fetchone()
        assert row == ("run-cli-explicit",)
    finally:
        conn.close()


def test_cli_restore_interactive_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    backup_file = tmp_path / "backup.db"
    _create_sample_db(backup_file)

    target_db = tmp_path / "target.db"
    _create_sample_db(target_db, run_id="run-uncancelled")
    original_bytes = target_db.read_bytes()

    # Simulate user answering "no" to the prompt
    monkeypatch.setattr("builtins.input", lambda _: "n")

    exit_code = cli_main([
        "--backup", str(backup_file),
        "--target", str(target_db),
    ])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Restoration cancelled by user" in captured.err
    assert target_db.read_bytes() == original_bytes


def test_cli_restore_with_latest_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    b_latest = backup_dir / "verifact_backup_20261010_120000.db"
    _create_sample_db(b_latest, run_id="run-from-latest")

    target_db = tmp_path / "target.db"
    _create_sample_db(target_db, run_id="run-old")

    monkeypatch.setattr("app.database.restore.get_default_backup_dir", lambda: backup_dir)

    exit_code = cli_main([
        "--latest",
        "--target", str(target_db),
        "--yes",
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "SUCCESS: Database restored" in captured.out

    conn = sqlite3.connect(target_db)
    try:
        row = conn.execute("SELECT id FROM runs").fetchone()
        assert row == ("run-from-latest",)
    finally:
        conn.close()
