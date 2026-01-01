# Database Migrations

This directory contains versioned SQL migration files for the Lavender Ledger database schema.

## Migration Naming Convention

Migrations are named: `{version}_{description}.sql`

- `version`: 3-digit zero-padded number (001, 002, 003, ...)
- `description`: Short snake_case description of the migration

Example: `001_add_ingestion_log.sql`

## How Migrations Work

1. The `schema_migrations` table tracks which migrations have been applied
2. Each migration file contains the SQL statements to modify the schema
3. Migrations are applied in version order
4. Once applied, a migration is recorded in `schema_migrations` and won't run again

## Running Migrations

```bash
# Apply all pending migrations
uv run python scripts/migrate.py

# Check migration status
uv run python scripts/migrate.py --status
```

## Creating a New Migration

1. Create a new file: `migrations/{next_version}_{description}.sql`
2. Add your SQL statements
3. Add a header comment describing the migration
4. Run `scripts/migrate.py` to apply it

## Migration File Format

```sql
-- Migration: Brief description
-- Version: {version}
-- Description: Longer description of what this migration does

-- Your SQL statements here
CREATE TABLE ...
ALTER TABLE ...
CREATE INDEX ...
```
