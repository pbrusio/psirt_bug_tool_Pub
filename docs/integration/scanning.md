# Device Scanning (Unified Assessment)

## Use Case
"Scan my device and tell me ALL vulnerabilities (PSIRTs + bugs)"

## Implementation

```python
def scan_device_unified(
    device: DeviceCredentials,
    platform: Optional[str] = None,
    version: Optional[str] = None,
    hardware_model: Optional[str] = None,
    features: Optional[List[str]] = None
) -> UnifiedScanResult:
    """
    Scan a single device against BOTH bug database and PSIRT cache.
    Returns unified vulnerability list.
    """

    # 1. Extract device info (if not provided)
    if not (platform and version and hardware_model and features):
        device_info = extract_device_info_via_ssh(device)
        platform = platform or device_info.platform
        version = version or device_info.version
        hardware_model = hardware_model or device_info.hardware_model
        features = features or device_info.features

    # 2. Scan bug database
    bugs = scan_bug_database(platform, version, hardware_model, features)

    # 3. Scan PSIRT cache (check all cached PSIRTs for this platform/version)
    psirts = scan_psirt_cache(platform, version)

    # 4. Convert to unified vulnerabilities
    vulnerabilities = (
        [bug_to_unified_vuln(b) for b in bugs] +
        [psirt_to_unified_vuln(p) for p in psirts]
    )

    # 5. Deduplicate by CVE ID
    vulnerabilities = deduplicate_by_cve(vulnerabilities)

    # 6. Sort by severity (Critical → High → Medium → Low)
    vulnerabilities.sort(key=lambda v: v.severity)

    # 7. Return unified result
    return UnifiedScanResult(
        device_hostname=device.host,
        platform=platform,
        version=version,
        hardware_model=hardware_model,
        features=features,
        total_vulnerabilities=len(vulnerabilities),
        critical=len([v for v in vulnerabilities if v.severity == 1]),
        high=len([v for v in vulnerabilities if v.severity == 2]),
        medium=len([v for v in vulnerabilities if v.severity == 3]),
        low=len([v for v in vulnerabilities if v.severity == 4]),
        vulnerabilities=vulnerabilities,
        breakdown={
            'from_bugs': len([v for v in vulnerabilities if v.type == "BUG"]),
            'from_psirts': len([v for v in vulnerabilities if v.type == "PSIRT"])
        },
        timestamp=datetime.now()
    )
```

## Deduplication Strategy

### Problem: Same vulnerability may appear as both bug and PSIRT

**Example:**
- Bug: CSCwk12345 → CVE-2023-20273
- PSIRT: cisco-sa-iosxe-webui → CVE-2023-20273

**Solution:** Deduplicate by CVE ID, keep the higher-confidence record

```python
def deduplicate_by_cve(vulnerabilities: List[UnifiedVulnerability]) -> List[UnifiedVulnerability]:
    """
    Remove duplicate vulnerabilities based on CVE ID.
    Keep bug over PSIRT if same CVE (bugs have more specific version data).
    """

    seen_cves = {}
    deduplicated = []

    for vuln in vulnerabilities:
        # If no CVE, keep it (can't deduplicate)
        if not vuln.cve_ids:
            deduplicated.append(vuln)
            continue

        # Check each CVE
        is_duplicate = False
        for cve in vuln.cve_ids:
            if cve in seen_cves:
                # Already have this CVE - decide which to keep
                existing = seen_cves[cve]

                # Prefer bug over PSIRT (bugs have better version data)
                # Prefer higher confidence
                if vuln.type == "BUG" and existing.type == "PSIRT":
                    # Replace PSIRT with bug
                    deduplicated.remove(existing)
                    deduplicated.append(vuln)
                    seen_cves[cve] = vuln
                elif vuln.confidence > existing.confidence:
                    # Replace lower confidence with higher
                    deduplicated.remove(existing)
                    deduplicated.append(vuln)
                    seen_cves[cve] = vuln

                is_duplicate = True
                break

        if not is_duplicate:
            deduplicated.append(vuln)
            for cve in vuln.cve_ids:
                seen_cves[cve] = vuln

    return deduplicated
```
