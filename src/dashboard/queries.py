"""Read-only database queries for the dashboard."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from src.database.models import IngestionLog


@dataclass
class MonthlySummary:
    """Monthly spending summary."""

    month: str
    total_income: float
    total_expenses: float
    net: float
    transaction_count: int
    average_daily_spend: float
    days_in_month: int
    days_elapsed: int


@dataclass
class CategoryBreakdown:
    """Spending breakdown by category."""

    category: str
    amount: float
    percentage: float
    color: str
    transaction_count: int


@dataclass
class TransactionView:
    """Transaction for display."""

    id: int
    date: str
    merchant: str
    category: str
    amount: float
    account_name: str
    transaction_type: str
    is_income: bool


class DashboardQueries:
    """Read-only queries for the dashboard."""

    def __init__(self, db_path: str):
        """Initialize with database path.

        Args:
            db_path: Path to SQLite database.
        """
        self.db_path = db_path

    @contextmanager
    def get_connection(self):
        """Get read-only database connection."""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def get_monthly_summary(self, year: int, month: int) -> MonthlySummary:
        """Get summary for a specific month.

        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)

        Returns:
            MonthlySummary with totals and stats.
        """
        month_str = f"{year}-{month:02d}"
        start_date = f"{month_str}-01"

        # Calculate end of month
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        with self.get_connection() as conn:
            # Get income (positive amounts)
            income_row = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) as total
                FROM transactions
                WHERE transaction_date >= ? AND transaction_date < ?
                AND amount > 0
                AND transaction_type NOT IN ('payment', 'transfer')
                """,
                (start_date, end_date),
            ).fetchone()
            total_income = abs(income_row["total"])

            # Get expenses (negative amounts)
            expense_row = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) as total
                FROM transactions
                WHERE transaction_date >= ? AND transaction_date < ?
                AND amount < 0
                AND transaction_type NOT IN ('payment', 'transfer')
                """,
                (start_date, end_date),
            ).fetchone()
            total_expenses = abs(expense_row["total"])

            # Get transaction count
            count_row = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM transactions
                WHERE transaction_date >= ? AND transaction_date < ?
                """,
                (start_date, end_date),
            ).fetchone()
            transaction_count = count_row["count"]

        # Calculate days
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        days_in_month = (month_end - month_start).days + 1

        today = date.today()
        if today.year == year and today.month == month:
            days_elapsed = today.day
        elif date(year, month, 1) < today:
            days_elapsed = days_in_month
        else:
            days_elapsed = 0

        avg_daily = total_expenses / days_elapsed if days_elapsed > 0 else 0

        return MonthlySummary(
            month=month_str,
            total_income=total_income,
            total_expenses=total_expenses,
            net=total_income - total_expenses,
            transaction_count=transaction_count,
            average_daily_spend=avg_daily,
            days_in_month=days_in_month,
            days_elapsed=days_elapsed,
        )

    def get_category_breakdown(self, year: int, month: int) -> list[CategoryBreakdown]:
        """Get spending breakdown by category for a month.

        Args:
            year: Year
            month: Month

        Returns:
            List of CategoryBreakdown sorted by amount.
        """
        month_str = f"{year}-{month:02d}"
        start_date = f"{month_str}-01"

        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        with self.get_connection() as conn:
            # Get totals by category (expenses only)
            rows = conn.execute(
                """
                SELECT
                    COALESCE(t.category, 'Uncategorized') as category,
                    SUM(ABS(t.amount)) as total,
                    COUNT(*) as count,
                    c.color
                FROM transactions t
                LEFT JOIN categories c ON t.category = c.name
                WHERE t.transaction_date >= ? AND t.transaction_date < ?
                AND t.amount < 0
                AND t.transaction_type NOT IN ('payment', 'transfer')
                GROUP BY t.category
                ORDER BY total DESC
                """,
                (start_date, end_date),
            ).fetchall()

            # Calculate total for percentages
            total_amount = sum(row["total"] for row in rows)

            categories = []
            for row in rows:
                pct = (row["total"] / total_amount * 100) if total_amount > 0 else 0
                categories.append(
                    CategoryBreakdown(
                        category=row["category"],
                        amount=row["total"],
                        percentage=pct,
                        color=row["color"] or "#9B7EBD",
                        transaction_count=row["count"],
                    )
                )

            return categories

    def get_transactions(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TransactionView], int]:
        """Get transactions with optional filters.

        Args:
            year: Filter by year
            month: Filter by month
            category: Filter by category
            search: Search in merchant name
            limit: Max results to return
            offset: Offset for pagination

        Returns:
            Tuple of (transactions, total_count)
        """
        conditions = []
        params = []

        if year and month:
            month_str = f"{year}-{month:02d}"
            start_date = f"{month_str}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"
            conditions.append("t.transaction_date >= ? AND t.transaction_date < ?")
            params.extend([start_date, end_date])

        if category:
            conditions.append("t.category = ?")
            params.append(category)

        if search:
            conditions.append(
                "(t.merchant_original LIKE ? OR t.merchant_cleaned LIKE ?)"
            )
            params.extend([f"%{search}%", f"%{search}%"])

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self.get_connection() as conn:
            # Get total count
            count_row = conn.execute(
                f"""
                SELECT COUNT(*) as count
                FROM transactions t
                WHERE {where_clause}
                """,
                params,
            ).fetchone()
            total_count = count_row["count"]

            # Get transactions
            rows = conn.execute(
                f"""
                SELECT
                    t.id,
                    t.transaction_date,
                    COALESCE(t.merchant_cleaned, t.merchant_original) as merchant,
                    COALESCE(t.category, 'Uncategorized') as category,
                    t.amount,
                    a.account_name,
                    t.transaction_type
                FROM transactions t
                LEFT JOIN accounts a ON t.account_id = a.id
                WHERE {where_clause}
                ORDER BY t.transaction_date DESC, t.id DESC
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            ).fetchall()

            transactions = [
                TransactionView(
                    id=row["id"],
                    date=row["transaction_date"],
                    merchant=row["merchant"],
                    category=row["category"],
                    amount=row["amount"],
                    account_name=row["account_name"] or "Unknown",
                    transaction_type=row["transaction_type"],
                    is_income=row["amount"] > 0,
                )
                for row in rows
            ]

            return transactions, total_count

    def get_top_categories(
        self, year: int, month: int, limit: int = 5
    ) -> list[CategoryBreakdown]:
        """Get top spending categories for a month.

        Args:
            year: Year
            month: Month
            limit: Max categories to return

        Returns:
            List of top CategoryBreakdown.
        """
        categories = self.get_category_breakdown(year, month)
        return categories[:limit]

    def get_available_months(self) -> list[tuple[int, int]]:
        """Get list of months that have transactions.

        Returns:
            List of (year, month) tuples, most recent first.
        """
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT
                    CAST(strftime('%Y', transaction_date) AS INTEGER) as year,
                    CAST(strftime('%m', transaction_date) AS INTEGER) as month
                FROM transactions
                ORDER BY year DESC, month DESC
                """
            ).fetchall()
            return [(row["year"], row["month"]) for row in rows]

    def get_available_months_with_expenses(self) -> list[tuple[int, int]]:
        """Get list of months that have expense transactions.

        Returns:
            List of (year, month) tuples, most recent first.
        """
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT
                    CAST(strftime('%Y', transaction_date) AS INTEGER) as year,
                    CAST(strftime('%m', transaction_date) AS INTEGER) as month
                FROM transactions
                WHERE amount < 0
                AND transaction_type NOT IN ('payment', 'transfer')
                ORDER BY year DESC, month DESC
                """
            ).fetchall()
            return [(row["year"], row["month"]) for row in rows]

    def get_top_merchants(self, year: int, month: int, limit: int = 10) -> list[dict]:
        """Get top merchants by spending for a month.

        Args:
            year: Year
            month: Month
            limit: Max merchants to return

        Returns:
            List of merchant info dicts.
        """
        month_str = f"{year}-{month:02d}"
        start_date = f"{month_str}-01"

        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(merchant_cleaned, merchant_original) as merchant,
                    SUM(ABS(amount)) as total,
                    COUNT(*) as visits,
                    category
                FROM transactions
                WHERE transaction_date >= ? AND transaction_date < ?
                AND amount < 0
                AND transaction_type NOT IN ('payment', 'transfer')
                GROUP BY merchant
                ORDER BY total DESC
                LIMIT ?
                """,
                (start_date, end_date, limit),
            ).fetchall()

            return [
                {
                    "merchant": row["merchant"],
                    "total": row["total"],
                    "visits": row["visits"],
                    "average": row["total"] / row["visits"] if row["visits"] > 0 else 0,
                    "category": row["category"],
                }
                for row in rows
            ]

    def get_flagged_count(self, year: int = None, month: int = None) -> int:
        """Get count of flagged transactions.

        Args:
            year: Optional year filter
            month: Optional month filter

        Returns:
            Count of flagged transactions (filtered by month if specified)
        """
        with self.get_connection() as conn:
            if year and month:
                # Filter by month
                month_str = f"{year}-{month:02d}"
                start_date = f"{month_str}-01"
                if month == 12:
                    end_date = f"{year + 1}-01-01"
                else:
                    end_date = f"{year}-{month + 1:02d}-01"

                row = conn.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM transactions
                    WHERE flagged_for_review = 1
                    AND transaction_date >= ?
                    AND transaction_date < ?
                    """,
                    (start_date, end_date),
                ).fetchone()
            else:
                # No filter - all flagged transactions
                row = conn.execute(
                    "SELECT COUNT(*) as count FROM transactions WHERE flagged_for_review = 1"
                ).fetchone()
            return row["count"]

    def get_spending_trend(self, months: int = 6) -> list[dict]:
        """Get spending trend over recent months.

        Args:
            months: Number of months to include.

        Returns:
            List of monthly totals.
        """
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    strftime('%Y-%m', transaction_date) as month,
                    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as income,
                    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as expenses
                FROM transactions
                WHERE transaction_type NOT IN ('payment', 'transfer')
                GROUP BY strftime('%Y-%m', transaction_date)
                ORDER BY month DESC
                LIMIT ?
                """,
                (months,),
            ).fetchall()

            return [
                {
                    "month": row["month"],
                    "income": row["income"],
                    "expenses": row["expenses"],
                }
                for row in reversed(rows)
            ]

    def get_last_updated(self) -> Optional[IngestionLog]:
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
