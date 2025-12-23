import { useState, useEffect } from 'react';
import { buildInventoryUrl, getApiHeaders } from '../api/config';
import { SSHCredentialsModal } from './SSHCredentialsModal';

interface Device {
  id: number;
  ise_id: string;
  hostname: string;
  ip_address: string;
  location: string | null;
  device_type: string | null;
  platform: string | null;
  version: string | null;
  hardware_model: string | null;
  features: string | null;  // JSON string of feature array
  discovery_status: 'pending' | 'success' | 'failed';
  discovery_error: string | null;
  last_scanned: string | null;
  last_scan_result: string | null;  // JSON string of scan summary
  last_scan_id: string | null;
  last_scan_timestamp: string | null;
  previous_scan_result: string | null;  // JSON string of previous scan summary
  previous_scan_id: string | null;
  previous_scan_timestamp: string | null;
  ise_sync_time: string;
  ssh_discovery_time: string | null;
}

interface ScanSummary {
  scan_id: string;
  timestamp: string;
  platform: string;
  version: string;
  hardware_model: string | null;
  total_bugs_checked: number;
  version_matches: number;
  hardware_filtered: number;
  feature_filtered: number;
  total_bugs: number;
  critical_high: number;
  medium_low: number;
  query_time_ms: number;
}

interface InventoryStats {
  total_devices: number;
  by_status: Record<string, number>;
  by_platform: Record<string, number>;
  needs_scan: number;
}

interface Bug {
  bug_id: string;
  headline: string;  // Backend returns 'headline', not 'title'
  summary: string;
  severity: number | string;  // Backend returns number (1=Critical, 2=High, etc.) but may be stringified
  affected_versions: string;  // Backend returns string, not array
  status: string;
  labels: string[];
  url: string;
  hardware_model?: string | null;
}

interface ScanResult {
  scan_id: string;
  platform: string;
  version: string;
  hardware_model: string | null;
  timestamp: string;
  total_bugs_checked: number;
  version_matches: number;
  hardware_filtered: number;
  feature_filtered: number;
  total_bugs: number;
  critical_high: number;
  medium_low: number;
  bugs: Bug[];
  query_time_ms: number;
}

interface ComparisonResult {
  comparison_id: string;
  current_scan: {
    scan_id: string;
    timestamp: string;
    platform: string;
    version: string;
    hardware_model: string | null;
    total_bugs: number;
  };
  previous_scan: {
    scan_id: string;
    timestamp: string;
    platform: string;
    version: string;
    hardware_model: string | null;
    total_bugs: number;
  };
  fixed_bugs: Bug[];
  new_bugs: Bug[];
  unchanged_bugs: Bug[];
  summary: {
    total_fixed: number;
    total_new: number;
    total_unchanged: number;
    net_change: number;
    fixed_by_severity: Record<string, number>;
    new_by_severity: Record<string, number>;
  };
}

interface VersionComparisonResult {
  success?: boolean;
  comparison_id: string;
  comparison_type?: string;
  platform?: string;
  hardware_model?: string | null;
  features_filtered?: string[];
  current_version_scan: {
    version: string;
    platform: string;
    hardware_model: string | null;
    total_bugs: number;
    critical_high: number;
    medium_low?: number;
    query_time_ms: number;
  };
  target_version_scan: {
    version: string;
    platform: string;
    hardware_model: string | null;
    total_bugs: number;
    critical_high: number;
    medium_low?: number;
    query_time_ms: number;
  };
  fixed_in_upgrade: Bug[];
  new_in_upgrade: Bug[];
  still_present: Bug[];
  summary: {
    total_fixed: number;
    total_new: number;
    total_unchanged: number;
    net_change: number;
    fixed_by_severity: Record<string, number>;
    new_by_severity: Record<string, number>;
  };
  upgrade_recommendation: {
    risk_score: number;
    risk_level: string;
    recommendation: string;
    metrics: {
      total_fixed: number;
      total_new: number;
      net_change: number;
      critical_fixed: number;
      high_fixed: number;
      critical_new: number;
      high_new: number;
    };
  };
}

export function InventoryManager() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [stats, setStats] = useState<InventoryStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useLabDevices, setUseLabDevices] = useState(true); // Use lab devices by default
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterPlatform, setFilterPlatform] = useState<string>('all');

  // ISE configuration state
  const [iseHost, setIseHost] = useState('192.168.0.30');
  const [iseUsername, setIseUsername] = useState('ersAdmin');
  const [isePassword, setIsePassword] = useState('Pa22word');
  const [showIseConfig, setShowIseConfig] = useState(false);

  // Modal state
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [showCompareModal, setShowCompareModal] = useState(false);
  const [showVersionCompareModal, setShowVersionCompareModal] = useState(false);
  const [selectedScanResult, setSelectedScanResult] = useState<ScanResult | null>(null);
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [comparisonResult, setComparisonResult] = useState<ComparisonResult | null>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);
  const [activeCompareTab, setActiveCompareTab] = useState<'fixed' | 'new' | 'unchanged'>('new');

  // SSH Credentials Modal state
  const [credentialsModal, setCredentialsModal] = useState<{
    isOpen: boolean;
    deviceId: number | null;
    deviceName: string;
    action: 'discover' | 'compare';
  }>({ isOpen: false, deviceId: null, deviceName: '', action: 'discover' });

  // Version comparison state
  const [versionComparisonResult, setVersionComparisonResult] = useState<VersionComparisonResult | null>(null);
  const [loadingVersionComparison, setLoadingVersionComparison] = useState(false);
  const [targetVersion, setTargetVersion] = useState<string>('');
  const [activeVersionTab, setActiveVersionTab] = useState<'fixed' | 'new' | 'unchanged'>('new');

  // Add Device modal state
  const [showAddDeviceModal, setShowAddDeviceModal] = useState(false);
  const [addingDevice, setAddingDevice] = useState(false);
  const [newDevice, setNewDevice] = useState({
    hostname: '',
    ip_address: '',
    platform: '',
    version: '',
    hardware_model: '',
    location: '',
  });

  // Bulk scan state
  const [bulkScanJob, setBulkScanJob] = useState<{
    jobId: string | null;
    status: 'idle' | 'running' | 'completed' | 'failed';
    progress: number;
    currentDevice: string | null;
    total: number;
    scanned: number;
    failed: number;
  } | null>(null);

  // CSV Import state
  const [showImportModal, setShowImportModal] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{
    success: boolean;
    total_rows: number;
    imported: number;
    updated: number;
    skipped: number;
    errors: string[];
  } | null>(null);

  // Severity helpers for bug display
  const getSeverityColor = (severity: number | string) => {
    const sev = typeof severity === 'string' ? severity : severity;
    if (sev === 1 || sev === 'Critical') return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
    if (sev === 2 || sev === 'High') return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400';
    if (sev === 3 || sev === 'Medium') return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400';
    return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400';
  };

  const getSeverityLabel = (severity: number | string) => {
    if (severity === 1 || severity === 'Critical') return 'Critical';
    if (severity === 2 || severity === 'High') return 'High';
    if (severity === 3 || severity === 'Medium') return 'Medium';
    return 'Low';
  };

  // Load devices and stats
  const loadDevices = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filterStatus !== 'all') params.append('discovery_status', filterStatus);
      if (filterPlatform !== 'all') params.append('platform', filterPlatform);

      const response = await fetch(`${buildInventoryUrl('devices')}?${params}`);
      const data = await response.json();

      if (data.success) {
        setDevices(data.devices);
      } else {
        setError('Failed to load devices');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load devices');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch(buildInventoryUrl('stats'));
      const data = await response.json();

      if (data.success) {
        setStats(data);
      }
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  // Sync from ISE
  const handleSync = async () => {
    // If using real ISE and config not shown, show it first
    if (!useLabDevices && !showIseConfig) {
      setShowIseConfig(true);
      return;
    }

    setSyncing(true);
    setError(null);
    setShowIseConfig(false);

    try {
      const requestBody: any = {
        max_devices: 50,
        use_mock: useLabDevices,
      };

      // Add ISE credentials if using real ISE
      if (!useLabDevices) {
        requestBody.ise_host = iseHost;
        requestBody.ise_username = iseUsername;
        requestBody.ise_password = isePassword;
      }

      const response = await fetch(buildInventoryUrl('sync-ise'), {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();

      if (data.success) {
        await loadDevices();
        await loadStats();
        const source = useLabDevices ? 'Lab Devices' : `ISE (${iseHost})`;
        alert(`✓ Synced from ${source}: ${data.devices_added} new devices, ${data.devices_updated} updated`);
      } else {
        setError(data.detail || 'ISE sync failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ISE sync failed');
    } finally {
      setSyncing(false);
    }
  };

  // Discover single device
  const handleDiscoverDevice = async (device: Device) => {
    // Open credentials modal
    setCredentialsModal({
      isOpen: true,
      deviceId: device.id,
      deviceName: device.hostname,
      action: 'discover'
    });
  };

  // Perform the actual SSH discovery with credentials
  const performDiscovery = async (deviceId: number, username: string, password: string) => {
    try {
      const response = await fetch(buildInventoryUrl('discover-device'), {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({
          device_id: deviceId,
          username,
          password,
          device_type: 'cisco_ios',
        }),
      });

      const data = await response.json();

      if (data.success) {
        await loadDevices();
        await loadStats();
        alert(`✓ Discovery successful: ${data.platform} ${data.version}`);
      } else {
        alert(`✗ Discovery failed: ${data.error}`);
      }
    } catch (err) {
      alert(`✗ Discovery failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  // Delete device
  const handleDeleteDevice = async (device: Device) => {
    if (!window.confirm(`Delete device "${device.hostname}"?\n\nThis will also remove all scan history for this device.`)) {
      return;
    }

    try {
      const response = await fetch(buildInventoryUrl(`devices/${device.id}`), {
        method: 'DELETE',
        headers: getApiHeaders(),
      });

      const data = await response.json();

      if (data.success) {
        await loadDevices();
        await loadStats();
        alert(`✓ Device "${device.hostname}" deleted`);
      } else {
        alert(`✗ Delete failed: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`✗ Delete failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  // Add device
  const handleAddDevice = async () => {
    if (!newDevice.hostname.trim() || !newDevice.ip_address.trim()) {
      alert('Hostname and IP address are required');
      return;
    }

    setAddingDevice(true);
    try {
      const response = await fetch(buildInventoryUrl('devices'), {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify(newDevice),
      });

      const data = await response.json();

      if (data.success) {
        await loadDevices();
        await loadStats();
        setShowAddDeviceModal(false);
        setNewDevice({ hostname: '', ip_address: '', platform: '', version: '', hardware_model: '', location: '' });
        alert(`✓ ${data.message}`);
      } else {
        alert(`✗ Add failed: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`✗ Add failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setAddingDevice(false);
    }
  };

  // Start bulk scan
  const handleBulkScan = async () => {
    try {
      const response = await fetch(buildInventoryUrl('scan-all'), {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({}),
      });

      const data = await response.json();

      if (data.job_id) {
        setBulkScanJob({
          jobId: data.job_id,
          status: 'running',
          progress: 0,
          currentDevice: null,
          total: data.total_devices || 0,
          scanned: 0,
          failed: 0,
        });
      } else {
        alert(`✗ Bulk scan failed: ${data.detail || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`✗ Bulk scan failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  // Download CSV template
  const handleDownloadTemplate = () => {
    window.open(buildInventoryUrl('devices/template'), '_blank');
  };

  // Import CSV file
  const handleImportCSV = async (file: File) => {
    setImporting(true);
    setImportResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(buildInventoryUrl('devices/import'), {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        setImportResult(data);
        await loadDevices();
        await loadStats();
      } else {
        setImportResult({
          success: false,
          total_rows: 0,
          imported: 0,
          updated: 0,
          skipped: 0,
          errors: [data.detail || 'Import failed']
        });
      }
    } catch (err) {
      setImportResult({
        success: false,
        total_rows: 0,
        imported: 0,
        updated: 0,
        skipped: 0,
        errors: [err instanceof Error ? err.message : 'Import failed']
      });
    } finally {
      setImporting(false);
    }
  };

  // Poll bulk scan progress
  useEffect(() => {
    if (!bulkScanJob?.jobId || bulkScanJob.status !== 'running') return;

    const interval = setInterval(async () => {
      try {
        const response = await fetch(buildInventoryUrl(`scan-status/${bulkScanJob.jobId}`));
        const data = await response.json();

        setBulkScanJob(prev => ({
          ...prev!,
          status: data.status,
          progress: data.progress_percent || 0,
          currentDevice: data.current_device,
          scanned: data.scanned || 0,
          failed: data.failed || 0,
        }));

        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(interval);
          await loadDevices();
          await loadStats();
        }
      } catch (err) {
        console.error('Failed to poll scan status:', err);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [bulkScanJob?.jobId, bulkScanJob?.status]);

  // Scan device for bugs
  const handleScanDevice = async (device: Device) => {
    if (!device.platform || !device.version) {
      alert('⚠️ Device must be discovered first (platform and version required)');
      return;
    }

    try {
      const response = await fetch(buildInventoryUrl(`scan-device/${device.id}`), {
        method: 'POST',
        headers: getApiHeaders(),
      });

      if (!response.ok) {
        const data = await response.json();
        alert(`✗ Scan failed: ${data.error || data.detail || 'Server error'}`);
        return;
      }

      const data = await response.json();

      if (data.success) {
        const summary = data.scan_summary;
        const bugCount = summary.total_bugs || 0;
        const criticalHigh = summary.critical_high || 0;

        // Refresh device list to show updated scan data
        await loadDevices();
        await loadStats();

        alert(
          `✓ Scan complete for ${data.hostname}\n\n` +
          `Found ${bugCount} bugs\n` +
          `  • Critical/High: ${criticalHigh}\n` +
          `  • Version matches: ${summary.version_matches}\n` +
          `  • Hardware filtered: ${summary.hardware_filtered || 0}\n\n` +
          `Scan results saved to inventory.`
        );
      } else {
        alert(`✗ Scan failed: ${data.error || 'Unknown error'}`);
      }
    } catch (err) {
      alert(`✗ Scan failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  // View scan details
  const handleViewDetails = async (device: Device) => {
    if (!device.last_scan_id) {
      alert('No scan results available');
      return;
    }

    setLoadingDetails(true);
    setSelectedDevice(device);
    setShowDetailsModal(true);

    try {
      const response = await fetch(buildInventoryUrl(`scan-results/${device.last_scan_id}`));
      const data = await response.json();

      if (data.success) {
        setSelectedScanResult(data.result);
      } else {
        alert('Failed to load scan results');
        setShowDetailsModal(false);
      }
    } catch (err) {
      alert(`Failed to load scan results: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setShowDetailsModal(false);
    } finally {
      setLoadingDetails(false);
    }
  };

  // Compare scans (before/after)
  const handleCompareToPrevious = async (device: Device) => {
    if (!device.last_scan_id || !device.previous_scan_id) {
      alert('Need both current and previous scan results for comparison');
      return;
    }

    setLoadingComparison(true);
    setSelectedDevice(device);
    setShowCompareModal(true);
    setActiveCompareTab('new'); // Start with new bugs tab (most important)

    try {
      const response = await fetch(
        `${buildInventoryUrl('compare-scans')}?current_scan_id=${device.last_scan_id}&previous_scan_id=${device.previous_scan_id}`,
        { method: 'POST', headers: getApiHeaders() }
      );
      const data = await response.json();

      if (data.success) {
        setComparisonResult(data);
      } else {
        alert('Failed to load comparison');
        setShowCompareModal(false);
      }
    } catch (err) {
      alert(`Failed to load comparison: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setShowCompareModal(false);
    } finally {
      setLoadingComparison(false);
    }
  };

  // Compare versions (upgrade planning)
  const handleCompareVersions = async (device: Device) => {
    if (!device.platform || !device.version) {
      alert('Device must be discovered first (platform and version required)');
      return;
    }

    // Check if features are extracted
    const features = device.features ? JSON.parse(device.features) : [];
    if (features.length === 0) {
      const proceed = window.confirm(
        '⚠️ WARNING: No features detected for this device!\n\n' +
        'Version comparison will show ALL bugs without filtering, ' +
        'including false positives (e.g., EIGRP, MPLS bugs on devices that don\'t use these features).\n\n' +
        'For accurate results:\n' +
        '1. Click "Refresh" to run SSH discovery and extract features\n' +
        '2. Then run version comparison again\n\n' +
        'Proceed anyway with unfiltered results?'
      );
      if (!proceed) return;
    }

    // Prompt for target version
    const target = prompt(`Enter target version to compare against current version (${device.version}):`, '');
    if (!target || target.trim() === '') return;

    setSelectedDevice(device);
    setTargetVersion(target.trim());
    setLoadingVersionComparison(true);
    setShowVersionCompareModal(true);
    setActiveVersionTab('new');

    try {
      // Parse features from device
      const features = device.features ? JSON.parse(device.features) : [];

      const response = await fetch(buildInventoryUrl('compare-versions'), {
        method: 'POST',
        headers: getApiHeaders(),
        body: JSON.stringify({
          platform: device.platform,
          current_version: device.version,
          target_version: target.trim(),
          hardware_model: device.hardware_model,
          features: features
        })
      });

      const data = await response.json();

      if (data.success) {
        setVersionComparisonResult(data);
      } else {
        alert('Failed to load version comparison');
        setShowVersionCompareModal(false);
      }
    } catch (err) {
      alert(`Failed to load version comparison: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setShowVersionCompareModal(false);
    } finally {
      setLoadingVersionComparison(false);
    }
  };

  // Handle SSH credentials submission
  const handleCredentialsSubmit = async (username: string, password: string) => {
    const { deviceId, action } = credentialsModal;

    // Close modal
    setCredentialsModal({ isOpen: false, deviceId: null, deviceName: '', action: 'discover' });

    if (!deviceId) return;

    // Perform the appropriate action
    if (action === 'discover') {
      await performDiscovery(deviceId, username, password);
    }
    // Note: 'compare' action not yet needed as version comparison doesn't require SSH
  };

  // Load on mount
  useEffect(() => {
    loadDevices();
    loadStats();
  }, [filterStatus, filterPlatform]);

  const getStatusBadge = (status: string) => {
    const badges = {
      pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400',
      success: 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400',
      failed: 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400',
    };
    return badges[status as keyof typeof badges] || badges.pending;
  };

  const parseScanSummary = (jsonString: string | null): ScanSummary | null => {
    if (!jsonString) return null;
    try {
      return JSON.parse(jsonString);
    } catch {
      return null;
    }
  };

  const formatScanSummary = (summary: ScanSummary | null) => {
    if (!summary) return null;

    const bugCount = summary.total_bugs;
    const criticalHigh = summary.critical_high;

    let color = 'text-gray-600 dark:text-gray-400';
    let icon = '✓';

    if (criticalHigh > 0) {
      color = 'text-red-600 dark:text-red-400';
      icon = '⚠️';
    } else if (bugCount > 0) {
      color = 'text-yellow-600 dark:text-yellow-400';
      icon = '⚠';
    } else {
      color = 'text-green-600 dark:text-green-400';
      icon = '✓';
    }

    return { text: `${icon} ${bugCount} bugs (${criticalHigh} crit/high)`, color };
  };

  // Clean HTML tags from bug text
  const cleanHtml = (text: string | null | undefined): string => {
    if (!text) return 'No summary available';
    return text
      .replace(/&nbsp;/g, ' ')
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/<B>/ig, '')
      .replace(/<\/B>/ig, '')
      .replace(/<I>/ig, '')
      .replace(/<\/I>/ig, '')
      .replace(/<U>/ig, '')
      .replace(/<\/U>/ig, '')
      .replace(/<BR>/ig, '\n')
      .trim();
  };

  return (
    <div className="space-y-6">
      {/* Header with Sync Button */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="card-header mb-2">Device Inventory</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Manage network devices synced from ISE
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowAddDeviceModal(true)}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg flex items-center gap-2"
            >
              <span>➕</span> Add Device
            </button>
            <button
              onClick={() => {
                setImportResult(null);
                setShowImportModal(true);
              }}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg flex items-center gap-2"
            >
              <span>📥</span> Import CSV
            </button>
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
              <input
                type="checkbox"
                checked={useLabDevices}
                onChange={(e) => {
                  setUseLabDevices(e.target.checked);
                  if (e.target.checked) setShowIseConfig(false);
                }}
                className="rounded"
              />
              Lab Devices
            </label>
            <button
              onClick={handleSync}
              disabled={syncing}
              className="btn btn-primary"
            >
              {syncing ? '⏳ Syncing...' : useLabDevices ? '📦 Load Lab Devices' : '🔄 Sync from ISE'}
            </button>
            <button
              onClick={handleBulkScan}
              disabled={bulkScanJob?.status === 'running'}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg flex items-center gap-2"
            >
              <span>🔍</span> Scan All
            </button>
          </div>
        </div>

        {/* ISE Configuration Panel */}
        {showIseConfig && !useLabDevices && (
          <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-3">
              🔐 ISE Connection Settings
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  ISE Server IP
                </label>
                <input
                  type="text"
                  value={iseHost}
                  onChange={(e) => setIseHost(e.target.value)}
                  placeholder="192.168.0.30"
                  className="input w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Username
                </label>
                <input
                  type="text"
                  value={iseUsername}
                  onChange={(e) => setIseUsername(e.target.value)}
                  placeholder="ersAdmin"
                  className="input w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={isePassword}
                  onChange={(e) => setIsePassword(e.target.value)}
                  placeholder="••••••••"
                  className="input w-full"
                />
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <button
                onClick={handleSync}
                disabled={syncing || !iseHost || !iseUsername || !isePassword}
                className="btn btn-primary"
              >
                {syncing ? '⏳ Connecting...' : '🔄 Connect to ISE'}
              </button>
              <button
                onClick={() => setShowIseConfig(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              Uses ISE ERS API: GET /ers/config/networkdevice (
              <a
                href="https://developer.cisco.com/docs/identity-services-engine/latest/ers-open-api-ers-open-api/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 dark:text-blue-400 underline"
              >
                API Docs
              </a>
              )
            </p>
          </div>
        )}

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <div className="text-2xl font-bold text-blue-700 dark:text-blue-400">
                {stats.total_devices}
              </div>
              <div className="text-xs text-blue-600 dark:text-blue-300">Total Devices</div>
            </div>
            <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <div className="text-2xl font-bold text-green-700 dark:text-green-400">
                {stats.by_status.success || 0}
              </div>
              <div className="text-xs text-green-600 dark:text-green-300">Discovered</div>
            </div>
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
              <div className="text-2xl font-bold text-yellow-700 dark:text-yellow-400">
                {stats.by_status.pending || 0}
              </div>
              <div className="text-xs text-yellow-600 dark:text-yellow-300">Pending</div>
            </div>
            <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
              <div className="text-2xl font-bold text-purple-700 dark:text-purple-400">
                {stats.needs_scan}
              </div>
              <div className="text-xs text-purple-600 dark:text-purple-300">Needs Scan</div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-4 mb-4">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="input text-sm"
          >
            <option value="all">All Status</option>
            <option value="pending">Pending</option>
            <option value="success">Discovered</option>
            <option value="failed">Failed</option>
          </select>

          <select
            value={filterPlatform}
            onChange={(e) => setFilterPlatform(e.target.value)}
            className="input text-sm"
          >
            <option value="all">All Platforms</option>
            {stats && Object.keys(stats.by_platform).map((platform) => (
              <option key={platform} value={platform}>
                {platform}
              </option>
            ))}
          </select>

          <button
            onClick={loadDevices}
            disabled={loading}
            className="btn btn-secondary text-sm"
          >
            {loading ? '⏳' : '🔄'} Refresh
          </button>
        </div>

        {error && (
          <div className="alert alert-error mb-4">
            <p>{error}</p>
          </div>
        )}
      </div>

      {/* Device Table */}
      <div className="card overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[1000px]">
          <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
            <tr>
              <th className="px-4 py-3 text-left font-semibold text-sm">Hostname</th>
              <th className="px-4 py-3 text-left font-semibold text-sm">IP Address</th>
              <th className="px-4 py-3 text-left font-semibold text-sm">Platform</th>
              <th className="px-4 py-3 text-left font-semibold text-sm">Version</th>
              <th className="px-4 py-3 text-left font-semibold text-sm">Hardware</th>
              <th className="px-4 py-3 text-left font-semibold text-sm">Status</th>
              <th className="px-4 py-3 text-left font-semibold text-sm">Last Scan</th>
              <th className="px-4 py-3 text-left font-semibold text-sm">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {loading ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                  Loading devices...
                </td>
              </tr>
            ) : devices.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-gray-500">
                  No devices found. Click "Sync from ISE" to import devices.
                </td>
              </tr>
            ) : (
              devices.map((device) => (
                <tr
                  key={device.id}
                  className="hover:bg-gray-50 dark:hover:bg-gray-800/50 border-b border-gray-100 dark:border-gray-800"
                >
                  <td className="px-4 py-4">
                    <div className="font-semibold text-gray-900 dark:text-gray-100">
                      {device.hostname}
                    </div>
                  </td>
                  <td className="px-4 py-4 font-mono text-sm">{device.ip_address}</td>
                  <td className="px-4 py-4 text-sm">
                    {device.platform || <span className="text-gray-400">—</span>}
                  </td>
                  <td className="px-4 py-4 font-mono text-sm">
                    {device.version || <span className="text-gray-400">—</span>}
                  </td>
                  <td className="px-4 py-4 text-sm">
                    {device.hardware_model || <span className="text-gray-400">—</span>}
                  </td>
                  <td className="px-4 py-4">
                    <span
                      className={`px-2 py-1 rounded-full text-sm font-medium ${getStatusBadge(
                        device.discovery_status
                      )}`}
                    >
                      {device.discovery_status}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    {(() => {
                      const summary = parseScanSummary(device.last_scan_result);
                      const formatted = formatScanSummary(summary);

                      if (!formatted) {
                        return <span className="text-sm text-gray-400">—</span>;
                      }

                      return (
                        <div>
                          <div className={`font-medium text-sm ${formatted.color}`}>
                            {formatted.text}
                          </div>
                          <div className="flex gap-2 mt-1">
                            <button
                              onClick={() => handleViewDetails(device)}
                              className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 underline"
                            >
                              Details
                            </button>
                            {device.previous_scan_id && (
                              <button
                                onClick={() => handleCompareToPrevious(device)}
                                className="text-sm text-purple-600 hover:text-purple-700 dark:text-purple-400 underline"
                              >
                                Compare
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })()}
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex gap-2">
                      {device.discovery_status === 'pending' && (
                        <button
                          onClick={() => handleDiscoverDevice(device)}
                          className="text-lg hover:scale-110 transition-transform"
                          title="Discover device via SSH"
                        >
                          🔍
                        </button>
                      )}
                      {device.discovery_status === 'success' && (
                        <>
                          <button
                            onClick={() => handleScanDevice(device)}
                            className="text-lg hover:scale-110 transition-transform"
                            title="Scan for known defects"
                          >
                            🛡️
                          </button>
                          <button
                            onClick={() => handleCompareVersions(device)}
                            className="text-lg hover:scale-110 transition-transform"
                            title="Compare versions"
                          >
                            📊
                          </button>
                          <button
                            onClick={() => handleDiscoverDevice(device)}
                            className="text-lg hover:scale-110 transition-transform"
                            title="Refresh device info"
                          >
                            🔄
                          </button>
                        </>
                      )}
                      {device.discovery_status === 'failed' && (
                        <button
                          onClick={() => handleDiscoverDevice(device)}
                          className="text-lg hover:scale-110 transition-transform"
                          title="Retry discovery"
                        >
                          ⚠️
                        </button>
                      )}
                      {/* Delete button - always visible */}
                      <button
                        onClick={() => handleDeleteDevice(device)}
                        className="text-lg hover:scale-110 transition-transform text-red-500 hover:text-red-700"
                        title="Delete device"
                      >
                        🗑️
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Details Modal */}
      {showDetailsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  Scan Results: {selectedDevice?.hostname}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {selectedDevice?.platform} {selectedDevice?.version} {selectedDevice?.hardware_model && `(${selectedDevice?.hardware_model})`}
                </p>
              </div>
              <button
                onClick={() => setShowDetailsModal(false)}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6">
              {loadingDetails ? (
                <div className="text-center py-8">
                  <div className="text-gray-600 dark:text-gray-400">Loading scan results...</div>
                </div>
              ) : selectedScanResult ? (
                <div className="space-y-4">
                  {/* Summary Stats */}
                  <div className="grid grid-cols-4 gap-4">
                    <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                      <div className="text-2xl font-bold text-blue-700 dark:text-blue-400">
                        {selectedScanResult.total_bugs}
                      </div>
                      <div className="text-xs text-blue-600 dark:text-blue-300">Total Known Defects</div>
                    </div>
                    <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                      <div className="text-2xl font-bold text-red-700 dark:text-red-400">
                        {selectedScanResult.critical_high}
                      </div>
                      <div className="text-xs text-red-600 dark:text-red-300">Critical/High</div>
                    </div>
                    <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                      <div className="text-2xl font-bold text-yellow-700 dark:text-yellow-400">
                        {selectedScanResult.medium_low}
                      </div>
                      <div className="text-xs text-yellow-600 dark:text-yellow-300">Medium/Low</div>
                    </div>
                    <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                      <div className="text-2xl font-bold text-green-700 dark:text-green-400">
                        {selectedScanResult.query_time_ms.toFixed(1)}ms
                      </div>
                      <div className="text-xs text-green-600 dark:text-green-300">Query Time</div>
                    </div>
                  </div>

                  {/* Bugs List */}
                  <div className="space-y-3">
                    <h4 className="font-semibold text-gray-900 dark:text-gray-100">
                      Known Defects ({selectedScanResult.bugs.length})
                    </h4>
                    {selectedScanResult.bugs.map((bug) => (
                      <details key={bug.bug_id} className="card">
                        <summary className="cursor-pointer p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className={`px-2 py-1 rounded text-xs font-medium ${getSeverityColor(bug.severity)}`}>
                                  {getSeverityLabel(bug.severity)}
                                </span>
                                <span className="font-mono text-xs text-gray-600 dark:text-gray-400">{bug.bug_id}</span>
                              </div>
                              <div className="mt-1 font-medium text-gray-900 dark:text-gray-100">{bug.headline}</div>
                            </div>
                          </div>
                        </summary>
                        <div className="px-4 pb-4 space-y-3 text-sm">
                          <div>
                            <div className="font-semibold text-gray-700 dark:text-gray-300">Summary:</div>
                            <div className="text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{cleanHtml(bug.summary)}</div>
                          </div>
                          {bug.affected_versions && (
                            <div>
                              <div className="font-semibold text-gray-700 dark:text-gray-300">Affected Versions:</div>
                              <div className="text-gray-600 dark:text-gray-400 font-mono text-xs">
                                {bug.affected_versions}
                              </div>
                            </div>
                          )}
                          {bug.labels && bug.labels.length > 0 && (
                            <div>
                              <div className="font-semibold text-gray-700 dark:text-gray-300">Features:</div>
                              <div className="flex flex-wrap gap-1 mt-1">
                                {bug.labels.map((label) => (
                                  <span key={label} className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400 rounded text-xs">
                                    {label}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </details>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">No scan results available</div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <button
                onClick={() => setShowDetailsModal(false)}
                className="btn btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Compare Modal */}
      {showCompareModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex justify-between items-center">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    Scan Comparison: {selectedDevice?.hostname}
                  </h3>
                  {comparisonResult && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                      {new Date(comparisonResult.previous_scan.timestamp).toLocaleString()} → {new Date(comparisonResult.current_scan.timestamp).toLocaleString()}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => setShowCompareModal(false)}
                  className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  ✕
                </button>
              </div>

              {/* Net Change Badge */}
              {comparisonResult && (
                <div className="mt-4">
                  <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${comparisonResult.summary.net_change < 0
                    ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                    : comparisonResult.summary.net_change > 0
                      ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                      : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400'
                    }`}>
                    {comparisonResult.summary.net_change > 0 && '+'}
                    {comparisonResult.summary.net_change} defects
                    {comparisonResult.summary.net_change < 0 && ' ✓'}
                    {comparisonResult.summary.net_change > 0 && ' ⚠️'}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6">
              {loadingComparison ? (
                <div className="text-center py-8">
                  <div className="text-gray-600 dark:text-gray-400">Loading comparison...</div>
                </div>
              ) : comparisonResult ? (
                <div className="space-y-6">
                  {/* Summary Cards */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border-2 border-green-200 dark:border-green-800">
                      <div className="text-3xl font-bold text-green-700 dark:text-green-400">
                        {comparisonResult.summary.total_fixed}
                      </div>
                      <div className="text-sm text-green-600 dark:text-green-300 mt-1">Fixed Defects ✓</div>
                      <div className="text-xs text-gray-600 dark:text-gray-400 mt-2">
                        Critical: {comparisonResult.summary.fixed_by_severity.Critical || 0} ·
                        High: {comparisonResult.summary.fixed_by_severity.High || 0}
                      </div>
                    </div>

                    <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border-2 border-red-200 dark:border-red-800">
                      <div className="text-3xl font-bold text-red-700 dark:text-red-400">
                        {comparisonResult.summary.total_new}
                      </div>
                      <div className="text-sm text-red-600 dark:text-red-300 mt-1">New Defects ⚠️</div>
                      <div className="text-xs text-gray-600 dark:text-gray-400 mt-2">
                        Critical: {comparisonResult.summary.new_by_severity.Critical || 0} ·
                        High: {comparisonResult.summary.new_by_severity.High || 0}
                      </div>
                    </div>

                    <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border-2 border-gray-200 dark:border-gray-600">
                      <div className="text-3xl font-bold text-gray-700 dark:text-gray-300">
                        {comparisonResult.summary.total_unchanged}
                      </div>
                      <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">Unchanged</div>
                      <div className="text-xs text-gray-500 dark:text-gray-500 mt-2">
                        Still present
                      </div>
                    </div>
                  </div>

                  {/* Tabbed View */}
                  <div>
                    <div className="border-b border-gray-200 dark:border-gray-700">
                      <nav className="-mb-px flex gap-6">
                        <button
                          onClick={() => setActiveCompareTab('new')}
                          className={`py-2 px-1 border-b-2 font-medium text-sm ${activeCompareTab === 'new'
                            ? 'border-red-500 text-red-600 dark:text-red-400'
                            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                            }`}
                        >
                          ⚠️ New Defects ({comparisonResult.summary.total_new})
                        </button>
                        <button
                          onClick={() => setActiveCompareTab('fixed')}
                          className={`py-2 px-1 border-b-2 font-medium text-sm ${activeCompareTab === 'fixed'
                            ? 'border-green-500 text-green-600 dark:text-green-400'
                            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                            }`}
                        >
                          ✓ Fixed Defects ({comparisonResult.summary.total_fixed})
                        </button>
                        <button
                          onClick={() => setActiveCompareTab('unchanged')}
                          className={`py-2 px-1 border-b-2 font-medium text-sm ${activeCompareTab === 'unchanged'
                            ? 'border-gray-500 text-gray-600 dark:text-gray-300'
                            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                            }`}
                        >
                          Unchanged ({comparisonResult.summary.total_unchanged})
                        </button>
                      </nav>
                    </div>

                    {/* Tab Content */}
                    <div className="mt-4 space-y-3">
                      {activeCompareTab === 'new' && comparisonResult.new_bugs.map((bug) => (
                        <details key={bug.bug_id} className="card border-l-4 border-red-500">
                          <summary className="cursor-pointer p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className={`px-2 py-1 rounded text-xs font-medium ${getSeverityColor(bug.severity)}`}>
                                    {getSeverityLabel(bug.severity)}
                                  </span>
                                  <span className="font-mono text-xs text-gray-600 dark:text-gray-400">{bug.bug_id}</span>
                                  <span className="text-xs px-2 py-1 bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400 rounded">NEW</span>
                                </div>
                                <div className="mt-1 font-medium text-gray-900 dark:text-gray-100">{bug.headline}</div>
                              </div>
                            </div>
                          </summary>
                          <div className="px-4 pb-4 space-y-3 text-sm">
                            <div>
                              <div className="font-semibold text-gray-700 dark:text-gray-300">Summary:</div>
                              <div className="text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{cleanHtml(bug.summary)}</div>
                            </div>
                            {bug.affected_versions && (
                              <div>
                                <div className="font-semibold text-gray-700 dark:text-gray-300">Affected Versions:</div>
                                <div className="text-gray-600 dark:text-gray-400 font-mono text-xs">
                                  {bug.affected_versions}
                                </div>
                              </div>
                            )}
                          </div>
                        </details>
                      ))}

                      {activeCompareTab === 'fixed' && comparisonResult.fixed_bugs.map((bug) => (
                        <details key={bug.bug_id} className="card border-l-4 border-green-500">
                          <summary className="cursor-pointer p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className={`px-2 py-1 rounded text-xs font-medium ${getSeverityColor(bug.severity)}`}>
                                    {getSeverityLabel(bug.severity)}
                                  </span>
                                  <span className="font-mono text-xs text-gray-600 dark:text-gray-400">{bug.bug_id}</span>
                                  <span className="text-xs px-2 py-1 bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 rounded">FIXED</span>
                                </div>
                                <div className="mt-1 font-medium text-gray-900 dark:text-gray-100">{bug.headline}</div>
                              </div>
                            </div>
                          </summary>
                          <div className="px-4 pb-4 space-y-3 text-sm">
                            <div>
                              <div className="font-semibold text-gray-700 dark:text-gray-300">Summary:</div>
                              <div className="text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{cleanHtml(bug.summary)}</div>
                            </div>
                          </div>
                        </details>
                      ))}

                      {activeCompareTab === 'unchanged' && comparisonResult.unchanged_bugs.map((bug) => (
                        <details key={bug.bug_id} className="card">
                          <summary className="cursor-pointer p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className={`px-2 py-1 rounded text-xs font-medium ${getSeverityColor(bug.severity)}`}>
                                    {getSeverityLabel(bug.severity)}
                                  </span>
                                  <span className="font-mono text-xs text-gray-600 dark:text-gray-400">{bug.bug_id}</span>
                                </div>
                                <div className="mt-1 font-medium text-gray-900 dark:text-gray-100">{bug.headline}</div>
                              </div>
                            </div>
                          </summary>
                          <div className="px-4 pb-4 space-y-3 text-sm">
                            <div>
                              <div className="font-semibold text-gray-700 dark:text-gray-300">Summary:</div>
                              <div className="text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{cleanHtml(bug.summary)}</div>
                            </div>
                            {bug.affected_versions && (
                              <div>
                                <div className="font-semibold text-gray-700 dark:text-gray-300">Affected Versions:</div>
                                <div className="text-gray-600 dark:text-gray-400 font-mono text-xs">
                                  {bug.affected_versions}
                                </div>
                              </div>
                            )}
                          </div>
                        </details>
                      ))}

                      {/* Empty state for each tab */}
                      {activeCompareTab === 'new' && comparisonResult.new_bugs.length === 0 && (
                        <div className="text-center py-8 text-gray-500">
                          <div className="text-4xl mb-2">✓</div>
                          <div>No new defects</div>
                        </div>
                      )}
                      {activeCompareTab === 'fixed' && comparisonResult.fixed_bugs.length === 0 && (
                        <div className="text-center py-8 text-gray-500">
                          <div className="text-4xl mb-2">—</div>
                          <div>No defects were fixed</div>
                        </div>
                      )}
                      {activeCompareTab === 'unchanged' && comparisonResult.unchanged_bugs.length === 0 && (
                        <div className="text-center py-8 text-gray-500">
                          <div className="text-4xl mb-2">∅</div>
                          <div>No unchanged defects</div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">No comparison data available</div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <button
                onClick={() => setShowCompareModal(false)}
                className="btn btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Version Comparison Modal */}
      {showVersionCompareModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex justify-between items-center">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    Version Comparison: {selectedDevice?.hostname}
                  </h3>
                  {versionComparisonResult && (
                    <div className="mt-1 space-y-1">
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {selectedDevice?.platform} - {versionComparisonResult.current_version_scan.version} → {versionComparisonResult.target_version_scan.version}
                      </p>
                      {selectedDevice?.features && JSON.parse(selectedDevice.features).length > 0 ? (
                        <p className="text-xs text-green-600 dark:text-green-400">
                          ✓ Feature filtering active ({JSON.parse(selectedDevice.features).length} features)
                        </p>
                      ) : (
                        <p className="text-xs text-yellow-600 dark:text-yellow-400">
                          ⚠️ No features detected - showing all defects (may include false positives)
                        </p>
                      )}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => setShowVersionCompareModal(false)}
                  className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6">
              {loadingVersionComparison ? (
                <div className="text-center py-8">
                  <div className="text-gray-600 dark:text-gray-400">Analyzing version comparison...</div>
                </div>
              ) : versionComparisonResult ? (
                <div className="space-y-6">
                  {/* Upgrade Recommendation Card */}
                  <div className={`p-6 rounded-lg border-2 ${versionComparisonResult.upgrade_recommendation.risk_level === 'LOW'
                    ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                    : versionComparisonResult.upgrade_recommendation.risk_level === 'MEDIUM'
                      ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
                      : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                    }`}>
                    <div className="flex items-start gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-3 py-1 rounded-full text-sm font-bold ${versionComparisonResult.upgrade_recommendation.risk_level === 'LOW'
                            ? 'bg-green-100 text-green-800 dark:bg-green-800 dark:text-green-100'
                            : versionComparisonResult.upgrade_recommendation.risk_level === 'MEDIUM'
                              ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-800 dark:text-yellow-100'
                              : 'bg-red-100 text-red-800 dark:bg-red-800 dark:text-red-100'
                            }`}>
                            {versionComparisonResult.upgrade_recommendation.risk_level} RISK
                          </span>
                          <span className="text-sm text-gray-600 dark:text-gray-400">
                            Risk Score: {versionComparisonResult.upgrade_recommendation.risk_score}
                          </span>
                        </div>
                        <p className="text-gray-900 dark:text-gray-100 font-medium">
                          {versionComparisonResult.upgrade_recommendation.recommendation}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Summary Cards */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border-2 border-green-200 dark:border-green-800">
                      <div className="text-3xl font-bold text-green-700 dark:text-green-400">
                        {versionComparisonResult.summary.total_fixed}
                      </div>
                      <div className="text-sm text-green-600 dark:text-green-300 mt-1">Fixed in Upgrade ✓</div>
                      <div className="text-xs text-gray-600 dark:text-gray-400 mt-2">
                        Critical: {versionComparisonResult.summary.fixed_by_severity.Critical || 0} ·
                        High: {versionComparisonResult.summary.fixed_by_severity.High || 0}
                      </div>
                    </div>

                    <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border-2 border-red-200 dark:border-red-800">
                      <div className="text-3xl font-bold text-red-700 dark:text-red-400">
                        {versionComparisonResult.summary.total_new}
                      </div>
                      <div className="text-sm text-red-600 dark:text-red-300 mt-1">New in Upgrade ⚠️</div>
                      <div className="text-xs text-gray-600 dark:text-gray-400 mt-2">
                        Critical: {versionComparisonResult.summary.new_by_severity.Critical || 0} ·
                        High: {versionComparisonResult.summary.new_by_severity.High || 0}
                      </div>
                    </div>

                    <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border-2 border-gray-200 dark:border-gray-600">
                      <div className="text-3xl font-bold text-gray-700 dark:text-gray-300">
                        {versionComparisonResult.summary.total_unchanged}
                      </div>
                      <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">Still Present</div>
                      <div className="text-xs text-gray-500 dark:text-gray-500 mt-2">
                        Net change: {versionComparisonResult.summary.net_change > 0 ? '+' : ''}{versionComparisonResult.summary.net_change}
                      </div>
                    </div>
                  </div>

                  {/* Tabbed View */}
                  <div>
                    <div className="border-b border-gray-200 dark:border-gray-700">
                      <nav className="-mb-px flex gap-6">
                        <button
                          onClick={() => setActiveVersionTab('new')}
                          className={`py-2 px-1 border-b-2 font-medium text-sm ${activeVersionTab === 'new'
                            ? 'border-red-500 text-red-600 dark:text-red-400'
                            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                            }`}
                        >
                          ⚠️ New in Upgrade ({versionComparisonResult.summary.total_new})
                        </button>
                        <button
                          onClick={() => setActiveVersionTab('fixed')}
                          className={`py-2 px-1 border-b-2 font-medium text-sm ${activeVersionTab === 'fixed'
                            ? 'border-green-500 text-green-600 dark:text-green-400'
                            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                            }`}
                        >
                          ✓ Fixed in Upgrade ({versionComparisonResult.summary.total_fixed})
                        </button>
                        <button
                          onClick={() => setActiveVersionTab('unchanged')}
                          className={`py-2 px-1 border-b-2 font-medium text-sm ${activeVersionTab === 'unchanged'
                            ? 'border-gray-500 text-gray-600 dark:text-gray-300'
                            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                            }`}
                        >
                          Still Present ({versionComparisonResult.summary.total_unchanged})
                        </button>
                      </nav>
                    </div>

                    {/* Tab Content */}
                    <div className="mt-4 space-y-3">
                      {activeVersionTab === 'new' && versionComparisonResult.new_in_upgrade.map((bug) => (
                        <details key={bug.bug_id} className="card border-l-4 border-red-500">
                          <summary className="cursor-pointer p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className={`px-2 py-1 rounded text-xs font-medium ${getSeverityColor(bug.severity)}`}>
                                    {getSeverityLabel(bug.severity)}
                                  </span>
                                  <span className="font-mono text-xs text-gray-600 dark:text-gray-400">{bug.bug_id}</span>
                                  <span className="text-xs px-2 py-1 bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400 rounded">NEW IN {targetVersion}</span>
                                </div>
                                <div className="mt-1 font-medium text-gray-900 dark:text-gray-100">{cleanHtml(bug.headline)}</div>
                              </div>
                            </div>
                          </summary>
                          <div className="px-4 pb-4 space-y-3 text-sm">
                            <div>
                              <div className="font-semibold text-gray-700 dark:text-gray-300">Summary:</div>
                              <div className="text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{cleanHtml(bug.summary)}</div>
                            </div>
                            {bug.affected_versions && (
                              <div>
                                <div className="font-semibold text-gray-700 dark:text-gray-300">Affected versions:</div>
                                <div className="text-gray-600 dark:text-gray-400 font-mono text-xs">
                                  {bug.affected_versions}
                                </div>
                              </div>
                            )}
                          </div>
                        </details>
                      ))}

                      {activeVersionTab === 'fixed' && versionComparisonResult.fixed_in_upgrade.map((bug) => (
                        <details key={bug.bug_id} className="card border-l-4 border-green-500">
                          <summary className="cursor-pointer p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className={`px-2 py-1 rounded text-xs font-medium ${getSeverityColor(bug.severity)}`}>
                                    {getSeverityLabel(bug.severity)}
                                  </span>
                                  <span className="font-mono text-xs text-gray-600 dark:text-gray-400">{bug.bug_id}</span>
                                  <span className="text-xs px-2 py-1 bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 rounded">FIXED BY {targetVersion}</span>
                                </div>
                                <div className="mt-1 font-medium text-gray-900 dark:text-gray-100">{cleanHtml(bug.headline)}</div>
                              </div>
                            </div>
                          </summary>
                          <div className="px-4 pb-4 space-y-3 text-sm">
                            <div>
                              <div className="font-semibold text-gray-700 dark:text-gray-300">Summary:</div>
                              <div className="text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{cleanHtml(bug.summary)}</div>
                            </div>
                          </div>
                        </details>
                      ))}

                      {activeVersionTab === 'unchanged' && versionComparisonResult.still_present.map((bug) => (
                        <details key={bug.bug_id} className="card">
                          <summary className="cursor-pointer p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <span className={`px-2 py-1 rounded text-xs font-medium ${getSeverityColor(bug.severity)}`}>
                                    {getSeverityLabel(bug.severity)}
                                  </span>
                                  <span className="font-mono text-xs text-gray-600 dark:text-gray-400">{bug.bug_id}</span>
                                </div>
                                <div className="mt-1 font-medium text-gray-900 dark:text-gray-100">{cleanHtml(bug.headline)}</div>
                              </div>
                            </div>
                          </summary>
                          <div className="px-4 pb-4 space-y-3 text-sm">
                            <div>
                              <div className="font-semibold text-gray-700 dark:text-gray-300">Summary:</div>
                              <div className="text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{cleanHtml(bug.summary)}</div>
                            </div>
                            {bug.affected_versions && (
                              <div>
                                <div className="font-semibold text-gray-700 dark:text-gray-300">Affected versions:</div>
                                <div className="text-gray-600 dark:text-gray-400 font-mono text-xs">
                                  {bug.affected_versions}
                                </div>
                              </div>
                            )}
                          </div>
                        </details>
                      ))}

                      {/* Empty state for each tab */}
                      {activeVersionTab === 'new' && versionComparisonResult.new_in_upgrade.length === 0 && (
                        <div className="text-center py-8 text-gray-500">
                          <div className="text-4xl mb-2">✓</div>
                          <div>No new defects in target version</div>
                        </div>
                      )}
                      {activeVersionTab === 'fixed' && versionComparisonResult.fixed_in_upgrade.length === 0 && (
                        <div className="text-center py-8 text-gray-500">
                          <div className="text-4xl mb-2">—</div>
                          <div>No defects fixed by this upgrade</div>
                        </div>
                      )}
                      {activeVersionTab === 'unchanged' && versionComparisonResult.still_present.length === 0 && (
                        <div className="text-center py-8 text-gray-500">
                          <div className="text-4xl mb-2">∅</div>
                          <div>No defects remain in both versions</div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">No comparison data available</div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
              <button
                onClick={() => setShowVersionCompareModal(false)}
                className="btn btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SSH Credentials Modal */}
      <SSHCredentialsModal
        isOpen={credentialsModal.isOpen}
        onClose={() => setCredentialsModal({ ...credentialsModal, isOpen: false })}
        onSubmit={handleCredentialsSubmit}
        deviceName={credentialsModal.deviceName}
        action={credentialsModal.action}
      />

      {/* Add Device Modal */}
      {showAddDeviceModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-lg">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Add Device to Inventory
              </h3>
              <button
                onClick={() => {
                  setShowAddDeviceModal(false);
                  setNewDevice({ hostname: '', ip_address: '', platform: '', version: '', hardware_model: '', location: '' });
                }}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-white text-2xl"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              {/* Required Fields */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                    Hostname <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={newDevice.hostname}
                    onChange={(e) => setNewDevice({ ...newDevice, hostname: e.target.value })}
                    placeholder="core-sw-01"
                    className="w-full px-3 py-2 bg-white dark:bg-gray-700 rounded border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                    IP Address <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={newDevice.ip_address}
                    onChange={(e) => setNewDevice({ ...newDevice, ip_address: e.target.value })}
                    placeholder="10.1.1.1"
                    className="w-full px-3 py-2 bg-white dark:bg-gray-700 rounded border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white"
                  />
                </div>
              </div>

              {/* Optional Fields */}
              <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                  Optional: Provide these now or use SSH Discovery later
                </p>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                      Platform
                    </label>
                    <select
                      value={newDevice.platform}
                      onChange={(e) => setNewDevice({ ...newDevice, platform: e.target.value })}
                      className="w-full px-3 py-2 bg-white dark:bg-gray-700 rounded border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white"
                    >
                      <option value="">-- Select --</option>
                      <option value="IOS-XE">IOS-XE</option>
                      <option value="IOS-XR">IOS-XR</option>
                      <option value="ASA">ASA</option>
                      <option value="FTD">FTD</option>
                      <option value="NX-OS">NX-OS</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                      Version
                    </label>
                    <input
                      type="text"
                      value={newDevice.version}
                      onChange={(e) => setNewDevice({ ...newDevice, version: e.target.value })}
                      placeholder="17.9.4"
                      className="w-full px-3 py-2 bg-white dark:bg-gray-700 rounded border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                      Hardware Model
                    </label>
                    <input
                      type="text"
                      value={newDevice.hardware_model}
                      onChange={(e) => setNewDevice({ ...newDevice, hardware_model: e.target.value })}
                      placeholder="Cat9300"
                      className="w-full px-3 py-2 bg-white dark:bg-gray-700 rounded border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">
                      Location
                    </label>
                    <input
                      type="text"
                      value={newDevice.location}
                      onChange={(e) => setNewDevice({ ...newDevice, location: e.target.value })}
                      placeholder="DC1-Rack-A1"
                      className="w-full px-3 py-2 bg-white dark:bg-gray-700 rounded border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white"
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <button
                  onClick={() => {
                    setShowAddDeviceModal(false);
                    setNewDevice({ hostname: '', ip_address: '', platform: '', version: '', hardware_model: '', location: '' });
                  }}
                  className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddDevice}
                  disabled={!newDevice.hostname.trim() || !newDevice.ip_address.trim() || addingDevice}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed rounded text-white font-medium"
                >
                  {addingDevice ? 'Adding...' : 'Add Device'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Import CSV Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-lg">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Import Devices from CSV
              </h3>
              <button
                onClick={() => {
                  setShowImportModal(false);
                  setImportResult(null);
                }}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-white text-2xl"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              {/* Template Download */}
              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                <p className="text-sm text-blue-800 dark:text-blue-200 mb-2">
                  Download the CSV template to see the required format:
                </p>
                <button
                  onClick={handleDownloadTemplate}
                  className="text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-2 text-sm font-medium"
                >
                  <span>📄</span> Download Template (device_import_template.csv)
                </button>
              </div>

              {/* File Upload */}
              <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center">
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      handleImportCSV(file);
                    }
                  }}
                  className="hidden"
                  id="csv-file-input"
                  disabled={importing}
                />
                <label
                  htmlFor="csv-file-input"
                  className={`cursor-pointer ${importing ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <div className="text-4xl mb-2">📁</div>
                  <p className="text-gray-700 dark:text-gray-300 font-medium">
                    {importing ? 'Importing...' : 'Click to select CSV file'}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    or drag and drop your file here
                  </p>
                </label>
              </div>

              {/* Import Results */}
              {importResult && (
                <div className={`p-4 rounded-lg ${importResult.success
                  ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                  : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
                }`}>
                  <h4 className={`font-semibold mb-2 ${importResult.success
                    ? 'text-green-800 dark:text-green-200'
                    : 'text-red-800 dark:text-red-200'
                  }`}>
                    {importResult.success ? '✓ Import Complete' : '✗ Import Failed'}
                  </h4>

                  {importResult.success && (
                    <div className="grid grid-cols-3 gap-4 text-center mb-3">
                      <div>
                        <div className="text-2xl font-bold text-green-700 dark:text-green-400">
                          {importResult.imported}
                        </div>
                        <div className="text-xs text-green-600 dark:text-green-300">Added</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold text-blue-700 dark:text-blue-400">
                          {importResult.updated}
                        </div>
                        <div className="text-xs text-blue-600 dark:text-blue-300">Updated</div>
                      </div>
                      <div>
                        <div className="text-2xl font-bold text-gray-700 dark:text-gray-400">
                          {importResult.skipped}
                        </div>
                        <div className="text-xs text-gray-600 dark:text-gray-300">Skipped</div>
                      </div>
                    </div>
                  )}

                  {importResult.errors.length > 0 && (
                    <div className="mt-2">
                      <p className="text-sm font-medium text-red-700 dark:text-red-300 mb-1">
                        Errors:
                      </p>
                      <ul className="text-sm text-red-600 dark:text-red-400 list-disc list-inside max-h-32 overflow-y-auto">
                        {importResult.errors.map((error, idx) => (
                          <li key={idx}>{error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Format Info */}
              <div className="text-sm text-gray-500 dark:text-gray-400">
                <p className="font-medium text-gray-700 dark:text-gray-300 mb-1">Required columns:</p>
                <p className="font-mono text-xs">hostname, ip_address</p>
                <p className="font-medium text-gray-700 dark:text-gray-300 mt-2 mb-1">Optional columns:</p>
                <p className="font-mono text-xs">platform, version, hardware_model, location</p>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  onClick={() => {
                    setShowImportModal(false);
                    setImportResult(null);
                  }}
                  className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Scan Progress Indicator */}
      {bulkScanJob?.status === 'running' && (
        <div className="fixed bottom-4 right-4 bg-white dark:bg-gray-800 rounded-lg shadow-lg p-4 w-80 border border-gray-200 dark:border-gray-700 z-50">
          <div className="flex justify-between items-center mb-2">
            <span className="font-medium text-gray-900 dark:text-white">Bulk Scan Progress</span>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {bulkScanJob.scanned}/{bulkScanJob.total}
            </span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mb-2">
            <div
              className="bg-purple-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${bulkScanJob.progress}%` }}
            />
          </div>
          {bulkScanJob.currentDevice && (
            <p className="text-sm text-gray-600 dark:text-gray-400 truncate">
              Scanning: {bulkScanJob.currentDevice}
            </p>
          )}
          {bulkScanJob.failed > 0 && (
            <p className="text-sm text-red-500 mt-1">
              {bulkScanJob.failed} failed
            </p>
          )}
        </div>
      )}
    </div>
  );
}
