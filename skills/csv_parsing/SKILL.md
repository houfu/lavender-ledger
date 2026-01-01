---
name: parse-csv
description: Parse bank statement CSV files into structured transaction data. Extracts account information and transactions from CSV exports. Use when you need to process CSV bank statements.
---

# CSV Bank Statement Parsing Skill

## Purpose
Parse CSV bank statement files into structured JSON format containing account information and transaction details. Works with CSV exports from any bank by intelligently interpreting the structure.

## When to Use
- Processing CSV files from staging folder during ingestion
- Converting CSV bank exports to structured data for database insertion
- Extracting transactions from downloaded CSV statements

## Input
- **CSV file content** (already read via Read tool)
- The CSV contains both account metadata and transaction rows

## Expected Output
Return JSON in this exact format:

```json
{
  "account_info": {
    "bank_name": "DBS",
    "account_type": "savings",
    "account_name": "BONUS$AVER",
    "last_four": "0941",
    "statement_date": "2025-12-30",
    "period_start": "2025-12-01",
    "period_end": "2025-12-30"
  },
  "transactions": [
    {
      "transaction_date": "2025-12-23",
      "merchant_original": "TOYOTA TSUSHO ASIA PACIFIC PTE.",
      "merchant_cleaned": "TOYOTA TSUSHO ASIA PACIFIC",
      "description": "SG2512220334663",
      "amount": 19525.00,
      "transaction_type": "deposit",
      "balance_after": 165327.09
    }
  ]
}
```

## Parsing Instructions

### Step 1: Identify CSV Structure

CSV files vary by bank, but generally follow patterns:

**Common Patterns:**
1. **Header rows** - Account info, statement period (first few lines)
2. **Column headers** - Field names like "Date", "Description", "Amount"
3. **Transaction rows** - Actual transaction data
4. **Footer rows** - Sometimes totals or notes at the end

**Look for:**
- Statement period/date range
- Account name/number
- Currency
- Column headers (Date, Description, Amount, Balance, etc.)

### Step 2: Extract Account Information

From header rows, extract:

```python
account_info = {
    "bank_name": "DBS",  # Infer from filename, headers, or transaction patterns
    "account_type": "savings" or "credit_card" or "checking",  # Infer from account name/headers
    "account_name": "BONUS$AVER",  # From header row with account details
    "last_four": "0941",  # Last 4 digits of account number
    "statement_date": "2025-12-30",  # End date of statement period
    "period_start": "2025-12-01",  # Start of statement period
    "period_end": "2025-12-30"  # End of statement period
}
```

**Bank Name Detection:**
- DBS/POSB: Look for "BONUS$AVER", "eMULTI CURRENCY", "MULTIPLIER"
- OCBC: Look for "360 ACCOUNT", "EASISAVE"
- UOB: Look for "ONE ACCOUNT", "UNIPLUS"
- Standard Chartered: Look for "BONUSSAVER", "ESAVER"
- Chase: Look for "CHASE", filename patterns
- Bank of America: Look for "BANK OF AMERICA", "BOFA"

**Account Type Detection:**
- Savings: "SAVINGS", "AVER", "SAVER", pattern of interest deposits
- Checking: "CHECKING", "CURRENT", "CHEQUING"
- Credit Card: "CARD", "CREDIT", separate Purchases/Payments columns

### Step 3: Parse Transaction Rows

**Identify transaction columns:**
- Date column (various formats: DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD)
- Description/Merchant column
- Amount columns (could be: single Amount, or separate Debit/Credit, or Deposit/Withdrawal)
- Balance column (optional)

**Handle amount formats:**
- Remove thousands separators: "1,234.56" → 1234.56
- Handle currency symbols: "$1,234.56" → 1234.56
- Determine sign:
  - If separate columns (Deposit/Withdrawal, Debit/Credit): deposit/credit = positive, withdrawal/debit = negative
  - If single Amount column with DR/CR: CR = positive, DR = negative
  - If single Amount column with +/-: keep as is
- **Singapore convention**: Income positive, expenses negative

**Extract transaction fields:**
```python
{
    "transaction_date": "2025-12-23",  # Convert to YYYY-MM-DD format
    "merchant_original": "TOYOTA TSUSHO ASIA PACIFIC PTE. SG2512220334663",  # Full description
    "merchant_cleaned": "TOYOTA TSUSHO ASIA PACIFIC",  # Clean version (remove codes, trailing junk)
    "description": "SG2512220334663",  # Extra details, reference numbers
    "amount": 19525.00,  # Positive for income, negative for expenses
    "transaction_type": "income",  # or "expense", "payment", "transfer", "interest", "fee"
    "balance_after": 165327.09  # Optional: balance after transaction
}
```

**Merchant Cleaning:**
- Remove trailing reference numbers (dates like "SG2512220334663")
- Remove repeated spaces
- Remove bank codes, branch codes
- Trim to meaningful merchant name
- Keep payment method prefixes if useful (e.g., "ONLINE PAY", "GIRO", "PAYNOW")

**Transaction Type Detection:**

IMPORTANT: Only use these valid types (matches database CHECK constraint):
- "income": DEPOSIT, CREDIT, incoming transfers, salary, dividends
- "expense": WITHDRAWAL, DEBIT, ATM, purchases, bills
- "transfer": TRANSFER, NTRF, internal account movements
- "payment": BILL PAYMENT, GIRO, credit card payments
- "interest": INTEREST, BONUS INTEREST
- "fee": FEE, CHARGE, SERVICE CHARGE

### Step 4: Sort Transactions

Ensure transactions are in **chronological order** (oldest first):
- CSVs often have newest first
- Reverse if needed so oldest transaction is first in array

### Step 5: Validate Output

Before returning, check:
- ✅ All required account_info fields present
- ✅ Transactions array not empty
- ✅ Dates in YYYY-MM-DD format
- ✅ Amounts are numbers (not strings)
- ✅ At least merchant_original or merchant_cleaned present
- ✅ Amount signs correct (income positive, expenses negative)

## Example Parsing

**Input CSV:**
```csv
Account transactions shown:,01/12/2025 To 30/12/2025

Account Name,Account Number,Currency,Current Balance,Available Balance
BONUS$AVER,'6109750941,SGD,"165,327.09 CR","20,327.09 CR"

Date,Transaction,Currency,Deposit,Withdrawal,Running Balance
23/12/2025,TOYOTA TSUSHO ASIA PACIFIC PTE. SG2512220334663,SGD,"19,525.00","","165,327.09 CR"
09/12/2025,TRANSFER WITHDRAWAL NTRF TO:6129962006,SGD,"","500.00","145,802.09 CR"
01/12/2025,BONUS INTEREST (SALARY),SGD,"123.29","","145,334.13 CR"
```

**Output JSON:**
```json
{
  "account_info": {
    "bank_name": "DBS",
    "account_type": "savings",
    "account_name": "BONUS$AVER",
    "last_four": "0941",
    "statement_date": "2025-12-30",
    "period_start": "2025-12-01",
    "period_end": "2025-12-30"
  },
  "transactions": [
    {
      "transaction_date": "2025-12-01",
      "merchant_original": "BONUS INTEREST (SALARY)",
      "merchant_cleaned": "BONUS INTEREST",
      "description": "SALARY",
      "amount": 123.29,
      "transaction_type": "interest",
      "balance_after": 145334.13
    },
    {
      "transaction_date": "2025-12-02",
      "merchant_original": "TOYOTA TSUSHO ASIA PACIFIC PTE. TTAPCLAIM IBFTO",
      "merchant_cleaned": "TOYOTA TSUSHO ASIA PACIFIC",
      "description": "TTAPCLAIM IBFTO",
      "amount": 2467.96,
      "transaction_type": "income",
      "balance_after": 147802.09
    },
    {
      "transaction_date": "2025-12-09",
      "merchant_original": "TRANSFER WITHDRAWAL NTRF TO:6129962006",
      "merchant_cleaned": "TRANSFER WITHDRAWAL",
      "description": "NTRF TO:6129962006",
      "amount": -500.00,
      "transaction_type": "transfer",
      "balance_after": 145802.09
    },
    {
      "transaction_date": "2025-12-23",
      "merchant_original": "TOYOTA TSUSHO ASIA PACIFIC PTE. SG2512220334663",
      "merchant_cleaned": "TOYOTA TSUSHO ASIA PACIFIC",
      "description": "SG2512220334663",
      "amount": 19525.00,
      "transaction_type": "income",
      "balance_after": 165327.09
    }
  ]
}
```

## Common CSV Formats

### Format 1: Deposit/Withdrawal Columns (DBS, POSB, OCBC)
- Separate columns for deposits and withdrawals
- Amounts without +/- signs
- Balance shows CR/DR suffix

### Format 2: Debit/Credit Columns (Chase, BofA)
- Separate columns for debits and credits
- Amounts without +/- signs
- Balance may be signed number

### Format 3: Single Amount Column (UOB, some banks)
- Single "Amount" column with +/- signs or DR/CR
- Negative = expense, Positive = income

### Format 4: Credit Card CSVs
- Usually: Date, Description, Amount, Category
- All amounts negative except payments/credits
- May have separate "Posted Date" vs "Transaction Date"

## Edge Cases

- **Multiple currencies**: Extract base currency from header, note if transaction in different currency
- **Pending transactions**: Usually not in CSV exports, but if present, note in description
- **Refunds/reversals**: Negative of normal direction (e.g., negative withdrawal = refund)
- **Fees within transactions**: Sometimes embedded in description, extract if clear
- **Split transactions**: Keep as single transaction, note in description if needed
- **Empty rows**: Skip blank rows between sections
- **Summary rows**: Ignore totals, opening/closing balance rows at end

## Important Notes

1. **Date format varies by region** - Auto-detect format (DD/MM/YYYY vs MM/DD/YYYY)
2. **Amount sign convention** - Always: income positive, expenses negative
3. **Merchant cleaning** - Remove junk but keep useful context
4. **Transaction type** - Best effort guess, categorization will refine later
5. **Balance field optional** - Not all CSVs have it, OK to omit
6. **Chronological order** - Oldest first (reverse CSV order if needed)
7. **Singapore context** - Familiar with SG banks, payment methods (PayNow, GIRO, FAST)

## Success Criteria

- ✅ Account information extracted correctly
- ✅ All transactions parsed with dates, merchants, amounts
- ✅ Amount signs correct (income +, expenses -)
- ✅ Transactions in chronological order (oldest first)
- ✅ Clean merchant names (removed junk codes)
- ✅ Valid JSON structure matching schema
- ✅ No data loss from original CSV
