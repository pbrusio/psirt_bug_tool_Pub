"""
Pydantic models for API request/response schemas
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict
from datetime import datetime
import re
import ipaddress


# FQDN pattern (hostname with optional domain)
FQDN_PATTERN = re.compile(
    r'^(?=.{1,253}$)(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(?:\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))*$'
)


def is_valid_ip(host: str) -> bool:
    """Check if host is a valid IPv4 or IPv6 address using Python's ipaddress module"""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


# Request Models

class AnalyzePSIRTRequest(BaseModel):
    """Request to analyze a PSIRT with SEC-8B"""
    summary: str = Field(..., description="PSIRT summary text", min_length=1, max_length=10000)
    platform: str = Field(..., description="Platform (IOS-XE, ASA, FTD, IOS-XR, NX-OS)")
    advisory_id: Optional[str] = Field(None, description="Optional advisory ID")


class DeviceCredentials(BaseModel):
    """Device SSH credentials with validated host"""
    host: str = Field(..., description="Device IP or hostname")
    username: str = Field(..., description="SSH username")
    password: str = Field(..., description="SSH password")
    device_type: str = Field(default="cisco_ios", description="Netmiko device type")

    @field_validator('host')
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host is a valid IP address or FQDN"""
        v = v.strip()

        if not v:
            raise ValueError('Host cannot be empty')

        # If it looks like an IP address (digits and dots only), validate as IP
        # This prevents invalid IPs like 192.168.1.256 from matching FQDN pattern
        if re.match(r'^[\d.]+$', v) or ':' in v:
            if is_valid_ip(v):
                return v
            raise ValueError(
                f'Invalid IP address: {v}. '
                'Check that all octets are between 0-255.'
            )

        # Check if it's a valid FQDN/hostname
        if FQDN_PATTERN.match(v):
            return v

        raise ValueError(
            f'Invalid host format: {v}. '
            'Must be a valid IPv4 address, IPv6 address, or FQDN/hostname.'
        )


class PSIRTMetadata(BaseModel):
    """PSIRT metadata for device verification"""
    product_names: List[str] = Field(default_factory=list, description="Affected product names")
    bug_id: Optional[str] = Field(None, description="PSIRT bug ID")


class FeatureSnapshot(BaseModel):
    """Pre-extracted feature snapshot from extract_device_features.py"""
    snapshot_id: str = Field(..., description="Snapshot ID")
    platform: str = Field(..., description="Device platform")
    extracted_at: str = Field(..., description="Extraction timestamp")
    features_present: List[str] = Field(..., description="List of detected feature labels")
    feature_count: int = Field(..., description="Number of features detected")
    total_checked: int = Field(..., description="Total features checked")
    extractor_version: str = Field(default="1.0.0", description="Extractor version")
    version: Optional[str] = Field(None, description="Device software version")
    hardware_model: Optional[str] = Field(None, description="Auto-detected hardware model (e.g., Cat9200, ASR9K)")


class VerifyDeviceRequest(BaseModel):
    """Request to verify device against PSIRT"""
    analysis_id: str = Field(..., description="Analysis ID from previous analyze call")
    device: DeviceCredentials
    psirt_metadata: PSIRTMetadata


class VerifySnapshotRequest(BaseModel):
    """Request to verify pre-extracted feature snapshot against PSIRT"""
    analysis_id: str = Field(..., description="Analysis ID from previous analyze call")
    snapshot: FeatureSnapshot = Field(..., description="Pre-extracted feature snapshot")
    psirt_metadata: Optional[PSIRTMetadata] = Field(None, description="Optional PSIRT metadata for version checking")


# Response Models

class AnalysisResult(BaseModel):
    """SEC-8B analysis result"""
    analysis_id: str
    psirt_summary: str
    platform: str
    advisory_id: Optional[str] = None
    predicted_labels: List[str]
    confidence: float
    config_regex: List[str]
    show_commands: List[str]
    source: str = Field(
        default="llm",
        description="'database' if from cache, 'llm' if from SEC-8B inference"
    )
    cached: bool = Field(
        default=False,
        description="True if LLM result was cached in database"
    )
    needs_review: bool = Field(
        default=False,
        description="True if confidence < 0.70 threshold, requires human review"
    )
    confidence_source: str = Field(
        default="model",
        description="Source of confidence: 'model' (high conf), 'heuristic' (low conf), 'cache' (from DB)"
    )
    timestamp: datetime


class VersionCheck(BaseModel):
    """Version matching result"""
    affected: bool
    reason: str
    matched_versions: List[str] = Field(default_factory=list)


class FeatureCheck(BaseModel):
    """Feature detection result"""
    present: List[str]
    absent: List[str]


class VerificationResult(BaseModel):
    """Device verification result"""
    verification_id: str
    analysis_id: str
    device_hostname: Optional[str] = None
    device_version: Optional[str] = None
    device_platform: Optional[str] = None
    version_check: Optional[VersionCheck] = None
    feature_check: Optional[FeatureCheck] = None
    overall_status: str  # "VULNERABLE" | "NOT VULNERABLE" | "ERROR"
    reason: str
    evidence: Dict[str, str] = Field(default_factory=dict)
    timestamp: datetime
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None


# NEW: Scanner API Models

class ScanDeviceRequest(BaseModel):
    """Request to scan device for bugs using database"""
    platform: str = Field(..., description="Device platform (IOS-XE, IOS-XR, ASA, FTD, NX-OS)")
    version: str = Field(..., description="Device software version (e.g., '17.3.5')")
    hardware_model: Optional[str] = Field(
        None,
        description="Optional hardware model for filtering (e.g., 'Cat9200', 'ASR9K') - NEW: 40-60% false positive reduction"
    )
    features: Optional[List[str]] = Field(
        None,
        description="Optional list of configured feature labels for filtering (e.g., ['MGMT_SSH_HTTP', 'SEC_CoPP'])"
    )
    severity_filter: Optional[List[int]] = Field(
        None,
        description="Optional severity filter (e.g., [1, 2] for Critical/High only)"
    )
    limit: Optional[int] = Field(None, description="Max results to return (pagination)")
    offset: int = Field(default=0, description="Pagination offset")


class BugFull(BaseModel):
    """Full bug details (Critical/High severity) - from Cisco Bug Search Tool"""
    bug_id: str
    advisory_id: str
    severity: int
    cvss_score: float
    cves: List[str]
    summary: str
    matched_labels: List[str]
    product_names: List[str]
    fixed_versions: List[str]
    config_regex: List[str]
    show_commands: List[str]
    unlabeled: bool = Field(
        default=False,
        description="True if no feature labels available (version match only)"
    )
    confidence: float = Field(
        default=0.0,
        description="LLM confidence score (0.0 if not from LLM)"
    )


class BugCollapsed(BaseModel):
    """Collapsed bug details (Medium/Low severity) - from Cisco Bug Search Tool"""
    bug_id: str
    advisory_id: str
    severity: int
    cvss_score: float
    summary: str


class DeviceInfo(BaseModel):
    """Device information from scan request"""
    platform: str
    version: str
    labels: List[str]


class PaginationInfo(BaseModel):
    """Pagination metadata"""
    limit: Optional[int]
    offset: int
    has_more: bool


class Bug(BaseModel):
    """Individual bug details from Cisco Bug Search Tool (CSCxxxx IDs)"""
    bug_id: str
    severity: int
    headline: str
    summary: Optional[str] = None
    status: str
    affected_versions: str
    labels: List[str]
    url: Optional[str] = None


class ScanResult(BaseModel):
    """Bug scan result - shows bugs you may be susceptible to"""
    scan_id: str
    platform: str
    version: str
    hardware_model: Optional[str] = None
    features: Optional[List[str]] = None
    total_bugs_checked: int
    version_matches: int
    hardware_filtered: Optional[int] = None
    hardware_filtered_count: int = Field(default=0, description="Number of bugs filtered out by hardware model")
    feature_filtered: Optional[int] = None
    critical_high: int
    medium_low: int
    # Separated bug/PSIRT counts (v3.1+)
    bug_count: Optional[int] = Field(default=None, description="Count of bugs (vuln_type='bug')")
    psirt_count: Optional[int] = Field(default=None, description="Count of PSIRTs (vuln_type='psirt')")
    bug_critical_high: Optional[int] = Field(default=None, description="Critical+High bugs")
    psirt_critical_high: Optional[int] = Field(default=None, description="Critical+High PSIRTs")
    bugs: List[Bug]
    filtered_bugs: Optional[List[Bug]] = None
    timestamp: datetime
    query_time_ms: float


# Feature Extraction Types

class ExtractFeaturesRequest(BaseModel):
    """Request to extract features from live device"""
    device: DeviceCredentials
    platform: Optional[str] = Field(None, description="Platform override (auto-detect if not specified)")
