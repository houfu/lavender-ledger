"""Shared test fixtures for Lavender Ledger tests."""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import date

from src.database.models import Database, Account, Transaction, Statement


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
def db_instance(temp_db):
    """Return a Database instance connected to temp database."""
    return Database(temp_db)


@pytest.fixture
def test_account(db_instance):
    """Create a test account and return (account_id, Database)."""
    account = Account(
        id=None,
        account_name="DBS BONUS$AVER (...0941)",
        account_type="savings",
        bank_name="DBS",
        last_four="0941",
        is_active=True,
        created_at=None,
    )
    account_id = db_instance.create_account(account)
    return account_id, db_instance


@pytest.fixture
def test_statement(test_account):
    """Create a test statement and return (statement_id, account_id, Database)."""
    account_id, db = test_account
    statement = Statement(
        id=None,
        account_id=account_id,
        statement_date=date(2025, 12, 30),
        period_start=date(2025, 12, 1),
        period_end=date(2025, 12, 30),
        file_path="data/statements/staging/test.csv",
        file_hash="abc123def456",
        total_transactions=0,
        processed_at=None,
    )
    statement_id = db.create_statement(statement)
    return statement_id, account_id, db


@pytest.fixture
def sample_parsed_json():
    """Sample parsed statement JSON (as returned by parsing skill)."""
    return {
        "file_path": "data/statements/staging/test.csv",
        "account_info": {
            "bank_name": "DBS",
            "account_type": "savings",
            "account_name": "BONUS$AVER",
            "last_four": "0941",
            "statement_date": "2025-12-30",
            "period_start": "2025-12-01",
            "period_end": "2025-12-30",
        },
        "transactions": [
            {
                "transaction_date": "2025-12-01",
                "merchant_original": "BONUS INTEREST (SALARY)",
                "merchant_cleaned": "BONUS INTEREST",
                "description": "SALARY",
                "amount": 123.29,
                "transaction_type": "interest",
                "balance_after": 145334.13,
            },
            {
                "transaction_date": "2025-12-02",
                "merchant_original": "TOYOTA TSUSHO ASIA PACIFIC PTE.",
                "merchant_cleaned": "TOYOTA TSUSHO ASIA PACIFIC",
                "description": "TTAPCLAIM IBFTO",
                "amount": 2467.96,
                "transaction_type": "income",
                "balance_after": 147802.09,
            },
            {
                "transaction_date": "2025-12-09",
                "merchant_original": "TRANSFER WITHDRAWAL NTRF TO:6129962006",
                "merchant_cleaned": "TRANSFER WITHDRAWAL",
                "description": "NTRF TO:6129962006",
                "amount": -500.00,
                "transaction_type": "transfer",
                "balance_after": 145802.09,
            },
        ],
    }


@pytest.fixture
def sample_categorizations():
    """Sample categorization results JSON (as returned by categorization skill)."""
    return {
        "categorizations": [
            {
                "transaction_id": 1,
                "category": "Other Income",
                "confidence": 1.00,
                "rule_pattern": "BONUS INTEREST*",
                "reasoning": "DBS Bonus Interest earned on salary credit.",
            },
            {
                "transaction_id": 2,
                "category": "Salary",
                "confidence": 0.95,
                "rule_pattern": "TOYOTA TSUSHO*",
                "reasoning": "Regular employer deposit.",
            },
            {
                "transaction_id": 3,
                "category": "Transfer",
                "confidence": 0.95,
                "rule_pattern": "TRANSFER WITHDRAWAL*",
                "reasoning": "NTRF indicates internal transfer.",
            },
        ]
    }


@pytest.fixture
def sample_dbs_csv():
    """Sample DBS CSV content."""
    return """Account transactions shown:,01/12/2025 To 30/12/2025

Account Name,Account Number,Currency,Current Balance,Available Balance
BONUS$AVER,'6109750941,SGD,"165,327.09 CR","20,327.09 CR"

Date,Transaction,Currency,Deposit,Withdrawal,Running Balance
01/12/2025,BONUS INTEREST (SALARY),SGD,"123.29","","145,334.13 CR"
02/12/2025,TOYOTA TSUSHO ASIA PACIFIC PTE. TTAPCLAIM IBFTO,SGD,"2,467.96","","147,802.09 CR"
09/12/2025,TRANSFER WITHDRAWAL NTRF TO:6129962006,SGD,"","500.00","145,802.09 CR"
"""


@pytest.fixture
def temp_json_file(tmp_path):
    """Create a temporary JSON file for testing."""

    def _make_json_file(data):
        """Create temp JSON file with given data."""
        json_file = tmp_path / "test_data.json"
        with open(json_file, "w") as f:
            json.dump(data, f, indent=2)
        return json_file

    return _make_json_file
