#!/usr/bin/env python3
"""Apply categorization results to transactions in the database.

This script takes JSON output from the categorization skill and updates
transaction categories in the database.

Usage:
    uv run python scripts/apply_categorizations.py <json_file> [--log-id <id>]
    echo '{"categorizations": [...]}' | uv run python scripts/apply_categorizations.py --stdin [--log-id <id>]

Input JSON format (from categorization skill):
    {
        "categorizations": [
            {
                "transaction_id": 1,
                "category": "Groceries",
                "confidence": 0.95,
                "rule_pattern": "WHOLEFDS*",
                "reasoning": "..."
            }
        ]
    }

Output (JSON to stdout):
    {
        "success": true,
        "updated": 35,
        "flagged": 2,
        "errors": 0
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


def apply_categorizations(
    db: Database,
    categorizations: list[dict],
    confidence_threshold: float = 0.7,
    auto_create_rules: bool = True,
) -> dict:
    """Apply categorization results to database and optionally auto-create rules.

    Args:
        db: Database instance.
        categorizations: List of categorization results.
        confidence_threshold: Threshold for flagging low-confidence categorizations.
        auto_create_rules: Whether to auto-create rules from high-confidence suggestions.

    Returns:
        Dictionary with application results including rules_created count.
    """
    logger = logging.getLogger(__name__)

    try:
        updated = 0
        flagged = 0
        errors = 0
        rules_created = []

        for cat in categorizations:
            try:
                transaction_id = cat["transaction_id"]
                category = cat["category"]
                confidence = float(cat["confidence"])
                should_flag = confidence < confidence_threshold

                # Update transaction
                db.update_transaction_category(
                    transaction_id=transaction_id,
                    category=category,
                    confidence_score=confidence,
                    flagged=should_flag,
                )

                updated += 1
                if should_flag:
                    flagged += 1
                    logger.debug(
                        f"Transaction {transaction_id} flagged for review "
                        f"(confidence: {confidence:.2f})"
                    )
                else:
                    logger.debug(
                        f"Transaction {transaction_id} categorized as '{category}' "
                        f"(confidence: {confidence:.2f})"
                    )

                # NEW: Auto-create rules for high-confidence patterns
                if auto_create_rules and cat.get("rule_pattern"):
                    rule_pattern = cat["rule_pattern"]
                    # Only create rules for high confidence (>=0.85)
                    if confidence >= 0.85:
                        # Check if rule already exists
                        existing = db.get_rule_by_pattern(rule_pattern)
                        if not existing:
                            from src.database.models import CategorizationRule

                            rule = CategorizationRule(
                                id=None,
                                merchant_pattern=rule_pattern,
                                category=category,
                                confidence=confidence,
                                auto_created=True,
                                user_confirmed=False,
                                notes=f"Auto-created: {cat.get('reasoning', '')[:100]}",
                            )
                            rule_id = db.create_rule(rule)
                            rules_created.append(
                                {"pattern": rule_pattern, "category": category}
                            )
                            logger.info(
                                f"Created rule: {rule_pattern} → {category} "
                                f"(confidence: {confidence:.2f}, rule_id: {rule_id})"
                            )

            except Exception as e:
                errors += 1
                logger.error(
                    f"Error updating transaction {cat.get('transaction_id')}: {e}"
                )

        logger.info(
            f"Applied {updated} categorizations, {flagged} flagged for review, "
            f"{len(rules_created)} rules created, {errors} errors"
        )

        return {
            "success": True,
            "updated": updated,
            "flagged": flagged,
            "errors": errors,
            "rules_created": len(rules_created),
            "new_rules": rules_created,
        }

    except Exception as e:
        logger.error(f"Error applying categorizations: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Apply categorization results to database"
    )
    parser.add_argument(
        "json_file",
        type=Path,
        nargs="?",
        help="JSON file with categorization results (deprecated, use --stdin)",
    )
    parser.add_argument(
        "--stdin", action="store_true", help="Read JSON from stdin instead of file"
    )
    parser.add_argument("--log-id", type=int, help="Ingestion log ID for tracking")
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for flagging (default: 0.7)",
    )
    parser.add_argument(
        "--auto-create-rules",
        action="store_true",
        default=True,
        help="Auto-create rules from high-confidence categorizations (default: True)",
    )
    parser.add_argument(
        "--no-auto-create-rules",
        dest="auto_create_rules",
        action="store_false",
        help="Disable auto-rule creation",
    )
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
    logger.info("Categorization Application Started")

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
            print(json.dumps(result, indent=2), file=sys.stderr)
            logger.error(result["error"])
            return 1
    except Exception as e:
        result = {"success": False, "error": f"Failed to load JSON: {e}"}
        print(json.dumps(result, indent=2))
        logger.error(result["error"])
        return 1

    logger.info(f"Confidence threshold: {args.confidence_threshold}")
    logger.info(f"Auto-create rules: {args.auto_create_rules}")
    if args.log_id:
        logger.info(f"Ingestion Log ID: {args.log_id}")
    logger.info("=" * 60)

    # Apply categorizations
    db = Database(config["database_path"])
    result = apply_categorizations(
        db, data["categorizations"], args.confidence_threshold, args.auto_create_rules
    )

    # Output JSON to stdout
    print(json.dumps(result, indent=2))

    if result["success"]:
        logger.info("Categorization application completed successfully")
        return 0
    else:
        logger.error(f"Categorization application failed: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
