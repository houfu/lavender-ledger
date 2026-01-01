# Transaction Memory

This file stores additional context and patterns for transaction categorization that complement the database `categorization_rules` table.

## Purpose

- **Additional context** - Notes and observations about merchant patterns
- **Quick reference** - Manual categorization decisions and reasoning
- **Experimentation** - Try patterns before promoting to database
- **Documentation** - Human-readable categorization logic

## How It Works

1. **Database rules** (categorization_rules table) - Fast, structured, production
2. **Memory file** (this file) - Context, notes, experimentation
3. **Workflow**: Memory → Test → Database

## Merchant Patterns

### Singapore Merchants

#### Transportation
- Grab / GrabCar / GrabFood delivery
- ComfortDelGro taxi
- SMRT transit
- LTA parking
- ERP charges

#### Groceries
- FairPrice / NTUC
- Cold Storage
- Sheng Siong
- Giant
- Prime / Amazon Fresh

#### Dining
- Kopitiam
- Food courts
- Hawker centres (use description)
- Deliveroo / Foodpanda

#### Shopping
- Lazada
- Shopee
- Qoo10
- Uniqlo
- Daiso

### International Merchants

#### E-commerce
- Amazon (check description: books=Education, etc.)
- eBay
- AliExpress

#### Streaming / Subscriptions
- Netflix → Entertainment
- Spotify → Entertainment
- Apple Music → Entertainment
- YouTube Premium → Entertainment

#### Software
- Adobe → Subscriptions
- Microsoft → Subscriptions
- Google Workspace → Professional Services

## Quick Notes

- Add temporary notes here
- Review periodically and promote to database rules

## Categories Reference

**Income:**
- Salary, Freelance, Investment Income, Other Income

**Expenses:**
- Groceries, Dining & Restaurants, Transportation
- Housing, Healthcare, Entertainment, Shopping
- Subscriptions, Travel, Personal Care, Education
- Insurance, Gifts & Donations, Pets, Childcare & Kids
- Home Improvement, Professional Services
- Fees & Interest, Taxes

**Special:**
- Transfer, Credit Card Payment, Uncategorized

## Confidence Scoring

- **1.00** - Certain (e.g., "NETFLIX" → Entertainment)
- **0.90-0.99** - Very confident (e.g., "WHOLE FOODS" → Groceries)
- **0.80-0.89** - Confident with minor ambiguity
- **0.70-0.79** - Moderate (e.g., "AMAZON" - need description)
- **<0.70** - Low confidence, flag for review

## Maintenance

- Review monthly
- Remove outdated patterns
- Promote stable patterns to database rules
- Keep file concise and relevant
