#!/usr/bin/env python3
"""Interactive review of flagged transactions.

This script presents flagged transactions to the user for review, allows them to
accept, change, or skip categorizations, and creates rules based on user feedback.

Usage:
    uv run python scripts/review_flagged.py [--log-id <id>]
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.database.models import Database, CategorizationRule


def display_transaction(txn, index, total):
    """Display a transaction for review."""
    print(
        f"\nTransaction #{index} of {total} (Confidence: {txn.confidence_score or 0:.2f})"
    )
    print("━" * 60)
    print(f"Date:           {txn.transaction_date}")
    print(f"Merchant:       {txn.merchant_cleaned or txn.merchant_original}")
    print(f"Amount:         ${abs(txn.amount):.2f}")
    if txn.description:
        # Truncate long descriptions
        desc = (
            txn.description[:50] + "..."
            if len(txn.description) > 50
            else txn.description
        )
        print(f"Description:    {desc}")
    print(f"Suggested:      {txn.category or 'Uncategorized'}")
    print()


def get_user_action():
    """Get user's choice for this transaction."""
    print("Actions:")
    print("  [A] Accept    - Keep suggested category")
    print("  [C] Change    - Specify a different category")
    print("  [R] Rule      - Accept and create rule")
    print("  [S] Skip      - Review later")
    print()

    while True:
        choice = input("Your choice: ").strip().upper()
        if choice in ["A", "C", "R", "S"]:
            return choice
        print("Invalid choice. Please enter A, C, R, or S.")


def select_category(db):
    """Let user select a category."""
    categories = db.get_category_names()

    print("\nAvailable categories:")
    for i, cat in enumerate(categories, 1):
        print(f"  {i:2d}. {cat}")
    print()

    while True:
        try:
            choice = input("Enter category number: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(categories):
                return categories[idx]
            print(f"Please enter a number between 1 and {len(categories)}")
        except ValueError:
            print("Please enter a valid number")


def create_rule_interactive(db, txn, category):
    """Interactive rule creation with optional conditions."""
    merchant = txn.merchant_cleaned or txn.merchant_original
    # Generate pattern (add wildcard)
    pattern = f"{merchant}*" if not merchant.endswith("*") else merchant

    print(f"\nCreate rule: {pattern} → {category}")
    print("\nRule conditions (optional):")
    print("  [1] Any amount (simple pattern rule)")
    print("  [2] Amount range (e.g., $20-50)")
    print("  [3] Add to memory instead (for complex patterns)")
    print("  [N] No rule, just accept")
    print()

    choice = input("Choice: ").strip()

    if choice == "1":
        # Simple pattern rule
        rule = CategorizationRule(
            id=None,
            merchant_pattern=pattern,
            category=category,
            confidence=1.0,
            user_confirmed=True,
            auto_created=False,
            notes=f"User-created during review on {datetime.now().strftime('%Y-%m-%d')}",
        )

        # Check if rule already exists
        existing = db.get_rule_by_pattern(pattern)
        if existing:
            print(f"⚠️  Rule for {pattern} already exists → {existing.category}")
            overwrite = input("Overwrite? [y/N]: ").strip().lower()
            if overwrite != "y":
                print("✓ Transaction accepted (no rule created)")
                return None
            # Delete existing and create new
            db.execute("DELETE FROM categorization_rules WHERE id = ?", (existing.id,))

        rule_id = db.create_rule(rule)
        print(f"✓ Created rule: {pattern} → {category}")
        return {"pattern": pattern, "category": category, "type": "simple"}

    elif choice == "2":
        # Amount-based rule
        print()
        min_amt_str = input("Minimum amount (or Enter to skip): ").strip()
        max_amt_str = input("Maximum amount (or Enter to skip): ").strip()

        min_amt = float(min_amt_str) if min_amt_str else None
        max_amt = float(max_amt_str) if max_amt_str else None

        rule = CategorizationRule(
            id=None,
            merchant_pattern=pattern,
            category=category,
            confidence=1.0,
            rule_type="complex",
            min_amount=min_amt,
            max_amount=max_amt,
            user_confirmed=True,
            auto_created=False,
            notes=f"User-created with amount filter during review on {datetime.now().strftime('%Y-%m-%d')}",
        )

        existing = db.get_rule_by_pattern(pattern)
        if existing:
            print(f"⚠️  Rule for {pattern} already exists")
            overwrite = input("Overwrite? [y/N]: ").strip().lower()
            if overwrite != "y":
                print("✓ Transaction accepted (no rule created)")
                return None
            db.execute("DELETE FROM categorization_rules WHERE id = ?", (existing.id,))

        rule_id = db.create_rule(rule)
        conditions = []
        if min_amt:
            conditions.append(f"min ${min_amt:.2f}")
        if max_amt:
            conditions.append(f"max ${max_amt:.2f}")
        cond_str = ", ".join(conditions)
        print(f"✓ Created rule: {pattern} → {category} ({cond_str})")
        return {
            "pattern": pattern,
            "category": category,
            "type": "complex",
            "conditions": cond_str,
        }

    elif choice == "3":
        # Add to memory
        print("✓ Will add to transaction memory")
        return {"pattern": pattern, "category": category, "type": "memory"}

    else:
        print("✓ Transaction accepted (no rule created)")
        return None


def update_memory_file(config, learnings):
    """Append learnings to transaction memory file."""
    if not learnings:
        return

    memory_path = Path(config["data_directory"]) / "TRANSACTION_MEMORY.md"

    # Create from template if doesn't exist
    if not memory_path.exists():
        template = Path("TRANSACTION_MEMORY.template.md")
        if template.exists():
            import shutil

            memory_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(template, memory_path)
            print(f"\n📝 Created memory file from template: {memory_path}")

    # Append learnings
    with open(memory_path, "a") as f:
        f.write(f"\n### Date: {datetime.now().strftime('%Y-%m-%d')} (Review Session)\n")
        for learning in learnings:
            action = learning["action"]
            if action == "confirmed":
                f.write(
                    f"- Confirmed: \"{learning['merchant']}\" → {learning['category']}\n"
                )
            elif action == "changed":
                f.write(
                    f"- Rejected: \"{learning['merchant']}\" suggested as {learning['from_category']}, changed to {learning['to_category']}\n"
                )
            elif action == "rule_created":
                f.write(
                    f"- Created rule: {learning['pattern']} → {learning['category']}"
                )
                if learning.get("conditions"):
                    f.write(f" ({learning['conditions']})")
                f.write("\n")
        f.write("\n")

    print(f"\n📝 Memory updated: {memory_path}")


def main():
    parser = argparse.ArgumentParser(description="Review flagged transactions")
    parser.add_argument("--log-id", type=int, help="Ingestion log ID for tracking")
    args = parser.parse_args()

    config = get_config()
    db = Database(config["database_path"])

    # Get flagged transactions
    flagged = db.get_flagged_transactions()

    if not flagged:
        print("\n✓ No flagged transactions to review")
        return 0

    print(f"\n📋 Found {len(flagged)} flagged transaction(s) to review")

    # Track statistics
    reviewed_count = 0
    accepted_count = 0
    changed_count = 0
    skipped_count = 0
    rules_created_count = 0
    learnings = []

    # Review each transaction
    for i, txn in enumerate(flagged, 1):
        display_transaction(txn, i, len(flagged))
        action = get_user_action()

        merchant = txn.merchant_cleaned or txn.merchant_original

        if action == "A":
            # Accept - unflag and set confidence to 1.0
            db.update_transaction_category(
                transaction_id=txn.id,
                category=txn.category,
                confidence_score=1.0,
                flagged=False,
            )
            print("✓ Accepted")
            accepted_count += 1
            reviewed_count += 1
            learnings.append(
                {"action": "confirmed", "merchant": merchant, "category": txn.category}
            )

        elif action == "C":
            # Change category
            new_category = select_category(db)
            db.update_transaction_category(
                transaction_id=txn.id,
                category=new_category,
                confidence_score=1.0,
                flagged=False,
            )
            print(f'\n✓ Updated to "{new_category}"')
            changed_count += 1
            reviewed_count += 1
            learnings.append(
                {
                    "action": "changed",
                    "merchant": merchant,
                    "from_category": txn.category,
                    "to_category": new_category,
                }
            )

        elif action == "R":
            # Create rule
            rule_info = create_rule_interactive(db, txn, txn.category)

            # Unflag transaction
            db.update_transaction_category(
                transaction_id=txn.id,
                category=txn.category,
                confidence_score=1.0,
                flagged=False,
            )

            if rule_info:
                rules_created_count += 1
                learnings.append({"action": "rule_created", **rule_info})

            accepted_count += 1
            reviewed_count += 1

        elif action == "S":
            # Skip - leave flagged
            print("⏭  Skipped for later review")
            skipped_count += 1

        print("\n" + "━" * 60)

    # Update memory file
    update_memory_file(config, learnings)

    # Display summary
    print("\n" + "=" * 60)
    print("Review Complete!")
    print("=" * 60)
    print(f"Reviewed:      {reviewed_count}")
    print(f"Accepted:      {accepted_count}")
    print(f"Changed:       {changed_count}")
    print(f"Rules created: {rules_created_count}")
    print(f"Skipped:       {skipped_count}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
