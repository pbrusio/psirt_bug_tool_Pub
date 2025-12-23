"""
API routes for PSIRT analysis and device verification
"""
from fastapi import APIRouter, HTTPException, status
from .models import (
    AnalyzePSIRTRequest,
    AnalysisResult,
    VerifyDeviceRequest,
    VerifySnapshotRequest,
    VerificationResult,
    ErrorResponse,
    ScanDeviceRequest,
    ScanResult,
    ExtractFeaturesRequest,
    FeatureSnapshot
)
from ..core.sec8b import get_analyzer
from ..core.verifier import get_verifier
from ..core.vulnerability_scanner import VulnerabilityScanner
from ..db.cache import get_cache, save_analysis, get_analysis
import logging
import sqlite3
import traceback

logger = logging.getLogger(__name__)


def handle_db_error(e: Exception, operation: str) -> HTTPException:
    """Handle database errors with appropriate status codes"""
    error_msg = str(e).lower()

    # Database is locked/busy - return 503 (Service Unavailable)
    if isinstance(e, sqlite3.OperationalError):
        if 'locked' in error_msg or 'busy' in error_msg:
            logger.error(f"{operation} - DB locked: {e}\n{traceback.format_exc()}")
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database is busy, please retry in a moment"
            )
        else:
            logger.error(f"{operation} - DB error: {e}\n{traceback.format_exc()}")
            return HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )

    # General error - return 500
    logger.error(f"{operation} failed: {e}\n{traceback.format_exc()}")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{operation} failed: {str(e)}"
    )

router = APIRouter(prefix="/api/v1", tags=["PSIRT Analysis"])


@router.post("/analyze-psirt", response_model=AnalysisResult)
async def analyze_psirt(request: AnalyzePSIRTRequest):
    """
    Analyze PSIRT with SEC-8B

    **Process:**
    1. Receives PSIRT summary and platform
    2. Runs SEC-8B few-shot inference
    3. Predicts feature labels
    4. Maps labels to config patterns and show commands
    5. Returns analysis result with unique ID

    **Supported platforms:**
    - IOS-XE (70 labels)
    - IOS-XR (22 labels)
    - ASA (46 labels)
    - FTD (46 labels)
    - NX-OS (25 labels)
    """
    try:
        # Validate platform
        valid_platforms = ["IOS-XE", "IOS-XR", "ASA", "FTD", "NX-OS"]
        if request.platform not in valid_platforms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid platform. Must be one of: {', '.join(valid_platforms)}"
            )

        # Get analyzer
        analyzer = get_analyzer()

        # Run analysis
        logger.info(f"Analyzing PSIRT for platform: {request.platform}")
        result = analyzer.analyze_psirt(
            summary=request.summary,
            platform=request.platform,
            advisory_id=request.advisory_id
        )

        # Cache result
        await save_analysis(result)

        logger.info(f"Analysis complete: {result['analysis_id']}")
        return AnalysisResult(**result)

    except HTTPException:
        raise
    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "Analysis")
    except Exception as e:
        raise handle_db_error(e, "Analysis")


@router.post("/verify-device", response_model=VerificationResult)
async def verify_device(request: VerifyDeviceRequest):
    """
    Verify device against PSIRT

    **Process:**
    1. Retrieves analysis result by ID
    2. Connects to device via SSH
    3. Stage 1: Version matching (device version in affected range?)
    4. Stage 2: Feature detection (vulnerable features configured?)
    5. Determines overall status (VULNERABLE / NOT VULNERABLE)
    6. Returns detailed verification report

    **Requirements:**
    - Device must be reachable via SSH
    - Credentials must have privilege to run show commands
    - Analysis ID must exist from previous /analyze-psirt call
    """
    try:
        # Get cached analysis
        analysis = await get_analysis(request.analysis_id)
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis ID not found: {request.analysis_id}"
            )

        # Get verifier
        verifier = get_verifier()

        # Run verification
        logger.info(f"Verifying device {request.device.host} against analysis {request.analysis_id}")
        result = verifier.verify_device(
            analysis_id=request.analysis_id,
            device_config={
                'host': request.device.host,
                'username': request.device.username,
                'password': request.device.password,
                'device_type': request.device.device_type
            },
            psirt_metadata={
                'product_names': request.psirt_metadata.product_names,
                'bug_id': request.psirt_metadata.bug_id
            },
            predicted_labels=analysis['predicted_labels'],
            config_regex=analysis['config_regex'],
            show_commands=analysis['show_commands']
        )

        logger.info(f"Verification complete: {result['overall_status']}")
        return VerificationResult(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )


@router.post("/verify-snapshot", response_model=VerificationResult)
async def verify_snapshot(request: VerifySnapshotRequest):
    """
    Verify pre-extracted feature snapshot against PSIRT

    **Process:**
    1. Retrieves analysis result by ID
    2. Compares predicted labels against snapshot's features_present
    3. Determines which vulnerable features are present/absent
    4. Returns verification status (no SSH required)

    **Use Cases:**
    - Air-gapped networks (extract features, transfer snapshot out)
    - Batch analysis (extract once, analyze multiple PSIRTs)
    - Compliance audits (snapshot as evidence)
    - Quick checks (no SSH latency)

    **Requirements:**
    - Analysis ID must exist from previous /analyze-psirt call
    - Snapshot platform should match PSIRT platform (warning if mismatch)
    - Snapshot created with extract_device_features.py
    """
    try:
        # Get cached analysis
        analysis = await get_analysis(request.analysis_id)
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis ID not found: {request.analysis_id}"
            )

        # Validate platform match
        if request.snapshot.platform != analysis['platform']:
            logger.warning(
                f"Platform mismatch: snapshot={request.snapshot.platform}, "
                f"analysis={analysis['platform']}"
            )

        # Compare predicted labels against snapshot features
        predicted_labels = set(analysis['predicted_labels'])
        snapshot_features = set(request.snapshot.features_present)

        features_present = list(predicted_labels & snapshot_features)
        features_absent = list(predicted_labels - snapshot_features)

        # Determine overall status
        if features_present:
            overall_status = "POTENTIALLY VULNERABLE"
            reason = (
                f"Vulnerable features DETECTED in snapshot: {', '.join(features_present)}. "
                f"⚠️ Version verification recommended - device may be vulnerable if running "
                f"affected software version."
            )
        else:
            overall_status = "LIKELY NOT VULNERABLE"
            reason = (
                f"Required features NOT found in snapshot: {', '.join(features_absent)}. "
                f"Device appears safe based on configuration, but version verification "
                f"recommended for certainty."
            )

        from datetime import datetime
        result = {
            "verification_id": f"snapshot-verify-{request.snapshot.snapshot_id}",
            "analysis_id": request.analysis_id,
            "device_hostname": None,
            "device_version": None,
            "device_platform": request.snapshot.platform,
            "version_check": None,
            "feature_check": {
                "present": features_present,
                "absent": features_absent
            },
            "overall_status": overall_status,
            "reason": reason,
            "evidence": {
                "snapshot_id": request.snapshot.snapshot_id,
                "extracted_at": request.snapshot.extracted_at,
                "total_features_in_snapshot": str(request.snapshot.feature_count),
                "extractor_version": request.snapshot.extractor_version
            },
            "timestamp": datetime.now(),
            "error": None
        }

        logger.info(
            f"Snapshot verification complete: {result['overall_status']} "
            f"({len(features_present)} present, {len(features_absent)} absent)"
        )
        return VerificationResult(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Snapshot verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Snapshot verification failed: {str(e)}"
        )


@router.post("/scan-device", response_model=ScanResult)
async def scan_device(request: ScanDeviceRequest):
    """
    Scan device for vulnerabilities using database

    **Feature-Aware Scanning:**
    - Version-only mode: Returns all bugs affecting the device version
    - Feature-aware mode: Filters by configured features (40-80% reduction in false positives)

    **Process:**
    1. Query database for bugs affecting device platform + version
    2. If features provided, filter by feature label matching
    3. Group by severity (Critical/High vs Medium/Low)
    4. Return sorted results with statistics

    **Supported platforms:**
    - IOS-XE (729 labeled bugs)
    - IOS-XR (future)
    - ASA (future)
    - FTD (future)
    - NX-OS (future)

    **Performance:**
    - Query time: <10ms for typical scans
    - Database indexed by platform, version, and labels
    """
    try:
        # Validate platform
        valid_platforms = ["IOS-XE", "IOS-XR", "ASA", "FTD", "NX-OS"]
        if request.platform not in valid_platforms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid platform. Must be one of: {', '.join(valid_platforms)}"
            )

        # Initialize scanner
        scanner = VulnerabilityScanner(db_path="vulnerability_db.sqlite")

        # Run scan
        logger.info(
            f"Scanning device: platform={request.platform}, version={request.version}, "
            f"hardware_model={request.hardware_model}, "
            f"features={len(request.features) if request.features else 0}"
        )

        result = scanner.scan_device(
            platform=request.platform,
            version=request.version,
            labels=request.features,
            hardware_model=request.hardware_model,
            severity_filter=request.severity_filter,
            limit=request.limit,
            offset=request.offset
        )

        logger.info(
            f"Scan complete: scan_id={result['scan_id']}, "
            f"version_matches={result['version_matches']}, "
            f"final_matches={len(result['bugs'])}"
        )

        return ScanResult(**result)

    except HTTPException:
        raise
    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "Scan")
    except Exception as e:
        raise handle_db_error(e, "Scan")


@router.get("/results/{analysis_id}")
async def get_results(analysis_id: str):
    """
    Get analysis results by ID

    Returns the cached analysis result including:
    - Predicted labels
    - Config patterns
    - Show commands
    - Timestamp
    """
    analysis = await get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis ID not found: {analysis_id}"
        )
    return analysis


@router.post("/extract-features", response_model=FeatureSnapshot)
async def extract_features(request: ExtractFeaturesRequest):
    """
    Extract features from live device via SSH

    **Process:**
    1. Connects to device via SSH (using Netmiko)
    2. Auto-detects platform if not specified
    3. Downloads running configuration
    4. Extracts feature labels using taxonomy YAMLs
    5. Returns sanitized snapshot (NO sensitive data)

    **Use Cases:**
    - Quick feature extraction for vulnerability scanning
    - Air-gapped workflow (extract once, transfer snapshot)
    - Batch analysis preparation

    **Supported Platforms:**
    - IOS-XE, IOS-XR, ASA, FTD, NX-OS

    **Note:** Requires SSH access to device
    """
    try:
        logger.info(f"Extracting features from device {request.device.host}")

        # Import feature extraction module
        import sys
        from pathlib import Path

        # Add parent directory to path to import extract_device_features
        parent_dir = Path(__file__).parent.parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))

        from extract_device_features import extract_from_live_device

        # Extract features
        snapshot = extract_from_live_device(
            host=request.device.host,
            username=request.device.username,
            password=request.device.password,
            platform=request.platform,
            device_type=request.device.device_type or 'cisco_ios',
            features_dir=str(parent_dir)
        )

        logger.info(f"Feature extraction complete: {snapshot['feature_count']} features detected")
        return FeatureSnapshot(**snapshot)

    except Exception as e:
        logger.error(f"Feature extraction failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Feature extraction failed: {str(e)}"
        )


@router.post("/export/csv")
async def export_csv(scan_result: ScanResult):
    """
    Export scan results to CSV

    **Process:**
    1. Accepts ScanResult from frontend
    2. Generates CSV with all vulnerability details
    3. Returns CSV file for download

    **Use Cases:**
    - Excel/spreadsheet analysis
    - Archival/compliance
    - Integration with other tools

    **Format:**
    - Headers: Bug ID, Severity, Headline, Summary, Status, Affected Versions, Labels, URL
    - One row per vulnerability
    - HTML tags cleaned from summaries
    """
    from fastapi.responses import Response
    from .export import generate_csv

    try:
        logger.info(f"Exporting scan {scan_result.scan_id} to CSV")

        # Convert ScanResult to dict
        scan_dict = scan_result.model_dump()

        # Generate CSV
        csv_content = generate_csv(scan_dict)

        # Return as downloadable file
        filename = f"vuln_scan_{scan_result.platform}_{scan_result.version}_{scan_result.scan_id}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"CSV export failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CSV export failed: {str(e)}"
        )


@router.post("/export/pdf")
async def export_pdf(scan_result: ScanResult):
    """
    Export scan results to PDF

    **Process:**
    1. Accepts ScanResult from frontend
    2. Generates professional PDF report
    3. Returns PDF file for download

    **Use Cases:**
    - Executive summaries
    - Management reporting
    - Audit documentation

    **Format:**
    - Title page with scan summary
    - Vulnerability table (first 50 entries)
    - Clean formatting with severity colors
    - Generated timestamp and branding

    **Note:** Requires reportlab library (pip install reportlab)
    """
    from fastapi.responses import Response
    from .export import generate_pdf

    try:
        logger.info(f"Exporting scan {scan_result.scan_id} to PDF")

        # Convert ScanResult to dict
        scan_dict = scan_result.model_dump()

        # Generate PDF
        pdf_bytes = generate_pdf(scan_dict)

        # Return as downloadable file
        filename = f"vuln_scan_{scan_result.platform}_{scan_result.version}_{scan_result.scan_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except RuntimeError as e:
        logger.error(f"PDF export failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"PDF export failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF export failed: {str(e)}"
        )


@router.post("/export/json")
async def export_json(scan_result: ScanResult):
    """
    Export scan results to JSON

    **Process:**
    1. Accepts ScanResult from frontend
    2. Cleans and formats for JSON
    3. Returns JSON file for download

    **Use Cases:**
    - Automation/scripting
    - Integration with SIEM/ticketing systems
    - Machine-readable archival

    **Format:**
    - Standard JSON with cleaned HTML
    - ISO 8601 timestamps
    - Full vulnerability details
    """
    from fastapi.responses import JSONResponse
    from .export import generate_json

    try:
        logger.info(f"Exporting scan {scan_result.scan_id} to JSON")

        # Convert ScanResult to dict
        scan_dict = scan_result.model_dump()

        # Generate cleaned JSON
        json_data = generate_json(scan_dict)

        # Return as downloadable file
        filename = f"vuln_scan_{scan_result.platform}_{scan_result.version}_{scan_result.scan_id}.json"
        return JSONResponse(
            content=json_data,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"JSON export failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"JSON export failed: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint

    Returns:
        {"status": "healthy", "message": "API is running"}
    """
    return {
        "status": "healthy",
        "message": "PSIRT Analysis API is running"
    }


@router.get("/health/db")
async def db_health_check():
    """
    Database health check endpoint

    Verifies database connectivity and returns status:
    - Runs SELECT 1 query via SafeSQLiteConnection
    - Reports journal_mode, busy_timeout, table count
    - Measures query latency

    Returns:
        {
            "status": "healthy|unhealthy",
            "db_path": "vulnerability_db.sqlite",
            "journal_mode": "wal",
            "busy_timeout_ms": 5000,
            "tables": [...],
            "latency_ms": 0.5
        }
    """
    try:
        from ..db.utils import check_db_health
        import time

        start_time = time.time()
        health_result = check_db_health("vulnerability_db.sqlite")
        latency_ms = (time.time() - start_time) * 1000

        return {
            **health_result,
            "latency_ms": round(latency_ms, 2)
        }

    except sqlite3.OperationalError as e:
        raise handle_db_error(e, "DB health check")
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database health check failed: {str(e)}"
        )
