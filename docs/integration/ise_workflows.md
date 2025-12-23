# ISE Integration (Inventory-Wide Assessment)

## Use Case
"Pull 100 devices from ISE, scan all against bugs + PSIRTs"

## Implementation

```python
def scan_ise_inventory_unified(
    ise_credentials: ISECredentials,
    refresh_device_info: bool = False
) -> InventoryScanResult:
    """
    Pull device list from ISE, scan ALL devices against unified vulnerability sources.
    """

    # 1. Pull device inventory from ISE
    devices = pull_devices_from_ise(ise_credentials)

    # 2. For each device, check cached info or refresh via SSH
    device_metadata = []
    for device in devices:
        if refresh_device_info or not has_cached_info(device.ip):
            # SSH to device and extract info
            info = extract_device_info_via_ssh(device)
            cache_device_info(device.ip, info)
        else:
            # Use cached info
            info = get_cached_info(device.ip)

        device_metadata.append(info)

    # 3. Scan each device against unified sources (bugs + PSIRTs)
    scan_results = []
    for info in device_metadata:
        result = scan_device_unified(
            device=None,  # Already have info, no SSH needed
            platform=info.platform,
            version=info.version,
            hardware_model=info.hardware_model,
            features=info.features
        )
        scan_results.append(result)

    # 4. Aggregate results
    return InventoryScanResult(
        total_devices=len(devices),
        devices_scanned=len(scan_results),
        total_vulnerabilities=sum(r.total_vulnerabilities for r in scan_results),
        critical=sum(r.critical for r in scan_results),
        high=sum(r.high for r in scan_results),
        medium=sum(r.medium for r in scan_results),
        low=sum(r.low for r in scan_results),
        scan_results=scan_results,
        timestamp=datetime.now()
    )
```
