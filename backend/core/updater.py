"""
Offline Updater - Ingest Labeled Vulnerability Package into Database
=====================================================================
Refactored from future_architecture/scripts/apply_offline_update.py for API usage.
Performs hash verification, schema validation, and generates audit reports.

Protocol:
1. Verify SHA256 hash of data file
2. Validate schema version
3. Upsert records (anti-affinity: skip existing, update if newer)
4. Return import statistics

Input Package Structure:
    update_YYYYMMDD/
    ├── labeled_update.jsonl     (labeled items)
    ├── manifest.json            (metadata)
    └── SHA256SUMS               (checksums for verification)
"""

import os
import json
import hashlib
import sqlite3
import zipfile
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

from backend.core.version_patterns import VersionPatternDetector
from backend.db.hardware_extractor import extract_hardware_model

logger = logging.getLogger(__name__)

# Supported schema versions
SUPPORTED_SCHEMA_VERSIONS = ["1.0"]

# Default database path
DEFAULT_DB_PATH = "vulnerability_db.sqlite"


@dataclass
class UpdateResult:
    """Result of an update operation."""
    success: bool
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    error_message: Optional[str] = None
    manifest: Optional[Dict] = None
    hash_verified: bool = False
    package_name: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "error_message": self.error_message,
            "manifest": self.manifest,
            "hash_verified": self.hash_verified,
            "package_name": self.package_name,
            "timestamp": self.timestamp,
            "total_processed": self.inserted + self.updated
        }


@dataclass
class ValidationResult:
    """Result of package validation."""
    valid: bool
    error: Optional[str] = None
    manifest: Optional[Dict] = None
    data_filename: Optional[str] = None
    item_count: int = 0
    hash_verified: bool = False
    hash_message: str = ""


class OfflineUpdater:
    """
    Handles offline vulnerability update packages.

    Usage:
        updater = OfflineUpdater(db_path="vulnerability_db.sqlite")

        # Validate first (optional)
        validation = updater.validate_package("/path/to/update.zip")
        if validation.valid:
            result = updater.apply_update("/path/to/update.zip")
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._temp_dir: Optional[str] = None
        self._version_detector = VersionPatternDetector()

    def validate_package(self, file_path: str, skip_hash: bool = False) -> ValidationResult:
        """
        Validate an update package without applying it.

        Args:
            file_path: Path to update package (directory or .zip)
            skip_hash: Skip hash verification

        Returns:
            ValidationResult with validation details
        """
        try:
            # Unpack if ZIP
            package_dir, was_zip = self._unpack_if_zip(file_path)

            # Validate manifest
            valid, manifest = self._validate_manifest(package_dir)
            if not valid:
                return ValidationResult(
                    valid=False,
                    error=manifest.get('error', 'Invalid manifest')
                )

            # Find data file (pass manifest so it can use the 'file' field)
            data_filename = self._find_data_file(package_dir, manifest)
            if not data_filename:
                return ValidationResult(
                    valid=False,
                    error="No data file found in package"
                )

            # Verify hash (pass manifest so it can use the sha256 field)
            hash_verified = False
            hash_message = ""
            if not skip_hash:
                hash_ok, hash_msg = self._verify_package_hash(package_dir, data_filename, manifest)
                hash_verified = hash_ok
                hash_message = hash_msg
                if not hash_ok:
                    return ValidationResult(
                        valid=False,
                        error=hash_msg
                    )
            else:
                hash_message = "Hash verification skipped (user request)"

            # Count items
            items = self._load_data(package_dir, data_filename)

            # Cleanup temp if was zip
            if was_zip and self._temp_dir:
                self._cleanup_temp()

            return ValidationResult(
                valid=True,
                manifest=manifest,
                data_filename=data_filename,
                item_count=len(items),
                hash_verified=hash_verified,
                hash_message=hash_message
            )

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return ValidationResult(
                valid=False,
                error=str(e)
            )

    def apply_update(
        self,
        file_path: str,
        skip_hash: bool = False,
        source: str = "offline_update"
    ) -> UpdateResult:
        """
        Apply an update package to the database.

        Args:
            file_path: Path to update package (directory or .zip)
            skip_hash: Skip hash verification
            source: Source identifier for tracking

        Returns:
            UpdateResult with operation details
        """
        try:
            # Unpack if ZIP
            package_dir, was_zip = self._unpack_if_zip(file_path)
            package_name = os.path.basename(file_path)

            logger.info(f"Applying update from: {package_name}")

            # Validate manifest
            valid, manifest = self._validate_manifest(package_dir)
            if not valid:
                return UpdateResult(
                    success=False,
                    error_message=manifest.get('error', 'Invalid manifest'),
                    package_name=package_name
                )

            # Find data file (pass manifest so it can use the 'file' field)
            data_filename = self._find_data_file(package_dir, manifest)
            if not data_filename:
                return UpdateResult(
                    success=False,
                    error_message="No data file found in package",
                    package_name=package_name
                )

            # Verify hash (pass manifest so it can use the sha256 field)
            hash_verified = False
            if not skip_hash:
                hash_ok, hash_msg = self._verify_package_hash(package_dir, data_filename, manifest)
                if not hash_ok:
                    return UpdateResult(
                        success=False,
                        error_message=hash_msg,
                        package_name=package_name
                    )
                hash_verified = True
                logger.info(f"{hash_msg}")

            # Load data
            items = self._load_data(package_dir, data_filename)
            logger.info(f"Loaded {len(items)} items from package")

            # Apply to database
            conn = self._init_db()
            stats = self._upsert_vulnerabilities(conn, items, source)

            # Update metadata
            self._update_metadata(conn, manifest, stats)
            conn.close()

            logger.info(f"Update complete: {stats['inserted']} inserted, {stats['updated']} updated")

            # Cleanup temp if was zip
            if was_zip and self._temp_dir:
                self._cleanup_temp()

            return UpdateResult(
                success=stats['errors'] == 0,
                inserted=stats['inserted'],
                updated=stats['updated'],
                skipped=stats['skipped'],
                errors=stats['errors'],
                manifest=manifest,
                hash_verified=hash_verified,
                package_name=package_name
            )

        except Exception as e:
            logger.error(f"Update error: {e}")
            return UpdateResult(
                success=False,
                error_message=str(e),
                package_name=os.path.basename(file_path) if file_path else ""
            )
        finally:
            # Always cleanup temp
            if self._temp_dir:
                self._cleanup_temp()

    def _compute_sha256(self, file_path: str) -> str:
        """Compute SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _verify_package_hash(self, package_dir: str, data_filename: str, manifest: Optional[Dict] = None) -> Tuple[bool, str]:
        """Verify the SHA256 hash of the data file."""
        data_path = os.path.join(package_dir, data_filename)

        # Try manifest.json sha256 field first (our standard format)
        if manifest and 'sha256' in manifest:
            expected_hash = manifest['sha256']
            actual_hash = self._compute_sha256(data_path)
            if actual_hash != expected_hash:
                return False, f"Hash mismatch! Expected: {expected_hash[:16]}..., Got: {actual_hash[:16]}..."
            return True, f"SHA256 verified: {actual_hash[:16]}..."

        # Try SHA256SUMS file (alternate format)
        sha256sums_path = os.path.join(package_dir, "SHA256SUMS")
        if os.path.exists(sha256sums_path):
            with open(sha256sums_path, 'r') as f:
                for line in f:
                    if line.strip():
                        parts = line.strip().split('  ')
                        if len(parts) == 2 and parts[1] == data_filename:
                            expected_hash = parts[0]
                            actual_hash = self._compute_sha256(data_path)
                            if actual_hash != expected_hash:
                                return False, f"Hash mismatch! Expected: {expected_hash[:16]}..., Got: {actual_hash[:16]}..."
                            return True, f"SHA256 verified: {actual_hash[:16]}..."
            return False, f"No hash for {data_filename} in SHA256SUMS"

        # Fall back to hashes.json
        hashes_path = os.path.join(package_dir, "hashes.json")
        if os.path.exists(hashes_path):
            with open(hashes_path, 'r') as f:
                hashes = json.load(f)
            expected_hash = hashes.get('files', {}).get(data_filename)
            if expected_hash:
                actual_hash = self._compute_sha256(data_path)
                if actual_hash != expected_hash:
                    return False, f"Hash mismatch! Expected: {expected_hash[:16]}..., Got: {actual_hash[:16]}..."
                return True, f"SHA256 verified: {actual_hash[:16]}..."

        return False, "No hash found in manifest or package (verification failed)"

    def _validate_manifest(self, package_dir: str) -> Tuple[bool, Dict]:
        """Validate and load the manifest."""
        manifest_path = os.path.join(package_dir, "manifest.json")

        if not os.path.exists(manifest_path):
            return False, {"error": "No manifest.json found"}

        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        # Check schema_version or pipeline_version (both are acceptable)
        schema_version = manifest.get('schema_version') or manifest.get('pipeline_version', '1.0')
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            return False, {"error": f"Unsupported schema version: {schema_version}"}

        return True, manifest

    def _find_data_file(self, package_dir: str, manifest: Optional[Dict] = None) -> Optional[str]:
        """Find the data file in the package."""
        # First, check if manifest specifies a file
        if manifest and 'file' in manifest:
            manifest_file = manifest['file']
            if os.path.exists(os.path.join(package_dir, manifest_file)):
                return manifest_file

        candidates = [
            "labeled_update.jsonl",
            "labeled_data.jsonl",
            "data.jsonl",
            "unlabeled_data.jsonl",
            "labeled_vulnerabilities.json",
            "update_content.json"
        ]

        for candidate in candidates:
            if os.path.exists(os.path.join(package_dir, candidate)):
                return candidate

        # Check in data/ subdirectory
        for candidate in candidates:
            if os.path.exists(os.path.join(package_dir, "data", candidate)):
                return os.path.join("data", candidate)

        # Fall back: look for any .jsonl file
        for f in os.listdir(package_dir):
            if f.endswith('.jsonl') and f != 'manifest.json':
                return f

        return None

    def _init_db(self) -> sqlite3.Connection:
        """Initialize database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _load_data(self, package_dir: str, data_filename: str) -> List[Dict]:
        """Load data from file (supports JSONL and JSON formats)."""
        data_path = os.path.join(package_dir, data_filename)
        items = []

        if data_filename.endswith('.jsonl'):
            with open(data_path, 'r') as f:
                for line in f:
                    if line.strip():
                        items.append(json.loads(line))
        else:
            with open(data_path, 'r') as f:
                content = json.load(f)
                if isinstance(content, list):
                    items = content
                elif isinstance(content, dict) and 'items' in content:
                    items = content['items']
                else:
                    items = [content]

        return items

    def _upsert_vulnerabilities(
        self,
        conn: sqlite3.Connection,
        items: List[Dict],
        source: str = "offline_update"
    ) -> Dict[str, int]:
        """
        Upsert vulnerability items into database with proper version pattern detection.

        This method now properly:
        1. Detects version patterns from affected_versions using VersionPatternDetector
        2. Populates version_min, version_max, version_pattern columns
        3. Creates version_index entries for EXPLICIT pattern versions
        4. Creates label_index entries for each label
        """
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()

        stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0
        }

        for item in items:
            try:
                # Extract identifiers - support both PSIRT and bug formats
                advisory_id = item.get('advisoryId', item.get('advisory_id', ''))
                bug_id = item.get('bug_id', advisory_id)  # Prefer bug_id if present

                if not bug_id:
                    stats['skipped'] += 1
                    continue

                vuln_type = item.get('type', item.get('vuln_type', 'psirt')).lower()
                platform = item.get('platform', 'Unknown')
                summary = item.get('summary', '')
                headline = item.get('headline', summary[:100] + '...' if len(summary) > 100 else summary)

                # Parse severity (handle string or int)
                severity = item.get('severity')
                if isinstance(severity, str):
                    severity_map = {'Critical': 1, 'High': 2, 'Medium': 3, 'Low': 4, 'Informational': 5}
                    severity = severity_map.get(severity, 3)

                # Labels can be list or string
                labels = item.get('labels', item.get('predicted_labels', []))
                if isinstance(labels, list):
                    labels_str = json.dumps(labels)
                    labels_list = labels
                else:
                    labels_str = str(labels)
                    labels_list = json.loads(labels) if labels else []

                # ========================================
                # VERSION PATTERN DETECTION (Critical Fix)
                # ========================================
                # Get raw version data - support multiple formats from different sources
                affected_versions_raw = ''
                affected_versions = item.get('affected_versions', item.get('affectedVersions', []))

                if isinstance(affected_versions, list) and affected_versions:
                    # Convert list to space-separated string for pattern detection
                    affected_versions_raw = ' '.join(str(v) for v in affected_versions)
                elif isinstance(affected_versions, str) and affected_versions:
                    affected_versions_raw = affected_versions
                else:
                    # Try other common field names
                    affected_versions_raw = item.get('affected_versions_raw',
                                                      item.get('known_affected', ''))

                # Detect version pattern using VersionPatternDetector
                pattern_info = self._version_detector.detect_pattern(affected_versions_raw)
                version_pattern = pattern_info['pattern']
                version_min = pattern_info['version_min']
                version_max = pattern_info['version_max']
                explicit_versions = pattern_info['versions']

                # Get fixed version if available
                fixed_version = item.get('fixed_version', item.get('firstFixed'))
                if isinstance(fixed_version, list) and fixed_version:
                    fixed_version = fixed_version[0]

                # ========================================
                # HARDWARE MODEL EXTRACTION
                # ========================================
                # First check if hardware_model is provided in the JSON
                hardware_model = item.get('hardware_model')

                # If not provided, try to extract from headline/summary
                if not hardware_model:
                    # Combine headline and summary for better extraction
                    text_for_hw = f"{headline} {summary}"
                    hardware_model = extract_hardware_model(text_for_hw, platform=platform)

                # Check if exists
                cursor.execute("SELECT id FROM vulnerabilities WHERE bug_id = ?", (bug_id,))
                existing = cursor.fetchone()

                if existing:
                    vuln_id = existing[0]
                    # Update existing record with version info if we have better data
                    cursor.execute("""
                        UPDATE vulnerabilities
                        SET labels = COALESCE(NULLIF(?, '[]'), labels),
                            labels_source = ?,
                            affected_versions_raw = CASE
                                WHEN ? != '' THEN ?
                                ELSE affected_versions_raw
                            END,
                            version_pattern = CASE
                                WHEN ? != 'UNKNOWN' THEN ?
                                ELSE version_pattern
                            END,
                            version_min = COALESCE(?, version_min),
                            version_max = COALESCE(?, version_max),
                            fixed_version = COALESCE(?, fixed_version),
                            last_modified = ?
                        WHERE bug_id = ?
                    """, (
                        labels_str,
                        source,
                        affected_versions_raw, affected_versions_raw,
                        version_pattern, version_pattern,
                        version_min,
                        version_max,
                        fixed_version,
                        timestamp,
                        bug_id
                    ))

                    # Update label_index if labels changed
                    if labels_list:
                        cursor.execute("DELETE FROM label_index WHERE vulnerability_id = ?", (vuln_id,))
                        for label in labels_list:
                            cursor.execute(
                                "INSERT INTO label_index (vulnerability_id, label) VALUES (?, ?)",
                                (vuln_id, label)
                            )

                    stats['updated'] += 1
                else:
                    # Insert new record with proper version detection and hardware
                    cursor.execute("""
                        INSERT INTO vulnerabilities (
                            bug_id, advisory_id, vuln_type,
                            headline, summary, platform,
                            severity, labels, labels_source,
                            affected_versions_raw, version_pattern,
                            version_min, version_max, fixed_version,
                            hardware_model,
                            last_modified, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        bug_id,
                        advisory_id if vuln_type == 'psirt' else None,
                        vuln_type,
                        headline,
                        summary,
                        platform,
                        severity,
                        labels_str,
                        source,
                        affected_versions_raw,
                        version_pattern,
                        version_min,
                        version_max,
                        fixed_version,
                        hardware_model,
                        timestamp,
                        timestamp
                    ))

                    vuln_id = cursor.lastrowid

                    # Populate version_index for EXPLICIT versions
                    for version_str in explicit_versions:
                        version_info = self._version_detector.parse_version(version_str)
                        if version_info:
                            cursor.execute("""
                                INSERT INTO version_index (
                                    vulnerability_id, version_normalized,
                                    version_major, version_minor, version_patch
                                ) VALUES (?, ?, ?, ?, ?)
                            """, (
                                vuln_id,
                                str(version_info),
                                version_info.major,
                                version_info.minor or 0,
                                version_info.patch or 0
                            ))

                    # Populate label_index
                    for label in labels_list:
                        cursor.execute(
                            "INSERT INTO label_index (vulnerability_id, label) VALUES (?, ?)",
                            (vuln_id, label)
                        )

                    stats['inserted'] += 1

                    if stats['inserted'] % 100 == 0:
                        logger.info(f"  Inserted {stats['inserted']} items...")

            except sqlite3.IntegrityError as e:
                logger.warning(f"Integrity error for {bug_id}: {e}")
                stats['skipped'] += 1
            except Exception as e:
                logger.error(f"Error processing {bug_id}: {e}")
                stats['errors'] += 1

        conn.commit()
        return stats

    def _update_metadata(self, conn: sqlite3.Connection, manifest: Dict, stats: Dict):
        """Update database metadata with import info."""
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()

        cursor.execute("""
            INSERT OR REPLACE INTO db_metadata (key, value, updated_at)
            VALUES ('last_import', ?, ?)
        """, (json.dumps({
            "timestamp": timestamp,
            "manifest": manifest,
            "stats": stats
        }), timestamp))

        cursor.execute("""
            INSERT OR REPLACE INTO db_metadata (key, value, updated_at)
            VALUES ('schema_version', ?, ?)
        """, (manifest.get('schema_version') or manifest.get('pipeline_version', '1.0'), timestamp))

        conn.commit()

    def _unpack_if_zip(self, package_path: str) -> Tuple[str, bool]:
        """Unpack ZIP file if needed."""
        if not package_path.endswith('.zip'):
            return package_path, False

        if not os.path.exists(package_path):
            raise FileNotFoundError(f"Package not found: {package_path}")

        # Extract to temp directory
        self._temp_dir = f"temp_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self._temp_dir, exist_ok=True)

        with zipfile.ZipFile(package_path, 'r') as zip_ref:
            zip_ref.extractall(self._temp_dir)

        # Find the actual package directory (might be nested)
        contents = os.listdir(self._temp_dir)
        if len(contents) == 1 and os.path.isdir(os.path.join(self._temp_dir, contents[0])):
            return os.path.join(self._temp_dir, contents[0]), True

        return self._temp_dir, True

    def _cleanup_temp(self):
        """Clean up temporary directory."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
                logger.debug(f"Cleaned up temp directory: {self._temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp dir: {e}")
            finally:
                self._temp_dir = None


# Singleton instance
_updater_instance: Optional[OfflineUpdater] = None


def get_updater(db_path: str = DEFAULT_DB_PATH) -> OfflineUpdater:
    """Get or create OfflineUpdater singleton."""
    global _updater_instance
    if _updater_instance is None:
        _updater_instance = OfflineUpdater(db_path)
    return _updater_instance
