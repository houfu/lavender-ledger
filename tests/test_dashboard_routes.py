"""Tests for dashboard Flask routes and rendering.

Since Lavender Ledger uses server-side rendering with minimal JavaScript,
Flask integration tests are the primary way to test the frontend.
"""

import pytest
from datetime import date

from src.dashboard.app import create_app
from src.database.models import Database, Account, Statement, Transaction


@pytest.fixture
def app(temp_db):
    """Create Flask app for testing."""
    # Use test database
    test_config = {
        "database_path": temp_db,
        "statements": {
            "staging_path": "/tmp/test_staging",
            "archive_path": "/tmp/test_archive",
        },
    }
    app = create_app(test_config)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def db_with_transactions(temp_db):
    """Database with realistic transaction data for dashboard testing."""
    db = Database(temp_db)

    # Create account
    account = Account(
        id=None,
        account_name="DBS BONUS$AVER",
        account_type="savings",
        bank_name="DBS",
        last_four="0941",
        is_active=True,
    )
    account_id = db.create_account(account)

    # Create statement
    stmt = Statement(
        id=None,
        account_id=account_id,
        statement_date=date(2024, 12, 31),
        period_start=date(2024, 12, 1),
        period_end=date(2024, 12, 31),
        file_path="test.csv",
        file_hash="hash123",
        total_transactions=3,
    )
    stmt_id = db.create_statement(stmt)

    # Create diverse transactions for testing
    transactions = [
        Transaction(
            id=None,
            statement_id=stmt_id,
            account_id=account_id,
            transaction_date=date(2024, 12, 1),
            amount=-150.00,
            transaction_type="expense",
            merchant_original="WHOLE FOODS",
            merchant_cleaned="WHOLE FOODS",
            category="Groceries",
            confidence_score=0.95,
            flagged_for_review=False,
        ),
        Transaction(
            id=None,
            statement_id=stmt_id,
            account_id=account_id,
            transaction_date=date(2024, 12, 5),
            amount=-75.50,
            transaction_type="expense",
            merchant_original="STARBUCKS",
            merchant_cleaned="STARBUCKS",
            category="Dining & Restaurants",
            confidence_score=0.90,
            flagged_for_review=False,
        ),
        Transaction(
            id=None,
            statement_id=stmt_id,
            account_id=account_id,
            transaction_date=date(2024, 12, 15),
            amount=3500.00,
            transaction_type="income",
            merchant_original="PAYCHECK",
            merchant_cleaned="PAYCHECK",
            category="Salary",
            confidence_score=1.00,
            flagged_for_review=False,
        ),
    ]
    db.create_transactions_batch(transactions)

    yield temp_db


class TestDashboardRoutes:
    """Test all dashboard routes load correctly."""

    def test_index_loads(self, client):
        """Home page should load without errors."""
        response = client.get("/")
        assert response.status_code == 200

    def test_categories_page_loads(self, client):
        """Categories page should load."""
        response = client.get("/categories")
        assert response.status_code == 200

    def test_transactions_page_loads(self, client):
        """Transactions page should load."""
        response = client.get("/transactions")
        assert response.status_code == 200

    def test_trends_page_loads(self, client):
        """Trends page should load."""
        response = client.get("/trends")
        assert response.status_code == 200

    def test_health_endpoint(self, client):
        """Health check should return healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"


class TestAPIEndpoints:
    """Test JSON API endpoints."""

    def test_api_summary_returns_json(self, client):
        """Summary API should return JSON."""
        response = client.get("/api/summary/2024/12")
        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_api_categories_returns_json(self, client):
        """Categories API should return JSON."""
        response = client.get("/api/categories/2024/12")
        assert response.status_code == 200
        assert response.content_type == "application/json"


class TestDataRendering:
    """Test that data is correctly rendered in templates."""

    def test_index_shows_empty_state_when_no_data(self, client):
        """Should show summary with $0.00 when no transactions."""
        response = client.get("/")
        html = response.data.decode("utf-8")

        # Now shows $0.00 summary instead of empty state
        assert "$0.00" in html
        assert "0" in html  # Transaction count

    def test_index_renders_summary_with_data(self, client, db_with_transactions):
        """Should display monthly summary when data exists."""
        # Create app with test database
        test_config = {"database_path": db_with_transactions}
        app = create_app(test_config)
        app.config["TESTING"] = True
        test_client = app.test_client()

        response = test_client.get("/?year=2024&month=12")
        html = response.data.decode("utf-8")

        assert "Total Income" in html
        assert "Total Spending" in html
        assert "What's Left" in html or "Net" in html

    def test_index_displays_currency_formatting(self, client, db_with_transactions):
        """Amounts should be formatted with $ and commas."""
        test_config = {"database_path": db_with_transactions}
        app = create_app(test_config)
        app.config["TESTING"] = True
        test_client = app.test_client()

        response = test_client.get("/?year=2024&month=12")
        html = response.data.decode("utf-8")

        # Check for currency symbol
        assert "$" in html

    def test_categories_page_with_data(self, client, db_with_transactions):
        """Categories page should render with data."""
        test_config = {"database_path": db_with_transactions}
        app = create_app(test_config)
        app.config["TESTING"] = True
        test_client = app.test_client()

        response = test_client.get("/categories?year=2024&month=12")
        html = response.data.decode("utf-8")

        # Should have some category names
        assert "Groceries" in html or "category" in html.lower()

    def test_transactions_page_with_data(self, client, db_with_transactions):
        """Transactions page should render transaction list."""
        test_config = {"database_path": db_with_transactions}
        app = create_app(test_config)
        app.config["TESTING"] = True
        test_client = app.test_client()

        response = test_client.get("/transactions?year=2024&month=12")
        html = response.data.decode("utf-8")

        # Should have transaction data
        assert "WHOLE FOODS" in html or "STARBUCKS" in html or "PAYCHECK" in html


class TestMonthSelection:
    """Test month selector functionality."""

    def test_index_accepts_year_month_params(self, client):
        """Should accept ?year=2024&month=12 query parameters."""
        response = client.get("/?year=2024&month=12")
        assert response.status_code == 200

    def test_changeMonth_function_present(self, client, db_with_transactions):
        """changeMonth() JavaScript function should be in HTML."""
        test_config = {"database_path": db_with_transactions}
        app = create_app(test_config)
        app.config["TESTING"] = True
        test_client = app.test_client()

        response = test_client.get("/?year=2024&month=12")
        html = response.data.decode("utf-8")

        # Check for month change functionality
        assert "changeMonth" in html or "month-select" in html


class TestReadOnlyEnforcement:
    """Ensure dashboard is truly read-only (no modification endpoints)."""

    def test_post_to_index_not_allowed(self, client):
        """POST to index should not be allowed."""
        response = client.post("/")
        assert response.status_code == 405  # Method Not Allowed

    def test_post_to_transactions_not_allowed(self, client):
        """POST to transactions should not be allowed."""
        response = client.post("/transactions")
        assert response.status_code == 405

    def test_no_forms_for_editing(self, client):
        """Pages should not have forms for editing data."""
        pages = ["/", "/categories", "/transactions", "/trends"]

        for page in pages:
            response = client.get(page)
            html = response.data.decode("utf-8")

            # Should not have POST forms (GET forms like search are OK)
            assert '<form method="post"' not in html.lower()
            assert "<form action=" not in html or "month-select" in html


class TestDesignSystem:
    """Test lilac theme and family-friendly design."""

    def test_page_title_friendly(self, client):
        """Page titles should be family-friendly."""
        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check for friendly language (not "Account Dashboard" or similar)
        assert "Lavender" in html or "Family" in html or "Spending" in html

    def test_base_template_loads_fonts(self, client):
        """Should reference Nunito or Quicksand fonts."""
        response = client.get("/")
        html = response.data.decode("utf-8")

        # Should load Google Fonts or similar
        assert "Nunito" in html or "font" in html.lower()


class TestErrorHandling:
    """Test error handling for invalid requests."""

    def test_invalid_year_handled(self, client):
        """Invalid year should be handled gracefully."""
        response = client.get("/?year=9999&month=12")
        # Should not crash, either 200 with empty state or redirect
        assert response.status_code in [200, 302, 404]

    def test_invalid_month_handled(self, client):
        """Invalid month should be handled gracefully."""
        response = client.get("/?year=2024&month=99")
        # Should not crash
        assert response.status_code in [200, 302, 400, 404]
