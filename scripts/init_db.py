#!/usr/bin/env python3
"""Initialize the Lavender Ledger database.

This script creates the database schema and seeds default categories.
Run this once before first use, or to reset the database.

Usage:
    uv run python scripts/init_db.py
"""

import sqlite3
import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config, ConfigError
from src.database.models import Database


def main():
    print("=" * 50)
    print("  Lavender Ledger - Database Initialization")
    print("=" * 50)
    print()

    try:
        config = get_config()
    except ConfigError as e:
        print(f"Error: {e}")
        print()
        print("Please create a config.yaml file:")
        print("  cp config.example.yaml config.yaml")
        print("  # Edit config.yaml with your settings")
        return 1

    db_path = config["database_path"]
    print(f"Database path: {db_path}")

    # Check if database already exists
    if Path(db_path).exists():
        response = input("Database already exists. Overwrite? [y/N]: ").strip().lower()
        if response != "y":
            print("Aborted.")
            return 0
        Path(db_path).unlink()
        print("Existing database removed.")

    # Create parent directory if needed
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Initialize database
    print("Creating database schema...")
    db = Database(db_path)
    db.init_schema()
    print("Schema created.")

    # Seed categories
    print("Seeding default categories...")
    db.seed_categories()
    print("Categories seeded.")

    # Run migrations
    print()
    print("Running migrations...")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "migrate.py")],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Error running migrations: {result.stderr}")
        return 1
    print(result.stdout)

    print("=" * 50)
    print("  Database initialized successfully!")
    print("=" * 50)
    print()
    print("Next steps:")
    print("  1. Place PDF statements in staging folder:")
    print(f"     {config['statements']['staging_path']}")
    print()
    print("  2. Ask Claude Code to run ingestion:")
    print('     "Please run the ingestion skill to process the PDFs in staging"')
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
