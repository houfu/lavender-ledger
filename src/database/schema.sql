-- Lavender Ledger Database Schema

-- Schema migrations table: Track applied migrations
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Accounts table: Bank accounts and credit cards
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL UNIQUE,
    account_type TEXT CHECK(account_type IN ('checking', 'savings', 'credit_card')),
    bank_name TEXT NOT NULL,
    last_four TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Statements table: Processed PDF statements
CREATE TABLE IF NOT EXISTS statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    statement_date DATE NOT NULL,
    period_start DATE,
    period_end DATE,
    file_path TEXT NOT NULL UNIQUE,
    file_hash TEXT NOT NULL UNIQUE,
    total_transactions INTEGER,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_statement_account ON statements(account_id);
CREATE INDEX IF NOT EXISTS idx_statement_hash ON statements(file_hash);

-- Categories table: Spending categories
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    parent_category TEXT,
    color TEXT,
    icon TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Transactions table: Individual financial transactions
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    statement_id INTEGER,
    account_id INTEGER NOT NULL,
    transaction_date DATE NOT NULL,
    post_date DATE,
    amount DECIMAL(10, 2) NOT NULL,
    transaction_type TEXT CHECK(transaction_type IN ('expense', 'income', 'payment', 'fee', 'interest', 'transfer')),
    merchant_original TEXT NOT NULL,
    merchant_cleaned TEXT,
    description TEXT,
    category TEXT,
    confidence_score DECIMAL(3, 2),
    flagged_for_review BOOLEAN DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (statement_id) REFERENCES statements(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    UNIQUE(account_id, transaction_date, amount, merchant_original)
);

CREATE INDEX IF NOT EXISTS idx_transaction_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_transaction_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transaction_flagged ON transactions(flagged_for_review);
CREATE INDEX IF NOT EXISTS idx_transaction_account ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_transaction_statement ON transactions(statement_id);

-- Categorization rules table: Learned patterns for auto-categorization
CREATE TABLE IF NOT EXISTS categorization_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_pattern TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    confidence DECIMAL(3, 2) DEFAULT 1.00,
    times_applied INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_merchant_pattern ON categorization_rules(merchant_pattern);

-- Ingestion log table: Track data ingestion runs
CREATE TABLE IF NOT EXISTS ingestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT CHECK(status IN ('running', 'completed', 'failed')),
    pdfs_processed INTEGER DEFAULT 0,
    transactions_added INTEGER DEFAULT 0,
    transactions_updated INTEGER DEFAULT 0,
    errors TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ingestion_log_completed ON ingestion_log(completed_at);
CREATE INDEX IF NOT EXISTS idx_ingestion_log_status ON ingestion_log(status);
