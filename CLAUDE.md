# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Lavender Ledger** is a personal expense tracking application that ingests PDF bank statements, automatically categorizes transactions using Claude AI, and displays spending patterns via a family-friendly dashboard.

**Key characteristics:**
- Single-user ingestion workflow (you) via local Python scripts with uv
- Read-only family dashboard via Docker
- Cloud-synced data directory (Dropbox/iCloud) for backup
- Warm, approachable lilac-themed design
- All transaction editing happens during ingestion via Claude Code, never in the dashboard

## Essential Commands

### Environment Setup
```bash
uv sync                              # Install dependencies
```

### Database
```bash
uv run python scripts/init_db.py     # Initialize database (first time)
uv run python scripts/migrate.py     # Run pending migrations
uv run python scripts/migrate.py --status  # Check migration status
```

### Ingestion Workflow (Claude Code Skills Only)
```bash
# 1. Stop dashboard before ingesting
docker compose down

# 2. Place PDFs in data/statements/staging/

# 3. Ask Claude Code to run ingestion
# "Please run the ingestion skill to process the PDFs in staging"
# Claude Code will execute the ingestion workflow using skills:
#   - Read PDF natively (perfect OCR, preserves tables)
#   - Parse PDF (via pdf_parsing skill)
#   - Insert data (via helper script)
#   - Categorize transactions (via categorization skill)
#   - Archive PDFs (via helper script)

# 4. Review flagged transactions if needed (Claude Code will prompt)

# 5. Restart dashboard after completion
docker compose up -d dashboard
```

**No API key required!** Claude Code provides all AI capabilities directly.

### Dashboard
```bash
# Local development
uv run python scripts/run_dashboard.py    # Run at http://localhost:5000

# Docker deployment (family access)
docker compose build                      # Build image
docker compose up -d dashboard            # Start in background
docker compose down                       # Stop (before ingestion)
docker compose logs -f dashboard          # View logs
```

### Code Quality
```bash
uv run black .                       # Format all Python code
uv run pytest tests/                 # Run tests
```

## Working with Claude Code

### What is Claude Code?
Claude Code is an AI-powered development assistant that can execute tasks, run commands, read/write files, and follow complex workflows. Lavender Ledger is designed to leverage Claude Code's capabilities through **skills**.

### Skills
Skills are markdown documents (`SKILL.md`) that define structured workflows for Claude Code to follow. They live in the `skills/` directory:

**Core Ingestion:**
- **`skills/ingestion/SKILL.md`** - Orchestrates the full PDF ingestion workflow
- **`skills/pdf_parsing/SKILL.md`** - Parses bank statement PDFs into structured JSON
- **`skills/csv_parsing/SKILL.md`** - Parses CSV bank statements into structured JSON
- **`skills/categorization/SKILL.md`** - Categorizes transactions with confidence scores

**Batch & Memory:**
- **`skills/batch_ingestion/SKILL.md`** - Process 50+ PDFs in batches with checkpointing
- **`skills/memory/SKILL.md`** - Manage transaction memory for categorization context

**Helpers:**
- **`skills/review_flagged/SKILL.md`** - Review flagged transactions

### How to Use Skills
Simply ask Claude Code to perform a task, and it will follow the relevant skill automatically:

```
You: "Please run the ingestion skill to process the PDFs in staging"

Claude Code will:
1. Read skills/ingestion/SKILL.md
2. Execute each step (extract, parse, insert, categorize, archive)
3. Invoke sub-skills (pdf_parsing, categorization) as needed
4. Report progress and results
```

### Why Skills?
- **No API keys needed** - Claude Code provides the AI intelligence directly
- **Consistent workflow** - Skills document the exact steps to follow
- **Maintainable** - Update the skill document instead of scattered code
- **Transparent** - See exactly what Claude Code will do before it runs
- **Interactive** - Claude Code can ask for clarification during execution

### Prerequisites for Ingestion
Before running ingestion via Claude Code:
1. ✅ Database initialized (`uv run python scripts/init_db.py`)
2. ✅ PDFs placed in staging folder (`data/statements/staging/`)
3. ✅ Dashboard stopped (`docker compose down`)
4. ✅ Claude Code active in this project directory

That's it! No API keys, no configuration - just ask Claude Code to run ingestion.

## Architecture

### Tech Stack
- **Language:** Python 3.11+
- **Environment:** uv for dependency management
- **Database:** SQLite 3
- **PDF Processing:** Claude Code native PDF reading (perfect OCR, preserves tables)
- **AI/Automation:** Claude Code with skills for parsing and categorization
- **Web Framework:** Flask
- **Frontend:** HTML/CSS/JavaScript with Chart.js/Plotly
- **Container:** Docker & Docker Compose (dashboard only)

### Repository Structure
```
lavender-ledger/                     # Git repository
├── pyproject.toml                   # uv project configuration
├── config.example.yaml              # Example config (in repo)
├── config.yaml                      # Actual config (gitignored)
├── CLAUDE.md                        # This file - instructions for Claude Code
├── Dockerfile                       # Dashboard container
├── docker-compose.yml               # Dashboard service
├── src/
│   ├── ingestion/                   # (Deprecated - use skills instead)
│   │   ├── pdf_parser.py
│   │   ├── categorizer.py
│   │   └── importer.py
│   ├── dashboard/
│   │   ├── app.py                   # Flask application
│   │   ├── queries.py               # Read-only database queries
│   │   └── templates/               # HTML templates with lilac theme
│   ├── database/
│   │   ├── schema.sql               # Database schema definition
│   │   └── models.py                # Database access layer
│   └── config.py                    # Configuration loader
├── skills/                          # Claude Code skills
│   ├── ingestion/
│   │   └── SKILL.md                 # Full ingestion workflow orchestrator
│   ├── pdf_parsing/
│   │   └── SKILL.md                 # PDF parsing skill (any bank format)
│   └── categorization/
│       └── SKILL.md                 # Transaction categorization skill
├── migrations/
│   ├── README.md                    # Migration system documentation
│   └── 001_add_ingestion_log.sql   # Migration files (versioned)
├── scripts/
│   ├── ingest.py                    # (Deprecated - use skills)
│   ├── insert_statement.py          # Helper: Insert parsed data to DB
│   ├── apply_categorizations.py     # Helper: Apply categorizations to DB
│   ├── archive_pdf.py               # Helper: Move PDF to archive
│   ├── run_dashboard.py             # Local dashboard dev server
│   ├── init_db.py                   # Database initialization
│   └── migrate.py                   # Migration runner
└── tests/
```

### Data Directory (Cloud-Synced, Gitignored)
```
~/Dropbox/PersonalFinance/           # Or iCloud/Google Drive
├── finance.db                       # SQLite database
└── statements/
    ├── staging/                     # New PDFs placed here
    └── archive/                     # Organized after processing
        ├── chase-credit/
        ├── bofa-checking/
        └── amex-platinum/
```

### Configuration
- Copy `config.example.yaml` to `config.yaml` and customize
- `config.yaml` is gitignored (contains paths and API keys)
- Database and PDFs live in cloud-synced directory, not repo

## Database Schema

### Key Tables
- `accounts`: Bank accounts and credit cards being tracked
- `statements`: PDFs that have been processed (links to source file)
- `transactions`: Individual transaction records
- `categorization_rules`: Learned patterns (e.g., "WHOLEFDS*" → Groceries)
- `categories`: Available spending categories with colors

### Important Constraints
- Duplicate detection via `(account_id, transaction_date, amount, merchant_original)` unique constraint
- Statement duplicate detection via `file_hash` (SHA256 of PDF)
- Foreign keys enforce referential integrity

### Database Migrations

The project uses a versioned migration system to manage schema changes systematically.

**Key Tables:**
- `schema_migrations`: Tracks which migrations have been applied (version, name, applied_at)

**Migration Files:**
- Location: `migrations/` directory
- Naming: `{version}_{description}.sql` (e.g., `001_add_ingestion_log.sql`)
- Version: 3-digit zero-padded number (001, 002, 003...)

**How It Works:**
1. Base schema (in `schema.sql`) creates core tables
2. Migration runner checks `schema_migrations` table for applied migrations
3. Pending migrations are applied in version order
4. Each applied migration is recorded in `schema_migrations`
5. Migrations are idempotent - safe to run multiple times

**Commands:**
```bash
# Apply all pending migrations
uv run python scripts/migrate.py

# Check migration status (see what's applied/pending)
uv run python scripts/migrate.py --status
```

**Creating New Migrations:**
1. Create file: `migrations/{next_version}_{description}.sql`
2. Add SQL statements with descriptive header comment
3. Run `scripts/migrate.py` to apply

**Example Migration:**
```sql
-- Migration: Add ingestion_log table
-- Version: 001
-- Description: Track when data was last updated

CREATE TABLE IF NOT EXISTS ingestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT CHECK(status IN ('running', 'completed', 'failed')),
    ...
);

CREATE INDEX IF NOT EXISTS idx_ingestion_log_completed ON ingestion_log(completed_at);
```

**Best Practices:**
- Always use `CREATE TABLE IF NOT EXISTS` for safety
- Always create indexes for foreign keys and frequently queried columns
- Test migrations on a copy of the database first
- Migrations should be forward-only (no rollbacks)
- Document the purpose in header comments

## Ingestion System Architecture

### Workflow Overview
The ingestion process is orchestrated by Claude Code using the `skills/ingestion/SKILL.md` skill:

1. **PDF Discovery:** Scan staging folder for PDFs using Glob tool
2. **Native PDF Reading:** Claude Code reads PDF directly using Read tool
   - Perfect OCR (no pdfplumber artifacts)
   - Preserves table structure for easy parsing
   - Visual layout awareness
3. **File Hash Generation:** Generate SHA256 hash via `shasum` for duplicate detection
4. **Claude Code PDF Parsing:** Claude Code follows `skills/pdf_parsing/SKILL.md` to:
   - Parse PDF content into structured data
   - Identify account information (bank, type, account number, dates)
   - Extract all transactions (date, amount, merchant, type)
   - Return JSON with account_info and transactions
5. **Database Insertion:** Insert parsed data via `scripts/insert_statement.py`
   - Creates/retrieves account record
   - Inserts statement record (with file_hash for duplicate detection)
   - Inserts transactions (with UNIQUE constraint for duplicate detection)
6. **Rule-Based Categorization:** Apply existing patterns from `categorization_rules` table
7. **Claude Code Categorization:** Claude Code follows `skills/categorization/SKILL.md` to:
   - Categorize uncategorized transactions
   - Assign confidence scores
   - Suggest new merchant pattern rules
8. **Apply Categorizations:** Update database via `scripts/apply_categorizations.py`
   - Flag low-confidence items (<0.7) for review
9. **Statement Archiving:** Move PDF to organized archive via `scripts/archive_pdf.py`
10. **Summary Report:** Display results and remind user to restart dashboard

### Skills Architecture
The ingestion workflow uses three skills:

**1. `skills/ingestion/SKILL.md`** (Orchestrator)
- Coordinates the entire ingestion workflow
- Uses Claude Code's Read tool for native PDF reading
- Calls helper scripts for database operations
- Invokes pdf_parsing and categorization skills
- Generates file hashes for duplicate detection
- Logs progress to database (ingestion_log table)

**2. `skills/pdf_parsing/SKILL.md`** (PDF Parser)
- Claude Code parses PDF content from Read tool
- Works with any bank format (DBS, Chase, BofA, Amex, Wells Fargo, credit unions, etc.)
- No hardcoded bank-specific regex parsers required
- Adapts to format changes automatically
- Leverages perfect OCR and preserved table structure
- Extracts transactions with proper amount signs and types
- Returns structured JSON

**3. `skills/categorization/SKILL.md`** (Categorizer)
- Claude Code categorizes transactions in-context
- Assigns categories with confidence scores
- Suggests merchant pattern rules for future automation
- Handles Singapore-specific merchants and payment methods

**Benefits of This Approach:**
- **Zero cost** - No API calls, Claude Code provides all intelligence
- **Better PDF parsing** - Native Read tool has perfect OCR, preserves tables
- **Fully integrated** - Everything happens in Claude Code session
- **Interactive** - Can ask user questions during workflow
- **Transparent** - User sees every step
- **Maintainable** - Skills are documentation + code
- **Logged** - Full history in database for dashboard

### Categorization Strategy
1. **Check rules database first** (fast, deterministic, 100% confidence)
2. **Invoke Claude Code categorization skill** for remaining uncategorized transactions
3. **Flag for review** if confidence < 0.7
4. **Learn new rules** based on user feedback during review

### Interactive Review (Via Claude Code)
- All transaction editing happens during ingestion
- Claude Code prompts user to review flagged transactions
- User can accept/reject/modify categorizations
- New rules are created based on user input
- Dashboard is read-only and never used for editing

## Dashboard Architecture

### Read-Only Design
- All database queries use `SELECT` only
- SQLite connection opened with `?mode=ro` flag
- No POST endpoints for modifications
- Dashboard stopped during ingestion to avoid locking

### Design Theme: Warm & Approachable
- **Color Palette:** Lilac/lavender theme (`#C8B6E2`, `#9B7EBD`, `#E6D5F5`)
- **Typography:** Rounded, friendly fonts (Nunito, Quicksand)
- **Cards:** Rounded corners (16px), soft shadows
- **Language:** Casual and family-friendly
  - "Where Your Money Goes" not "Category Breakdown"
  - "Getting Around" not "Transportation"
  - Emoji icons throughout for warmth

### Dashboard Views
1. **Home/Overview:** Monthly summary, top categories, quick stats
2. **Categories:** Pie chart, category cards with trends
3. **Transactions:** Searchable/filterable list in card format
4. **Trends:** Spending over time, top merchants
5. **Flagged Items:** Read-only view of transactions needing review

## Claude Categorization Skill

### Location
`skills/categorization/SKILL.md`

### Input Format
```json
{
  "transactions": [
    {
      "id": 1,
      "date": "2024-12-15",
      "amount": -45.23,
      "merchant_original": "WHOLEFDS MKTPL #12345",
      "merchant_cleaned": "WHOLEFDS MKTPL",
      "description": "WHOLE FOODS MARKET PURCHASE",
      "account_type": "credit_card"
    }
  ],
  "available_categories": ["Groceries", "Dining & Restaurants", ...],
  "existing_rules": [{"pattern": "TRADER JOE*", "category": "Groceries"}]
}
```

### Expected Output
```json
{
  "categorizations": [
    {
      "transaction_id": 1,
      "category": "Groceries",
      "confidence": 0.95,
      "rule_pattern": "WHOLEFDS*",
      "reasoning": "Whole Foods Market is a well-known grocery store..."
    }
  ]
}
```

### Confidence Scoring Guidelines
- **1.00:** Absolutely certain (e.g., "WHOLE FOODS" → Groceries)
- **0.90-0.99:** Very confident (e.g., "CHEVRON" → Transportation)
- **0.80-0.89:** Confident with minor ambiguity
- **0.70-0.79:** Moderately confident (e.g., "AMAZON")
- **<0.70:** Low confidence, flag for review

### Batch Processing
- Process 20-50 transactions per API call for efficiency
- Minimize API costs while maintaining quality
- Handle API errors gracefully with retry logic

## Critical Development Guidelines

### File Organization
- **Database (`finance.db`):** MUST be gitignored, lives in cloud-synced directory
- **PDFs:** MUST be gitignored, live in cloud-synced directory
- **Staging folder:** MUST be gitignored
- **config.yaml:** MUST be gitignored (contains API keys)
- **config.example.yaml:** MUST be committed (template for users)

### Always Use uv
```bash
uv sync                    # Never use pip install
uv add <package>           # Never use pip install <package>
uv run python <script>     # Run scripts in uv environment
```

### Always Format with Black
```bash
uv run black .             # Before committing any Python code
```

### Database Best Practices
- **Parameterized queries only** (prevent SQL injection)
- **Batch inserts** for performance (can insert 100+ transactions)
- **Use transactions** for multi-step operations
- **Dashboard uses read-only mode:** `sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)`
- **Close connections** in finally blocks

### PDF Parsing Best Practices
- **Error handling is critical** - malformed PDFs are common
- **Log parsing failures** with enough detail to debug
- **Test with actual statements** from target banks
- **Handle encoding issues** (weird character encodings)
- **Validate extracted data** (dates valid, amounts numeric)

### Ingestion Workflow Rules
1. **Check for config.yaml** at startup, error with helpful message if missing
2. **Hash and deduplicate** at statement level before parsing
3. **Move PDFs to archive** after successful processing only
4. **Log everything** - successes, errors, skipped files
5. **Remind user to restart dashboard** after ingestion completes

### Design Implementation Rules
- **Use CSS variables** for color palette (enables theming)
- **Rounded corners everywhere** (16px cards, 24px buttons)
- **Soft shadows** not harsh borders
- **Emoji in UI** for warmth (but not overdone)
- **Friendly language** throughout
- **Test colors for accessibility** (sufficient contrast)

### Security Considerations
- **Sanitize all user inputs** (even in CLI scripts)
- **Read-only database access** in Docker (`?mode=ro`)
- **Don't log sensitive data** (full account numbers)
- **Secure file permissions** on database and PDFs

## Common Pitfalls to Avoid

❌ **Don't hardcode file paths** - Use config.yaml
❌ **Don't assume PDF format is consistent** - Banks change formats
❌ **Don't skip duplicate detection** - Users will re-upload statements
❌ **Don't over-engineer early** - MVP first, iterate later
❌ **Don't ignore edge cases** - Refunds, credits, fees, foreign transactions
❌ **Don't forget to close database connections**
❌ **Don't run dashboard with write access in Docker**
❌ **Don't forget to remind user to restart dashboard after ingestion**
❌ **Don't use harsh colors or formal language** - Keep warm and casual
❌ **Don't create files for editing in dashboard** - All edits during ingestion only

## Default Categories

### Income
- Salary, Freelance, Investment Income, Other Income

### Expenses
- Groceries
- Dining & Restaurants
- Transportation (Gas, Transit, Parking, Rideshare)
- Housing (Rent, Utilities, Maintenance, HOA)
- Healthcare (Medical, Dental, Pharmacy, Insurance)
- Entertainment (Movies, Concerts, Hobbies, Streaming)
- Shopping (Clothing, Electronics, Home Goods)
- Subscriptions (Software, Media, Memberships)
- Travel (Flights, Hotels, Vacation)
- Personal Care (Haircuts, Gym, Beauty)
- Education (Courses, Books, Tuition)
- Insurance (Auto, Home, Life)
- Gifts & Donations
- Pets
- Childcare & Kids
- Home Improvement
- Professional Services (Legal, Accounting)
- Fees & Interest (Bank Fees, Credit Card Interest)
- Taxes

### Special
- Uncategorized
- Transfer (between own accounts)
- Credit Card Payment

## Performance Considerations

- **Index frequently queried columns** (date, category, account_id)
- **Limit query results** with pagination (50 per page)
- **Cache dashboard data** for current month
- **Lazy load** charts and visualizations
- **Profile slow queries** and optimize
- **Test with realistic data** (1000+ transactions)

## Testing Strategy

### Unit Tests
- PDF parsing logic (with mock PDFs)
- Categorization rule matching
- Database queries
- Utility functions

### Integration Tests
- Full ingestion workflow (with sample PDFs)
- Dashboard rendering (with sample data)

### Manual Testing
- Real bank statements from target banks
- UI/UX in browser (desktop and tablet)
- Docker deployment
- Family member experience

## Development Workflow

1. **Make changes** to code
2. **Format code:** `uv run black .`
3. **Run tests:** `uv run pytest tests/`
4. **Test locally** with sample PDFs in staging folder
5. **Test dashboard** with `uv run python scripts/run_dashboard.py`
6. **Commit** with clear messages
7. **Build Docker** and test containerized dashboard

## Quick Database Access

```bash
sqlite3 ~/Dropbox/PersonalFinance/finance.db
```

```sql
-- View schema
.schema

-- Check data
SELECT COUNT(*) FROM transactions;
SELECT * FROM transactions ORDER BY transaction_date DESC LIMIT 10;
SELECT category, COUNT(*), SUM(amount) FROM transactions GROUP BY category;

-- Exit
.quit
```
