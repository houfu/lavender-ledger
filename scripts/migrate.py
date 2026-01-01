#!/usr/bin/env python3
"""Database migration runner for Lavender Ledger."""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from src.config import get_config


def get_db_path() -> Path:
    """Get database path from config."""
    config = get_config()
    return Path(config["database_path"])


def get_migrations_dir() -> Path:
    """Get migrations directory path."""
    return Path(__file__).parent.parent / "migrations"


def get_applied_migrations(conn: sqlite3.Connection) -> set[int]:
    """Get set of migration versions that have been applied.

    Args:
        conn: Database connection.

    Returns:
        Set of applied migration version numbers.
    """
    cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version")
    return {row[0] for row in cursor.fetchall()}


def get_pending_migrations(
    migrations_dir: Path, applied: set[int]
) -> list[tuple[int, str, Path]]:
    """Get list of migrations that haven't been applied yet.

    Args:
        migrations_dir: Path to migrations directory.
        applied: Set of applied migration versions.

    Returns:
        List of (version, name, path) tuples for pending migrations, sorted by version.
    """
    pending = []

    for migration_file in sorted(migrations_dir.glob("*.sql")):
        # Skip README and non-migration files
        if migration_file.name == "README.md":
            continue

        # Parse version from filename: 001_description.sql
        try:
            version_str = migration_file.stem.split("_")[0]
            version = int(version_str)
            name = migration_file.stem[
                len(version_str) + 1 :
            ]  # Everything after "001_"

            if version not in applied:
                pending.append((version, name, migration_file))
        except (ValueError, IndexError):
            print(
                f"Warning: Skipping invalid migration filename: {migration_file.name}"
            )
            continue

    return sorted(pending, key=lambda x: x[0])


def apply_migration(
    conn: sqlite3.Connection, version: int, name: str, path: Path
) -> None:
    """Apply a single migration.

    Args:
        conn: Database connection.
        version: Migration version number.
        name: Migration name.
        path: Path to migration SQL file.

    Raises:
        Exception: If migration fails.
    """
    print(f"Applying migration {version:03d}: {name}...", end=" ")

    try:
        # Read migration SQL
        sql = path.read_text()

        # Execute migration
        conn.executescript(sql)

        # Record migration as applied
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, name, datetime.now().isoformat()),
        )

        conn.commit()
        print("✓")

    except Exception as e:
        conn.rollback()
        print(f"✗\nError applying migration {version:03d}: {e}")
        raise


def show_status(conn: sqlite3.Connection, migrations_dir: Path) -> None:
    """Show migration status.

    Args:
        conn: Database connection.
        migrations_dir: Path to migrations directory.
    """
    applied = get_applied_migrations(conn)
    pending = get_pending_migrations(migrations_dir, applied)

    print("Database Migration Status")
    print("=" * 60)
    print(f"Database: {get_db_path()}")
    print(f"Migrations directory: {migrations_dir}")
    print()

    # Show applied migrations
    if applied:
        print(f"Applied migrations: {len(applied)}")
        cursor = conn.execute(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        )
        for row in cursor.fetchall():
            version, name, applied_at = row
            print(f"  ✓ {version:03d}: {name} (applied {applied_at})")
    else:
        print("No migrations applied yet")

    print()

    # Show pending migrations
    if pending:
        print(f"Pending migrations: {len(pending)}")
        for version, name, _ in pending:
            print(f"  • {version:03d}: {name}")
    else:
        print("No pending migrations - database is up to date!")


def run_migrations(conn: sqlite3.Connection, migrations_dir: Path) -> int:
    """Run all pending migrations.

    Args:
        conn: Database connection.
        migrations_dir: Path to migrations directory.

    Returns:
        Number of migrations applied.
    """
    applied = get_applied_migrations(conn)
    pending = get_pending_migrations(migrations_dir, applied)

    if not pending:
        print("No pending migrations - database is up to date!")
        return 0

    print(f"Found {len(pending)} pending migration(s)")
    print()

    for version, name, path in pending:
        apply_migration(conn, version, name, path)

    print()
    print(f"✓ Successfully applied {len(pending)} migration(s)")
    return len(pending)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show migration status without applying any migrations",
    )
    args = parser.parse_args()

    # Get paths
    db_path = get_db_path()
    migrations_dir = get_migrations_dir()

    # Check database exists
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        print("Run 'uv run python scripts/init_db.py' first to initialize the database")
        sys.exit(1)

    # Check migrations directory exists
    if not migrations_dir.exists():
        print(f"Error: Migrations directory not found at {migrations_dir}")
        sys.exit(1)

    # Connect to database
    conn = sqlite3.connect(db_path)

    try:
        # Ensure schema_migrations table exists
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()

        if args.status:
            show_status(conn, migrations_dir)
        else:
            run_migrations(conn, migrations_dir)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
