---
name: memory
description: Manage transaction memory to view patterns, add quick notes, search for merchants, and clean up outdated entries. Use when you need to check what's in memory, add new learnings, or maintain the memory file.
---

# Transaction Memory Management Skill

## Purpose

Manage the transaction memory file (`data/TRANSACTION_MEMORY.md`) to view patterns, add quick learnings, search for specific merchants, and remove outdated entries. This skill helps maintain the quality and relevance of the memory that powers categorization.

The memory file **complements** the database `categorization_rules` table by providing:
- Additional context and notes about merchant patterns
- Quick reference for manual categorization decisions
- Human-readable documentation of categorization logic
- Temporary notes before promoting patterns to database rules

## When to Use

- **View memory** - "Show me what's in my transaction memory"
- **Search patterns** - "Find all Grab patterns in memory"
- **Quick add** - "Remember: Amazon books should be Education"
- **Clean up** - "Remove outdated patterns from memory"
- **Validate** - "Check my memory for conflicts"

## Prerequisites

- Memory file exists at `data/TRANSACTION_MEMORY.md`
- If not exists, will be created from `TRANSACTION_MEMORY.template.md`

## Operations

### 1. View Memory Contents

Display the current memory file with formatted sections.

**Usage:**
```
"Show me my transaction memory"
"What patterns do I have in memory?"
"Display memory contents"
```

**Implementation:**
```python
from pathlib import Path
from src.config import get_config

config = get_config()
data_dir = Path(config["data_directory"])
memory_file = data_dir / "TRANSACTION_MEMORY.md"

if not memory_file.exists():
    # Create from template
    template = Path("TRANSACTION_MEMORY.template.md")
    if template.exists():
        memory_file.write_text(template.read_text())
    else:
        # Create basic template
        memory_file.write_text("""# Transaction Memory

## Merchant Patterns

## Quick Notes

## Categories

""")

# Display contents
print(memory_file.read_text())
```

### 2. Search for Patterns

Find specific merchant patterns or categories.

**Usage:**
```
"Find Grab in memory"
"Search for Shopping category patterns"
```

**Implementation:**
```python
query = "Grab"  # or category name
content = memory_file.read_text()

# Search and highlight matches
import re
for i, line in enumerate(content.split('\n'), 1):
    if re.search(query, line, re.IGNORECASE):
        print(f"Line {i}: {line}")
```

### 3. Add Quick Note

Add a pattern or note to memory.

**Usage:**
```
"Remember: Amazon books should be Education"
"Add note: Grab is Transportation"
```

**Implementation:**
```python
note = "Amazon books -> Education"
content = memory_file.read_text()

# Add under appropriate section
if "## Quick Notes" in content:
    parts = content.split("## Quick Notes")
    notes_section = parts[1].split("\n##")[0]
    new_notes = notes_section.rstrip() + f"\n- {note}\n"
    new_content = parts[0] + "## Quick Notes" + new_notes
    if len(parts[1].split("\n##")) > 1:
        new_content += "\n##" + "\n##".join(parts[1].split("\n##")[1:])
    memory_file.write_text(new_content)
    print(f"✓ Added to memory: {note}")
```

### 4. Promote to Database Rule

Convert memory pattern to database categorization rule.

**Usage:**
```
"Promote 'Amazon books -> Education' to database rule"
```

**Implementation:**
```python
from src.database.models import Database, CategorizationRule

# Parse pattern
merchant_pattern = "AMAZON*BOOKS*"
category = "Education"
confidence = 0.95

# Create rule in database
db = Database(config["database_path"])
rule = CategorizationRule(
    id=None,
    merchant_pattern=merchant_pattern,
    category=category,
    confidence=confidence,
    notes=f"Promoted from memory on {datetime.now().strftime('%Y-%m-%d')}"
)
db.create_categorization_rule(rule)

print(f"✓ Created database rule: {merchant_pattern} -> {category}")
```

### 5. Clean Up Outdated Entries

Remove old or conflicting patterns.

**Usage:**
```
"Remove outdated patterns from memory"
"Clean up memory conflicts"
```

**Implementation:**
Ask user which patterns to remove, then update the file.

## Integration with Categorization

When using the categorization skill:
1. **Check database rules first** (fast, structured)
2. **Consult memory file** for additional context and edge cases
3. **Add new learnings** to memory during categorization
4. **Periodically promote** stable patterns from memory to database

## Notes

- Memory file is markdown for human readability
- Database rules are for production categorization
- Use memory for experimentation and notes
- Promote proven patterns to database for performance
