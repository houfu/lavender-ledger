#!/bin/bash
# Clean Lavender Ledger to Fresh Installation State
# This script resets the system while preserving the repository structure

set -e  # Exit on error

echo "🧹 Lavender Ledger - Fresh Installation Cleanup"
echo "==============================================="
echo ""

# Check if data directory exists
if [ ! -d "data" ]; then
    echo "✓ No data directory found - already clean!"
    exit 0
fi

echo "This will remove:"
echo "  - Database (finance.db and backups)"
echo "  - All log files"
echo "  - Archived statements"
echo "  - Transaction memory file"
echo "  - macOS .DS_Store files"
echo ""
echo "This will keep:"
echo "  - Staging folder and any PDFs/CSVs in it"
echo "  - Directory structure (.gitkeep files)"
echo ""

read -p "Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Starting cleanup..."
echo ""

# Remove database files
if [ -f "data/finance.db" ]; then
    echo "  🗑️  Removing database: data/finance.db"
    rm -f data/finance.db
fi

if compgen -G "data/finance.db.backup-*" > /dev/null; then
    echo "  🗑️  Removing database backups"
    rm -f data/finance.db.backup-*
fi

# Remove transaction memory
if [ -f "data/TRANSACTION_MEMORY.md" ]; then
    echo "  🗑️  Removing transaction memory: data/TRANSACTION_MEMORY.md"
    rm -f data/TRANSACTION_MEMORY.md
fi

# Clear logs directory (keep .gitkeep)
if [ -d "data/logs" ]; then
    echo "  🗑️  Clearing logs directory"
    find data/logs -type f ! -name '.gitkeep' -delete
fi

# Clear archive directory (keep structure)
if [ -d "data/statements/archive" ]; then
    echo "  🗑️  Clearing archive directory"
    find data/statements/archive -type f ! -name '.gitkeep' -delete
    # Remove empty subdirectories
    find data/statements/archive -type d -empty ! -path "data/statements/archive" -delete
fi

# Remove .DS_Store files (macOS artifacts)
echo "  🗑️  Removing .DS_Store files"
find data -name '.DS_Store' -delete 2>/dev/null || true

# Summary of what's left
echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Fresh installation state achieved:"
echo "  ✓ Database removed (will be created on init)"
echo "  ✓ Logs cleared"
echo "  ✓ Archive cleared"
echo "  ✓ Memory file removed"
echo ""

# Check if staging has files
STAGING_COUNT=$(find data/statements/staging -type f ! -name '.DS_Store' ! -name '.gitkeep' | wc -l | tr -d ' ')
if [ "$STAGING_COUNT" -gt 0 ]; then
    echo "📄 Staging folder still contains $STAGING_COUNT file(s):"
    find data/statements/staging -type f ! -name '.DS_Store' ! -name '.gitkeep' -exec basename {} \;
    echo ""
    echo "These files are preserved for testing."
    echo "Remove them manually if you want a completely clean state."
fi

echo ""
echo "Next steps:"
echo "  1. Initialize database:    uv run python scripts/init_db.py"
echo "  2. Test ingestion:         Place PDFs in data/statements/staging/"
echo "  3. Run ingestion:          Ask Claude Code to run ingestion skill"
echo ""
