# Scanner Design Decisions

## Overview

This document provides detailed rationale for the four key design questions posed in the architecture requirements.

## Question 1: Should scan results include verification commands?

**Decision: YES - Always include config_regex and show_commands**

### Rationale

#### 1. Enables Immediate Action

When an analyst receives a scan showing 20 vulnerabilities, the next question is always: "Is my device actually vulnerable?" Without verification commands, they must:

1. Find the original advisory
2. Read the technical details
3. Figure out what features to check
4. SSH to device
5. Run commands

**With commands included:** Copy/paste directly into SSH session.

#### 2. Enables Automated Verification

The frontend can auto-populate the verification form:

```javascript
// User clicks "Verify" on a scan result
onClick={() => {
  setVerificationForm({
    device: currentDevice,
    advisory_id: vuln.advisory_id,
    config_regex: vuln.config_regex,      // Pre-filled
    show_commands: vuln.show_commands      // Pre-filled
  })
}}
```

No additional API call needed to fetch commands.

#### 3. Minimal Cost

**Payload size comparison:**

```json
// WITHOUT commands (~200 bytes per vulnerability)
{
  "vuln_id": "vuln-001",
  "advisory_id": "cisco-sa-iosxe-ssh-dos",
  "severity": 1,
  "summary": "Denial of Service in SSH..."
}

// WITH commands (~400 bytes per vulnerability)
{
  "vuln_id": "vuln-001",
  "advisory_id": "cisco-sa-iosxe-ssh-dos",
  "severity": 1,
  "summary": "Denial of Service in SSH...",
  "config_regex": ["^ip ssh", "^line vty"],
  "show_commands": ["show ip ssh", "show line vty"]
}
```

**Impact for 50 vulnerabilities:**
- Without: 10 KB
- With: 20 KB
- Difference: 10 KB (negligible on modern networks)

#### 4. Consistency with Existing API

The `/analyze-psirt` endpoint already returns commands:

```json
{
  "analysis_id": "...",
  "predicted_labels": ["MGMT_SSH_HTTP"],
  "config_regex": ["^ip ssh"],
  "show_commands": ["show ip ssh"]
}
```

Scan results should match this pattern for consistency.

### Trade-offs

**Pros:**
- Immediate actionability
- No extra API calls
- Frontend auto-populate
- Consistent with existing API

**Cons:**
- Slightly larger response size (acceptable)

**Decision:** Include commands in all scan results.

## Question 2: How to handle vulnerabilities with no labels?

**Decision: Include with `unlabeled: true` flag and version-only matching**

### Problem Context

From the training data statistics:

```
Total records: 5,952
Labeled examples: 2,654 (44.6%)
Empty labels: 3,298 (55.4%)
```

**~55% of bugs have no labels** because:
- SEC-8B couldn't determine features (low confidence)
- Bug description too vague
- Features not in taxonomy
- Pre-ship bugs (not field-verifiable)

### Rationale

#### 1. Version Match Still Valuable

Even without feature detection, knowing the version is affected is useful:

**Scenario:**
```
Device: IOS-XE 17.3.5
Bug: CSCabc12345
Status: Severity 2 (High)
Version affected: 17.3.1-17.3.7
Labels: [] (none)
```

**Analyst decision:**
- Device version IS in affected range
- No feature detection available
- Should manually investigate
- **Better to know than not know**

#### 2. False Negative Risk

**Option A: Exclude unlabeled bugs**
- Risk: Miss critical vulnerabilities
- Impact: Device remains vulnerable, analyst unaware

**Option B: Include with warning**
- Risk: Some false positives (analyst must verify)
- Impact: Analyst aware, can investigate

**Security principle:** Better false positive than false negative.

#### 3. Clear UI Indication

Frontend shows prominent warning:

```
┌─────────────────────────────────────────────────┐
│ ⚠️  Manual Verification Required                │
│                                                 │
│ CSCabc12345 - Denial of Service vulnerability  │
│ Severity: 2 (High)                              │
│                                                 │
│ No feature labels available for automated       │
│ verification. Please manually review advisory   │
│ and check device configuration.                 │
│                                                 │
│ Version affected: ✓ (17.3.5 in range 17.3.1-7) │
│ Features: ⚠️  Unknown                           │
└─────────────────────────────────────────────────┘
```

#### 4. Analyst Context

Unlabeled bugs are typically:
- Edge cases
- Complex bugs requiring deep understanding
- Pre-ship bugs (infrastructure/tooling)

**Analysts already expect to manually verify high-severity bugs**, so flagging these for manual review is consistent with workflow.

### Implementation

**Database query:**

```sql
-- Version-only matching (no label filter)
SELECT v.*
FROM vulnerabilities v
JOIN version_index vi ON v.vuln_id = vi.vuln_id
WHERE vi.platform = ?
  AND vi.major = ?
  AND vi.minor = ?
  AND (vi.patch IS NULL OR vi.patch <= ?)
  AND v.labels IS NULL OR v.labels = '[]';
```

**Response format:**

```json
{
  "vuln_id": "vuln-042",
  "advisory_id": "CSCabc12345",
  "severity": 2,
  "summary": "Denial of Service in platform software",
  "unlabeled": true,
  "labels": [],
  "config_regex": [],
  "show_commands": [],
  "warning": "No feature labels available - manual verification required"
}
```

**UI rendering:**

```jsx
{vuln.unlabeled && (
  <Alert severity="warning">
    <AlertTitle>Manual Verification Required</AlertTitle>
    No feature detection available for this vulnerability.
    Please review advisory and manually verify configuration.
  </Alert>
)}
```

### Trade-offs

**Pros:**
- No false negatives (don't miss vulnerabilities)
- Analyst aware of all version matches
- Clear warning about manual verification
- Maintains complete coverage

**Cons:**
- Some false positives (version match but feature not configured)
- Analyst must manually verify

**Decision:** Include unlabeled bugs with prominent warnings.

## Question 3: Should we cache LLM results in database automatically?

**Decision: YES - Auto-cache if confidence >= 0.75 and advisory_id present**

### Rationale

#### 1. Database Grows Organically

**Scenario:** New PSIRT published at 9am.

```
9:00 AM - PSIRT published (cisco-sa-iosxe-new-vuln)
9:05 AM - Analyst A analyzes it (LLM inference, 3.4s)
          → High confidence (0.87), cached to database
9:10 AM - Analyst B scans devices (database hit, <10ms)
9:15 AM - Analyst C scans devices (database hit, <10ms)
```

**Without auto-cache:**
- Each analyst waits 3.4s for LLM
- 3 x 3.4s = 10.2s total

**With auto-cache:**
- First analyst: 3.4s (LLM)
- Second analyst: <10ms (database)
- Third analyst: <10ms (database)
- Total: 3.4s + 20ms

**Benefit:** 66% reduction in total time across team.

#### 2. Consistency Across Team

**Without cache:**
- Analyst A runs SEC-8B at 9am → Labels: ["MGMT_SSH_HTTP"]
- Analyst B runs SEC-8B at 11am → Labels: ["MGMT_SSH_HTTP", "SEC_CoPP"]  (different examples retrieved)
- **Inconsistent results for same PSIRT**

**With cache:**
- Analyst A runs SEC-8B → Labels cached
- Analyst B gets cached result → Same labels
- **Consistent results across team**

#### 3. Offline Capability

Once cached, system works without SEC-8B:

```
Database: 2,654 vulnerabilities (initial training data)
+ 50 new PSIRTs analyzed by team (auto-cached)
= 2,704 total queryable vulnerabilities

SEC-8B server goes down → Database still works
```

**Resilience:** System degrades gracefully (DB queries still fast).

### Cache Policy

**Cache if ALL conditions met:**

```python
def _should_cache(result):
    return (
        result['advisory_id'] is not None and      # Identifiable
        result['confidence'] >= 0.75 and            # High quality
        len(result['predicted_labels']) > 0         # Has labels
    )
```

**Rationale for each condition:**

#### advisory_id is not None

**Why required:** Need unique identifier for cache lookups.

**Example of NO cache:**
```json
{
  "advisory_id": null,  // Ad-hoc query, no ID
  "summary": "What if there's a bug in SSH?",
  "confidence": 0.92
}
```
→ Don't cache (can't look up later, ephemeral query)

#### confidence >= 0.75

**Why threshold at 0.75:** Based on training data analysis.

**Confidence distribution:**
```
HIGH (≥0.75):    81.4% of labeled data  ← Cache these
MEDIUM (0.60-0.74): 15.2%
LOW (<0.60):     3.5%
```

**Example of NO cache:**
```json
{
  "advisory_id": "cisco-sa-xyz",
  "confidence": 0.62,  // MEDIUM confidence
  "predicted_labels": ["MGMT_SSH_HTTP"]
}
```
→ Don't cache (might be wrong, could improve with better examples)

**Benefit:** Only cache high-quality results, minimize bad data.

#### len(predicted_labels) > 0

**Why required:** No point caching if no labels predicted.

**Example of NO cache:**
```json
{
  "advisory_id": "cisco-sa-abc",
  "confidence": 0.85,
  "predicted_labels": []  // SEC-8B couldn't determine
}
```
→ Don't cache (no value, already have unlabeled bugs in DB)

### Cache Management

**Admin operations (future):**

```sql
-- View cache statistics
SELECT
  COUNT(*) as total_cached,
  AVG(confidence) as avg_confidence,
  MIN(created_at) as oldest_entry
FROM vulnerabilities
WHERE source = 'llm_cached';

-- Purge low-confidence entries
DELETE FROM vulnerabilities
WHERE source = 'llm_cached'
  AND confidence < 0.70;

-- Purge old entries (if DB too large)
DELETE FROM vulnerabilities
WHERE source = 'llm_cached'
  AND created_at < date('now', '-6 months');
```

### Trade-offs

**Pros:**
- Faster for subsequent users (3400ms → <10ms)
- Consistent results across team
- Database grows organically
- Offline capability

**Cons:**
- Potential for bad data if confidence threshold too low
- Database size grows over time
- Need purge strategy for old entries

**Safeguards:**
- High confidence threshold (0.75)
- Track confidence in DB for filtering
- Admin tools to purge if needed

**Decision:** Auto-cache high-confidence results.

## Question 4: How to paginate if device has 100+ vulnerabilities?

**Decision: Two-tier pagination - severity-based grouping + optional limit**

### Problem Context

**Typical result distribution:**

```
Device: Cisco ASA 9.12.4 (very old version)

Critical/High (Severity 1-2): 15 vulnerabilities
Medium (Severity 3-4):        45 vulnerabilities
Low (Severity 5-6):           80 vulnerabilities
────────────────────────────────────────────────
Total:                        140 vulnerabilities
```

**Challenge:** Returning 140 full vulnerability records (400 bytes each) = 56 KB response.

### Rationale

#### 1. Analysts Triage by Severity

**Standard security workflow:**

1. Review all Critical/High first
2. If time permits, review Medium
3. Rarely review Low (noise)

**UI should match this workflow:**

```
┌─────────────────────────────────────────┐
│ Critical & High (15)  ← Expanded        │
├─────────────────────────────────────────┤
│ • cisco-sa-asa-webvpn-dos (Sev 1)       │
│   CVSS: 9.8, CVE-2023-12345             │
│   Labels: [MGMT_ASDM, SEC_WebVPN]       │
│   [Verify] [Details]                    │
├─────────────────────────────────────────┤
│ • cisco-sa-asa-auth-bypass (Sev 2)      │
│   CVSS: 8.1, CVE-2023-67890             │
│   ...                                   │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Medium & Low (125)  ← Collapsed         │
│ [Expand to view]                        │
└─────────────────────────────────────────┘
```

#### 2. Tier 1: Severity-Based Grouping (Built-in)

**Critical/High (Severity 1-2):**
- Full details: summary, labels, fix versions, commands
- Typical count: 5-20 vulnerabilities
- Response size: ~8 KB for 20 vulns

**Medium/Low (Severity 3-6):**
- Collapsed: vuln_id, advisory_id, severity, summary only
- Typical count: 30-100 vulnerabilities
- Response size: ~20 KB for 100 vulns

**Total response:** ~28 KB (acceptable)

**Code:**

```python
{
  "critical_high": [
    {
      "vuln_id": "vuln-001",
      "advisory_id": "cisco-sa-...",
      "severity": 1,
      "cvss_score": 9.8,
      "summary": "...",
      "labels": [...],
      "config_regex": [...],
      "show_commands": [...]  # FULL details
    }
  ],
  "medium_low": [
    {
      "vuln_id": "vuln-042",
      "advisory_id": "CSCabc123",
      "severity": 4,
      "cvss_score": 5.3,
      "summary": "..."  # MINIMAL details
    }
  ]
}
```

#### 3. Tier 2: Optional Limit (User-Controlled)

For extreme cases (100+ Critical/High):

**Request:**

```json
{
  "platform": "ASA",
  "version": "9.12.4",
  "labels": [...],
  "severity_filter": [1, 2],  // Only Critical/High
  "limit": 50,                 // First 50 results
  "offset": 0
}
```

**Response:**

```json
{
  "total_vulnerabilities": 140,
  "critical_high": [...],  // 50 results
  "medium_low": [],        // Empty (filtered out)
  "pagination": {
    "limit": 50,
    "offset": 0,
    "has_more": true,      // More results available
    "next_offset": 50
  }
}
```

**Frontend:**

```jsx
{pagination.has_more && (
  <Button onClick={() => fetchMore(pagination.next_offset)}>
    Load 50 More Vulnerabilities
  </Button>
)}
```

#### 4. Expand-on-Demand for Medium/Low

When user clicks "Expand Medium/Low":

**Request:**

```http
GET /api/v1/vulnerability/vuln-042
```

**Response:**

```json
{
  "vuln_id": "vuln-042",
  "advisory_id": "CSCabc123",
  "severity": 4,
  "summary": "...",
  "labels": [...],          // NOW included
  "config_regex": [...],     // NOW included
  "show_commands": [...]     // NOW included
}
```

**Frontend:**

```jsx
const expandVulnerability = async (vuln_id) => {
  const details = await fetchVulnerabilityDetails(vuln_id)
  setExpandedVulns({ ...expandedVulns, [vuln_id]: details })
}
```

**Benefit:** Only fetch details when analyst needs them.

### Edge Cases

#### Very Old Device (500+ vulnerabilities)

```
Device: IOS-XE 16.9.1 (EOL version, not patched in years)

Critical/High: 120 vulnerabilities
Medium/Low: 380 vulnerabilities
```

**Response strategy:**

1. **First request:** Return first 50 Critical/High (collapsed Medium/Low)
   - Response time: <100ms
   - Response size: ~20 KB

2. **User clicks "Load More":** Return next 50 Critical/High
   - Offset: 50, Limit: 50

3. **User clicks "Show Medium/Low":** Separate API call
   - `severity_filter: [3, 4, 5, 6]`
   - Collapsed format only

**Prevents:**
- Browser hang (500 full records = 200 KB)
- API timeout
- Poor UX

#### Only Low Severity Vulnerabilities

```
Device: IOS-XE 17.9.1 (latest, well-patched)

Critical/High: 0 vulnerabilities
Medium/Low: 5 vulnerabilities
```

**Response:**

```json
{
  "total_vulnerabilities": 5,
  "critical_high": [],
  "medium_low": [
    {"vuln_id": "vuln-1", "severity": 5, ...},
    {"vuln_id": "vuln-2", "severity": 6, ...},
    ...
  ]
}
```

**UI:**

```
┌─────────────────────────────────────────┐
│ ✅ No Critical or High Vulnerabilities  │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Medium & Low (5)                        │
│ • CSCabc123 (Sev 5) - Info disclosure   │
│ • CSCdef456 (Sev 6) - Minor bug         │
│ ...                                     │
└─────────────────────────────────────────┘
```

**Collapsed by default**, but small enough to show all.

### Performance Comparison

**Scenario:** 140 vulnerabilities (15 Critical/High, 125 Medium/Low)

| Strategy | Response Size | Load Time | User Experience |
|----------|---------------|-----------|-----------------|
| All full details | 56 KB | 150ms | Slow, overwhelming |
| Two-tier grouping | 28 KB | 80ms | Fast, focused |
| Two-tier + limit 50 | 20 KB | 60ms | Very fast, paginated |

**Winner:** Two-tier grouping (best balance)

### Implementation

**Database query:**

```python
def scan_device(self, platform, version, labels, severity_filter, limit, offset):
    # Query all matching vulnerabilities
    all_vulns = self.db.query_vulnerabilities(platform, version, labels)

    # Group by severity
    critical_high = [v for v in all_vulns if v['severity'] in [1, 2]]
    medium_low = [v for v in all_vulns if v['severity'] in [3, 4, 5, 6]]

    # Apply severity filter
    if severity_filter:
        if 1 not in severity_filter and 2 not in severity_filter:
            critical_high = []
        if all(s not in severity_filter for s in [3, 4, 5, 6]):
            medium_low = []

    # Apply pagination
    total = len(critical_high) + len(medium_low)

    if limit:
        critical_high = critical_high[offset:offset + limit]
        medium_low = medium_low[offset:offset + limit]

    # Format results
    critical_high_formatted = [self._format_full_vuln(v) for v in critical_high]
    medium_low_formatted = [self._format_collapsed_vuln(v) for v in medium_low]

    return {
        'critical_high': critical_high_formatted,
        'medium_low': medium_low_formatted,
        'total_vulnerabilities': total,
        'pagination': {
            'limit': limit,
            'offset': offset,
            'has_more': total > (offset + len(critical_high) + len(medium_low))
        }
    }
```

### Trade-offs

**Pros:**
- Fast response times (smaller payload)
- Matches analyst workflow (triage by severity)
- Handles extreme cases (100+ vulns)
- Expand-on-demand for details

**Cons:**
- Requires second API call for Medium/Low details
- Slightly more complex frontend logic

**Decision:** Use two-tier pagination (severity + optional limit).

## Summary

| Question | Decision | Key Rationale |
|----------|----------|---------------|
| Include verification commands? | **YES** | Immediate actionability, minimal cost |
| Handle unlabeled bugs? | **Include with warning** | Better false positive than false negative |
| Auto-cache LLM results? | **YES (confidence ≥0.75)** | Faster for team, consistent results |
| Pagination strategy? | **Two-tier (severity + limit)** | Matches workflow, handles edge cases |

All four decisions prioritize:
1. **Security** (don't miss vulnerabilities)
2. **Performance** (fast scans, small payloads)
3. **Usability** (match analyst workflow)
4. **Scalability** (handle edge cases gracefully)
