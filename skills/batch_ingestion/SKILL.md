---
name: batch-ingest
description: Process large volumes of bank statements (50+ PDFs) in batches with checkpointing and progress tracking. Orchestrates the standard ingestion skill across multiple batches for resumable processing.
---

# Batch Ingestion Skill

## Purpose

Process large volumes of bank statements (50+ PDFs) in manageable batches with:
- **Progress tracking** via TodoWrite
- **User verification** between batches
- **Resume capability** using database ingestion_log
- **Error recovery** without losing progress

## When to Use

- Processing 50+ PDFs at once
- Want to review progress between batches
- Need ability to pause and resume
- Want checkpointing in case of errors

## Prerequisites

- Database initialized (`uv run python scripts/init_db.py`)
- PDFs in staging folder (`data/statements/staging/`)
- Dashboard stopped (`docker compose down`)

## Workflow

### Phase 1: Discover and Plan

1. **Count PDFs in staging:**
```bash
ls data/statements/staging/*.pdf | wc -l
```

2. **Ask user for batch size:**
- Recommend 10-15 PDFs per batch
- Smaller batches = more checkpoints
- Larger batches = faster but less granular

3. **Create TodoWrite plan:**
```python
total_pdfs = 73  # from ls count
batch_size = 15
num_batches = (total_pdfs + batch_size - 1) // batch_size

todos = [
    {"content": f"Process batch {i+1} of {num_batches} ({batch_size} PDFs)",
     "status": "pending",
     "activeForm": f"Processing batch {i+1}"}
    for i in range(num_batches)
]
# Add final todo
todos.append({
    "content": "Restart dashboard after completion",
    "status": "pending",
    "activeForm": "Restarting dashboard"
})

# Use TodoWrite tool to create the plan
```

### Phase 2: Process Batches

For each batch:

1. **Mark batch as in_progress** using TodoWrite

2. **Get next batch of PDFs:**
```bash
ls data/statements/staging/*.pdf | head -n 15
```

3. **Run ingestion skill** on this batch:
- Use the standard `skills/ingestion/SKILL.md`
- Process all PDFs in the batch
- The ingestion skill will handle:
  - PDF reading and parsing
  - Database insertion
  - Categorization
  - Archiving
  - Error handling

4. **Mark batch as completed** using TodoWrite

5. **Show progress summary:**
```python
from src.database.models import Database
from src.config import get_config

config = get_config()
db = Database(config["database_path"])

# Get most recent ingestion log
log = db.get_last_ingestion_log()
if log:
    print(f"✓ Batch completed")
    print(f"  PDFs processed: {log.pdfs_processed}")
    print(f"  Transactions added: {log.transactions_added}")
    print(f"  Status: {log.status}")
```

6. **Ask user to continue:**
```
Batch X of Y completed. Continue to next batch? (yes/no)
```

If user says no: Stop and remind them they can resume later.

### Phase 3: Resume Capability

To resume an interrupted batch ingestion:

1. **Check remaining PDFs:**
```bash
ls data/statements/staging/*.pdf | wc -l
```

2. **Check TodoWrite list** to see which batches are pending

3. **Continue from where you left off** - just process the remaining batches

## Error Handling

If a PDF fails during batch processing:
- The ingestion skill will log the error
- Continue with remaining PDFs in batch
- Summarize failed PDFs at end of batch
- User can review and retry failed PDFs separately

## Progress Tracking

The ingestion skill automatically updates the `ingestion_log` table:
- Tracks PDFs processed
- Tracks transactions added/updated
- Records errors
- Stores summary

Query progress:
```python
from src.database.models import Database

db = Database("/path/to/finance.db")

# Get all ingestion runs
conn = db.get_connection()
logs = conn.execute("""
    SELECT started_at, completed_at, status, pdfs_processed, transactions_added
    FROM ingestion_log
    ORDER BY started_at DESC
    LIMIT 10
""").fetchall()

for log in logs:
    print(f"{log[0]}: {log[3]} PDFs, {log[4]} transactions ({log[2]})")
```

## Advantages Over Single Run

- **Checkpoint progress** - Resume anytime
- **User control** - Review between batches
- **Memory management** - Process in chunks
- **Error isolation** - One bad PDF doesn't stop everything

## Example Session

```
User: "I have 73 PDFs to process. Run batch ingestion."

Claude: I'll process them in batches of 15 PDFs each (5 batches total).

[Creates TodoWrite plan with 5 batch todos]

Processing batch 1 of 5...
[Runs ingestion skill on first 15 PDFs]
✓ Batch 1 completed: 15 PDFs, 287 transactions

Continue to batch 2?

User: yes

Processing batch 2 of 5...
[Continues...]
```

## Notes

- Uses the standard `skills/ingestion/SKILL.md` for actual processing
- No complex Python scripts required
- All state tracked in database + TodoWrite
- Can stop and resume anytime
- Simpler and more maintainable than old batch system
