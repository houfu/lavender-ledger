#!/usr/bin/env python3
"""Insert statement data into the database.

This script takes JSON output from the pdf_parsing skill and inserts
the account, statement, and transactions into the database.

Usage:
    uv run python scripts/insert_statement.py <json_file> [--log-id <id>] [--file-hash <hash>]
    echo '{"account_info": {...}, "transactions": [...]}' | uv run python scripts/insert_statement.py --stdin [--log-id <id>] --file-hash <hash>

Input JSON format (from pdf_parsing skill):
    {
        "account_info": {
            "bank_name": "DBS Bank",
            "account_type": "savings",
            "account_name": "DBS eMulti-Currency Autosave Account (...9653)",
            "last_four": "9653",
            "statement_date": "2025-08-31",
            "period_start": "2025-08-01",
            "period_end": "2025-08-31"
        },
        "transactions": [...]
    }

Output (JSON to stdout):
    {
        "success": true,
        "statement_id": 2,
        "account_id": 2,
        "transactions_inserted": 35,
        "transactions_duplicate": 0,
        "account_created": true
    }
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.database.models import Account, Database, Statement, Transaction


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


def parse_date(date_str: str):
    """Parse date string to date object."""
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def insert_statement_data(db: Database, data: dict, file_hash: str) -> dict:
    """Insert statement data into database.

    Args:
        db: Database instance.
        data: Parsed statement data from pdf_parsing skill.
        file_hash: SHA256 hash of the PDF file.

    Returns:
        Dictionary with insertion results.
    """
    logger = logging.getLogger(__name__)

    try:
        account_info = data["account_info"]
        transactions_data = data["transactions"]

        # Get or create account first (needed for duplicate check)
        account_name = account_info["account_name"]
        account = db.get_account_by_name(account_name)
        account_created = False

        if account is None:
            logger.info(f"Creating new account: {account_name}")
            account_obj = Account(
                id=None,
                account_name=account_name,
                account_type=account_info["account_type"],
                bank_name=account_info["bank_name"],
                last_four=account_info.get("last_four"),
                is_active=True,
                created_at=None,
            )
            account_id = db.create_account(account_obj)
            account = db.get_account_by_name(account_name)
            account_created = True
            logger.info(f"Account created with ID: {account_id}")
        else:
            account_id = account.id
            logger.info(f"Using existing account ID: {account_id}")

        # Check if statement already exists for this account (supports consolidated statements)
        if db.statement_exists(file_hash, account_id=account_id):
            logger.warning(
                f"Statement with hash {file_hash} for account {account_id} already exists. Skipping."
            )
            return {
                "success": True,
                "duplicate_statement": True,
                "message": "Statement already processed",
            }

        # Create statement
        statement_obj = Statement(
            id=None,
            account_id=account_id,
            statement_date=parse_date(account_info.get("statement_date")),
            period_start=parse_date(account_info.get("period_start")),
            period_end=parse_date(account_info.get("period_end")),
            file_path=data.get("file_path", ""),
            file_hash=file_hash,
            total_transactions=len(transactions_data),
            processed_at=None,
        )
        statement_id = db.create_statement(statement_obj)
        logger.info(f"Statement created with ID: {statement_id}")

        # Insert transactions
        transactions_to_insert = []
        duplicates = 0

        for txn_data in transactions_data:
            # Check if transaction already exists
            if db.transaction_exists(
                account_id=account_id,
                transaction_date=parse_date(txn_data["transaction_date"]),
                amount=float(txn_data["amount"]),
                merchant=txn_data["merchant_original"],
            ):
                duplicates += 1
                logger.debug(
                    f"Duplicate transaction: {txn_data['merchant_original']} "
                    f"({txn_data['amount']})"
                )
                continue

            # Create transaction object
            txn_obj = Transaction(
                id=None,
                statement_id=statement_id,
                account_id=account_id,
                transaction_date=parse_date(txn_data["transaction_date"]),
                post_date=parse_date(txn_data.get("post_date")),
                amount=float(txn_data["amount"]),
                transaction_type=txn_data["transaction_type"],
                merchant_original=txn_data["merchant_original"],
                merchant_cleaned=txn_data.get("merchant_cleaned"),
                description=txn_data.get("description"),
                category=None,  # Will be categorized later
                confidence_score=None,
                flagged_for_review=False,
                notes=None,
                created_at=None,
                updated_at=None,
            )
            transactions_to_insert.append(txn_obj)

        # Batch insert transactions
        inserted = db.create_transactions_batch(transactions_to_insert)
        logger.info(
            f"Inserted {inserted} transactions, {duplicates} duplicates skipped"
        )

        return {
            "success": True,
            "statement_id": statement_id,
            "account_id": account_id,
            "transactions_inserted": inserted,
            "transactions_duplicate": duplicates,
            "account_created": account_created,
            "duplicate_statement": False,
        }

    except Exception as e:
        logger.error(f"Error inserting statement data: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Insert statement data into database")
    parser.add_argument(
        "json_file",
        type=Path,
        nargs="?",
        help="JSON file with parsed statement data (deprecated, use --stdin)",
    )
    parser.add_argument(
        "--stdin", action="store_true", help="Read JSON from stdin instead of file"
    )
    parser.add_argument("--log-id", type=int, help="Ingestion log ID for tracking")
    parser.add_argument(
        "--file-hash", type=str, required=True, help="SHA256 hash of PDF file"
    )
    args = parser.parse_args()

    # Get database path from environment or config
    import os

    db_path = os.environ.get("DATABASE_PATH")
    if db_path:
        # Use environment variable (for testing)
        logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.DEBUG, handlers=[logging.StreamHandler(sys.stderr)]
        )
        logger.info("=" * 60)
        logger.info("Statement Insertion Started (using DATABASE_PATH from env)")
    else:
        # Use config file
        config = get_config()
        db_path = config["database_path"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = (
            Path(config.get("log_directory", "data/logs"))
            / f"ingestion_{timestamp}.log"
        )
        setup_logging(log_file)
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("Statement Insertion Started")

    # Load JSON data from stdin or file
    try:
        if args.stdin:
            logger.info("Reading JSON from stdin")
            data = json.load(sys.stdin)
        elif args.json_file:
            logger.info(f"JSON file: {args.json_file}")
            with open(args.json_file, "r") as f:
                data = json.load(f)
        else:
            result = {"success": False, "error": "Provide either json_file or --stdin"}
            print(json.dumps(result, indent=2))
            logger.error(result["error"])
            return 1
    except Exception as e:
        result = {"success": False, "error": f"Failed to load JSON: {e}"}
        print(json.dumps(result, indent=2))
        logger.error(result["error"])
        return 1

    logger.info(f"File hash: {args.file_hash}")
    if args.log_id:
        logger.info(f"Ingestion Log ID: {args.log_id}")
    logger.info("=" * 60)

    # Insert into database
    db = Database(db_path)
    result = insert_statement_data(db, data, args.file_hash)

    # Update ingestion log if provided
    if args.log_id and result["success"] and not result.get("duplicate_statement"):
        try:
            # Note: We'll update the final counts at the end of ingestion
            # For now, just log that we processed this statement
            logger.info(f"Updated ingestion log {args.log_id}")
        except Exception as e:
            logger.warning(f"Failed to update ingestion log: {e}")

    # Output JSON to stdout
    print(json.dumps(result, indent=2))

    if result["success"]:
        logger.info("Statement insertion completed successfully")
        return 0
    else:
        logger.error(f"Statement insertion failed: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
