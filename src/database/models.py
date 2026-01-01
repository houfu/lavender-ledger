"""Database access layer for Lavender Ledger."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional


@dataclass
class Account:
    id: Optional[int]
    account_name: str
    account_type: str
    bank_name: str
    last_four: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class Statement:
    id: Optional[int]
    account_id: int
    statement_date: date
    file_path: str
    file_hash: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    total_transactions: Optional[int] = None
    processed_at: Optional[datetime] = None


@dataclass
class Transaction:
    id: Optional[int]
    account_id: int
    transaction_date: date
    amount: float
    merchant_original: str
    transaction_type: str
    statement_id: Optional[int] = None
    post_date: Optional[date] = None
    merchant_cleaned: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    confidence_score: Optional[float] = None
    flagged_for_review: bool = False
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CategorizationRule:
    id: Optional[int]
    merchant_pattern: str
    category: str
    confidence: float = 1.0
    times_applied: int = 0
    last_used: Optional[datetime] = None
    created_at: Optional[datetime] = None
    notes: Optional[str] = None
    # Enhanced fields for complex rules and learning
    rule_type: str = "pattern"
    conditions: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    account_type_filter: Optional[str] = None
    user_confirmed: bool = False
    auto_created: bool = False
    times_rejected: int = 0
    accuracy_score: Optional[float] = None


@dataclass
class Category:
    id: Optional[int]
    name: str
    parent_category: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class IngestionLog:
    id: Optional[int]
    started_at: datetime
    status: str = "running"
    completed_at: Optional[datetime] = None
    pdfs_processed: int = 0
    transactions_added: int = 0
    transactions_updated: int = 0
    errors: Optional[str] = None
    summary: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class IngestionBatch:
    """Represents a batch of PDFs processed together."""

    id: Optional[int]
    ingestion_log_id: int
    batch_number: int
    started_at: datetime
    status: str = "pending"
    completed_at: Optional[datetime] = None
    total_files: int = 0
    files_processed: int = 0
    files_failed: int = 0
    summary: Optional[str] = None


@dataclass
class IngestionFileStatus:
    """Tracks individual file processing status for resume capability."""

    id: Optional[int]
    ingestion_log_id: int
    file_name: str
    file_hash: str
    file_path: str
    status: str = "pending"
    batch_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    statement_id: Optional[int] = None
    transactions_inserted: Optional[int] = None


class Database:
    """Database access layer with read-only mode support."""

    def __init__(self, db_path: str, read_only: bool = False):
        self.db_path = db_path
        self.read_only = read_only

    @contextmanager
    def get_connection(self):
        """Get database connection with proper handling."""
        if self.read_only:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, query: str, params=None):
        """Execute a raw SQL query (for delete/update operations)."""
        with self.get_connection() as conn:
            if params:
                conn.execute(query, params)
            else:
                conn.execute(query)
            conn.commit()

    def init_schema(self):
        """Initialize database schema from SQL file."""
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path) as f:
            schema_sql = f.read()

        with self.get_connection() as conn:
            conn.executescript(schema_sql)
            conn.commit()

    def seed_categories(self):
        """Seed default categories with lilac-themed colors."""
        categories = [
            # Income
            ("Salary", "Income", "#81C784", None),
            ("Freelance", "Income", "#A5D6A7", None),
            ("Investment Income", "Income", "#C8E6C9", None),
            ("Other Income", "Income", "#E8F5E9", None),
            # Expenses
            ("Groceries", "Expenses", "#9B7EBD", None),
            ("Dining & Restaurants", "Expenses", "#C8B6E2", None),
            ("Transportation", "Expenses", "#7B68A6", None),
            ("Housing", "Expenses", "#D5C6E8", None),
            ("Healthcare", "Expenses", "#B39CD8", None),
            ("Entertainment", "Expenses", "#E6D5F5", None),
            ("Shopping", "Expenses", "#A890C8", None),
            ("Subscriptions", "Expenses", "#BFA9D4", None),
            ("Travel", "Expenses", "#9D85BA", None),
            ("Personal Care", "Expenses", "#D0BFEA", None),
            ("Education", "Expenses", "#C4B0DC", None),
            ("Insurance", "Expenses", "#B8A4D0", None),
            ("Gifts & Donations", "Expenses", "#D8CAE8", None),
            ("Pets", "Expenses", "#CFC0E0", None),
            ("Childcare & Kids", "Expenses", "#E0D4F0", None),
            ("Home Improvement", "Expenses", "#A698C0", None),
            ("Professional Services", "Expenses", "#9A8CB4", None),
            ("Fees & Interest", "Expenses", "#8E80A8", None),
            ("Taxes", "Expenses", "#82749C", None),
            # Special
            ("Uncategorized", "Special", "#BDBDBD", None),
            ("Transfer", "Special", "#90A4AE", None),
            ("Credit Card Payment", "Special", "#78909C", None),
        ]

        with self.get_connection() as conn:
            for name, parent, color, icon in categories:
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO categories (name, parent_category, color, icon)
                        VALUES (?, ?, ?, ?)
                        """,
                        (name, parent, color, icon),
                    )
                except sqlite3.IntegrityError:
                    pass
            conn.commit()

    # Account methods
    def create_account(self, account: Account) -> int:
        """Create a new account and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO accounts (account_name, account_type, bank_name, last_four, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    account.account_name,
                    account.account_type,
                    account.bank_name,
                    account.last_four,
                    account.is_active,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_account_by_name(self, account_name: str) -> Optional[Account]:
        """Get account by name."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE account_name = ?", (account_name,)
            ).fetchone()
            if row:
                return Account(
                    id=row["id"],
                    account_name=row["account_name"],
                    account_type=row["account_type"],
                    bank_name=row["bank_name"],
                    last_four=row["last_four"],
                    is_active=bool(row["is_active"]),
                    created_at=row["created_at"],
                )
            return None

    def get_all_accounts(self) -> list[Account]:
        """Get all active accounts."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE is_active = 1 ORDER BY bank_name, account_name"
            ).fetchall()
            return [
                Account(
                    id=row["id"],
                    account_name=row["account_name"],
                    account_type=row["account_type"],
                    bank_name=row["bank_name"],
                    last_four=row["last_four"],
                    is_active=bool(row["is_active"]),
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    # Statement methods
    def statement_exists(
        self, file_hash: str, account_id: Optional[int] = None
    ) -> bool:
        """Check if a statement with this hash already exists.

        Args:
            file_hash: SHA256 hash of the PDF file
            account_id: Optional account ID to check compound key (file_hash, account_id).
                       If provided, checks if this specific account's statement exists.
                       If None, checks if ANY statement with this hash exists (legacy behavior).

        Returns:
            True if statement exists, False otherwise
        """
        with self.get_connection() as conn:
            if account_id is not None:
                # Check compound key (file_hash, account_id) for consolidated statements
                row = conn.execute(
                    "SELECT 1 FROM statements WHERE file_hash = ? AND account_id = ?",
                    (file_hash, account_id),
                ).fetchone()
            else:
                # Legacy behavior: check if any statement with this hash exists
                row = conn.execute(
                    "SELECT 1 FROM statements WHERE file_hash = ?", (file_hash,)
                ).fetchone()
            return row is not None

    def create_statement(self, statement: Statement) -> int:
        """Create a new statement and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO statements
                (account_id, statement_date, period_start, period_end, file_path, file_hash, total_transactions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    statement.account_id,
                    statement.statement_date,
                    statement.period_start,
                    statement.period_end,
                    statement.file_path,
                    statement.file_hash,
                    statement.total_transactions,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    # Transaction methods
    def transaction_exists(
        self, account_id: int, transaction_date: date, amount: float, merchant: str
    ) -> bool:
        """Check if a transaction already exists."""
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM transactions
                WHERE account_id = ? AND transaction_date = ? AND amount = ? AND merchant_original = ?
                """,
                (account_id, transaction_date, amount, merchant),
            ).fetchone()
            return row is not None

    def create_transaction(self, transaction: Transaction) -> int:
        """Create a new transaction and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO transactions
                (statement_id, account_id, transaction_date, post_date, amount, transaction_type,
                 merchant_original, merchant_cleaned, description, category, confidence_score,
                 flagged_for_review, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction.statement_id,
                    transaction.account_id,
                    transaction.transaction_date,
                    transaction.post_date,
                    transaction.amount,
                    transaction.transaction_type,
                    transaction.merchant_original,
                    transaction.merchant_cleaned,
                    transaction.description,
                    transaction.category,
                    transaction.confidence_score,
                    transaction.flagged_for_review,
                    transaction.notes,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def create_transactions_batch(self, transactions: list[Transaction]) -> int:
        """Create multiple transactions in a batch. Returns count of inserted."""
        inserted = 0
        with self.get_connection() as conn:
            for t in transactions:
                try:
                    conn.execute(
                        """
                        INSERT INTO transactions
                        (statement_id, account_id, transaction_date, post_date, amount, transaction_type,
                         merchant_original, merchant_cleaned, description, category, confidence_score,
                         flagged_for_review, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            t.statement_id,
                            t.account_id,
                            t.transaction_date,
                            t.post_date,
                            t.amount,
                            t.transaction_type,
                            t.merchant_original,
                            t.merchant_cleaned,
                            t.description,
                            t.category,
                            t.confidence_score,
                            t.flagged_for_review,
                            t.notes,
                        ),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    # Duplicate transaction, skip
                    pass
            conn.commit()
        return inserted

    def update_transaction_category(
        self,
        transaction_id: int,
        category: str,
        confidence_score: float,
        flagged: bool = False,
    ):
        """Update transaction category."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE transactions
                SET category = ?, confidence_score = ?, flagged_for_review = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (category, confidence_score, flagged, transaction_id),
            )
            conn.commit()

    def get_flagged_transactions(self) -> list[Transaction]:
        """Get all transactions flagged for review."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM transactions
                WHERE flagged_for_review = 1
                ORDER BY transaction_date DESC
                """
            ).fetchall()
            return [self._row_to_transaction(row) for row in rows]

    def get_uncategorized_transactions(self) -> list[Transaction]:
        """Get transactions without a category."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM transactions
                WHERE category IS NULL OR category = 'Uncategorized'
                ORDER BY transaction_date DESC
                """
            ).fetchall()
            return [self._row_to_transaction(row) for row in rows]

    def _row_to_transaction(self, row) -> Transaction:
        """Convert a database row to a Transaction object."""
        return Transaction(
            id=row["id"],
            statement_id=row["statement_id"],
            account_id=row["account_id"],
            transaction_date=row["transaction_date"],
            post_date=row["post_date"],
            amount=row["amount"],
            transaction_type=row["transaction_type"],
            merchant_original=row["merchant_original"],
            merchant_cleaned=row["merchant_cleaned"],
            description=row["description"],
            category=row["category"],
            confidence_score=row["confidence_score"],
            flagged_for_review=bool(row["flagged_for_review"]),
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # Categorization rules methods
    def get_all_rules(self) -> list[CategorizationRule]:
        """Get all categorization rules."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM categorization_rules ORDER BY times_applied DESC"
            ).fetchall()
            return [self._row_to_rule(row) for row in rows]

    def find_matching_rule(
        self, merchant: str, transaction: Optional[Transaction] = None
    ) -> Optional[CategorizationRule]:
        """Find a rule that matches the merchant name and optional transaction criteria.

        Args:
            merchant: Merchant name to match
            transaction: Optional transaction for complex rule matching (amount, account_type)

        Returns:
            First matching rule, prioritized by:
            1. User-confirmed rules
            2. More specific patterns (longer)
            3. Higher accuracy scores
        """
        with self.get_connection() as conn:
            # Order by user_confirmed DESC, then pattern length, then accuracy
            rows = conn.execute(
                """
                SELECT * FROM categorization_rules
                ORDER BY user_confirmed DESC, LENGTH(merchant_pattern) DESC, accuracy_score DESC NULLS LAST
                """
            ).fetchall()

            for row in rows:
                pattern = row["merchant_pattern"]
                # Convert SQL LIKE pattern to comparison
                # Pattern like "WHOLEFDS*" should match "WHOLEFDS MARKET #123"
                sql_pattern = pattern.replace("*", "%")
                match_row = conn.execute(
                    "SELECT ? LIKE ?", (merchant.upper(), sql_pattern.upper())
                ).fetchone()

                if match_row[0]:
                    # Pattern matches - now check complex conditions if present
                    rule = self._row_to_rule(row)

                    # If transaction provided, check amount and account filters
                    if transaction:
                        # Check min amount
                        if (
                            rule.min_amount is not None
                            and transaction.amount > -rule.min_amount
                        ):
                            continue
                        # Check max amount
                        if (
                            rule.max_amount is not None
                            and transaction.amount < -rule.max_amount
                        ):
                            continue
                        # Check account type filter
                        if rule.account_type_filter:
                            # Would need to fetch account info - for now, skip
                            pass

                    return rule

        return None

    def create_rule(self, rule: CategorizationRule) -> int:
        """Create a new categorization rule with support for complex conditions."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO categorization_rules
                (merchant_pattern, category, confidence, notes, rule_type, conditions,
                 min_amount, max_amount, account_type_filter, user_confirmed, auto_created)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.merchant_pattern,
                    rule.category,
                    rule.confidence,
                    rule.notes,
                    rule.rule_type,
                    rule.conditions,
                    rule.min_amount,
                    rule.max_amount,
                    rule.account_type_filter,
                    1 if rule.user_confirmed else 0,
                    1 if rule.auto_created else 0,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def increment_rule_usage(self, rule_id: int):
        """Increment the times_applied counter for a rule."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE categorization_rules
                SET times_applied = times_applied + 1, last_used = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (rule_id,),
            )
            conn.commit()

    def get_rule_by_pattern(self, pattern: str) -> Optional[CategorizationRule]:
        """Check if a rule with this pattern already exists."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM categorization_rules WHERE merchant_pattern = ?",
                (pattern,),
            ).fetchone()
            if row:
                return self._row_to_rule(row)
            return None

    def update_rule_feedback(self, rule_id: int, accepted: bool):
        """Track whether user accepted or rejected a rule application.

        Args:
            rule_id: ID of the rule
            accepted: True if user accepted the categorization, False if rejected
        """
        with self.get_connection() as conn:
            if accepted:
                # Increment times_applied, improve accuracy score
                conn.execute(
                    """
                    UPDATE categorization_rules
                    SET times_applied = times_applied + 1,
                        accuracy_score = COALESCE(accuracy_score, 0.5) + 0.1,
                        last_used = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (rule_id,),
                )
            else:
                # Increment times_rejected, decrease accuracy score
                conn.execute(
                    """
                    UPDATE categorization_rules
                    SET times_rejected = times_rejected + 1,
                        accuracy_score = COALESCE(accuracy_score, 0.5) - 0.1
                    WHERE id = ?
                    """,
                    (rule_id,),
                )
            conn.commit()

    def _row_to_rule(self, row) -> CategorizationRule:
        """Convert a database row to a CategorizationRule object."""
        return CategorizationRule(
            id=row["id"],
            merchant_pattern=row["merchant_pattern"],
            category=row["category"],
            confidence=row["confidence"],
            times_applied=row["times_applied"],
            last_used=row["last_used"],
            created_at=row["created_at"],
            notes=row["notes"],
            rule_type=row.get("rule_type", "pattern"),
            conditions=row.get("conditions"),
            min_amount=row.get("min_amount"),
            max_amount=row.get("max_amount"),
            account_type_filter=row.get("account_type_filter"),
            user_confirmed=bool(row.get("user_confirmed", 0)),
            auto_created=bool(row.get("auto_created", 0)),
            times_rejected=row.get("times_rejected", 0),
            accuracy_score=row.get("accuracy_score"),
        )

    # Category methods
    def get_all_categories(self) -> list[Category]:
        """Get all active categories."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM categories WHERE is_active = 1 ORDER BY parent_category, name"
            ).fetchall()
            return [
                Category(
                    id=row["id"],
                    name=row["name"],
                    parent_category=row["parent_category"],
                    color=row["color"],
                    icon=row["icon"],
                    is_active=bool(row["is_active"]),
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def get_category_names(self) -> list[str]:
        """Get just category names for categorization."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT name FROM categories WHERE is_active = 1 ORDER BY name"
            ).fetchall()
            return [row["name"] for row in rows]

    # Ingestion log methods
    def create_ingestion_log(self, log: IngestionLog) -> int:
        """Create a new ingestion log entry and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ingestion_log (started_at, status)
                VALUES (?, ?)
                """,
                (log.started_at, log.status),
            )
            conn.commit()
            return cursor.lastrowid

    def update_ingestion_log(
        self,
        log_id: int,
        status: str,
        completed_at: datetime,
        pdfs_processed: int = 0,
        transactions_added: int = 0,
        transactions_updated: int = 0,
        errors: Optional[str] = None,
        summary: Optional[str] = None,
    ):
        """Update an ingestion log entry."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE ingestion_log
                SET status = ?, completed_at = ?, pdfs_processed = ?,
                    transactions_added = ?, transactions_updated = ?,
                    errors = ?, summary = ?
                WHERE id = ?
                """,
                (
                    status,
                    completed_at,
                    pdfs_processed,
                    transactions_added,
                    transactions_updated,
                    errors,
                    summary,
                    log_id,
                ),
            )
            conn.commit()

    def get_last_ingestion(self) -> Optional[IngestionLog]:
        """Get the most recent completed ingestion log."""
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM ingestion_log
                WHERE status = 'completed'
                ORDER BY completed_at DESC
                LIMIT 1
                """
            ).fetchone()
            if row:
                return IngestionLog(
                    id=row["id"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    status=row["status"],
                    pdfs_processed=row["pdfs_processed"],
                    transactions_added=row["transactions_added"],
                    transactions_updated=row["transactions_updated"],
                    errors=row["errors"],
                    summary=row["summary"],
                    created_at=row["created_at"],
                )
            return None

    def get_ingestion_history(self, limit: int = 10) -> list[IngestionLog]:
        """Get recent ingestion history."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM ingestion_log
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                IngestionLog(
                    id=row["id"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    status=row["status"],
                    pdfs_processed=row["pdfs_processed"],
                    transactions_added=row["transactions_added"],
                    transactions_updated=row["transactions_updated"],
                    errors=row["errors"],
                    summary=row["summary"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    # === Batch Tracking Methods ===

    def create_batch(self, batch: IngestionBatch) -> int:
        """Create a new batch record for tracking batch progress."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ingestion_batches (
                    ingestion_log_id, batch_number, started_at, status,
                    total_files, files_processed, files_failed, summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.ingestion_log_id,
                    batch.batch_number,
                    batch.started_at,
                    batch.status,
                    batch.total_files,
                    batch.files_processed,
                    batch.files_failed,
                    batch.summary,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update_batch_status(self, batch_id: int, status: str, **kwargs):
        """Update batch status and optional metrics."""
        updates = ["status = ?"]
        params = [status]

        if "completed_at" in kwargs:
            updates.append("completed_at = ?")
            params.append(kwargs["completed_at"])
        if "files_processed" in kwargs:
            updates.append("files_processed = ?")
            params.append(kwargs["files_processed"])
        if "files_failed" in kwargs:
            updates.append("files_failed = ?")
            params.append(kwargs["files_failed"])
        if "summary" in kwargs:
            updates.append("summary = ?")
            params.append(kwargs["summary"])

        params.append(batch_id)

        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE ingestion_batches SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

    def create_file_status(self, file_status: IngestionFileStatus) -> int:
        """Track individual file processing status."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ingestion_file_status (
                    ingestion_log_id, batch_id, file_name, file_hash, file_path,
                    status, started_at, completed_at, error_message,
                    statement_id, transactions_inserted
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_status.ingestion_log_id,
                    file_status.batch_id,
                    file_status.file_name,
                    file_status.file_hash,
                    file_status.file_path,
                    file_status.status,
                    file_status.started_at,
                    file_status.completed_at,
                    file_status.error_message,
                    file_status.statement_id,
                    file_status.transactions_inserted,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update_file_status(self, file_id: int, status: str, **kwargs):
        """Update file status and optional fields."""
        updates = ["status = ?"]
        params = [status]

        if "started_at" in kwargs:
            updates.append("started_at = ?")
            params.append(kwargs["started_at"])
        if "completed_at" in kwargs:
            updates.append("completed_at = ?")
            params.append(kwargs["completed_at"])
        if "error_message" in kwargs:
            updates.append("error_message = ?")
            params.append(kwargs["error_message"])
        if "statement_id" in kwargs:
            updates.append("statement_id = ?")
            params.append(kwargs["statement_id"])
        if "transactions_inserted" in kwargs:
            updates.append("transactions_inserted = ?")
            params.append(kwargs["transactions_inserted"])

        params.append(file_id)

        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE ingestion_file_status SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

    def get_pending_files(self, log_id: int) -> list[IngestionFileStatus]:
        """Get files that need processing (pending or failed status)."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM ingestion_file_status
                WHERE ingestion_log_id = ? AND status IN ('pending', 'failed')
                ORDER BY id
                """,
                (log_id,),
            ).fetchall()

            return [
                IngestionFileStatus(
                    id=row["id"],
                    ingestion_log_id=row["ingestion_log_id"],
                    batch_id=row["batch_id"],
                    file_name=row["file_name"],
                    file_hash=row["file_hash"],
                    file_path=row["file_path"],
                    status=row["status"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    error_message=row["error_message"],
                    statement_id=row["statement_id"],
                    transactions_inserted=row["transactions_inserted"],
                )
                for row in rows
            ]

    def get_batch_progress(self, batch_id: int) -> dict:
        """Get current batch progress metrics."""
        with self.get_connection() as conn:
            batch_row = conn.execute(
                "SELECT * FROM ingestion_batches WHERE id = ?", (batch_id,)
            ).fetchone()

            if not batch_row:
                return {}

            return {
                "batch_number": batch_row["batch_number"],
                "status": batch_row["status"],
                "total_files": batch_row["total_files"],
                "files_processed": batch_row["files_processed"],
                "files_failed": batch_row["files_failed"],
            }

    def detect_resume_state(self, log_id: int) -> dict:
        """Check if this is a resume scenario and return state."""
        with self.get_connection() as conn:
            # Check for existing batch records
            batches = conn.execute(
                """
                SELECT * FROM ingestion_batches
                WHERE ingestion_log_id = ?
                ORDER BY batch_number
                """,
                (log_id,),
            ).fetchall()

            if not batches:
                return {"is_resume": False}

            # Find incomplete batch
            incomplete_batch = None
            for batch in batches:
                if batch["status"] in ("pending", "processing"):
                    incomplete_batch = batch
                    break

            if not incomplete_batch:
                return {"is_resume": False, "reason": "All batches completed"}

            # Get file statuses
            files = conn.execute(
                """
                SELECT file_name, status, file_hash, error_message
                FROM ingestion_file_status
                WHERE ingestion_log_id = ?
                ORDER BY id
                """,
                (log_id,),
            ).fetchall()

            completed_files = [
                f["file_hash"] for f in files if f["status"] == "completed"
            ]
            failed_files = [
                {"file": f["file_name"], "error": f["error_message"]}
                for f in files
                if f["status"] == "failed"
            ]

            return {
                "is_resume": True,
                "current_batch": incomplete_batch["batch_number"],
                "completed_files": completed_files,
                "failed_files": failed_files,
                "files_to_process": [
                    f for f in files if f["status"] in ("pending", "failed")
                ],
            }

    def get_completed_file_hashes(self, log_id: int) -> set[str]:
        """Get set of file hashes that have been completed."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT file_hash FROM ingestion_file_status
                WHERE ingestion_log_id = ? AND status = 'completed'
                """,
                (log_id,),
            ).fetchall()
            return {row["file_hash"] for row in rows}
