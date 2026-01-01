#!/usr/bin/env python3
"""Run the Lavender Ledger dashboard locally for development.

This script starts the Flask development server with debug mode enabled.
For production use, run via Docker instead.

Usage:
    uv run python scripts/run_dashboard.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config, ConfigError
from src.dashboard.app import create_app


def main():
    print()
    print("🌸 Lavender Ledger - Dashboard (Development Mode)")
    print("=" * 50)
    print()

    try:
        config = get_config()
    except ConfigError as e:
        print(f"Error: {e}")
        return 1

    # Check if database exists
    db_path = Path(config["database_path"])
    if not db_path.exists():
        print(f"Warning: Database not found: {db_path}")
        print("The dashboard will show an error until you initialize the database.")
        print()
        print("To initialize:")
        print("  uv run python scripts/init_db.py")
        print()

    # Get dashboard config
    host = config.get("dashboard", {}).get("host", "127.0.0.1")
    port = config.get("dashboard", {}).get("port", 5000)
    debug = config.get("dashboard", {}).get("debug", True)

    print(f"Database: {db_path}")
    print(f"Starting server at http://{host}:{port}")
    print()
    print("Press Ctrl+C to stop")
    print()

    # Create and run app
    app = create_app(config)
    app.run(host=host, port=port, debug=debug)

    return 0


if __name__ == "__main__":
    sys.exit(main())
