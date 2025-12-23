"""
System Administration API Routes
================================
Provides endpoints for:
- Offline bug database update packages
- Database statistics and health
- Cache management
- System information
"""

import os
import json
import sqlite3
import shutil
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, status
from pydantic import BaseModel

from ..core.updater import OfflineUpdater, UpdateResult, ValidationResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["System Administration"])

# Default database path
DB_PATH = "vulnerability_db.sqlite"


# =============================================================================
# Response Models
# =============================================================================

class UpdateResponse(BaseModel):
    """Response model for update operations."""
    success: bool
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    total_processed: int = 0
    error_message: Optional[str] = None
    package_name: str = ""
    hash_verified: bool = False
    manifest: Optional[Dict] = None
    timestamp: str = ""


class ValidationResponse(BaseModel):
    """Response model for validation operations."""
    valid: bool
    error: Optional[str] = None
    item_count: int = 0
    hash_verified: bool = False
    hash_message: str = ""
    manifest: Optional[Dict] = None


class DetailedStats(BaseModel):
    """Statistics for a single vulnerability type (bug or psirt)."""
    total: int
    by_platform: Dict[str, int]
    labeled_count: int
    unlabeled_count: int


class DBStatsResponse(BaseModel):
    """Response model for database statistics."""
    success: bool
    total_bugs: int
    by_platform: Dict[str, int]
    by_type: Dict[str, int]
    labeled_count: int
    unlabeled_count: int
    # NEW: Separated stats
    bugs: Optional[DetailedStats] = None
    psirts: Optional[DetailedStats] = None
    # Rest unchanged
    last_import: Optional[Dict] = None
    db_size_mb: float
    table_counts: Dict[str, int]


class SystemHealthResponse(BaseModel):
    """Response model for system health."""
    status: str
    database: Dict
    model: Dict
    cache: Dict
    uptime_info: Dict


class CacheClearResponse(BaseModel):
    """Response model for cache clear operations."""
    success: bool
    cleared: Dict[str, int]
    message: str


# =============================================================================
# Offline Update Endpoints
# =============================================================================

@router.post("/update/offline", response_model=UpdateResponse)
async def apply_offline_update(
    file: UploadFile = File(..., description="ZIP package containing labeled bugs"),
    skip_hash: bool = False
):
    """
    Apply an offline bug database update package.

    The package should be a ZIP file containing:
    - labeled_update.jsonl or similar data file
    - manifest.json with metadata
    - SHA256SUMS for hash verification (optional)

    Args:
        file: ZIP file upload
        skip_hash: Skip hash verification (use with caution)

    Returns:
        UpdateResponse with import statistics
    """
    temp_path = None
    try:
        # Validate file type
        if not file.filename or not file.filename.endswith('.zip'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a .zip package"
            )

        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix='.zip',
            prefix='vuln_update_'
        ) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        logger.info(f"Received update package: {file.filename} ({len(content)} bytes)")

        # Apply update
        updater = OfflineUpdater(db_path=DB_PATH)
        result = updater.apply_update(temp_path, skip_hash=skip_hash)

        return UpdateResponse(
            success=result.success,
            inserted=result.inserted,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
            total_processed=result.inserted + result.updated,
            error_message=result.error_message,
            package_name=file.filename or "",
            hash_verified=result.hash_verified,
            manifest=result.manifest,
            timestamp=result.timestamp
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Update failed: {str(e)}"
        )
    finally:
        # Cleanup temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file: {e}")


@router.post("/update/validate", response_model=ValidationResponse)
async def validate_update_package(
    file: UploadFile = File(..., description="ZIP package to validate")
):
    """
    Validate an update package without applying it.

    Useful for pre-flight checks before committing to an update.

    Args:
        file: ZIP file upload

    Returns:
        ValidationResponse with package details
    """
    temp_path = None
    try:
        if not file.filename or not file.filename.endswith('.zip'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a .zip package"
            )

        # Save uploaded file
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix='.zip',
            prefix='vuln_validate_'
        ) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Validate
        updater = OfflineUpdater(db_path=DB_PATH)
        result = updater.validate_package(temp_path)

        return ValidationResponse(
            valid=result.valid,
            error=result.error,
            item_count=result.item_count,
            hash_verified=result.hash_verified,
            hash_message=result.hash_message,
            manifest=result.manifest
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


# =============================================================================
# Database Statistics
# =============================================================================

@router.get("/stats/database", response_model=DBStatsResponse)
async def get_database_stats():
    """
    Get comprehensive database statistics.

    Returns counts by platform, type, label status, and more.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Total count
        cursor.execute("SELECT COUNT(*) FROM vulnerabilities")
        total = cursor.fetchone()[0]

        # By platform
        cursor.execute("""
            SELECT platform, COUNT(*) as count
            FROM vulnerabilities
            GROUP BY platform
        """)
        by_platform = {row['platform'] or 'Unknown': row['count'] for row in cursor.fetchall()}

        # By type
        cursor.execute("""
            SELECT vuln_type, COUNT(*) as count
            FROM vulnerabilities
            GROUP BY vuln_type
        """)
        by_type = {row['vuln_type'] or 'Unknown': row['count'] for row in cursor.fetchall()}

        # Labeled vs unlabeled
        cursor.execute("""
            SELECT COUNT(*) FROM vulnerabilities
            WHERE labels IS NOT NULL AND labels != '[]' AND labels != ''
        """)
        labeled = cursor.fetchone()[0]

        # Bugs by platform
        cursor.execute("""
            SELECT platform, COUNT(*) as count
            FROM vulnerabilities
            WHERE vuln_type = 'bug'
            GROUP BY platform
        """)
        bugs_by_platform = {row['platform'] or 'Unknown': row['count'] for row in cursor.fetchall()}

        # PSIRTs by platform
        cursor.execute("""
            SELECT platform, COUNT(*) as count
            FROM vulnerabilities
            WHERE vuln_type = 'psirt'
            GROUP BY platform
        """)
        psirts_by_platform = {row['platform'] or 'Unknown': row['count'] for row in cursor.fetchall()}

        # Labeled bugs count
        cursor.execute("""
            SELECT COUNT(*) FROM vulnerabilities
            WHERE vuln_type = 'bug'
            AND labels IS NOT NULL AND labels != '[]' AND labels != ''
        """)
        bugs_labeled = cursor.fetchone()[0]

        # Labeled PSIRTs count
        cursor.execute("""
            SELECT COUNT(*) FROM vulnerabilities
            WHERE vuln_type = 'psirt'
            AND labels IS NOT NULL AND labels != '[]' AND labels != ''
        """)
        psirts_labeled = cursor.fetchone()[0]

        # Last import info
        cursor.execute("SELECT value FROM db_metadata WHERE key = 'last_import'")
        last_import_row = cursor.fetchone()
        last_import = json.loads(last_import_row['value']) if last_import_row else None

        # Table counts
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        table_counts = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            table_counts[table] = cursor.fetchone()[0]

        conn.close()

        # DB file size
        db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024) if os.path.exists(DB_PATH) else 0

        return DBStatsResponse(
            success=True,
            total_bugs=total,
            by_platform=by_platform,
            by_type=by_type,
            labeled_count=labeled,
            unlabeled_count=total - labeled,
            bugs=DetailedStats(
                total=by_type.get('bug', 0),
                by_platform=bugs_by_platform,
                labeled_count=bugs_labeled,
                unlabeled_count=by_type.get('bug', 0) - bugs_labeled
            ),
            psirts=DetailedStats(
                total=by_type.get('psirt', 0),
                by_platform=psirts_by_platform,
                labeled_count=psirts_labeled,
                unlabeled_count=by_type.get('psirt', 0) - psirts_labeled
            ),
            last_import=last_import,
            db_size_mb=round(db_size_mb, 2),
            table_counts=table_counts
        )

    except Exception as e:
        logger.error(f"Failed to get DB stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database statistics: {str(e)}"
        )


# =============================================================================
# System Health
# =============================================================================

def _detect_inference_platform() -> dict:
    """
    Detect the inference platform and appropriate adapter path.

    Returns:
        dict with 'platform', 'adapter_path', 'backend', and 'device_info'
    """
    import sys

    result = {
        "platform": "cpu",
        "adapter_path": None,
        "backend": "transformers",
        "device_info": "CPU (no GPU detected)"
    }

    # Check for Mac/MPS (MLX)
    if sys.platform == 'darwin':
        try:
            import torch
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                result["platform"] = "mlx"
                result["adapter_path"] = "models/adapters/mlx_v1"
                result["backend"] = "mlx"
                result["device_info"] = "Apple Silicon (MPS)"
                return result
        except ImportError:
            pass

        # Try MLX directly
        try:
            import mlx
            result["platform"] = "mlx"
            result["adapter_path"] = "models/adapters/mlx_v1"
            result["backend"] = "mlx"
            result["device_info"] = "Apple Silicon (MLX)"
            return result
        except ImportError:
            pass

    # Check for CUDA
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            result["platform"] = "cuda"
            result["adapter_path"] = "models/adapters/cuda_v1"
            result["backend"] = "transformers+peft"
            result["device_info"] = f"CUDA ({gpu_name})"
            return result
    except ImportError:
        pass

    # CPU fallback - still use CUDA adapter if available
    result["adapter_path"] = "models/adapters/cuda_v1"
    return result


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health():
    """
    Get comprehensive system health information.

    Checks database connectivity, model availability, and cache status.
    Platform-aware: checks for MLX adapter on Mac, CUDA adapter on Linux.
    """
    health = {
        "status": "healthy",
        "database": {"status": "unknown"},
        "model": {"status": "unknown"},
        "cache": {"status": "unknown"},
        "uptime_info": {}
    }

    # Check database
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM vulnerabilities")
        count = cursor.fetchone()[0]

        # Check WAL mode
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]

        conn.close()

        health["database"] = {
            "status": "healthy",
            "bug_count": count,
            "journal_mode": journal_mode,
            "path": DB_PATH,
            "exists": os.path.exists(DB_PATH)
        }
    except Exception as e:
        health["database"] = {"status": "error", "error": str(e)}
        health["status"] = "degraded"

    # Detect platform and check appropriate model files
    platform_info = _detect_inference_platform()
    adapter_path = platform_info["adapter_path"]
    faiss_path = "models/faiss_index.bin"
    embedder_path = "models/embedder_info.json"

    # Check if adapter exists
    adapter_exists = adapter_path and os.path.exists(adapter_path)

    # Determine model health status
    model_status = "healthy"
    if not adapter_exists:
        model_status = "missing"
    elif not os.path.exists(faiss_path):
        model_status = "degraded"

    health["model"] = {
        "status": model_status,
        "platform": platform_info["platform"],
        "backend": platform_info["backend"],
        "device_info": platform_info["device_info"],
        "adapter_path": adapter_path,
        "adapter_exists": adapter_exists,
        "faiss_index": os.path.exists(faiss_path),
        "faiss_size_mb": round(os.path.getsize(faiss_path) / (1024 * 1024), 2) if os.path.exists(faiss_path) else 0,
        "embedder_config": os.path.exists(embedder_path)
    }

    # Only mark degraded if adapter is truly missing
    if not adapter_exists:
        health["status"] = "degraded"

    # Check PSIRT cache
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM psirt_cache" if _table_exists(cursor, 'psirt_cache') else "SELECT 0")
        cache_count = cursor.fetchone()[0]
        conn.close()

        health["cache"] = {
            "status": "healthy",
            "psirt_cache_entries": cache_count
        }
    except Exception:
        health["cache"] = {"status": "not_configured", "psirt_cache_entries": 0}

    # System info
    health["uptime_info"] = {
        "timestamp": datetime.now().isoformat(),
        "python_version": _get_python_version()
    }

    return SystemHealthResponse(**health)


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def _get_python_version() -> str:
    """Get Python version string."""
    import sys
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


# =============================================================================
# Cache Management
# =============================================================================

@router.post("/cache/clear", response_model=CacheClearResponse)
async def clear_cache(cache_type: str = "all"):
    """
    Clear system caches.

    Args:
        cache_type: Type of cache to clear ("psirt", "all")

    Returns:
        CacheClearResponse with cleared counts
    """
    cleared = {"psirt_cache": 0}

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if cache_type in ["psirt", "all"]:
            if _table_exists(cursor, 'psirt_cache'):
                cursor.execute("SELECT COUNT(*) FROM psirt_cache")
                count = cursor.fetchone()[0]
                cursor.execute("DELETE FROM psirt_cache")
                cleared["psirt_cache"] = count
                logger.info(f"Cleared {count} PSIRT cache entries")

        conn.commit()
        conn.close()

        return CacheClearResponse(
            success=True,
            cleared=cleared,
            message=f"Cleared {sum(cleared.values())} cache entries"
        )

    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache clear failed: {str(e)}"
        )


@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        stats = {
            "psirt_cache": {
                "entries": 0,
                "exists": False
            }
        }

        if _table_exists(cursor, 'psirt_cache'):
            cursor.execute("SELECT COUNT(*) FROM psirt_cache")
            stats["psirt_cache"]["entries"] = cursor.fetchone()[0]
            stats["psirt_cache"]["exists"] = True

        conn.close()

        return {"success": True, "cache_stats": stats}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache stats: {str(e)}"
        )
