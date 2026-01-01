---
name: parse-bank-statement-pdf
description: Parse bank statement PDF text into structured transaction data with account information and transactions in consistent JSON format. Works with any bank format. Use when you need to extract or parse transactions from PDF bank statements.
---

# Bank Statement PDF Parsing Skill

## Purpose
Extract structured transaction data from bank statement PDFs. Parse any bank's statement format and return transactions in a consistent JSON structure.

## Input Format
You will receive:
- `pdf_text`: The full text extracted from a PDF bank statement
- `file_name`: The PDF filename (may contain hints about the bank)

## Expected Output
Return a JSON object with:
```json
{
  "account_info": {
    "bank_name": "Chase",
    "account_type": "credit_card",
    "account_name": "Chase Credit Card",
    "last_four": "1234",
    "statement_date": "2024-12-15",
    "period_start": "2024-11-16",
    "period_end": "2024-12-15"
  },
  "transactions": [
    {
      "transaction_date": "2024-12-01",
      "post_date": "2024-12-02",
      "amount": -45.23,
      "merchant_original": "WHOLE FOODS MARKET #12345",
      "description": "GROCERY PURCHASE",
      "transaction_type": "expense"
    }
  ]
}
```

## Field Definitions

### account_info
- **bank_name**: Name of the bank (e.g., "Chase", "Bank of America", "Wells Fargo")
- **account_type**: One of: "credit_card", "checking", "savings"
- **account_name**: Friendly name like "Chase Credit Card (...1234)"
- **last_four**: Last 4 digits of account number
- **statement_date**: Statement closing/end date (YYYY-MM-DD)
- **period_start**: Statement period start date (YYYY-MM-DD)
- **period_end**: Statement period end date (YYYY-MM-DD)

### transactions
Each transaction must have:
- **transaction_date**: Date of transaction (YYYY-MM-DD format, required)
- **post_date**: Posting date if different from transaction date (YYYY-MM-DD, optional)
- **amount**: Transaction amount as a float (required)
  - **Negative for expenses**: -45.23 (money going out)
  - **Positive for income/credits**: +100.00 (money coming in)
  - **Always use negative for purchases/fees, positive for payments/refunds**
- **merchant_original**: Merchant name exactly as it appears on statement (required)
- **description**: Additional description if available (optional)
- **transaction_type**: One of (required):
  - `"expense"` - Regular purchases, bills
  - `"income"` - Deposits, salary, refunds
  - `"payment"` - Credit card payments
  - `"fee"` - Bank fees, late fees
  - `"interest"` - Interest charges
  - `"transfer"` - Transfers between accounts

## Amount Sign Convention (CRITICAL)

**Use consistent negative/positive regardless of how the bank displays it:**

- **Expenses/Purchases**: Always negative (e.g., grocery purchase = -45.23)
- **Income/Deposits**: Always positive (e.g., paycheck = +1000.00)
- **Credit Card Payments**: Always positive (e.g., payment made = +500.00)
- **Fees**: Always negative (e.g., late fee = -35.00)
- **Interest Charges**: Always negative (e.g., interest = -12.50)
- **Refunds/Credits**: Always positive (e.g., refund = +25.00)

## Parsing Guidelines

### 1. Identify Bank and Account
Look for:
- Bank name in header/footer
- Account type keywords (Credit Card, Checking, Savings)
- Account numbers (use last 4 digits only)
- Statement dates

### 2. Find Transaction Section
Banks typically have sections like:
- "Transactions", "Activity", "Account Activity"
- "Purchases", "Payments and Credits"
- Transaction tables with columns

### 3. Extract Each Transaction
For each transaction line:
- Date (various formats: MM/DD, MM/DD/YYYY, DD-MMM-YY)
- Merchant/description
- Amount (handle various formats: $1,234.56, 1234.56, (1234.56) for negatives)
- Apply consistent sign convention

### 4. Determine Transaction Type
Use these heuristics:
- **PAYMENT, THANK YOU, AUTOPAY**: payment
- **DEPOSIT, DIRECT DEPOSIT, ACH CREDIT**: income
- **FEE, CHARGE, PENALTY**: fee
- **INTEREST CHARGED**: interest
- **TRANSFER, XFER**: transfer
- **ATM WITHDRAWAL**: expense
- **Everything else**: expense (if negative) or income (if positive)

### 5. Handle Edge Cases
- **Missing dates**: Use statement end date as fallback
- **Subtotals/totals**: Skip lines like "Total Purchases", "Balance Forward"
- **Multiple pages**: Parse all transactions across all pages
- **Foreign transactions**: Convert to base currency if exchange rate shown
- **Pending transactions**: Exclude if explicitly marked as pending

## Quality Checks

Before returning:
1. **All required fields present** for each transaction
2. **Dates are valid** and in YYYY-MM-DD format
3. **Amounts are numbers** (not strings)
4. **Signs are consistent** (expenses negative, income positive)
5. **At least some transactions found** (warn if zero)
6. **Transaction dates within statement period** (or close to it)

## Example Input/Output

### Input PDF Text (excerpt):
```
CHASE CREDIT CARD STATEMENT
Account ending in 1234
Statement Period: 11/16/2024 - 12/15/2024

PURCHASES
12/01  WHOLE FOODS MKT #456      45.23
12/03  SHELL OIL 789012          38.50
12/05  AMAZON.COM*MARKETPLACE    124.99

PAYMENTS AND CREDITS
12/10  ONLINE PAYMENT - THANK YOU  500.00CR
```

### Expected Output:
```json
{
  "account_info": {
    "bank_name": "Chase",
    "account_type": "credit_card",
    "account_name": "Chase Credit Card (...1234)",
    "last_four": "1234",
    "statement_date": "2024-12-15",
    "period_start": "2024-11-16",
    "period_end": "2024-12-15"
  },
  "transactions": [
    {
      "transaction_date": "2024-12-01",
      "amount": -45.23,
      "merchant_original": "WHOLE FOODS MKT #456",
      "transaction_type": "expense"
    },
    {
      "transaction_date": "2024-12-03",
      "amount": -38.50,
      "merchant_original": "SHELL OIL 789012",
      "transaction_type": "expense"
    },
    {
      "transaction_date": "2024-12-05",
      "amount": -124.99,
      "merchant_original": "AMAZON.COM*MARKETPLACE",
      "transaction_type": "expense"
    },
    {
      "transaction_date": "2024-12-10",
      "amount": 500.00,
      "merchant_original": "ONLINE PAYMENT - THANK YOU",
      "transaction_type": "payment"
    }
  ]
}
```

## Important Notes

1. **Be thorough** - Extract ALL transactions, not just a sample
2. **Preserve original merchant names** - Don't clean them yet
3. **Use consistent date format** - Always YYYY-MM-DD
4. **Handle year rollovers** - If statement is Dec 2024 but transaction shows Jan, it's Jan 2025
5. **Return valid JSON** - No markdown, just pure JSON
6. **If uncertain about amount sign** - Follow the convention: expenses negative, income positive
7. **If parsing fails** - Return partial results with what you could parse, include error message
