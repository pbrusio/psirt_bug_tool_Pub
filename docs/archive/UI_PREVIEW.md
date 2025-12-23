# UI Preview: What Vulnerability Scanning Will Look Like

## Current State: Feature-Aware Scanning ✅ COMPLETE

**Status:** Phase 1 complete - 729 labeled bugs, feature-aware filtering working

Right now you can demo the scanning with the Python script:

```bash
# Version-only scan (shows all 16 bugs)
python demo_scan_feature_aware.py 17.10.1

# Feature-aware scan (shows only 3 bugs - 81% reduction!)
python demo_scan_feature_aware.py 17.10.1 --features MGMT_SSH_HTTP SEC_CoPP RTE_BGP

# Snapshot-based scan (shows 9 bugs - 43% reduction)
python demo_scan_feature_aware.py 17.10.1 --snapshot test-device-snapshot.json
```

**Results:**
- ✅ 729 labeled bugs (100% with feature labels)
- ✅ Version-only: 16 vulnerabilities found
- ✅ Feature-aware (3 features): 3 vulnerabilities (81% reduction!)
- ✅ Feature-aware (13 features): 9 vulnerabilities (43% reduction!)
- ✅ Query time: <10ms
- ✅ Works with device snapshots (air-gapped friendly)

## Future UI (Phase 3): What You'll Click

### New "Scan Device" Tab

```
┌────────────────────────────────────────────────────────────────┐
│  Tabs: [ Analyze PSIRT ]  [ Scan Device ] ← NEW TAB           │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ 🔍 Device Vulnerability Scanner                                │
├────────────────────────────────────────────────────────────────┤
│ Scan Mode:                                                     │
│ (*) Feature-Aware (Recommended)   ( ) Version-Only             │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐  │
│ │ Platform:  [IOS-XE ▼]                                    │  │
│ │ Version:   [17.10.1________________]                     │  │
│ │                                                          │  │
│ │ Device Features: (optional but recommended)              │  │
│ │ [ ] Upload Snapshot JSON                                 │  │
│ │ [x] Provide features manually                            │  │
│ │                                                          │  │
│ │ Selected Features (3):                                   │  │
│ │ [x] MGMT_SSH_HTTP    [x] SEC_CoPP    [x] RTE_BGP        │  │
│ │ [ ] MGMT_SNMP        [ ] L2_STP      [ ] RTE_EIGRP      │  │
│ │ ... [Show All 66 Features]                               │  │
│ │                                                          │  │
│ │ OR Upload Feature Snapshot:                              │  │
│ │ ┌────────────────────────────────────────────────────┐  │  │
│ │ │ Drag & drop snapshot.json here                     │  │  │
│ │ │ or click to browse                                 │  │  │
│ │ └────────────────────────────────────────────────────┘  │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│                [ Scan Device for Vulnerabilities ]             │
└────────────────────────────────────────────────────────────────┘
```

### Scan Results Display (Feature-Aware Mode)

```
┌────────────────────────────────────────────────────────────────┐
│ 📊 Scan Results - Feature-Aware Mode                          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ✅ FINAL RESULTS: 3 VULNERABILITIES                          │
│  (Reduced from 16 by filtering for configured features)       │
│                                                                │
│  📍 Step 1: Version Matching                                  │
│     Found 16 bugs affecting version 17.10.1                   │
│                                                                │
│  🎯 Step 2: Feature Filtering                                 │
│     Kept 3 bugs (feature match)                               │
│     Filtered out 13 bugs (features not configured)            │
│                                                                │
│  Scanned 729 bugs in 8.3ms                                    │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ 📋 MEDIUM / LOW SEVERITY (3)                                  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ 🟡 CSCwe84597 (Severity 5) - OPEN                            │
│                                                                │
│ Summary:                                                       │
│ Default-information originate is not properly accepted in...  │
│                                                                │
│ Affected Versions:                                            │
│ 17.10.1, 17.12.4, 17.13.1, 17.15.1                           │
│                                                                │
│ Required Features:                                             │
│ ✓ RTE_BGP (configured on your device)                         │
│                                                                │
│ [ View Cisco Bug Details ] [ Show Verification Commands ]     │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ 🚫 FILTERED OUT (13 bugs)                                     │
├────────────────────────────────────────────────────────────────┤
│ These bugs affect version 17.10.1 but require features        │
│ that are NOT configured on your device:                       │
│                                                                │
│ 🔴 CSCwo92456 (Severity 2 - CRITICAL) - OPEN                 │
│ Summary: Evaluation of Cat9300X for CVE-2024-38796            │
│ Required Features: SYS_Boot_Upgrade (NOT configured)          │
│ Status: ✅ NOT VULNERABLE (feature not present)               │
│                                                                │
│ 🟡 CSCwk93518 (Severity 5) - OPEN                            │
│ Summary: C9600X/C9500X SPAN stops transmitting packets...     │
│ Required Features: MGMT_SPAN_ERSPAN (NOT configured)          │
│ Status: ✅ NOT VULNERABLE (feature not present)               │
│                                                                │
│ ... [Show All 13 Filtered Bugs]                               │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│ 💡 Recommendations                                             │
├────────────────────────────────────────────────────────────────┤
│ • Review 3 applicable bugs during next maintenance window      │
│ • 13 bugs filtered out (features not configured)              │
│ • 81% reduction in false positives from feature filtering     │
│ • Export results for tracking                                  │
│                                                                │
│ [ Export as JSON ] [ Generate Report ] [ Scan Another Device ] │
│ [ Switch to Version-Only Mode (see all 16 bugs) ]             │
└────────────────────────────────────────────────────────────────┘
```

### Feature Comparison Toggle

```
┌────────────────────────────────────────────────────────────────┐
│ 📊 Scan Mode Comparison                                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ ┌──────────────────────────┬──────────────────────────┐       │
│ │  Version-Only Mode       │  Feature-Aware Mode      │       │
│ ├──────────────────────────┼──────────────────────────┤       │
│ │  16 vulnerabilities      │  3 vulnerabilities       │       │
│ │                          │  81% reduction ✨        │       │
│ ├──────────────────────────┼──────────────────────────┤       │
│ │  1 Critical/High         │  0 Critical/High         │       │
│ │  15 Medium/Low           │  3 Medium/Low            │       │
│ ├──────────────────────────┼──────────────────────────┤       │
│ │  Shows ALL bugs for      │  Shows ONLY bugs for     │       │
│ │  this version            │  configured features     │       │
│ │                          │                          │       │
│ │  More false positives    │  Fewer false positives   │       │
│ │  Overwhelming for large  │  Actionable results      │       │
│ │  environments            │                          │       │
│ └──────────────────────────┴──────────────────────────┘       │
│                                                                │
│ Recommendation: Use Feature-Aware mode to focus on real risks │
└────────────────────────────────────────────────────────────────┘
```

##  Side-by-Side Comparison

### Old UI (Still Works!)
```
User → Paste PSIRT text → Analyze → Get labels → Verify device
       (One PSIRT at a time, manual entry)
```

### New UI (Addition)
```
User → Enter device version + features → Scan → Get ALL matching bugs
       (Comprehensive scan in <10ms, feature-filtered)
```

### Use Both Together!
```
Workflow 1: Proactive Scanning
  → Scan device for ALL known bugs (prevention)

Workflow 2: PSIRT Triage
  → New advisory published → Analyze with SEC-8B → Verify device
```

## Demo Commands You Can Run NOW

```bash
# Version-only scan (baseline - shows all 16 bugs)
python demo_scan_feature_aware.py 17.10.1

# Feature-aware scan - minimal config (shows only 3 bugs)
python demo_scan_feature_aware.py 17.10.1 \
  --features MGMT_SSH_HTTP SEC_CoPP RTE_BGP

# Feature-aware scan - typical switch config (shows 9 bugs)
python demo_scan_feature_aware.py 17.10.1 \
  --snapshot test-device-snapshot.json

# Try other versions
python demo_scan_feature_aware.py 17.12.4 --snapshot test-device-snapshot.json
python demo_scan_feature_aware.py 17.15.1 --features MGMT_SSH_HTTP
```

## Database Statistics (Current State)

✅ **Complete:**
- 729 bugs loaded (100% labeled with GPT-4o)
- 60 unique feature labels
- 960 total label assignments (1.32 avg per bug)
- 1,292 version index entries
- 95.7% HIGH confidence labels

✅ **Performance:**
- Query time: <10ms for typical scans
- Version matching: Indexed lookup
- Feature filtering: Label-based (fast)

✅ **Quality:**
- All bugs have version data
- All bugs have feature labels
- All bugs have severity ratings
- All bugs have Cisco Bug Tool URLs

## What's Working

✅ **Database:**
- Bug IDs (CSCwo92456, etc.)
- Affected versions (explicit version lists)
- Severity (1-6)
- Status (Open/Fixed)
- Labels/features (60 unique labels)
- Headlines/summaries
- URLs to Cisco Bug Tool

✅ **Scanner:**
- Version matching (fast indexed lookups)
- Feature filtering (label-based)
- Severity grouping
- False positive reduction (40-80%)

✅ **Integration:**
- Works with device snapshots (air-gapped)
- Compatible with PSIRT analyzer
- Ready for API integration

## Next Steps to Get the UI

### Phase 2: Scanner API (In Progress) 🚧
1. ✅ Scanner logic complete (`demo_scan_feature_aware.py`)
2. 🔄 Implement `/api/v1/scan-device` endpoint (FastAPI)
3. 🔄 Add request/response models
4. 🔄 Test with curl examples
5. 🔄 Document API

**Estimated Time:** 1 day

### Phase 3: Frontend UI (2 days)
1. Create `ScanForm.tsx` component
   - Platform dropdown
   - Version input
   - Feature checklist (66 IOS-XE features)
   - Snapshot upload
   - Mode toggle (Version-only vs Feature-aware)

2. Create `ScanResults.tsx` component
   - Results table with severity badges
   - Filtered bugs section
   - Comparison stats (before/after filtering)
   - Export functionality

3. Add "Scan Device" tab to App.tsx
   - Tab navigation
   - Hook up to scan API
   - Loading states
   - Error handling

**Estimated Time:** 2 days

### Total Time: ~3 days to fully working UI

## Try It Yourself Right Now!

```bash
# Run version-only scan
python demo_scan_feature_aware.py 17.10.1

# Run feature-aware scan
python demo_scan_feature_aware.py 17.10.1 \
  --features MGMT_SSH_HTTP SEC_CoPP RTE_BGP

# Check database stats
sqlite3 vulnerability_db.sqlite \
  "SELECT COUNT(*) as total,
   SUM(CASE WHEN labels != '[]' THEN 1 ELSE 0 END) as labeled
   FROM vulnerabilities"

# View top labels
sqlite3 vulnerability_db.sqlite \
  "SELECT label, COUNT(*) as count
   FROM label_index
   GROUP BY label
   ORDER BY count DESC
   LIMIT 10"
```

## What This Proves

✅ **Database works** - 729 labeled bugs loaded and queryable
✅ **Version matching works** - Found 16 bugs for 17.10.1
✅ **Feature filtering works** - Reduced to 3 bugs (81% reduction)
✅ **Performance works** - <10ms scan time
✅ **Severity grouping works** - Critical/High vs Medium/Low
✅ **Architecture is sound** - Ready for API + UI integration
✅ **Air-gapped compatible** - Works with snapshot files

The hard part is done! API + UI is just wrapping this in FastAPI + React. 🎉

## Real-World Example

**Device:** Cat9200L running IOS-XE 17.10.1 with basic enterprise config

**Configured Features:**
- MGMT_SSH_HTTP (SSH/HTTP management)
- SEC_CoPP (Control Plane Policing)
- MGMT_AAA_TACACS_RADIUS (AAA)
- MGMT_SNMP (SNMP monitoring)
- MGMT_Syslog (Syslog)
- L2_STP (Spanning Tree)
- L2_VLAN_VTP (VLANs)
- IF_Physical (Physical interfaces)
- RTE_CEF (CEF routing)
- MGMT_LLDP_CDP (LLDP/CDP)
- QOS_MQC_ClassPolicy (QoS)
- SEC_ACL_Standard_Extended (ACLs)

**Scan Results:**
- Version-only: **16 bugs** (overwhelming)
- Feature-aware: **9 bugs** (actionable) - **43% reduction**

**Critical Bug Filtered:**
- CSCwo92456 (Severity 2) requires `SYS_Boot_Upgrade`
- Device doesn't have that feature
- **Correctly filtered out** - NOT VULNERABLE ✅

This is the power of feature-aware scanning!
