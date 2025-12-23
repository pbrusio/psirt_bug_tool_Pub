# Hardware Model Filtering Implementation Plan

**Priority:** CRITICAL - 50%+ additional false positive reduction potential
**Date:** 2025-10-14
**Status:** ✅ IMPLEMENTED - See `HARDWARE_FILTERING_TEST_REPORT.md` for production validation

> **Note:** This planning document has been fully implemented. Hardware filtering is now in production
> with 470 hardware-specific bugs (4.9%) and 25-60% false positive reduction. All tests passing.

## Problem Statement

### Current Issue
Many bugs in the Cisco bug database are **hardware-specific**, but our current filtering only checks:
1. Platform (IOS-XE, IOS-XR, ASA, FTD) ✅
2. Software Version (17.10.1, etc.) ✅
3. Feature Labels (MGMT_SSH_HTTP, etc.) ✅

**Missing:** Hardware Model filtering (Cat9200 vs Cat9300 vs ASR1K, etc.) ❌

### Real-World Impact
**Example:** Scanning a **Catalyst 9200** running IOS-XE 17.10.1:
```
❌ CSCwa78273 shows up: "GETVPN: IPsec stateful HA failover support for ASR1K (dual-RP)"
   → Bug is for ASR1K hardware, NOT Cat9200 → FALSE POSITIVE

❌ CSCwo92456 shows up: "Evaluation of Cat9300X for CVE-2024-38796"
   → Bug is for Cat9300X hardware, NOT Cat9200 → FALSE POSITIVE

❌ CSCwr08412 shows up: "SDA Edge 9200CX Switch not forwarding VXLAN..."
   → Bug is for C9200CX hardware, NOT Cat9200 → FALSE POSITIVE
```

### Scale of Problem
**Analysis of 30 random IOS-XE bugs:**
- **16 out of 30 (53%)** mention specific hardware models
- **Estimated false positive rate:** 40-60% of version-matched bugs may be for wrong hardware

### Expected Impact
**Current Filtering Chain:**
```
9,586 total bugs
  → Platform filter (IOS-XE) → 729 bugs (92% reduction)
    → Version filter (17.10.1) → 16 bugs (98% reduction)
      → Feature filter (3 labels) → 3 bugs (81% reduction from version baseline)
```

**With Hardware Filtering:**
```
9,586 total bugs
  → Platform filter (IOS-XE) → 729 bugs (92% reduction)
    → Version filter (17.10.1) → 16 bugs (98% reduction)
      → Hardware filter (Cat9200) → ~8 bugs (50% reduction) ⬅️ NEW!
        → Feature filter (3 labels) → ~2 bugs (75% reduction from hardware baseline)
```

**Combined Impact:** 40-80% (features) + 50% (hardware) = **70-90% total false positive reduction**

---

## Solution Design

### 4-Tier Filtering System
```
Tier 1: Platform      (IOS-XE, IOS-XR, ASA, FTD)           ✅ Implemented
Tier 2: Version       (17.10.1, 9.12.4, etc.)              ✅ Implemented
Tier 3: Hardware      (Cat9200, ASR1K, C8500, etc.)        ❌ THIS PLAN
Tier 4: Features      (MGMT_SSH_HTTP, SEC_CoPP, etc.)     ✅ Implemented
```

### Database Schema Changes
**Add new column to `vulnerabilities` table:**
```sql
ALTER TABLE vulnerabilities ADD COLUMN hardware_model TEXT;

-- Optional: Index for faster queries
CREATE INDEX idx_hardware_model ON vulnerabilities(hardware_model);
```

**Normalization Rules:**
- NULL = Generic bug (applies to all hardware on platform)
- "Cat9200" = Specific to Catalyst 9200 series
- "Cat9300" = Specific to Catalyst 9300 series
- "ASR1K" = Specific to ASR 1000 series
- etc.

**Filtering Logic:**
```python
if bug.hardware_model is not None:
    if user_hardware_model is None:
        # User didn't specify hardware - include generic bugs only
        if bug.hardware_model != NULL:
            FILTER_OUT  # Bug is hardware-specific, user scan is generic
    else:
        # User specified hardware - must match
        if bug.hardware_model != user_hardware_model:
            FILTER_OUT  # Different hardware
        else:
            INCLUDE  # Hardware matches
else:
    # Bug has no hardware specified → Generic, applies to all
    INCLUDE
```

---

## Implementation Plan

### Phase 1: Database Enhancement (Day 1)

#### 1.1: Add Hardware Column
**File:** `backend/db/schema.py` (if exists) or direct migration script

**Migration script:**
```python
# migration_add_hardware_model.py
import sqlite3

def migrate():
    db = sqlite3.connect('vulnerability_db.sqlite')
    cursor = db.cursor()

    # Add column
    cursor.execute('ALTER TABLE vulnerabilities ADD COLUMN hardware_model TEXT')

    # Create index
    cursor.execute('CREATE INDEX idx_hardware_model ON vulnerabilities(hardware_model)')

    db.commit()
    db.close()
    print("✅ Migration complete: hardware_model column added")
```

#### 1.2: Hardware Extraction Patterns
**File:** `backend/db/hardware_extractor.py` (NEW FILE)

**Hardware patterns to extract from bug summaries:**
```python
HARDWARE_PATTERNS = {
    # Catalyst 9000 Series
    r'(?:Cat|Catalyst)?\s*9200(?:CX|L)?(?:-[A-Z0-9]+)?': 'Cat9200',
    r'(?:Cat|Catalyst)?\s*9300(?:X|L|LM)?(?:-[A-Z0-9]+)?': 'Cat9300',
    r'(?:Cat|Catalyst)?\s*9400(?:-[A-Z0-9]+)?': 'Cat9400',
    r'(?:Cat|Catalyst)?\s*9500(?:-[A-Z0-9]+)?': 'Cat9500',
    r'(?:Cat|Catalyst)?\s*9600(?:-[A-Z0-9]+)?': 'Cat9600',
    r'(?:Cat|Catalyst)?\s*9800(?:-[A-Z0-9]+)?': 'Cat9800',  # Wireless controller

    # Catalyst 8000 Series
    r'(?:Cat|Catalyst)?\s*8[0-9]{3}(?:v|L)?(?:-[A-Z0-9]+)?': 'Cat8000',
    r'C8[0-9]{3}(?:v|L)?(?:-[A-Z0-9]+)?': 'Cat8000',

    # ASR Series
    r'ASR\s*1[0-9]{3}[KkXx]?': 'ASR1K',
    r'ASR\s*9[0-9]{2}[KkXx]?': 'ASR9K',

    # ISR Series
    r'ISR\s*[0-9]{4}(?:-[A-Z0-9]+)?': 'ISR4K',

    # CSR (Virtual)
    r'CSR\s*1000[vV]': 'CSR1000v',

    # Nexus (if we add NX-OS later)
    r'Nexus\s*[0-9]{4}': lambda m: f'Nexus{m.group().split()[1]}',

    # Firepower
    r'FTD\s*[0-9]{4}': lambda m: f'FTD{m.group().split()[1]}',
    r'Firepower\s*[0-9]{4}': lambda m: f'FTD{m.group().split()[1]}',
}

def extract_hardware_model(text: str) -> str | None:
    """
    Extract hardware model from bug headline/summary.

    Args:
        text: Bug headline + summary combined

    Returns:
        Normalized hardware model (e.g., 'Cat9200') or None (generic bug)
    """
    import re

    for pattern, normalized in HARDWARE_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if callable(normalized):
                return normalized(match)
            else:
                return normalized

    return None  # No hardware found → generic bug
```

#### 1.3: Backfill Existing Bugs
**File:** `backfill_hardware_models.py` (NEW SCRIPT)

**Process:**
```python
#!/usr/bin/env python3
"""
Backfill hardware_model for all existing bugs in database
"""
import sqlite3
from backend.db.hardware_extractor import extract_hardware_model

def backfill():
    db = sqlite3.connect('vulnerability_db.sqlite')
    cursor = db.cursor()

    # Get all bugs
    cursor.execute('SELECT id, headline, summary FROM vulnerabilities WHERE vuln_type = "bug"')
    bugs = cursor.fetchall()

    print(f"Processing {len(bugs)} bugs...")

    updated = 0
    for bug_id, headline, summary in bugs:
        text = (headline or '') + ' ' + (summary or '')
        hardware = extract_hardware_model(text)

        if hardware:
            cursor.execute('UPDATE vulnerabilities SET hardware_model = ? WHERE id = ?',
                         (hardware, bug_id))
            updated += 1

    db.commit()
    db.close()

    print(f"✅ Updated {updated}/{len(bugs)} bugs with hardware models")
    print(f"   {len(bugs) - updated} bugs are generic (no hardware specified)")

if __name__ == '__main__':
    backfill()
```

**Run backfill:**
```bash
python backfill_hardware_models.py
```

**Expected output:**
```
Processing 9,586 bugs...
✅ Updated 5,000/9,586 bugs with hardware models
   4,586 bugs are generic (no hardware specified)

Hardware distribution:
  Cat9300: 823 bugs
  Cat9200: 412 bugs
  ASR1K: 734 bugs
  Cat8000: 298 bugs
  ...
```

---

### Phase 2: Ingestion Pipeline Update (Day 1)

#### 2.1: Update Bug Loader
**File:** `backend/db/load_bugs.py`

**Changes:**
```python
from backend.db.hardware_extractor import extract_hardware_model

def parse_bug_row(self, row: Dict, platform: str = 'IOS-XE') -> Optional[Dict]:
    """Parse a bug CSV row into database format."""

    # ... existing parsing logic ...

    # NEW: Extract hardware model
    text = (headline or '') + ' ' + (summary or '')
    hardware_model = extract_hardware_model(text)

    return {
        'bug_id': bug_id,
        'vuln_type': 'bug',
        'platform': platform,
        'hardware_model': hardware_model,  # NEW FIELD
        # ... rest of fields ...
    }
```

**Update INSERT statement:**
```python
cursor.execute('''
    INSERT INTO vulnerabilities (
        bug_id, advisory_id, vuln_type, severity, headline, summary,
        url, status, platform, product_series, hardware_model,  # <-- NEW
        affected_versions_raw, version_pattern, version_min, version_max,
        fixed_version, labels, labels_source, last_modified
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
    bug['bug_id'], bug.get('advisory_id'), bug['vuln_type'],
    bug.get('severity'), bug.get('headline'), bug.get('summary'),
    bug.get('url'), bug.get('status'), bug['platform'],
    bug.get('product_series'), bug.get('hardware_model'),  # <-- NEW
    # ... rest of values ...
))
```

---

### Phase 3: Scanner Logic Update (Day 2)

#### 3.1: Update Scanner Core
**File:** `backend/core/vulnerability_scanner.py`

**Changes to `scan_device()` method:**
```python
def scan_device(
    self,
    platform: str,
    version: str,
    labels: List[str] = None,
    hardware_model: str = None  # NEW PARAMETER
) -> Dict:
    """
    Scan for vulnerabilities affecting a device.

    Args:
        platform: Platform (IOS-XE, IOS-XR, ASA, FTD)
        version: Software version (e.g., '17.10.1')
        labels: Optional list of configured features for filtering
        hardware_model: Optional hardware model (e.g., 'Cat9200')  # NEW
    """

    # ... existing platform/version query logic ...

    # NEW: Add hardware filtering
    if hardware_model:
        # Include bugs that:
        #   1. Have no hardware specified (generic), OR
        #   2. Match the user's hardware
        cursor.execute("""
            SELECT * FROM vulnerabilities
            WHERE platform = ?
              AND vuln_type = 'bug'
              AND (hardware_model IS NULL OR hardware_model = ?)
        """, (platform, hardware_model))
    else:
        # User didn't specify hardware - only return generic bugs
        cursor.execute("""
            SELECT * FROM vulnerabilities
            WHERE platform = ?
              AND vuln_type = 'bug'
              AND hardware_model IS NULL
        """, (platform,))

    # ... rest of scanning logic ...
```

#### 3.2: Update API Models
**File:** `backend/api/models.py`

**Add `hardware_model` to request model:**
```python
class ScanRequest(BaseModel):
    platform: str
    version: str
    features: Optional[List[str]] = None
    hardware_model: Optional[str] = None  # NEW FIELD

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "IOS-XE",
                "version": "17.10.1",
                "features": ["MGMT_SSH_HTTP", "SEC_CoPP"],
                "hardware_model": "Cat9200"  # NEW
            }
        }
```

#### 3.3: Update API Route
**File:** `backend/api/routes.py`

**Pass hardware_model to scanner:**
```python
@router.post("/scan-device")
async def scan_device(request: ScanRequest):
    result = scanner.scan_device(
        platform=request.platform,
        version=request.version,
        labels=request.features,
        hardware_model=request.hardware_model  # NEW
    )
    return result
```

---

### Phase 4: Feature Extraction Enhancement (Day 2)

#### 4.1: Auto-Detect Hardware from "show version"
**File:** `sidecar_extractor/extract_iosxe_features_standalone.py`

**Add hardware detection:**
```python
def extract_hardware_model(show_version_output: str) -> str:
    """
    Extract hardware model from 'show version' output.

    Example outputs:
    - "Cisco IOS Software [Amsterdam], Catalyst L3 Switch Software (CAT9300-UNIVERSALK9-M)"
      → Hardware: Cat9300

    - "cisco C9200L-24T-4G (X86_64_LINUX_IOSD-UNIVERSALK9-M)"
      → Hardware: Cat9200
    """
    import re

    # Pattern 1: CAT9XXX in software image name
    match = re.search(r'CAT([0-9]{4}[A-Z]*)-', show_version_output, re.IGNORECASE)
    if match:
        model = match.group(1)
        return f"Cat{model[:4]}"  # Normalize to series (Cat9200, Cat9300, etc.)

    # Pattern 2: cisco C9XXX in platform line
    match = re.search(r'cisco\s+(C[0-9]{4}[A-Z]*)', show_version_output, re.IGNORECASE)
    if match:
        model = match.group(1)[1:]  # Remove 'C' prefix
        return f"Cat{model[:4]}"

    # Pattern 3: ASR in model name
    match = re.search(r'(ASR[0-9]{4})', show_version_output, re.IGNORECASE)
    if match:
        return 'ASR1K'  # Normalize ASR models

    return None  # Could not detect hardware

def extract_features_from_config(config_text: str, show_version: str = None) -> dict:
    """Extract both features and hardware from device outputs."""

    # ... existing feature extraction logic ...

    # NEW: Extract hardware if show version provided
    hardware_model = None
    if show_version:
        hardware_model = extract_hardware_model(show_version)

    return {
        'platform': 'IOS-XE',
        'hardware_model': hardware_model,  # NEW
        'features': detected_features,
        'timestamp': datetime.now().isoformat()
    }
```

#### 4.2: Update Live Device Verification
**File:** `backend/core/device_verifier.py`

**Extract hardware during SSH connection:**
```python
def extract_features_from_device(self, hostname: str, username: str, password: str) -> dict:
    """SSH to device and extract features + hardware."""

    # ... existing SSH connection logic ...

    # Get show version
    stdin, stdout, stderr = ssh.exec_command('show version')
    show_version = stdout.read().decode('utf-8')

    # Get running config
    stdin, stdout, stderr = ssh.exec_command('show running-config')
    config = stdout.read().decode('utf-8')

    # Extract features
    from sidecar_extractor.extract_iosxe_features_standalone import (
        extract_features_from_config,
        extract_hardware_model
    )

    result = extract_features_from_config(config, show_version=show_version)

    # result now contains:
    # {
    #   'platform': 'IOS-XE',
    #   'hardware_model': 'Cat9200',  # <-- NEW
    #   'features': ['MGMT_SSH_HTTP', 'SEC_CoPP', ...]
    # }

    return result
```

---

### Phase 5: Frontend Updates (Day 3)

#### 5.1: Add Hardware Dropdown to Scanner UI
**File:** `frontend/src/components/VulnerabilityScanner.tsx`

**Add hardware model selection:**
```typescript
// Hardware models by platform
const HARDWARE_MODELS = {
  'IOS-XE': [
    { value: null, label: 'Any Hardware (Generic Bugs Only)' },
    { value: 'Cat9200', label: 'Catalyst 9200 Series' },
    { value: 'Cat9300', label: 'Catalyst 9300 Series' },
    { value: 'Cat9400', label: 'Catalyst 9400 Series' },
    { value: 'Cat9500', label: 'Catalyst 9500 Series' },
    { value: 'Cat9600', label: 'Catalyst 9600 Series' },
    { value: 'Cat8000', label: 'Catalyst 8000 Series' },
    { value: 'ASR1K', label: 'ASR 1000 Series' },
    { value: 'ISR4K', label: 'ISR 4000 Series' },
  ],
  'IOS-XR': [
    { value: null, label: 'Any Hardware (Generic Bugs Only)' },
    { value: 'ASR9K', label: 'ASR 9000 Series' },
    { value: 'NCS5K', label: 'NCS 5000 Series' },
    { value: 'NCS5500', label: 'NCS 5500 Series' },
  ],
  // ... more platforms ...
};

const [hardwareModel, setHardwareModel] = useState<string | null>(null);

// UI component:
<div className="form-group">
  <label>Hardware Model (Optional)</label>
  <select
    value={hardwareModel || ''}
    onChange={(e) => setHardwareModel(e.target.value || null)}
    className="form-control"
  >
    {HARDWARE_MODELS[platform]?.map(hw => (
      <option key={hw.value} value={hw.value || ''}>
        {hw.label}
      </option>
    ))}
  </select>
  <small className="text-muted">
    Select hardware to filter out bugs for other models (e.g., Cat9300 bugs won't show for Cat9200)
  </small>
</div>
```

#### 5.2: Show Hardware Filtering Impact
**Update results display:**
```typescript
{result.hardware_model && (
  <div className="alert alert-info">
    <strong>Hardware Filter Active:</strong> {result.hardware_model}
    <br/>
    Showing bugs for {result.hardware_model} and generic bugs only.
    <br/>
    {result.hardware_filtered_count > 0 && (
      <span className="text-success">
        ✓ Filtered out {result.hardware_filtered_count} bugs for other hardware models
        ({Math.round(result.hardware_filtered_count / result.total_bugs_checked * 100)}% reduction)
      </span>
    )}
  </div>
)}
```

#### 5.3: Auto-populate from Live Device
**When user selects "Live Device" mode:**
```typescript
const handleLiveDeviceScan = async () => {
  // Extract features + hardware from device
  const deviceInfo = await extractFeaturesFromDevice(hostname, username, password);

  // Auto-populate form
  setPlatform(deviceInfo.platform);
  setHardwareModel(deviceInfo.hardware_model);  // <-- NEW
  setFeatures(deviceInfo.features);

  // Run scan with hardware filter
  const result = await scanDevice({
    platform: deviceInfo.platform,
    version: deviceInfo.version,
    hardware_model: deviceInfo.hardware_model,  // <-- NEW
    features: deviceInfo.features
  });
};
```

---

### Phase 6: Testing & Validation (Day 3)

#### 6.1: Unit Tests
**File:** `test_hardware_filtering.py` (NEW)

```python
#!/usr/bin/env python3
"""
Test hardware filtering functionality
"""
import sqlite3
from backend.db.hardware_extractor import extract_hardware_model
from backend.core.vulnerability_scanner import VulnerabilityScanner

def test_hardware_extraction():
    """Test hardware model extraction from bug text"""
    test_cases = [
        ('Cat9300 switch crashes with VXLAN', 'Cat9300'),
        ('C9200L memory leak in SNMP', 'Cat9200'),
        ('ASR1K dual-RP failover issue', 'ASR1K'),
        ('Generic IOS-XE SSH vulnerability', None),  # No hardware
    ]

    print("Testing hardware extraction...")
    for text, expected in test_cases:
        result = extract_hardware_model(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{text[:40]}...' → {result} (expected: {expected})")

def test_scanner_filtering():
    """Test scanner hardware filtering logic"""
    scanner = VulnerabilityScanner()

    # Scan Cat9200 - should NOT get Cat9300 bugs
    result = scanner.scan_device(
        platform='IOS-XE',
        version='17.10.1',
        hardware_model='Cat9200'
    )

    # Verify no Cat9300 bugs in results
    cat9300_bugs = [
        v for v in result['vulnerabilities']
        if 'Cat9300' in (v.get('headline', '') + v.get('summary', ''))
    ]

    if len(cat9300_bugs) == 0:
        print("✅ Hardware filtering working - no Cat9300 bugs for Cat9200 scan")
    else:
        print(f"❌ Hardware filtering failed - found {len(cat9300_bugs)} Cat9300 bugs")

def test_database_stats():
    """Show hardware distribution in database"""
    db = sqlite3.connect('vulnerability_db.sqlite')
    cursor = db.cursor()

    cursor.execute("""
        SELECT hardware_model, COUNT(*)
        FROM vulnerabilities
        WHERE vuln_type = 'bug' AND platform = 'IOS-XE'
        GROUP BY hardware_model
        ORDER BY COUNT(*) DESC
    """)

    print("\nHardware distribution (IOS-XE bugs):")
    for hw, count in cursor.fetchall():
        hw_label = hw or "Generic (no hardware)"
        print(f"  {hw_label:30s}: {count:,} bugs")

    db.close()

if __name__ == '__main__':
    test_hardware_extraction()
    test_scanner_filtering()
    test_database_stats()
```

#### 6.2: Integration Test
**Before/After comparison:**
```python
def test_false_positive_reduction():
    """Measure false positive reduction from hardware filtering"""

    scanner = VulnerabilityScanner()

    # Test Case: Cat9200 running IOS-XE 17.10.1

    # WITHOUT hardware filter
    result_no_hw = scanner.scan_device(
        platform='IOS-XE',
        version='17.10.1',
        hardware_model=None  # No hardware specified
    )

    # WITH hardware filter
    result_with_hw = scanner.scan_device(
        platform='IOS-XE',
        version='17.10.1',
        hardware_model='Cat9200'
    )

    reduction = len(result_no_hw['vulnerabilities']) - len(result_with_hw['vulnerabilities'])
    reduction_pct = reduction / len(result_no_hw['vulnerabilities']) * 100

    print(f"\nFalse Positive Reduction Test:")
    print(f"  Without hardware filter: {len(result_no_hw['vulnerabilities'])} bugs")
    print(f"  With hardware filter:    {len(result_with_hw['vulnerabilities'])} bugs")
    print(f"  Reduction:               {reduction} bugs ({reduction_pct:.1f}%)")
```

---

## Success Metrics

### Quantitative Goals
1. **Hardware Detection Rate:** ≥50% of bugs should have hardware model extracted
2. **False Positive Reduction:** ≥40% reduction in version-matched bugs when hardware filter applied
3. **Performance:** Hardware filtering adds <5ms to query time
4. **Zero Regressions:** Generic bugs (no hardware) still show for all devices

### Test Coverage
- [ ] Hardware extraction from 20+ sample bugs (various formats)
- [ ] Scanner returns correct results for 4+ hardware models
- [ ] Generic bugs (no hardware) included in all scans
- [ ] Hardware-specific bugs excluded when hardware doesn't match
- [ ] Frontend dropdown populated correctly for all platforms
- [ ] Live device extraction detects hardware from "show version"

---

## Rollout Plan

### Day 1 (Database & Ingestion)
- [ ] Run database migration (add `hardware_model` column)
- [ ] Create `hardware_extractor.py` with pattern matching
- [ ] Run backfill script on existing 9,586 bugs
- [ ] Verify backfill results (spot-check 20 bugs)
- [ ] Update `load_bugs.py` to extract hardware during ingestion
- [ ] Test new bug ingestion with hardware extraction

### Day 2 (Backend Logic)
- [ ] Update `vulnerability_scanner.py` with hardware filtering
- [ ] Add `hardware_model` parameter to API models
- [ ] Update API routes to accept hardware parameter
- [ ] Update live device verifier to extract hardware
- [ ] Test API endpoints with Postman/curl

### Day 3 (Frontend & Testing)
- [ ] Add hardware dropdown to scanner UI
- [ ] Wire up hardware parameter to API calls
- [ ] Auto-populate hardware from live device extraction
- [ ] Show hardware filtering impact in results
- [ ] Run comprehensive test suite
- [ ] Measure false positive reduction on real devices

### Day 4 (Validation & Documentation)
- [ ] Test on 5+ different hardware models
- [ ] Validate generic bugs still appear correctly
- [ ] Update API documentation
- [ ] Update user guide with hardware filtering instructions
- [ ] Create "before/after" demo screenshots

---

## Risks & Mitigations

### Risk 1: Hardware Extraction False Positives
**Risk:** Regex patterns might misidentify hardware (e.g., "Cat" in "Category")

**Mitigation:**
- Use word boundaries in regex patterns
- Require numeric model numbers after keywords
- Manual review of top 50 extracted hardware models
- Whitelist approach (only extract known models)

### Risk 2: Hardware Naming Inconsistency
**Risk:** Same hardware called different names in different bugs (C9200 vs Cat9200 vs Catalyst 9200)

**Mitigation:**
- Normalize all variants to single format (e.g., "Cat9200")
- Comprehensive pattern matching in `hardware_extractor.py`
- Validation script to check for near-duplicates

### Risk 3: Generic Bugs Incorrectly Tagged
**Risk:** Bug mentions hardware in description but actually affects all hardware

**Mitigation:**
- Conservative extraction (only extract from headline, not full summary)
- Manual review of ambiguous cases
- Allow NULL hardware_model to indicate generic bugs
- Provide UI option to "Show all bugs (ignore hardware)"

### Risk 4: Performance Impact
**Risk:** Additional SQL filtering slows down queries

**Mitigation:**
- Create index on `hardware_model` column
- Use OR condition in SQL (hardware IS NULL OR hardware = ?)
- Monitor query time before/after (should stay <5ms)

---

## Future Enhancements

### Phase 2 Features (Post-MVP)
1. **Hardware Aliases:**
   - Map C9200L-24T → Cat9200 (series-level grouping)
   - Support user entering specific model (e.g., "C9200L-24T") → auto-map to Cat9200

2. **Hardware Compatibility Matrix:**
   - Some bugs affect multiple hardware models
   - Store as array: `hardware_models: ['Cat9200', 'Cat9300']`

3. **Auto-Correction UI:**
   - Show user: "Did you mean Cat9200?" if they enter "9200"
   - Suggest hardware based on detected software version

4. **Hardware-Specific Show Commands:**
   - Different verification commands for different hardware
   - Feature taxonomy could include `show_cmds_by_hardware`

5. **Telemetry:**
   - Track which hardware models are most commonly scanned
   - Identify bugs that need better hardware tagging

---

## Dependencies

### Python Libraries (Already Installed)
- `sqlite3` - Database operations
- `re` - Regex pattern matching

### New Files Created
- `backend/db/hardware_extractor.py` - Hardware extraction logic
- `migration_add_hardware_model.py` - Database migration
- `backfill_hardware_models.py` - Backfill existing data
- `test_hardware_filtering.py` - Test suite

### Files Modified
- `backend/db/load_bugs.py` - Add hardware extraction to ingestion
- `backend/core/vulnerability_scanner.py` - Add hardware filtering
- `backend/api/models.py` - Add hardware_model field
- `backend/api/routes.py` - Pass hardware_model to scanner
- `backend/core/device_verifier.py` - Extract hardware from show version
- `sidecar_extractor/extract_iosxe_features_standalone.py` - Hardware detection
- `frontend/src/components/VulnerabilityScanner.tsx` - Hardware UI
- `CLAUDE.md` - Update with hardware filtering feature

---

## Questions to Resolve

1. **Hardware Granularity:** Should we normalize to series (Cat9200) or support specific models (C9200L-24T)?
   - **Recommendation:** Series-level (Cat9200) for MVP, add aliases later

2. **Multiple Hardware per Bug:** Some bugs affect multiple models. Store as array or separate rows?
   - **Recommendation:** Start with single value, add array support in Phase 2

3. **Unknown Hardware:** What to do if hardware extraction fails?
   - **Recommendation:** Set to NULL (generic bug), conservative approach

4. **User Input:** Free text or dropdown for hardware?
   - **Recommendation:** Dropdown for consistency, with "Other" option

---

## Summary

**What This Fixes:**
- Eliminates 40-60% of false positives from hardware mismatches
- Improves user confidence in scan results
- Reduces alert fatigue for network operators

**How It Works:**
1. Extract hardware model from bug text during ingestion (regex patterns)
2. Store in new `hardware_model` column (NULL = generic)
3. Filter bugs during scan: `WHERE hardware_model IS NULL OR hardware_model = ?`
4. Auto-detect hardware from "show version" for live devices
5. UI dropdown for manual hardware selection

**Timeline:** 3-4 days for full implementation + testing

**Next Steps:**
1. Review this plan with team
2. Approve database schema change
3. Begin Day 1 implementation (database migration + backfill)
