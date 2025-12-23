# API Specifications

## New Unified Endpoints

```python
# Version Comparison (Unified)
@app.post("/api/v1/compare-versions")
def compare_versions(request: VersionComparisonRequest):
    """
    Compare two versions across bugs AND PSIRTs.
    Returns unified vulnerability delta.
    """
    return compare_versions_unified(
        current_version=request.current_version,
        target_version=request.target_version,
        platform=request.platform,
        hardware_model=request.hardware_model,
        features=request.features
    )

# Device Scan (Unified)
@app.post("/api/v1/scan-device-unified")
def scan_device_unified_endpoint(request: UnifiedScanRequest):
    """
    Scan device against bugs AND PSIRTs.
    Returns unified vulnerability list.
    """
    if request.device_credentials:
        # SSH to device
        return scan_device_unified(
            device=request.device_credentials,
            platform=request.platform,
            version=request.version,
            hardware_model=request.hardware_model,
            features=request.features
        )
    else:
        # Use provided metadata
        return scan_device_unified(
            device=None,
            platform=request.platform,
            version=request.version,
            hardware_model=request.hardware_model,
            features=request.features
        )

# ISE Inventory Scan (Unified)
@app.post("/api/v1/scan-ise-inventory")
def scan_ise_inventory(request: ISEScanRequest):
    """
    Pull devices from ISE, scan against bugs AND PSIRTs.
    Returns inventory-wide unified vulnerability report.
    """
    return scan_ise_inventory_unified(
        ise_credentials=request.ise_credentials,
        refresh_device_info=request.refresh_device_info
    )

# Detection Rule Generation (Unified)
@app.post("/api/v1/generate-detection-rules")
def generate_rules(request: DetectionRuleRequest):
    """
    Generate detection rules for vulnerabilities (bugs OR PSIRTs).
    Supports Firepower, Stealthwatch, Snort formats.
    """
    return generate_detection_rules_unified(
        vulnerabilities=request.vulnerabilities,
        rule_format=request.format
    )
```
