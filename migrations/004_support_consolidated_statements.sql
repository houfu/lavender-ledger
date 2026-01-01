-- Migration: Support consolidated statements (multiple cards per PDF)
-- Version: 004
-- Description: Modify statements table to allow multiple statement records from the same PDF file
--              by removing UNIQUE constraints on file_path and file_hash, and adding compound
--              UNIQUE constraint on (file_hash, account_id) to prevent duplicate imports per card.

-- SQLite doesn't support DROP CONSTRAINT, so we need to recreate the table

-- Step 1: Create new statements table with corrected schema
CREATE TABLE statements_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    statement_date DATE NOT NULL,
    period_start DATE,
    period_end DATE,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    total_transactions INTEGER,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    -- Compound unique constraint: same file_hash can appear multiple times,
    -- but only once per account (prevents duplicate imports per card)
    UNIQUE(file_hash, account_id)
);

-- Step 2: Copy existing data from old table
INSERT INTO statements_new (
    id, account_id, statement_date, period_start, period_end,
    file_path, file_hash, total_transactions, processed_at
)
SELECT
    id, account_id, statement_date, period_start, period_end,
    file_path, file_hash, total_transactions, processed_at
FROM statements;

-- Step 3: Drop old table
DROP TABLE statements;

-- Step 4: Rename new table
ALTER TABLE statements_new RENAME TO statements;

-- Step 5: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_statement_account ON statements(account_id);
CREATE INDEX IF NOT EXISTS idx_statement_hash ON statements(file_hash);
CREATE INDEX IF NOT EXISTS idx_statement_date ON statements(statement_date);

-- Explanation:
-- With this change, a consolidated PDF (e.g., DBS Credit Cards with 2 cards) can now be
-- ingested as 2 separate statement records:
--   Statement 1: file_hash=abc123, account_id=1 (Visa card ending 3347)
--   Statement 2: file_hash=abc123, account_id=2 (Mastercard ending 9390)
--
-- The compound UNIQUE constraint (file_hash, account_id) ensures:
-- ✓ Same PDF can create multiple statements (different cards)
-- ✗ Cannot import the same card from the same PDF twice (prevents duplicates)
--
-- Example queries:
--   -- Find all statements from same PDF:
--   SELECT * FROM statements WHERE file_hash = 'abc123';
--
--   -- Check if specific card already imported:
--   SELECT * FROM statements WHERE file_hash = 'abc123' AND account_id = 1;
