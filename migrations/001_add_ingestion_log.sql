-- Migration: Add ingestion_log table
-- Version: 001
-- Description: Track when data was last updated and ingestion statistics

-- Ingestion log table: Track when data was last updated
CREATE TABLE IF NOT EXISTS ingestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT CHECK(status IN ('running', 'completed', 'failed')) DEFAULT 'running',
    pdfs_processed INTEGER DEFAULT 0,
    transactions_added INTEGER DEFAULT 0,
    transactions_updated INTEGER DEFAULT 0,
    errors TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ingestion_log_completed ON ingestion_log(completed_at);
CREATE INDEX IF NOT EXISTS idx_ingestion_log_status ON ingestion_log(status);
