"""Tests for insert_statement.py script with stdin support.

Critical tests for recent refactor to eliminate temp files.
"""

import json
import subprocess
import pytest
from pathlib import Path


class TestInsertStatementStdin:
    """Test insert_statement.py --stdin interface."""

    def test_accepts_stdin_flag(self, temp_db, sample_parsed_json, monkeypatch):
        """Script should accept --stdin flag and read JSON from stdin."""
        # Set up environment
        monkeypatch.setenv("DATABASE_PATH", temp_db)

        # Prepare command
        cmd = [
            "uv",
            "run",
            "python",
            "scripts/insert_statement.py",
            "--stdin",
            "--file-hash",
            "test_hash_123",
        ]

        # Run with JSON piped to stdin
        result = subprocess.run(
            cmd,
            input=json.dumps(sample_parsed_json),
            capture_output=True,
            text=True,
        )

        # Should succeed
        assert result.returncode == 0

        # Parse output
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["transactions_inserted"] == 3

    def test_stdin_invalid_json_returns_error(self, temp_db, monkeypatch):
        """Invalid JSON on stdin should return error."""
        monkeypatch.setenv("DATABASE_PATH", temp_db)

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/insert_statement.py",
            "--stdin",
            "--file-hash",
            "test_hash",
        ]

        result = subprocess.run(
            cmd,
            input="{ invalid json }",
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        output = json.loads(result.stdout)
        assert output["success"] is False
        assert "Failed to load JSON" in output["error"]

    def test_requires_file_hash(self, temp_db, sample_parsed_json, monkeypatch):
        """--file-hash should be required."""
        monkeypatch.setenv("DATABASE_PATH", temp_db)

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/insert_statement.py",
            "--stdin",
            # Missing --file-hash
        ]

        result = subprocess.run(
            cmd,
            input=json.dumps(sample_parsed_json),
            capture_output=True,
            text=True,
        )

        # Should fail with error about required argument
        assert result.returncode != 0

    def test_stdin_or_file_path_required(self, temp_db, monkeypatch):
        """Either --stdin or file path must be provided."""
        monkeypatch.setenv("DATABASE_PATH", temp_db)

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/insert_statement.py",
            "--file-hash",
            "test_hash",
            # No --stdin, no file path
        ]

        result = subprocess.run(
            cmd,
            input="",  # Empty stdin
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        output = json.loads(result.stdout)
        assert output["success"] is False
        assert "Provide either json_file or --stdin" in output["error"]


class TestInsertStatementBackwardCompatibility:
    """Test insert_statement.py file path interface (backward compatibility)."""

    def test_accepts_file_path(
        self, temp_db, sample_parsed_json, temp_json_file, monkeypatch
    ):
        """Script should still accept file path argument."""
        monkeypatch.setenv("DATABASE_PATH", temp_db)

        # Create temp JSON file
        json_file = temp_json_file(sample_parsed_json)

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/insert_statement.py",
            str(json_file),
            "--file-hash",
            "test_hash_file",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["transactions_inserted"] == 3

    def test_file_not_found_returns_error(self, temp_db, monkeypatch):
        """Non-existent file should return error."""
        monkeypatch.setenv("DATABASE_PATH", temp_db)

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/insert_statement.py",
            "/nonexistent/file.json",
            "--file-hash",
            "test_hash",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        assert result.returncode == 1
        output = json.loads(result.stdout)
        assert output["success"] is False
        assert "Failed to load JSON" in output["error"]


class TestInsertStatementDuplicateDetection:
    """Test duplicate statement and transaction detection."""

    def test_duplicate_statement_skipped(
        self, temp_db, sample_parsed_json, monkeypatch
    ):
        """Statement with duplicate file_hash should be skipped."""
        monkeypatch.setenv("DATABASE_PATH", temp_db)

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/insert_statement.py",
            "--stdin",
            "--file-hash",
            "duplicate_hash",
        ]

        # First insertion
        result1 = subprocess.run(
            cmd,
            input=json.dumps(sample_parsed_json),
            capture_output=True,
            text=True,
        )
        output1 = json.loads(result1.stdout)
        assert output1["success"] is True
        assert output1["duplicate_statement"] is False
        assert output1["transactions_inserted"] == 3

        # Second insertion with same hash
        result2 = subprocess.run(
            cmd,
            input=json.dumps(sample_parsed_json),
            capture_output=True,
            text=True,
        )
        output2 = json.loads(result2.stdout)
        assert output2["success"] is True
        assert output2["duplicate_statement"] is True

    def test_duplicate_transactions_counted(
        self, temp_db, sample_parsed_json, monkeypatch
    ):
        """Duplicate transactions should be counted separately."""
        monkeypatch.setenv("DATABASE_PATH", temp_db)

        # Modify sample to have unique hashes and file paths
        import copy

        parsed1 = copy.deepcopy(sample_parsed_json)
        parsed2 = copy.deepcopy(sample_parsed_json)
        parsed2["file_path"] = "data/statements/staging/test2.csv"

        # First insertion
        result1 = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/insert_statement.py",
                "--stdin",
                "--file-hash",
                "hash_1",
            ],
            input=json.dumps(parsed1),
            capture_output=True,
            text=True,
        )
        output1 = json.loads(result1.stdout)
        assert output1["transactions_inserted"] == 3
        assert output1["transactions_duplicate"] == 0

        # Second insertion (different hash, same transactions)
        result2 = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/insert_statement.py",
                "--stdin",
                "--file-hash",
                "hash_2",
            ],
            input=json.dumps(parsed2),
            capture_output=True,
            text=True,
        )
        output2 = json.loads(result2.stdout)
        # All transactions are duplicates
        assert output2["transactions_inserted"] == 0
        assert output2["transactions_duplicate"] == 3


class TestInsertStatementAccountCreation:
    """Test account creation behavior."""

    def test_creates_new_account(self, temp_db, sample_parsed_json, monkeypatch):
        """Should create account if it doesn't exist."""
        monkeypatch.setenv("DATABASE_PATH", temp_db)

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/insert_statement.py",
            "--stdin",
            "--file-hash",
            "test_hash",
        ]

        result = subprocess.run(
            cmd,
            input=json.dumps(sample_parsed_json),
            capture_output=True,
            text=True,
        )

        output = json.loads(result.stdout)
        assert output["success"] is True
        assert output["account_created"] is True

    def test_reuses_existing_account(self, temp_db, sample_parsed_json, monkeypatch):
        """Should reuse account if it exists."""
        monkeypatch.setenv("DATABASE_PATH", temp_db)

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/insert_statement.py",
            "--stdin",
            "--file-hash",
        ]

        # First insertion creates account
        result1 = subprocess.run(
            [*cmd, "hash_1"],
            input=json.dumps(sample_parsed_json),
            capture_output=True,
            text=True,
        )
        output1 = json.loads(result1.stdout)
        assert output1["account_created"] is True

        # Second insertion reuses account
        import copy

        parsed2 = copy.deepcopy(sample_parsed_json)
        parsed2["file_path"] = "data/statements/staging/test2.csv"
        result2 = subprocess.run(
            [*cmd, "hash_2"],
            input=json.dumps(parsed2),
            capture_output=True,
            text=True,
        )
        output2 = json.loads(result2.stdout)
        assert output2["account_created"] is False
        assert output2["account_id"] == output1["account_id"]
