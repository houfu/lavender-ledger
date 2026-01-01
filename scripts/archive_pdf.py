#!/usr/bin/env python3
"""Archive a processed statement file (PDF or CSV).

This script moves a statement file from the staging folder to the organized archive
structure: archive/{account-name}/YYYY-MM.{ext}

The original file extension is preserved (.pdf for PDFs, .csv for CSVs).

Usage:
    uv run python scripts/archive_pdf.py <file_path> <account_name> <statement_date> [--log-id <id>]

Output (JSON to stdout):
    {
        "success": true,
        "archive_path": "/path/to/archive/dbs-savings/2025-08.csv",
        "original_path": "/path/to/staging/file.csv"
    }
"""

import argparse
import json
import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.database.models import Database


def setup_logging(log_file: Path):
    """Set up logging to file."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr),
        ],
    )


def sanitize_account_name(account_name: str) -> str:
    """Sanitize account name for use as folder name.

    Args:
        account_name: Account name from database.

    Returns:
        Sanitized folder name (lowercase, no special chars).
    """
    # Remove content in parentheses (e.g., "(...9653)")
    name = re.sub(r"\(.*?\)", "", account_name)
    # Convert to lowercase and replace spaces/special chars with hyphens
    name = re.sub(r"[^\w\s-]", "", name.lower())
    name = re.sub(r"[-\s]+", "-", name)
    return name.strip("-")


def archive_pdf(
    pdf_path: Path, account_name: str, statement_date: str, archive_base: Path
) -> dict:
    """Archive a statement file (PDF or CSV) to the organized archive folder.

    Args:
        pdf_path: Path to statement file in staging (PDF or CSV).
        account_name: Account name for folder organization.
        statement_date: Statement date (YYYY-MM-DD format).
        archive_base: Base archive directory.

    Returns:
        Dictionary with archival results.
    """
    logger = logging.getLogger(__name__)

    try:
        # Sanitize account name for folder
        folder_name = sanitize_account_name(account_name)
        logger.debug(f"Sanitized account name: '{account_name}' -> '{folder_name}'")

        # Create archive folder
        archive_folder = archive_base / folder_name
        archive_folder.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Archive folder: {archive_folder}")

        # Generate filename from statement date (YYYY-MM.ext)
        # Preserve original file extension (pdf, csv, etc.)
        original_ext = pdf_path.suffix  # .pdf or .csv
        date_obj = datetime.strptime(statement_date, "%Y-%m-%d").date()
        new_filename = f"{date_obj.year}-{date_obj.month:02d}{original_ext}"
        archive_path = archive_folder / new_filename

        # If file already exists, append timestamp
        if archive_path.exists():
            timestamp = datetime.now().strftime("%H%M%S")
            new_filename = (
                f"{date_obj.year}-{date_obj.month:02d}_{timestamp}{original_ext}"
            )
            archive_path = archive_folder / new_filename
            logger.warning(
                f"Archive file already exists, using timestamped name: {new_filename}"
            )

        # Move file
        logger.info(f"Moving PDF: {pdf_path} -> {archive_path}")
        shutil.move(str(pdf_path), str(archive_path))

        return {
            "success": True,
            "archive_path": str(archive_path.absolute()),
            "original_path": str(pdf_path.absolute()),
        }

    except Exception as e:
        logger.error(f"Error archiving PDF: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Archive processed PDF statement")
    parser.add_argument("pdf_path", type=Path, help="Path to PDF file")
    parser.add_argument("account_name", type=str, help="Account name for organization")
    parser.add_argument(
        "statement_date", type=str, help="Statement date (YYYY-MM-DD format)"
    )
    parser.add_argument("--log-id", type=int, help="Ingestion log ID for tracking")
    args = parser.parse_args()

    # Set up logging
    config = get_config()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = (
        Path(config.get("log_directory", "data/logs")) / f"ingestion_{timestamp}.log"
    )
    setup_logging(log_file)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("PDF Archival Started")
    logger.info(f"PDF: {args.pdf_path}")
    logger.info(f"Account: {args.account_name}")
    logger.info(f"Statement date: {args.statement_date}")
    if args.log_id:
        logger.info(f"Ingestion Log ID: {args.log_id}")
    logger.info("=" * 60)

    # Check if file exists
    if not args.pdf_path.exists():
        result = {"success": False, "error": f"File not found: {args.pdf_path}"}
        print(json.dumps(result, indent=2))
        logger.error(result["error"])
        return 1

    # Archive PDF
    archive_base = Path(config["statements"]["archive_path"])
    result = archive_pdf(
        args.pdf_path, args.account_name, args.statement_date, archive_base
    )

    # Update database with new path if we have statement_id
    # (This would require additional parameter, skip for now)

    # Output JSON to stdout
    print(json.dumps(result, indent=2))

    if result["success"]:
        logger.info("PDF archival completed successfully")
        return 0
    else:
        logger.error(f"PDF archival failed: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
