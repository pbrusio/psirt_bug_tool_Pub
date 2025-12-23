# Unified Vulnerability Data Model

## Common Vulnerability Object

Both PSIRTs and Bugs map to this unified schema:

```python
class UnifiedVulnerability:
    # Core Identification
    id: str                    # "CSCwk12345" or "cisco-sa-iosxe-webui-priv"
    type: str                  # "BUG" or "PSIRT"

    # Vulnerability Details
    title: str                 # Short headline
    summary: str               # Full description
    severity: int              # 1-4 (Critical, High, Medium, Low)
    cvss_score: float          # 0-10
    cve_ids: List[str]         # ["CVE-2023-20273", ...]

    # Affected Systems
    platform: str              # "IOS-XE"
    affected_versions: str     # "17.6.1-17.10.1"
    hardware_models: List[str] # ["Cat9300", "Cat9400"] or None (generic)

    # Feature/Label Mapping
    labels: List[str]          # ["MGMT_SSH_HTTP", "SEC_CoPP"]
    config_regex: List[str]    # Patterns to detect affected config
    show_commands: List[str]   # Commands to verify vulnerability

    # Metadata
    published_date: datetime
    last_updated: datetime
    status: str                # "Open", "Fixed", "Mitigated"
    url: str                   # Link to advisory/bug page

    # Source Tracking
    source: str                # "psirt_db", "bug_db", "sec8b_inference"
    confidence: float          # 0-1 (for LLM-predicted labels)

    # Exploitation Intelligence (for detection rules)
    exploit_available: bool
    exploit_iocs: List[dict]   # IOCs for rule generation
    affected_ports: List[int]
    affected_protocols: List[str]
```

## Mappings

### Bug → UnifiedVulnerability

```python
def bug_to_unified_vuln(bug: Bug) -> UnifiedVulnerability:
    """Convert bug database record to unified vulnerability."""
    return UnifiedVulnerability(
        id=bug.bug_id,
        type="BUG",
        title=bug.headline,
        summary=bug.summary,
        severity=bug.severity,
        cvss_score=extract_cvss_from_summary(bug.summary),  # Parse if available
        cve_ids=extract_cves_from_summary(bug.summary),
        platform=bug.platform,
        affected_versions=bug.affected_versions,
        hardware_models=[bug.hardware_model] if bug.hardware_model else None,
        labels=bug.labels.split(',') if bug.labels else [],
        config_regex=load_config_patterns(bug.labels),  # From features.yml
        show_commands=load_show_commands(bug.labels),
        published_date=bug.last_modified,
        status=bug.status,
        url=bug.url,
        source="bug_db",
        confidence=1.0,  # Database records are 100% confident
        exploit_available=False,  # Default, can enhance later
        exploit_iocs=[],
        affected_ports=[],
        affected_protocols=[]
    )
```

### PSIRT → UnifiedVulnerability

```python
def psirt_to_unified_vuln(psirt: AnalysisResult, metadata: PSIRTMetadata) -> UnifiedVulnerability:
    """Convert PSIRT analysis to unified vulnerability."""
    return UnifiedVulnerability(
        id=psirt.advisory_id or generate_temp_id(),
        type="PSIRT",
        title=extract_title_from_summary(psirt.summary),
        summary=psirt.summary,
        severity=infer_severity_from_summary(psirt.summary),
        cvss_score=extract_cvss_from_summary(psirt.summary),
        cve_ids=extract_cves_from_summary(psirt.summary),
        platform=psirt.platform,
        affected_versions=metadata.product_names,  # Version info from metadata
        hardware_models=None,  # PSIRTs rarely specify hardware
        labels=psirt.predicted_labels,
        config_regex=psirt.config_regex,
        show_commands=psirt.show_commands,
        published_date=psirt.timestamp,
        status="Open",  # Default for new PSIRTs
        url=f"https://sec.cloudapps.cisco.com/security/center/content/CiscoSecurityAdvisory/{psirt.advisory_id}",
        source="sec8b_inference" if psirt.confidence < 1.0 else "psirt_db",
        confidence=psirt.confidence,
        exploit_available=check_exploit_db(psirt.advisory_id),  # Query threat intel
        exploit_iocs=fetch_iocs(psirt.advisory_id),
        affected_ports=infer_ports_from_labels(psirt.predicted_labels),
        affected_protocols=infer_protocols_from_labels(psirt.predicted_labels)
    )
```

## Database Schema Updates

### New Table: `psirt_cache`

Store analyzed PSIRTs in database alongside bugs for unified querying.

```sql
CREATE TABLE psirt_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    advisory_id TEXT UNIQUE,
    platform TEXT NOT NULL,
    summary TEXT,
    predicted_labels TEXT,  -- JSON array
    config_regex TEXT,      -- JSON array
    show_commands TEXT,     -- JSON array
    confidence REAL,
    affected_versions TEXT, -- "17.6.1-17.10.1"
    cve_ids TEXT,          -- JSON array
    severity INTEGER,
    published_date TEXT,
    cached_at TEXT,
    source TEXT,           -- "sec8b_inference", "exact_match", "manual"

    -- For unified querying
    FOREIGN KEY (platform) REFERENCES vulnerabilities(platform)
);

CREATE INDEX idx_psirt_platform_version ON psirt_cache(platform, affected_versions);
CREATE INDEX idx_psirt_advisory ON psirt_cache(advisory_id);
```

### Unified Query Function

```python
def query_vulnerabilities_unified(
    platform: str,
    version: str,
    hardware_model: Optional[str] = None,
    features: Optional[List[str]] = None
) -> List[UnifiedVulnerability]:
    """
    Query BOTH vulnerabilities table (bugs) and psirt_cache table.
    Return unified vulnerability list.
    """

    # Query bugs
    bugs = db.query('''
        SELECT * FROM vulnerabilities
        WHERE platform = ?
        AND version_matches(?, affected_versions) = 1
        AND (hardware_model IS NULL OR hardware_model = ?)
    ''', (platform, version, hardware_model))

    # Query PSIRTs
    psirts = db.query('''
        SELECT * FROM psirt_cache
        WHERE platform = ?
        AND version_matches(?, affected_versions) = 1
    ''', (platform, version))

    # Convert to unified objects
    vulnerabilities = (
        [bug_to_unified_vuln(b) for b in bugs] +
        [psirt_to_unified_vuln(p) for p in psirts]
    )

    # Filter by features if provided
    if features:
        vulnerabilities = feature_filter(vulnerabilities, features)

    return deduplicate_by_cve(vulnerabilities)
```
