---
name: categorize-transactions
description: Categorize financial transactions by analyzing merchant names, amounts, and context. Assigns spending categories with confidence scores and suggests pattern rules. Use when you need to categorize transactions or determine spending patterns.
---

# Transaction Categorization Skill

## Purpose
Automatically categorize financial transactions by analyzing merchant names, amounts, and context to assign appropriate spending categories with confidence scores.

## Input Format
You will receive a JSON object with:
- `transactions`: Array of transactions to categorize
- `available_categories`: List of valid category names
- `existing_rules`: Array of existing pattern-to-category mappings for reference
- `memory_context` (optional): Content from TRANSACTION_MEMORY.md with personal context and learnings

### Transaction Object
```json
{
  "id": 1,
  "date": "2024-12-15",
  "amount": -45.23,
  "merchant_original": "WHOLEFDS MKTPL #12345",
  "merchant_cleaned": "WHOLEFDS MKTPL",
  "description": "WHOLE FOODS MARKET PURCHASE",
  "account_type": "credit_card"
}
```

## Expected Output
Return a JSON object with categorizations:
```json
{
  "categorizations": [
    {
      "transaction_id": 1,
      "category": "Groceries",
      "confidence": 0.95,
      "rule_pattern": "WHOLEFDS*",
      "reasoning": "Whole Foods Market is a well-known grocery store chain."
    }
  ]
}
```

## Confidence Scoring Guidelines

- **1.00**: Absolutely certain (e.g., "WHOLE FOODS" -> Groceries)
- **0.90-0.99**: Very confident (e.g., "CHEVRON" -> Transportation)
- **0.80-0.89**: Confident with minor ambiguity (e.g., "CVS" could vary)
- **0.70-0.79**: Moderately confident (e.g., "AMAZON" - varies widely)
- **<0.70**: Low confidence, flag for review (e.g., "ACH TRANSFER XYZ")

## Context Clues

### Amount
- Small pharmacy amounts (<$20): likely Healthcare
- Large pharmacy amounts (>$100): likely Shopping

### Account Type
- Credit card payments -> "Credit Card Payment"
- Transfers between accounts -> "Transfer"

### Description Keywords
- "PAYMENT THANK YOU" -> Credit Card Payment
- "ATM WITHDRAWAL" -> Transfer
- Contains "MARKET", "FOODS", "GROCERY" -> Groceries
- Contains "RESTAURANT", "CAFE", "PIZZA" -> Dining & Restaurants
- Contains "GAS", "FUEL", "CHEVRON", "SHELL" -> Transportation

### Recurring Patterns
- Same merchant, same amount, recurring -> likely Subscription

## Ambiguous Cases

- **Amazon/Online Retailers**: Default to "Shopping" unless description gives clue
- **Walmart/Target**: Prefer "Shopping" as more general
- **CVS/Walgreens**: "Healthcare" for small amounts, "Shopping" for large
- **ACH Transfers**: Flag for review if purpose unclear
- **Venmo/PayPal/Zelle**: Flag for review - person-to-person

## Rule Pattern Guidelines

Use wildcards (*) for flexible matching:
- `WHOLEFDS*` matches all Whole Foods locations
- `SPOTIFY*` matches various Spotify formats
- `AMAZON.COM*` matches Amazon purchases

Avoid overly generic patterns:
- Don't use `MARKET*` (too broad)
- Don't use `CAFE*` alone (could match unrelated)

## Categories Available

### Income
- Salary, Freelance, Investment Income, Other Income

### Expenses
- Groceries
- Dining & Restaurants
- Transportation
- Housing
- Healthcare
- Entertainment
- Shopping
- Subscriptions
- Travel
- Personal Care
- Education
- Insurance
- Gifts & Donations
- Pets
- Childcare & Kids
- Home Improvement
- Professional Services
- Fees & Interest
- Taxes

### Special
- Uncategorized
- Transfer
- Credit Card Payment

## Memory Context Integration (Phase 3)

**When `memory_context` is provided**, use it to improve categorization accuracy:

### How to Use Memory
1. **Read the memory** before categorizing transactions
2. **Apply learned patterns** from "Merchant Patterns & Preferences" section
3. **Use personal context** (location, household, payment methods) to resolve ambiguities
4. **Follow anti-patterns** documented in the memory
5. **Increase confidence** when memory provides clear guidance
6. **Decrease confidence** when memory suggests ambiguity

### Examples of Memory-Enhanced Categorization

**Example 1: Time-Based Patterns**
```
Memory says: "Grab weekday mornings (7-9am): Transportation (commute)"
Transaction: GRAB HOLDINGS, $8.50, 2025-08-15 07:30
Without memory: Dining & Restaurants (0.70) - uncertain
With memory: Transportation (0.90) - high confidence due to time pattern
```

**Example 2: Merchant-Specific Rules**
```
Memory says: "Amazon - always flag for review, too varied"
Transaction: AMAZON.COM, $45.99
Without memory: Shopping (0.75)
With memory: Shopping (0.65) - lower confidence, flag for review
```

**Example 3: PayLah/PayNow Extraction**
```
Memory says: "PayLah - check description for actual merchant"
Transaction: PAYLAH, description: "FAIRPRICE FINEST"
Without memory: Transfer (0.80)
With memory: Groceries (0.85) - extracted merchant from description
```

**Example 4: Amount-Based Rules**
```
Memory says: "Guardian Pharmacy: <$20 = Healthcare, >$50 = Shopping"
Transaction: GUARDIAN, $15.50
Without memory: Healthcare (0.75)
With memory: Healthcare (0.90) - amount confirms it's medicine
```

**Example 5: Personal Context**
```
Memory says: "Location: Singapore, Smart Buddy is school canteen"
Transaction: SMART BUDDY, $3.50
Without memory: Dining & Restaurants (0.70)
With memory: Childcare & Kids (0.95) - local context provides certainty
```

### Confidence Adjustments with Memory

When memory provides clear guidance:
- **Increase confidence by +0.10 to +0.20** (e.g., 0.75 → 0.90)
- **Prefer specific categories** over general ones when memory suggests it
- **Add memory reference in reasoning**: "Based on transaction memory, Grab on weekday mornings is typically commute transportation"

When memory indicates ambiguity or "always flag":
- **Decrease confidence by -0.05 to -0.10** (e.g., 0.80 → 0.70)
- **Flag for review** even if you'd normally be confident
- **Note in reasoning**: "Transaction memory indicates this merchant varies, flagging for review"

### Memory Sections to Pay Attention To

1. **Personal Context**: Understand user's location, banks, household
2. **Merchant Patterns & Preferences**: Time-based, usage patterns for specific merchants
3. **Known Ambiguous Merchants**: Amount-based thresholds, context clues
4. **Category Preferences**: User's preferences for edge cases
5. **Learnings from Past Reviews**: Recent confirmations and rejections
6. **Anti-Patterns**: Things to never auto-categorize
7. **Complex Rules & Patterns**: Amount ranges, time windows, description parsing

### Rule Pattern Suggestions with Memory

When memory shows confirmed patterns:
- **Suggest rules confidently** if memory confirms the pattern multiple times
- **Don't suggest rules** if memory says "always flag for review"
- **Include conditions** (amount ranges) if memory specifies them
- **Reference memory in reasoning**: "Pattern confirmed in transaction memory"

## Important Notes

1. Always provide reasoning for transparency
2. If genuinely unsure, prefer flagging over guessing (confidence < 0.7)
3. Suggest rules conservatively - only for clear patterns
4. Be consistent across similar merchants
5. Process all transactions in the batch
6. **NEW: When memory_context is provided, prioritize it over generic categorization logic**
7. **NEW: Reference memory in reasoning when it influenced your decision**
