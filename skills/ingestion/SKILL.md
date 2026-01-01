---
name: ingest
description: Extract transactions from PDF or CSV bank statements in the staging folder, categorize them using Claude AI, insert into database, and archive processed files. Use when you need to ingest, process, or import new bank statements (PDF or CSV format).
---

# Bank Statement Ingestion Skill

## Purpose
Extract transactions from PDF or CSV bank statements in the staging folder, categorize them using Claude AI, insert into database, and archive processed files. All runs are logged to the database for display on the dashboard history page.

## Invocation
```bash
claude ingest          # Command line
/ingest                # Claude Code CLI
```

## Prerequisites
- Database exists at path specified in config.yaml
- Statement files (PDF or CSV) placed in staging folder (`data/statements/staging/`)
- Dashboard stopped to avoid database locks
- Claude Code active (no API key needed!)

## Architecture

This skill orchestrates the ingestion workflow using Claude Code's native capabilities:
- **Read tool** - Native file reading (PDFs with perfect OCR, CSVs as plain text)
- **Bash tool** - Helper scripts for database operations
- **Skills** - pdf_parsing, csv_parsing, and categorization

Helper scripts used:
- **`scripts/insert_statement.py`** - Insert account, statement, transactions
- **`scripts/apply_categorizations.py`** - Apply categorization results
- **`scripts/archive_pdf.py`** - Move PDF to archive folder

Skills invoked:
- **`skills/pdf_parsing/SKILL.md`** - Parse PDF into structured transaction data
- **`skills/categorization/SKILL.md`** - Categorize transactions with confidence scores

## Workflow

### Step 1: Initialize

Load configuration and create ingestion log entry:

```python
from src.config import get_config
from src.database.models import Database, IngestionLog
from pathlib import Path
from datetime import datetime

config = get_config()
db_path = Path(config['database_path'])
staging_path = Path(config['statements']['staging_path'])

# Verify database exists
if not db_path.exists():
    print("❌ Database not found. Please run: uv run python scripts/init_db.py")
    exit(1)

# Create ingestion log entry
db = Database(str(db_path))
log = IngestionLog(
    id=None,
    started_at=datetime.now(),
    status='running'
)
log_id = db.create_ingestion_log(log)
print(f"🌸 Starting ingestion (log ID: {log_id})")
```

### Step 2: Discover Statement Files

Use Glob tool to find both PDFs and CSVs in staging folder:

```python
from pathlib import Path

# Find PDFs
pdf_pattern = f"{staging_path}/*.pdf"
pdf_files = glob(pdf_pattern)

# Find CSVs
csv_pattern = f"{staging_path}/*.csv"
csv_files = glob(csv_pattern)

# Combine all files
statement_files = pdf_files + csv_files
```

If no files found:
```python
if not statement_files:
    print("ℹ️  No statement files (PDF/CSV) found in staging folder")
    db.update_ingestion_log(
        log_id=log_id,
        status='completed',
        completed_at=datetime.now(),
        summary='No files to process'
    )
    exit(0)
```

Otherwise:
```python
print(f"📄 Found {len(statement_files)} statement file(s) to process:")
for file in statement_files:
    file_type = "PDF" if file.suffix.lower() == ".pdf" else "CSV"
    print(f"  - {file.name} ({file_type})")
print()
```

### Step 3: Parallel File Processing (OPTIMIZED)

**IMPORTANT: For large batches (>10 files), use parallel processing to improve efficiency.**

Process files in batches to minimize token usage and wall-clock time:

```python
BATCH_SIZE = 10  # Process 10 files at a time
file_batches = [statement_files[i:i+BATCH_SIZE] for i in range(0, len(statement_files), BATCH_SIZE)]

print(f"🚀 Processing {len(statement_files)} files in {len(file_batches)} batch(es) of up to {BATCH_SIZE}")
print()

for batch_num, batch_files in enumerate(file_batches, 1):
    print(f"📦 Batch {batch_num}/{len(file_batches)}: {len(batch_files)} files")
    # Process this batch using steps 3.1 through 3.5 below
```

For each **batch of statement files** (PDF or CSV), execute the following steps:

#### 3.1: Parallel Read & Hash Generation (OPTIMIZED)

**For batches with 5+ files, use parallel read operations:**

**Option A: Parallel file reading (fastest for large batches)**
```python
# Generate all file hashes first (can run in parallel via bash chaining)
file_data = []
for file_path in batch_files:
    file_type = "PDF" if file_path.suffix.lower() == ".pdf" else "CSV"
    file_data.append({
        "path": file_path,
        "type": file_type,
        "name": file_path.name
    })

# Batch hash generation using a single bash command
file_paths_str = " ".join([f'"{f["path"]}"' for f in file_data])
hash_results = run_bash(f'shasum -a 256 {file_paths_str}')

# Parse hash results and pair with files
for i, line in enumerate(hash_results.strip().split('\n')):
    file_hash = line.split()[0]
    file_data[i]['hash'] = file_hash
```

**Check for duplicates in batch:**
```python
# Filter out duplicates before reading content
non_duplicate_files = []
for fd in file_data:
    existing = db.get_statement_by_hash(fd['hash'])
    if existing:
        print(f"  ⏭️  Skipped: {fd['name']} (already processed)")
        skipped_count += 1
    else:
        non_duplicate_files.append(fd)

print(f"  📄 {len(non_duplicate_files)} new files to process (skipped {skipped_count} duplicates)")
```

**Read file contents in sequence (with progress indicator):**
```python
# Read all non-duplicate files
for i, fd in enumerate(non_duplicate_files, 1):
    print(f"  [{i}/{len(non_duplicate_files)}] Reading {fd['name']}...")

    # Use Read tool
    # Store content in fd['content'] for parsing step
    fd['content'] = read_file_content  # From Read tool result
```

**Option B: Sequential processing (simpler, for small batches <5 files)**
```python
# For small batches, process sequentially as before
for file_path in batch_files:
    file_type = "PDF" if file_path.suffix.lower() == ".pdf" else "CSV"
    print(f"\n📄 Processing {file_type}: {file_path.name}")

    # Read file content using Read tool
    # Generate hash
    file_hash = run_bash(f'shasum -a 256 "{file_path}"').split()[0]

    # Check duplicate
    existing_statement = db.get_statement_by_hash(file_hash)
    if existing_statement:
        print(f"  ⏭️  Skipped: Already processed")
        continue

    # Continue with parsing...
```

#### 3.2: Parse with Appropriate Skill

Now that you have the file content (from Read tool), invoke the correct parsing skill based on file type:

**For PDF files:**
1. Follow the instructions in `skills/pdf_parsing/SKILL.md`
2. Parse the PDF content you just read
3. Extract account_info and transactions
4. Return structured JSON

**For CSV files:**
1. Follow the instructions in `skills/csv_parsing/SKILL.md`
2. Parse the CSV content you just read
3. Extract account_info and transactions
4. Return structured JSON

The file content is already in your context from the Read tool - no need to pass it again.

**Expected output:** JSON matching the format in `skills/pdf_parsing/SKILL.md`:
```json
{
  "account_info": {
    "bank_name": "DBS",
    "account_type": "savings",
    "account_name": "DBS eMulti-Currency Autosave Account (...9653)",
    "last_four": "9653",
    "statement_date": "2025-08-31",
    "period_start": "2025-08-01",
    "period_end": "2025-08-31"
  },
  "transactions": [...]
}
```

Confirm parsing completed:
```python
print(f"  ✓ Parsed {len(parsed_data['transactions'])} transactions")
```

#### 3.3: Insert Statement Data

Pass parsed data via stdin to insert_statement.py (no temp files created):

```bash
echo '{json.dumps(parsed_data)}' | uv run python scripts/insert_statement.py --stdin \
  --log-id {log_id} \
  --file-hash "{file_hash}"
```

**Capture JSON output:**
```json
{
  "success": true,
  "statement_id": 2,
  "account_id": 2,
  "transactions_inserted": 35,
  "transactions_duplicate": 0,
  "duplicate_statement": false
}
```

If `duplicate_statement` is true:
```python
print(f"  ⏭️  Skipped (already processed)")
continue  # Skip to next PDF
```

Otherwise:
```python
print(f"  ✓ Inserted {result['transactions_inserted']} transactions")
# Track totals for final summary
total_transactions_added += result['transactions_inserted']
pdfs_processed += 1
```

#### 3.4: Batch Categorization (OPTIMIZED)

**Process categorization for the entire batch after all files are inserted:**

```python
# After all files in batch are inserted, categorize all new transactions at once
print(f"\n🏷️  Categorizing transactions from batch {batch_num}...")

# Get all uncategorized transactions from this batch
# (filter by statement IDs from this batch)
batch_statement_ids = [result['statement_id'] for result in batch_insert_results]
uncategorized = db.get_uncategorized_transactions()
batch_txns = [t for t in uncategorized if t.statement_id in batch_statement_ids]

if not batch_txns:
    print(f"  ✓ No new transactions to categorize")
else:
    print(f"  📊 Found {len(batch_txns)} transactions to categorize")
```

**Tier 1: Rule-based categorization (fast)**

Apply existing rules first to reduce Claude API calls:
```python
auto_categorized = 0
for txn in batch_txns:
    merchant = txn.merchant_cleaned or txn.merchant_original
    rule = db.find_matching_rule(merchant)
    if rule:
        db.update_transaction_category(
            transaction_id=txn.id,
            category=rule.category,
            confidence_score=rule.confidence,
            flagged=False
        )
        db.increment_rule_usage(rule.id)
        auto_categorized += 1

if auto_categorized > 0:
    print(f"  ✓ Auto-categorized {auto_categorized} transactions using existing rules")
```

**Tier 2: Claude-based batch categorization (optimized)**

Process remaining transactions in sub-batches of 50-100 to avoid hitting rate limits:

```python
# Get remaining uncategorized after rules
still_uncategorized = [t for t in batch_txns if t.category is None]

if still_uncategorized:
    # Load transaction memory for context-aware categorization
    memory_path = Path(config['data_directory']) / 'TRANSACTION_MEMORY.md'
    memory_context = ""
    if memory_path.exists():
        with open(memory_path) as f:
            memory_context = f.read()
        print("  📖 Loaded transaction memory for context")

    # Process in sub-batches of 100 transactions
    CATEGORIZATION_BATCH_SIZE = 100
    cat_batches = [still_uncategorized[i:i+CATEGORIZATION_BATCH_SIZE]
                   for i in range(0, len(still_uncategorized), CATEGORIZATION_BATCH_SIZE)]

    print(f"  🤖 Categorizing {len(still_uncategorized)} transactions with Claude AI in {len(cat_batches)} sub-batch(es)")

    for cat_batch_num, cat_batch in enumerate(cat_batches, 1):
        print(f"    Sub-batch {cat_batch_num}/{len(cat_batches)}: {len(cat_batch)} transactions")

        # Prepare categorization input
        categorization_input = {
            "transactions": [
                {
                    "id": t.id,
                    "date": t.transaction_date,
                    "amount": float(t.amount),
                    "merchant_original": t.merchant_original,
                    "merchant_cleaned": t.merchant_cleaned or t.merchant_original,
                    "description": t.description or "",
                    "account_type": "credit_card"  # Infer from statement
                }
                for t in cat_batch
            ],
            "available_categories": db.get_category_names(),
            "existing_rules": [
                {"pattern": r.merchant_pattern, "category": r.category}
                for r in db.get_all_rules()
            ],
            "memory_context": memory_context
        }

        # Invoke categorization skill
        # (Follow categorization skill instructions with the input above)
        # Store results in categorization_results variable

        # Apply categorizations
        apply_result = run_bash(f'''
            echo '{json.dumps(categorization_results)}' | uv run python scripts/apply_categorizations.py --stdin \\
              --log-id {log_id} \\
              --confidence-threshold 0.7
        ''')

        print(f"      ✓ Categorized {apply_result['updated']} transactions")
        if apply_result['flagged'] > 0:
            print(f"      ⚠️  {apply_result['flagged']} flagged for review")
            flagged_count += apply_result['flagged']
```

**Expected improvement:** Categorizing 100 transactions at once instead of 10-20 per file reduces:
- API calls by 5-10x
- Rate limit risk
- Wall-clock time

#### 3.5: Archive PDF

Use Bash tool to run archive_pdf.py:

```bash
uv run python scripts/archive_pdf.py "{pdf_path}" \
  "{account_name}" \
  "{statement_date}" \
  --log-id {log_id}
```

Capture result:
```python
if result['success']:
    print(f"  ✓ Archived to: {Path(result['archive_path']).relative_to(archive_base)}")
else:
    print(f"  ⚠️  Archive failed: {result['error']}")
```

### Step 4: Finalize Ingestion Log

After processing all PDFs, update the ingestion log:

```python
summary = f"Processed {pdfs_processed} PDF(s), added {total_transactions_added} transactions"
if flagged_count > 0:
    summary += f", {flagged_count} flagged for review"

db.update_ingestion_log(
    log_id=log_id,
    status='completed',
    completed_at=datetime.now(),
    pdfs_processed=pdfs_processed,
    transactions_added=total_transactions_added,
    transactions_updated=0,
    errors=None if errors == 0 else f"{errors} error(s) occurred",
    summary=summary
)
```

### Step 5: Display Summary

```python
print()
print("=" * 60)
print("🌸 Ingestion Complete!")
print("=" * 60)
print(f"PDFs processed: {pdfs_processed}")
print(f"Transactions added: {total_transactions_added}")
if flagged_count > 0:
    print(f"Flagged for review: {flagged_count}")
print()
print("📊 View results:")
print(f"  - Dashboard: http://127.0.0.1:5000")
print(f"  - History: http://127.0.0.1:5000/history")
print()
print("⚠️  Don't forget to restart the dashboard:")
print("  docker compose up -d dashboard")
print()
```

### Step 6: Interactive Review (Optional)

If there are flagged transactions, offer interactive review.

**When executing within Claude Code**, use the **AskUserQuestion tool** to review flagged transactions:

```python
if flagged_count > 0:
    print(f"\n⚠️  {flagged_count} transaction(s) flagged for review (low confidence)")
    print()

    # Within Claude Code: Use AskUserQuestion tool to review flagged transactions
    # Follow the workflow in skills/review_flagged/SKILL.md
    # 1. Fetch flagged transactions from database
    # 2. For each transaction, use AskUserQuestion to present options
    # 3. Update database based on user selections
    # 4. Append learnings to data/TRANSACTION_MEMORY.md
```

**For standalone CLI execution**, use subprocess to run the review script:

```python
if flagged_count > 0:
    response = input("Review flagged transactions now? [Y/n]: ").strip().lower()

    if response in ['y', 'yes', '']:
        print("\nStarting interactive review...\n")
        import subprocess
        result = subprocess.run(
            ['uv', 'run', 'python', 'scripts/review_flagged.py', '--log-id', str(log_id)],
            capture_output=False  # Let user interact directly
        )

        if result.returncode == 0:
            print("\n✓ Review completed successfully")
        else:
            print(f"\n⚠️  Review exited with code {result.returncode}")
    else:
        print("Skipped review. View flagged items in dashboard:")
        print("  http://127.0.0.1:5000/flagged")
```

## Error Handling

- If any script fails (success=false in JSON), log the error and continue with next PDF
- Track errors in ingestion log
- Never stop the entire process due to one bad PDF
- Always finalize ingestion log even if errors occurred

## Logging

All scripts write to:
- **File**: `data/logs/ingestion_TIMESTAMP.log` (detailed debugging)
- **Database**: `ingestion_log` table (for dashboard display)
- **Stderr**: Progress messages (visible during execution)
- **Stdout**: JSON results (captured by skill)

## Database Tables Used

- **`ingestion_log`** - Track runs and display in history page
- **`accounts`** - Create/get accounts
- **`statements`** - Track processed PDFs (file_hash prevents duplicates)
- **`transactions`** - Store individual transactions
- **`categorization_rules`** - Match merchants to categories

## Singapore-Specific Handling

The pdf_parsing and categorization skills are aware of Singapore banks and merchants:
- **Banks**: DBS, POSB, Standard Chartered, Citibank, OCBC, UOB
- **Payment methods**: PayNow, FAST, GIRO, PayLah, GrabPay
- **Merchants**: IRAS (taxes), CDP (dividends), Smart Buddy (school canteen), LittleLives, etc.
- **Amount sign convention**: Expenses negative, income positive

## Success Criteria

- ✅ All PDFs processed or skipped (duplicates)
- ✅ Transactions inserted into database
- ✅ Categorizations applied with confidence scores
- ✅ Low-confidence items flagged for review
- ✅ PDFs archived to organized folders
- ✅ Ingestion log created for dashboard display
- ✅ Summary displayed to user

## Performance Optimization (New in v2.0)

### Batch Processing Benefits

**Previous approach (serial):**
- 59 PDFs × 7 min/file = ~7 hours
- 59 PDF reads + 59 parses + 59 inserts + 59 categorizations = ~236 operations
- High risk of hitting rate limits
- Required multiple sessions with manual resumption

**Optimized approach (batched):**
- 59 PDFs ÷ 10 files/batch = 6 batches × 15 min/batch = **~90 minutes**
- Batch hash generation + batch categorization = **~70 operations** (70% reduction)
- Lower rate limit risk (distributed across batches)
- Single session completion

### Key Optimizations

1. **Parallel hash generation**: All files in batch hashed in one `shasum` call
2. **Duplicate filtering upfront**: Skip reading files that are already processed
3. **Batch categorization**: 100 transactions per API call instead of 10-20
4. **Progressive learning**: Rules learned in earlier batches improve later batches

### Expected Performance (59 PDFs)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Wall-clock time** | 7-8 hours | 60-90 min | **5-6x faster** |
| **API calls** | ~120 | ~25 | **80% reduction** |
| **Sessions needed** | 2-3 | 1 | **Single run** |
| **Rate limit risk** | High | Low | **Minimal risk** |
| **Categorization backlog** | Large (814 txns) | None | **0% backlog** |

## Notes

- **Run time**: 10-15 min per batch of 10 files (~1-2 hours for 60 files)
- **API calls**: ~2-4 per batch (parsing + categorization) instead of per-file
- **Duplicate handling**: Automatic via file_hash and UNIQUE constraints
- **Dashboard**: Stop before ingestion, restart after
- **Debugging**: Check `data/logs/` for detailed logs
- **History**: View all runs at http://127.0.0.1:5000/history
- **Batch size**: Configurable (default 10 files) - increase for faster processing on powerful machines
