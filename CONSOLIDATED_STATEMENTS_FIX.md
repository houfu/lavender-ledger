# Consolidated Statements Support - Implementation Summary

## Problem Statement

The original database schema assumed **1 PDF = 1 statement**, but consolidated bank statements (e.g., DBS Credit Cards with multiple cards) contain **multiple cards in a single PDF**, each requiring separate statement records.

### Original Schema Constraints

```sql
file_path TEXT NOT NULL UNIQUE,
file_hash TEXT NOT NULL UNIQUE,
```

These UNIQUE constraints prevented creating multiple statement records from the same PDF file.

## Solution Implemented

### Migration 004: Support Consolidated Statements

**File:** `migrations/004_support_consolidated_statements.sql`

**Changes:**
1. **Removed** UNIQUE constraint from `file_path`
2. **Removed** UNIQUE constraint from `file_hash`
3. **Added** compound UNIQUE constraint: `UNIQUE(file_hash, account_id)`

**Result:**
- ✅ Multiple cards from same PDF can each have their own statement record
- ✅ Same PDF can appear multiple times (different accounts)
- ✅ Cannot import the same card twice (prevents duplicates per account)

### Code Updates

#### 1. Database Models (`src/database/models.py`)

**Updated `statement_exists()` method:**

```python
def statement_exists(self, file_hash: str, account_id: Optional[int] = None) -> bool:
    """Check if a statement with this hash already exists.

    Args:
        file_hash: SHA256 hash of the PDF file
        account_id: Optional account ID to check compound key (file_hash, account_id).
                   If provided, checks if this specific account's statement exists.
                   If None, checks if ANY statement with this hash exists (legacy behavior).

    Returns:
        True if statement exists, False otherwise
    """
    if account_id is not None:
        # Check compound key (file_hash, account_id) for consolidated statements
        query = "SELECT 1 FROM statements WHERE file_hash = ? AND account_id = ?"
        params = (file_hash, account_id)
    else:
        # Legacy behavior: check if any statement with this hash exists
        query = "SELECT 1 FROM statements WHERE file_hash = ?"
        params = (file_hash,)
```

#### 2. Insert Statement Script (`scripts/insert_statement.py`)

**Reordered logic:**
1. Get/create account **first** (to obtain `account_id`)
2. Check for duplicates using **compound key** `(file_hash, account_id)`
3. Create statement if not duplicate

```python
# Get or create account first (needed for duplicate check)
account_name = account_info["account_name"]
account = db.get_account_by_name(account_name)
# ... create account if needed ...
account_id = account.id

# Check if statement already exists for this account (supports consolidated statements)
if db.statement_exists(file_hash, account_id=account_id):
    logger.warning(f"Statement with hash {file_hash} for account {account_id} already exists. Skipping.")
    return {"success": True, "duplicate_statement": True, "message": "Statement already processed"}
```

## Testing Results

### Example: DBS Credit Cards Consolidated Statement (April 2025)

**Single PDF contains 2 cards:**
1. LIVE FRESH DBS VISA PAYWAVE PLATINUM (ending 3347) - 39 transactions
2. DBS WOMAN'S WORLD MASTERCARD (ending 9390) - 46 transactions

**Database records created:**

```sql
-- Statements table
id  account_id  account_name                              file_hash        total_txns
2   2           LIVE FRESH DBS VISA PAYWAVE PLATINUM      e2b1475...       39
3   3           DBS WOMAN'S WORLD MASTERCARD              e2b1475...       46
```

**Key observations:**
- ✅ Both statements share the same `file_hash` (same PDF)
- ✅ Different `account_id` values (2 and 3)
- ✅ Compound UNIQUE constraint enforced: `(file_hash=e2b1475..., account_id=2)` and `(file_hash=e2b1475..., account_id=3)`
- ✅ No constraint violations
- ✅ Cannot insert the same card twice (duplicate detection works)

## Workflow for Consolidated Statements

### Ingestion Process

1. **Read PDF once** using Read tool
2. **Parse into multiple account_info structures** (one per card)
3. **For each card:**
   - Create separate JSON with `account_info` and transactions for that card
   - Insert using **same file_hash** (since it's the same PDF)
   - System creates separate accounts and statements automatically
   - Duplicate detection uses compound key `(file_hash, account_id)`

### Example JSON Structure

**Card 1:**
```json
{
  "account_info": {
    "bank_name": "DBS",
    "account_type": "credit_card",
    "account_name": "LIVE FRESH DBS VISA PAYWAVE PLATINUM",
    "account_number_last4": "3347",
    "statement_date": "2025-04-30"
  },
  "transactions": [ ... 39 transactions ... ]
}
```

**Card 2:**
```json
{
  "account_info": {
    "bank_name": "DBS",
    "account_type": "credit_card",
    "account_name": "DBS WOMAN'S WORLD MASTERCARD",
    "account_number_last4": "9390",
    "statement_date": "2025-04-30"
  },
  "transactions": [ ... 46 transactions ... ]
}
```

**Both inserted with same file_hash but different account names/IDs.**

## Backwards Compatibility

### Legacy Behavior Preserved

The updated `statement_exists()` method maintains backwards compatibility:

```python
# Old code (still works)
if db.statement_exists(file_hash):
    # Checks if ANY statement with this hash exists

# New code (consolidated statement support)
if db.statement_exists(file_hash, account_id=account_id):
    # Checks if THIS SPECIFIC ACCOUNT's statement exists
```

### Migration Safety

- ✅ Existing data preserved (copied to new table structure)
- ✅ All indexes recreated
- ✅ Foreign key constraints maintained
- ✅ No data loss during migration

## Benefits

1. **Accurate Representation:** Each credit card gets its own account and statement records
2. **Proper Balance Tracking:** Individual card balances tracked separately
3. **Correct Rewards:** Card-specific rewards programs properly attributed
4. **Better Reporting:** Dashboard can show per-card spending and trends
5. **Duplicate Prevention:** Cannot accidentally import same card twice
6. **Flexibility:** Supports any number of cards in consolidated statement

## Files Modified

1. **migrations/004_support_consolidated_statements.sql** (NEW)
2. **src/database/models.py** (MODIFIED - `statement_exists()` method)
3. **scripts/insert_statement.py** (MODIFIED - reordered duplicate check logic)

## Testing Checklist

- [x] Migration 004 applies cleanly
- [x] Compound UNIQUE constraint enforced
- [x] Multiple cards from same PDF can be inserted
- [x] Duplicate detection prevents re-importing same card
- [x] Legacy single-statement PDFs still work
- [x] Backwards compatibility maintained
- [ ] Full batch ingestion test with consolidated statements

## Known Limitations

### Token Consumption

Interactive PDF parsing via Claude Code is high quality but token-intensive:
- Current: ~45K tokens for 1 PDF (with consolidated statement complexity)
- Projected: ~5M tokens for 58 PDFs (exceeds 200K context limit by 25x)

**Recommendation:** For high-volume ingestion (50+ PDFs), consider:
- Processing smaller batches (5-10 files per session)
- Automated parsing script for simple statement formats
- Hybrid approach: automated for simple, interactive for complex

## Next Steps

1. ✅ **COMPLETED:** Fix consolidated statement schema
2. **PENDING:** Decide on batch ingestion approach for remaining 57 PDFs
   - Option A: Process in smaller batches (5-10 at a time)
   - Option B: Create automated pdfplumber-based script
   - Option C: Hybrid approach (automated for simple, interactive for complex)
3. **FUTURE:** Update dashboard to show per-card views for consolidated statements

## Summary

The consolidated statements issue has been **fully resolved**. The system now correctly handles:
- Single-account statements (existing functionality preserved)
- Multi-card consolidated statements (new functionality added)
- Duplicate prevention at the per-card level
- Backwards compatibility with existing code

The schema change enables accurate financial tracking for users with consolidated credit card statements, which is common in Singapore banks like DBS, OCBC, and UOB.
