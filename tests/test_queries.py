"""Tests for dashboard query functionality."""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import date

from src.database.models import Database, Transaction, Account
from src.dashboard.queries import DashboardQueries


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Initialize schema
    db = Database(db_path)
    db.init_schema()
    db.seed_categories()

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def db_with_data(temp_db):
    """Create a database with sample data."""
    db = Database(temp_db)

    # Create an account
    account = Account(
        id=None,
        account_name="Test Credit Card",
        account_type="credit_card",
        bank_name="Test Bank",
        last_four="1234",
    )
    account_id = db.create_account(account)

    # Create transactions
    transactions = [
        Transaction(
            id=None,
            account_id=account_id,
            transaction_date=date(2024, 12, 1),
            amount=-50.00,
            merchant_original="GROCERY STORE",
            transaction_type="expense",
            category="Groceries",
            confidence_score=0.95,
        ),
        Transaction(
            id=None,
            account_id=account_id,
            transaction_date=date(2024, 12, 5),
            amount=-25.00,
            merchant_original="RESTAURANT",
            transaction_type="expense",
            category="Dining & Restaurants",
            confidence_score=0.90,
        ),
        Transaction(
            id=None,
            account_id=account_id,
            transaction_date=date(2024, 12, 10),
            amount=1000.00,
            merchant_original="PAYCHECK",
            transaction_type="income",
            category="Salary",
            confidence_score=1.0,
        ),
    ]
    db.create_transactions_batch(transactions)

    return temp_db


class TestDashboardQueries:
    """Tests for dashboard queries."""

    def test_monthly_summary(self, db_with_data):
        """Test monthly summary calculation."""
        queries = DashboardQueries(db_with_data)
        summary = queries.get_monthly_summary(2024, 12)

        assert summary.month == "2024-12"
        assert summary.total_income == 1000.00
        assert summary.total_expenses == 75.00  # 50 + 25
        assert summary.net == 925.00
        assert summary.transaction_count == 3

    def test_category_breakdown(self, db_with_data):
        """Test category breakdown."""
        queries = DashboardQueries(db_with_data)
        breakdown = queries.get_category_breakdown(2024, 12)

        # Should have 2 expense categories
        assert len(breakdown) == 2

        # Groceries should be first (larger amount)
        assert breakdown[0].category == "Groceries"
        assert breakdown[0].amount == 50.00

        # Dining second
        assert breakdown[1].category == "Dining & Restaurants"
        assert breakdown[1].amount == 25.00

    def test_empty_month(self, temp_db):
        """Test queries for month with no data."""
        queries = DashboardQueries(temp_db)
        summary = queries.get_monthly_summary(2024, 1)

        assert summary.total_income == 0
        assert summary.total_expenses == 0
        assert summary.transaction_count == 0

    def test_get_transactions(self, db_with_data):
        """Test transaction retrieval."""
        queries = DashboardQueries(db_with_data)
        transactions, total = queries.get_transactions(year=2024, month=12)

        assert total == 3
        assert len(transactions) == 3

        # Should be ordered by date descending
        assert transactions[0].date == "2024-12-10"

    def test_get_transactions_with_category_filter(self, db_with_data):
        """Test filtering transactions by category."""
        queries = DashboardQueries(db_with_data)
        transactions, total = queries.get_transactions(
            year=2024, month=12, category="Groceries"
        )

        assert total == 1
        assert transactions[0].category == "Groceries"

    def test_read_only_connection(self, db_with_data):
        """Test that dashboard uses read-only connection."""
        queries = DashboardQueries(db_with_data)

        with queries.get_connection() as conn:
            # Attempt to write should fail
            with pytest.raises(sqlite3.OperationalError):
                conn.execute(
                    "INSERT INTO accounts (account_name, bank_name) VALUES ('test', 'test')"
                )
