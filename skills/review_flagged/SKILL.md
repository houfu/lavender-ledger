---
name: review-flagged
description: Interactively review flagged transactions to confirm or correct categorizations, and create rules based on user feedback.
---

# Review Flagged Transactions Skill

## Purpose

Present flagged transactions (low confidence < 0.7) to the user for review, accept corrections, and create categorization rules based on confirmed patterns. This skill enables the system to learn from user feedback and improve categorization accuracy over time.

**Important**: When executing this skill within Claude Code, use the **AskUserQuestion tool** to interact with the user, not the `scripts/review_flagged.py` script (which is for standalone CLI use).

## When to Use

- After ingestion when transactions are flagged for review
- When user explicitly requests to review flagged transactions
- Periodically to review accumulated flagged items

## Execution Methods

### Within Claude Code (Recommended)
Use the **AskUserQuestion tool** to present transactions and collect user feedback:
- Fetch flagged transactions from database
- Present each transaction using AskUserQuestion with options: Accept, Change category, Skip
- Update database based on user selections
- Append learnings to TRANSACTION_MEMORY.md

### Standalone CLI
Run `scripts/review_flagged.py` for command-line interactive review:
```bash
uv run python scripts/review_flagged.py [--log-id <id>]
```
This provides a full-featured CLI with rule creation options.

## Prerequisites

- Database initialized
- Flagged transactions exist (confidence_score < 0.7 OR flagged_for_review = 1)

## Workflow (Claude Code Method)

### Step 1: Fetch Flagged Transactions

Query database for all flagged transactions:

```python
from src.database.models import Database
from src.config import get_config

config = get_config()
db = Database(config['database_path'])

flagged = db.get_flagged_transactions()

if not flagged:
    print("No flagged transactions to review.")
    exit(0)

print(f"\n📋 Found {len(flagged)} flagged transaction(s) to review\n")
```

### Step 2: Present Each Transaction Using AskUserQuestion

**When using Claude Code**, use the AskUserQuestion tool to present transactions:

```python
from src.database.models import Database
from src.config import get_config

# Prepare transaction details for display
for txn in flagged:
    merchant = txn.merchant_cleaned or txn.merchant_original

    # Use AskUserQuestion tool with structured options
    questions = [{
        "question": f"Transaction: {merchant} (${abs(txn.amount):.2f}) on {txn.transaction_date}\nSuggested category: {txn.category}\nConfidence: {txn.confidence_score or 0:.2f}\n\nWhat would you like to do?",
        "header": "Review",
        "multiSelect": False,
        "options": [
            {
                "label": f"Accept as {txn.category}",
                "description": f"Keep the suggested category ({txn.category})"
            },
            {
                "label": "Change category",
                "description": "Select a different category from the list"
            },
            {
                "label": "Skip for now",
                "description": "Leave flagged and review later"
            }
        ]
    }]
```

**For standalone CLI review**, the script displays:

```
Transaction #12 (Confidence: 0.65)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Date:           2025-08-10
Merchant:       GRAB HOLDINGS
Amount:         -$35.50
Description:    Point-of-Sale Transaction
Suggested:      Dining & Restaurants

Actions:
  [A] Accept    - Keep as "Dining & Restaurants"
  [C] Change    - Specify a different category
  [R] Rule      - Accept and create rule for GRAB*
  [S] Skip      - Review later

Your choice: _
```

### Step 3: Handle User Actions

**Action: Accept (A)**
```python
# Unflag transaction, keep existing category
db.execute("""
    UPDATE transactions
    SET flagged_for_review = 0, confidence_score = 1.0
    WHERE id = ?
""", (txn_id,))
```

**Action: Change (C)**
```python
# Display available categories
categories = db.get_category_names()
for i, cat in enumerate(categories, 1):
    print(f"  {i}. {cat}")

choice = input("Enter category number: ")
new_category = categories[int(choice) - 1]

# Update transaction
db.update_transaction_category(
    transaction_id=txn_id,
    category=new_category,
    confidence_score=1.0,
    flagged=False
)
```

**Action: Rule (R)**
```python
# Accept categorization and offer rule creation
print(f"\nCreate rule: {merchant_pattern} → {category}")
print("\nRule conditions (optional):")
print("  [1] Any amount (simple pattern rule)")
print("  [2] Amount range (e.g., $20-50)")
print("  [3] Specific account type")
print("  [4] Add to memory instead (complex pattern)")
print("  [N] No rule, just accept")

choice = input("Choice: ")

if choice == "1":
    # Simple pattern rule
    rule = CategorizationRule(
        id=None,
        merchant_pattern=merchant_pattern,
        category=category,
        confidence=1.0,
        user_confirmed=True,
        auto_created=False,
        notes=f"User-created during review on {datetime.now()}"
    )
    db.create_rule(rule)

elif choice == "2":
    # Amount-based rule
    min_amt = input("Minimum amount (or Enter to skip): ")
    max_amt = input("Maximum amount (or Enter to skip): ")

    rule = CategorizationRule(
        id=None,
        merchant_pattern=merchant_pattern,
        category=category,
        confidence=1.0,
        rule_type="complex",
        min_amount=float(min_amt) if min_amt else None,
        max_amount=float(max_amt) if max_amt else None,
        user_confirmed=True,
        auto_created=False,
        notes=f"User-created with amount filter during review"
    )
    db.create_rule(rule)

elif choice == "4":
    # Add to memory file
    update_memory_file(merchant_pattern, category, txn)
```

**Action: Skip (S)**
```python
# Leave flagged, continue to next
continue
```

### Step 4: Update Transaction Memory

After review session, append learnings to `data/TRANSACTION_MEMORY.md`:

```python
def update_memory_file(learnings: list[dict]):
    memory_path = Path(config['data_directory']) / 'TRANSACTION_MEMORY.md'

    # Create from template if doesn't exist
    if not memory_path.exists():
        template = Path('TRANSACTION_MEMORY.template.md')
        if template.exists():
            shutil.copy(template, memory_path)

    # Append learnings
    with open(memory_path, 'a') as f:
        f.write(f"\n### Date: {datetime.now().strftime('%Y-%m-%d')} (Review Session)\n")
        for learning in learnings:
            if learning['action'] == 'confirmed':
                f.write(f"- Confirmed: \"{learning['merchant']}\" → {learning['category']}\n")
            elif learning['action'] == 'changed':
                f.write(f"- Rejected: \"{learning['merchant']}\" suggested as {learning['from_category']}, changed to {learning['to_category']}\n")
            elif learning['action'] == 'rule_created':
                f.write(f"- Created rule: {learning['pattern']} → {learning['category']}")
                if learning.get('conditions'):
                    f.write(f" (conditions: {learning['conditions']})")
                f.write("\n")
        f.write("\n")
```

### Step 5: Display Summary

```python
print("\n" + "=" * 60)
print("Review Complete!")
print("=" * 60)
print(f"Reviewed:      {reviewed_count}")
print(f"Accepted:      {accepted_count}")
print(f"Changed:       {changed_count}")
print(f"Rules created: {rules_created_count}")
print(f"Skipped:       {skipped_count}")
print("=" * 60)
```

## Example Session

```
📋 Found 3 flagged transaction(s) to review

Transaction #1 of 3 (Confidence: 0.65)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Date:           2025-08-10
Merchant:       AMAZON.COM
Amount:         -$45.99
Description:    Online Purchase
Suggested:      Shopping

Actions:
  [A] Accept    - Keep as "Shopping"
  [C] Change    - Specify a different category
  [R] Rule      - Accept and create rule for AMAZON*
  [S] Skip      - Review later

Your choice: C

Available categories:
  1. Groceries
  2. Dining & Restaurants
  ...
  14. Education
  ...

Enter category number: 14

✓ Updated to "Education"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Transaction #2 of 3 (Confidence: 0.68)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Date:           2025-08-15
Merchant:       GRAB HOLDINGS
Amount:         -$8.50
Description:    Point-of-Sale Transaction
Suggested:      Transportation

Actions:
  [A] Accept    - Keep as "Transportation"
  [C] Change    - Specify a different category
  [R] Rule      - Accept and create rule for GRAB*
  [S] Skip      - Review later

Your choice: R

Create rule: GRAB* → Transportation

Rule conditions (optional):
  [1] Any amount (simple pattern rule)
  [2] Amount range (e.g., $20-50)
  [3] Specific account type
  [4] Add to memory instead (complex pattern)
  [N] No rule, just accept

Choice: 2

Minimum amount (or Enter to skip):
Maximum amount (or Enter to skip): 15

✓ Created rule: GRAB* → Transportation (amount ≤ $15)
✓ Transaction accepted

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Transaction #3 of 3 (Confidence: 0.55)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Date:           2025-08-20
Merchant:       VENDOR XYZ
Amount:         -$120.00
Description:    Payment
Suggested:      Shopping

Actions:
  [A] Accept    - Keep as "Shopping"
  [C] Change    - Specify a different category
  [R] Rule      - Accept and create rule for VENDOR XYZ*
  [S] Skip      - Review later

Your choice: S

⏭  Skipped for later review

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

============================================================
Review Complete!
============================================================
Reviewed:      3
Accepted:      1
Changed:       1
Rules created: 1
Skipped:       1
============================================================

Memory updated: data/TRANSACTION_MEMORY.md
```

## Success Criteria

- ✅ User can review each flagged transaction
- ✅ User can accept, change, or skip categorizations
- ✅ Rules created based on user confirmation
- ✅ Complex rules supported (amount ranges, etc.)
- ✅ Memory file updated with learnings
- ✅ Clear summary displayed at end

## Integration Points

This skill is invoked by:
- **Ingestion skill** (Step 6) after categorization completes
- **Manual invocation** when user wants to review flagged items

Invocation from ingestion:
```bash
uv run python scripts/review_flagged.py
```

## Notes

- User-confirmed rules have `user_confirmed=True` and `auto_created=False`
- Auto-created rules have `user_confirmed=False` and `auto_created=True`
- Rules can be complex with amount ranges, account filters, etc.
- Memory file stores contextual learnings that don't fit structured rules
- Review can be done interactively during ingestion or as a separate batch later
