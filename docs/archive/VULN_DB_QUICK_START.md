# Vulnerability Database - Quick Start Guide

## Setup (One-Time)

```bash
# Activate virtual environment
source venv/bin/activate

# Load bugs from CSV
python backend/db/load_bugs.py bugs/Cat9Kbugs_IOSXE_17.csv --limit 100

# Verify database
python backend/db/get_last_update.py

# Run tests
python backend/db/test_vuln_db.py
```

## Daily Operations

### Check Database Status
```bash
python backend/db/get_last_update.py
```

### Incremental Update
```bash
# Load only new/modified bugs
python backend/db/incremental_update.py bugs/Cat9Kbugs_IOSXE_17.csv
```

### Full Reload (if needed)
```bash
# Remove old database
rm vulnerability_db.sqlite

# Reload all bugs
python backend/db/load_bugs.py bugs/Cat9Kbugs_IOSXE_17.csv
```

## Query Examples

### Python - Scan Device for Vulnerabilities

```python
import sqlite3
from backend.core.version_patterns import VersionPatternDetector
from backend.core.version_matcher import VersionMatcher

# Connect to database
conn = sqlite3.connect('vulnerability_db.sqlite')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Device info
device_version = "17.10.1"
platform = "IOS-XE"

# Query bugs
cursor.execute('''
    SELECT bug_id, headline, version_pattern, version_min, version_max,
           affected_versions_raw, fixed_version, labels, severity
    FROM vulnerabilities
    WHERE platform = ?
''', (platform,))

bugs = cursor.fetchall()

# Match against device
matcher = VersionMatcher()
detector = VersionPatternDetector()

print(f"Scanning {platform} {device_version}...\n")

for bug in bugs:
    # Parse explicit versions if needed
    explicit_versions = []
    if bug['version_pattern'] == 'EXPLICIT':
        pattern = detector.detect_pattern(bug['affected_versions_raw'])
        explicit_versions = pattern['versions']

    # Check if vulnerable
    is_vuln, reason = matcher.is_version_affected(
        device_version=device_version,
        pattern_type=bug['version_pattern'],
        version_min=bug['version_min'],
        version_max=bug['version_max'],
        explicit_versions=explicit_versions,
        fixed_version=bug['fixed_version']
    )

    if is_vuln:
        print(f"[Sev {bug['severity']}] {bug['bug_id']}: {bug['headline']}")
        print(f"  Reason: {reason}")
        print(f"  Labels: {bug['labels']}")
        print()

conn.close()
```

### SQL - Direct Queries

```bash
# Open database
sqlite3 vulnerability_db.sqlite

# Query bugs by severity
SELECT bug_id, headline, severity, version_pattern
FROM vulnerabilities
WHERE severity <= 2
ORDER BY severity
LIMIT 10;

# Query bugs with labels
SELECT v.bug_id, v.headline, v.labels
FROM vulnerabilities v
WHERE v.labels != '[]'
LIMIT 10;

# Query by specific label
SELECT v.bug_id, v.headline
FROM vulnerabilities v
JOIN label_index l ON v.id = l.vulnerability_id
WHERE l.label = 'MGMT_SSH_HTTP';

# Pattern distribution
SELECT version_pattern, COUNT(*) as count
FROM vulnerabilities
GROUP BY version_pattern
ORDER BY count DESC;
```

## Testing

### Run All Tests
```bash
python backend/db/test_vuln_db.py
```

### Test Version Matching Manually
```bash
python backend/core/version_matcher.py
```

### Test Pattern Detection
```bash
python backend/core/version_patterns.py
```

## Common Issues

### Database Locked
```bash
# Close all connections, remove DB, reload
rm vulnerability_db.sqlite
python backend/db/load_bugs.py bugs/Cat9Kbugs_IOSXE_17.csv --limit 10
```

### Import Errors
```bash
# Ensure you're in project root with venv activated
cd /path/to/cve_EVAL_V2
source venv/bin/activate
```

### Slow Queries
```bash
# Check database size
ls -lh vulnerability_db.sqlite

# Check indexes
sqlite3 vulnerability_db.sqlite ".schema vulnerabilities"

# Analyze query performance
sqlite3 vulnerability_db.sqlite "EXPLAIN QUERY PLAN SELECT * FROM vulnerabilities WHERE platform = 'IOS-XE'"
```

## Version Pattern Cheat Sheet

| Raw String | Pattern | Min | Max | Description |
|------------|---------|-----|-----|-------------|
| `17.10.1 17.12.4` | EXPLICIT | 17.10.1 | 17.12.4 | Only these versions |
| `17.10.x` | WILDCARD | 17.10.0 | - | All 17.10.* |
| `17.10.3 and later` | OPEN_LATER | 17.10.3 | - | 17.10.3+ (same train) |
| `17.10 and later` | MAJOR_WILDCARD | 17.10 | - | 17.10.*, 17.11.*, ... |
| `17.10.4 and earlier` | OPEN_EARLIER | - | 17.10.4 | ≤ 17.10.4 |

**Key:** "17.10.3 and later" means 17.10.* train only (NOT 17.11.x)

## Performance Targets

- **Query time**: <10ms for platform filter
- **Matching time**: <100ms for 2,819 bugs
- **Total scan**: <100ms per device

**Actual (10 bugs):**
- Query: 0.04ms
- Matching: 0.07ms
- Total: 0.11ms ✅

## Next Steps

1. Load full dataset (20K bugs)
2. Test performance with full dataset
3. Add PSIRT loading
4. Build FastAPI scanning endpoint
5. Integrate with web UI

## File Locations

- **Database**: `vulnerability_db.sqlite` (in project root)
- **Bug CSV**: `bugs/Cat9Kbugs_IOSXE_17.csv`
- **Training Data**: `training_data_bugs_20251008_142230.csv`
- **Schema**: `backend/db/vuln_schema.sql`
- **Code**: `backend/core/` and `backend/db/`
