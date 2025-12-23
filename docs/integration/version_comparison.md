# Version Comparison (Combined PSIRT + Bug Analysis)

## Use Case
"Should I upgrade from 17.10.1 to 17.12.1?"

## Current vs Target State
**Current State:** Only compares bugs in database
**Target State:** Compares bugs AND PSIRTs affecting both versions

## Implementation

```python
def compare_versions_unified(
    current_version: str,
    target_version: str,
    platform: str,
    hardware_model: Optional[str] = None,
    features: Optional[List[str]] = None
) -> VersionComparisonResult:
    """
    Compare two versions across BOTH bug database and PSIRT cache.
    Returns unified vulnerability delta.
    """

    # 1. Query Bug Database for both versions
    current_bugs = scan_bug_database(platform, current_version, hardware_model, features)
    target_bugs = scan_bug_database(platform, target_version, hardware_model, features)

    # 2. Query PSIRT Database/Cache for both versions
    current_psirts = scan_psirt_cache(platform, current_version)
    target_psirts = scan_psirt_cache(platform, target_version)

    # 3. Convert to unified vulnerability objects
    current_vulns = (
        [bug_to_unified_vuln(b) for b in current_bugs] +
        [psirt_to_unified_vuln(p) for p in current_psirts]
    )
    target_vulns = (
        [bug_to_unified_vuln(b) for b in target_bugs] +
        [psirt_to_unified_vuln(p) for p in target_psirts]
    )

    # 4. Deduplicate (same CVE in both bug and PSIRT)
    current_vulns = deduplicate_by_cve(current_vulns)
    target_vulns = deduplicate_by_cve(target_vulns)

    # 5. Calculate delta
    vulns_fixed = [v for v in current_vulns if v.id not in [t.id for t in target_vulns]]
    new_vulns = [v for v in target_vulns if v.id not in [c.id for c in current_vulns]]

    # 6. Analyze and recommend
    return VersionComparisonResult(
        current_version=current_version,
        target_version=target_version,
        current_total=len(current_vulns),
        target_total=len(target_vulns),
        vulnerabilities_fixed=vulns_fixed,
        new_vulnerabilities=new_vulns,
        net_change=len(vulns_fixed) - len(new_vulns),
        recommendation="UPGRADE" if len(vulns_fixed) > len(new_vulns) else "REVIEW",
        breakdown={
            'bugs_fixed': len([v for v in vulns_fixed if v.type == "BUG"]),
            'psirts_fixed': len([v for v in vulns_fixed if v.type == "PSIRT"]),
            'new_bugs': len([v for v in new_vulns if v.type == "BUG"]),
            'new_psirts': len([v for v in new_vulns if v.type == "PSIRT"])
        }
    )
```

## UI Mockup

```
┌──────────────────────────────────────────────────────────┐
│ Version Comparison: 17.10.1 → 17.12.1                   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ Current Version (17.10.1): 18 Vulnerabilities           │
│   • 15 Bugs (12 Critical, 3 High)                       │
│   • 3 PSIRTs (2 Critical, 1 High)                       │
│                                                          │
│ Target Version (17.12.1): 7 Vulnerabilities             │
│   • 5 Bugs (2 Critical, 3 High)                         │
│   • 2 PSIRTs (1 Critical, 1 High)                       │
│                                                          │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│
│                                                          │
│ ✅ Fixed: 13 Vulnerabilities                            │
│   ┌────────────────────────────────────────────┐       │
│   │ 🐛 CSCwk12345 (Bug - Critical)              │       │
│   │    SSH DoS vulnerability                    │       │
│   │                                             │       │
│   │ 🔒 cisco-sa-iosxe-webui (PSIRT - Critical) │       │
│   │    CVE-2023-20273 - Web UI privilege esc   │       │
│   │                                             │       │
│   │ 🐛 CSCwj99876 (Bug - High)                  │       │
│   │    BGP routing loop                         │       │
│   │                                             │       │
│   │ ... (10 more)                               │       │
│   └────────────────────────────────────────────┘       │
│                                                          │
│ ⚠️  New: 2 Vulnerabilities                              │
│   ┌────────────────────────────────────────────┐       │
│   │ 🐛 CSCwl11111 (Bug - Medium)                │       │
│   │    OSPF convergence delay                   │       │
│   │                                             │       │
│   │ 🐛 CSCwl22222 (Bug - Low)                   │       │
│   │    Logging buffer overflow                  │       │
│   └────────────────────────────────────────────┘       │
│                                                          │
│ 📈 Net Change: +11 vulnerabilities fixed (61% better)   │
│ 🎯 Recommendation: ✅ UPGRADE RECOMMENDED               │
│                                                          │
│ [📄 Generate Report] [🔍 View Details]                  │
└──────────────────────────────────────────────────────────┘
```
