-- Migration: Enhance categorization rules with complex rule support
-- Version: 002
-- Description: Add support for complex categorization rules with conditions,
--              amount ranges, account filters, and performance tracking.
--              Enables the transaction memory system to learn and store
--              sophisticated patterns beyond simple merchant name matching.

-- Add rule type (simple pattern vs complex with conditions)
ALTER TABLE categorization_rules ADD COLUMN rule_type TEXT DEFAULT 'pattern'
  CHECK(rule_type IN ('pattern', 'complex'));

-- Add JSON blob for complex rule conditions (flexible future extension)
ALTER TABLE categorization_rules ADD COLUMN conditions TEXT;

-- Add common filter columns for efficient querying
ALTER TABLE categorization_rules ADD COLUMN min_amount DECIMAL(10, 2);
ALTER TABLE categorization_rules ADD COLUMN max_amount DECIMAL(10, 2);
ALTER TABLE categorization_rules ADD COLUMN account_type_filter TEXT;

-- Track rule origin and user confirmation
ALTER TABLE categorization_rules ADD COLUMN user_confirmed INTEGER DEFAULT 0;
ALTER TABLE categorization_rules ADD COLUMN auto_created INTEGER DEFAULT 0;

-- Performance tracking for rule learning
ALTER TABLE categorization_rules ADD COLUMN times_rejected INTEGER DEFAULT 0;
ALTER TABLE categorization_rules ADD COLUMN accuracy_score DECIMAL(3, 2);

-- Create indexes for efficient rule matching
CREATE INDEX IF NOT EXISTS idx_rule_type ON categorization_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_user_confirmed ON categorization_rules(user_confirmed);
CREATE INDEX IF NOT EXISTS idx_auto_created ON categorization_rules(auto_created);

-- Example of what these new fields enable:
--
-- Simple pattern rule (existing functionality):
--   merchant_pattern: "WHOLEFDS*"
--   category: "Groceries"
--   rule_type: "pattern"
--   confidence: 1.0
--
-- Complex rule with amount filter:
--   merchant_pattern: "GUARDIAN*"
--   category: "Healthcare"
--   rule_type: "complex"
--   min_amount: NULL
--   max_amount: 20.00
--   confidence: 0.9
--   notes: "Guardian under $20 is usually pharmacy/healthcare"
--
-- Complex rule with account filter:
--   merchant_pattern: "AMZN*"
--   category: "Shopping"
--   rule_type: "complex"
--   account_type_filter: "credit_card"
--   confidence: 0.8
--   notes: "Amazon on credit card usually shopping, not subscriptions"
--
-- Auto-created rule from high-confidence categorization:
--   merchant_pattern: "SPOTIFY*"
--   category: "Subscriptions"
--   rule_type: "pattern"
--   auto_created: 1
--   user_confirmed: 0
--   confidence: 0.95
--   notes: "Auto-created from categorization: Music streaming subscription"
