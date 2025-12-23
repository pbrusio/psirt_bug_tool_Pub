# Vulnerability Database System

Complete SQLite-based vulnerability database for fast scanning of Cisco bugs and PSIRTs against device versions and labels.

## Overview

This database system provides:
- **Fast scanning**: <100ms to check 2,819+ vulnerabilities
- **Smart version matching**: Handles wildcards, ranges, and "and later" patterns
- **Incremental updates**: Track last update and only insert new bugs
- **Label integration**: Links bugs to ML-labeled features
- **Flexible queries**: Search by version, platform, label, or severity

## Architecture

### Database Schema

**Tables:**
1. `vulnerabilities` - Main table (1 row per bug/PSIRT)
2. `version_index` - Fast version lookups (normalized versions)
3. `label_index` - Fast label-based queries
4. `db_metadata` - Incremental update tracking

**Key Columns:**
- `version_pattern`: EXPLICIT, WILDCARD, OPEN_LATER, OPEN_EARLIER, MAJOR_WILDCARD
- `version_min/max`: Normalized version boundaries
- `fixed_version`: First fixed release
- `labels`: JSON array of feature labels

### Version Pattern Detection

The system intelligently detects 5 version pattern types:

| Pattern | Example | Meaning | Matches |
|---------|---------|---------|---------|
| **EXPLICIT** | `17.10.1 17.12.4` | Only these versions | Exact matches only |
| **WILDCARD** | `17.10.x` | All in minor train | 17.10.0, 17.10.1, ... (not 17.11.x) |
| **OPEN_LATER** | `17.10.3 and later` | X and later in SAME train | 17.10.3+ (not 17.11.x) |
| **OPEN_EARLIER** | `17.10.4 and earlier` | X and earlier | ≤17.10.4 |
| **MAJOR_WILDCARD** | `17.10 and later` | All later trains | 17.10.x, 17.11.x, 17.12.x... |

**Key Logic:** "17.10.3 and later" only matches 17.10.* train (NOT 17.11.x). The "and later" applies to the most specific digit.

### Version Matching

**Rules:**
1. Parse device version and normalize (17.03.05 → 17.3.5)
2. Check pattern type and apply matching logic
3. Respect fixed version: If device ≥ fixed_version, NOT vulnerable
4. Handle train boundaries for OPEN_LATER pattern

**Example:**
```python
from backend.core.version_matcher import VersionMatcher

matcher = VersionMatcher()

# Bug: 17.10.3 and later (OPEN_LATER pattern)
is_vuln, reason = matcher.is_version_affected(
    device_version="17.10.5",
    pattern_type="OPEN_LATER",
    version_min="17.10.3",
    version_max=None,
    explicit_versions=[],
    fixed_version="17.10.7"
)

# Result: (True, "Device version 17.10.5 >= 17.10.3 (within same train)")
```

## Components

### 1. Schema Definition
**File:** `vuln_schema.sql`

Creates database tables with indexes optimized for fast scanning.

### 2. Version Pattern Detector
**File:** `backend/core/version_patterns.py`

Detects version patterns from raw CSV strings.

**Usage:**
```python
from backend.core.version_patterns import VersionPatternDetector

detector = VersionPatternDetector()

result = detector.detect_pattern("17.10.1 17.12.4 17.13.1")
# {'pattern': 'EXPLICIT',
#  'version_min': '17.10.1',
#  'version_max': '17.13.1',
#  'versions': ['17.10.1', '17.12.4', '17.13.1']}

result = detector.detect_pattern("17.10.3 and later")
# {'pattern': 'OPEN_LATER',
#  'version_min': '17.10.3',
#  'description': '17.10.3 and later (within 17.10.* train)'}
```

### 3. Version Matcher
**File:** `backend/core/version_matcher.py`

Matches device versions against vulnerability patterns.

**Usage:**
```python
from backend.core.version_matcher import VersionMatcher

matcher = VersionMatcher()

is_vuln, reason = matcher.is_version_affected(
    device_version="17.10.1",
    pattern_type="EXPLICIT",
    version_min="17.10.1",
    version_max="17.13.1",
    explicit_versions=["17.10.1", "17.12.4", "17.13.1"]
)
# (True, "Device version 17.10.1 matches explicit vulnerable version")
```

### 4. Bug Loader
**File:** `backend/db/load_bugs.py`

Loads bugs from CSV into database with label integration.

**Usage:**
```bash
# Load 10 bugs (testing)
python backend/db/load_bugs.py bugs/Cat9Kbugs_IOSXE_17.csv --limit 10

# Load all bugs
python backend/db/load_bugs.py bugs/Cat9Kbugs_IOSXE_17.csv

# Custom database path
python backend/db/load_bugs.py bugs/Cat9Kbugs_IOSXE_17.csv --db custom.sqlite
```

**Features:**
- Detects version patterns automatically
- Integrates labels from `training_data_bugs_20251008_142230.csv`
- Creates version and label indexes
- Shows progress and statistics

### 5. Incremental Update
**File:** `backend/db/incremental_update.py`

Updates database with only new/modified bugs.

**Usage:**
```bash
# Incremental update (skips duplicates)
python backend/db/incremental_update.py bugs/Cat9Kbugs_IOSXE_17.csv

# Updates db_metadata with new timestamp
```

### 6. Get Last Update
**File:** `backend/db/get_last_update.py`

CLI tool to show database status and last update timestamp.

**Usage:**
```bash
python backend/db/get_last_update.py
```

**Output:**
```
================================================================================
VULNERABILITY DATABASE STATUS
================================================================================
Database: /home/.../vulnerability_db.sqlite

Schema Version: 1.0
Last Update:    2025-10-10T13:03:25.802303
                (0 days ago)

Total Vulnerabilities: 2819
  Bugs:                2819
  PSIRTs:              0
  With Labels:         145

Platform Distribution:
  IOS-XE: 2819

Version Pattern Distribution:
  EXPLICIT: 2650
  WILDCARD: 120
  OPEN_LATER: 35
  UNKNOWN: 14
================================================================================
```

### 7. Test Suite
**File:** `backend/db/test_vuln_db.py`

Comprehensive test suite for database and version matching.

**Usage:**
```bash
python backend/db/test_vuln_db.py
```

**Tests:**
1. Database loading verification
2. Version matching logic
3. Query performance (<100ms target)
4. Incremental update metadata

## Quick Start

### 1. Initial Database Setup

```bash
# Activate virtual environment
source venv/bin/activate

# Load bugs from CSV (initial load)
python backend/db/load_bugs.py bugs/Cat9Kbugs_IOSXE_17.csv --limit 100

# Check database status
python backend/db/get_last_update.py

# Run tests
python backend/db/test_vuln_db.py
```

### 2. Query Examples

**Query bugs affecting specific version:**
```python
import sqlite3
from backend.core.version_patterns import VersionPatternDetector
from backend.core.version_matcher import VersionMatcher

conn = sqlite3.connect('vulnerability_db.sqlite')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all IOS-XE bugs
cursor.execute('''
    SELECT bug_id, headline, version_pattern, version_min, version_max,
           affected_versions_raw, fixed_version
    FROM vulnerabilities
    WHERE platform = 'IOS-XE'
''')

bugs = cursor.fetchall()

# Match against device version
device_version = "17.10.1"
matcher = VersionMatcher()
detector = VersionPatternDetector()

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
        print(f"VULNERABLE: {bug['bug_id']} - {bug['headline']}")

conn.close()
```

**Query bugs by label:**
```python
import sqlite3

conn = sqlite3.connect('vulnerability_db.sqlite')
cursor = conn.cursor()

# Find bugs with specific label
label = "MGMT_SSH_HTTP"

cursor.execute('''
    SELECT v.bug_id, v.headline, v.labels
    FROM vulnerabilities v
    JOIN label_index l ON v.id = l.vulnerability_id
    WHERE l.label = ?
''', (label,))

bugs = cursor.fetchall()

for bug in bugs:
    print(f"{bug[0]}: {bug[1]}")

conn.close()
```

### 3. Incremental Updates

```bash
# Day 1: Initial load
python backend/db/load_bugs.py bugs/Cat9Kbugs_IOSXE_17.csv

# Day 2: Incremental update (skips duplicates)
python backend/db/incremental_update.py bugs/Cat9Kbugs_IOSXE_17.csv

# Check last update
python backend/db/get_last_update.py
```

## Performance

**Target:** <100ms to scan 2,819 bugs for a single device version

**Actual Performance (10 bugs):**
- Query time: 0.04 ms
- Matching time: 0.07 ms
- Total: 0.11 ms

**Optimizations:**
- Indexed columns: `platform`, `version_pattern`, `bug_id`
- Version index for fast version lookups
- Label index for label-based queries
- Row factory for efficient row access

## Data Sources

**Bug CSV:** `bugs/Cat9Kbugs_IOSXE_17.csv`
- 20,254 rows (Catalyst 9K bugs for IOS-XE 17.x)
- Columns: BUG Id, headline, severity, Known Affected Release(s), Known Fixed Releases

**Training Data:** `training_data_bugs_20251008_142230.csv`
- 4,665 bug summaries with ML-generated labels
- Used to enrich bugs with feature labels

## Current Capabilities

| Feature | Status | Implementation |
|---------|--------|----------------|
| PSIRT Loading | Done | `load_psirts.py` |
| Multi-platform | Done | IOS-XE, IOS-XR, ASA, FTD, NX-OS |
| Web API | Done | FastAPI endpoints in `routes.py` |
| Three-tier Caching | Done | DB → FAISS → MLX inference |
| Offline Updates | Done | `backend/core/updater.py` with version pattern detection |
| Hardware Filtering | Done | `hardware_extractor.py` |

## Future Enhancements

1. **CVE Mapping:** Link bugs to CVE IDs
2. **Better SMU parsing:** Handle interim builds and SMU versions

## File Structure

```
backend/
├── core/
│   ├── version_patterns.py    # Pattern detection (EXPLICIT, OPEN_LATER, etc.)
│   ├── version_matcher.py     # Version matching logic
│   └── updater.py             # Offline update with version pattern detection
└── db/
    ├── vuln_schema.sql         # Database schema
    ├── load_bugs.py            # Bug CSV loader
    ├── load_psirts.py          # PSIRT JSON loader
    ├── hardware_extractor.py   # Hardware model extraction
    ├── incremental_update.py   # Incremental update system
    ├── get_last_update.py      # CLI status tool
    ├── test_vuln_db.py         # Test suite
    └── README_VULN_DB.md       # This file
```

## Troubleshooting

**Database locked error:**
```bash
# Close all connections, then:
rm vulnerability_db.sqlite
python backend/db/load_bugs.py bugs/Cat9Kbugs_IOSXE_17.csv --limit 10
```

**Import errors:**
```bash
# Ensure you're in project root and venv is activated
source venv/bin/activate
python backend/db/test_vuln_db.py
```

**Performance issues:**
```bash
# Check database size and indexes
sqlite3 vulnerability_db.sqlite ".schema"
sqlite3 vulnerability_db.sqlite "SELECT COUNT(*) FROM vulnerabilities"
```

## Contact

For questions about the vulnerability database system, see the main project CLAUDE.md file.
