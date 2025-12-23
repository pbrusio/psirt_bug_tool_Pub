"""
Database Scanner - Fast Path (Path A)

Handles fast database queries for known bugs.
Extracted from vulnerability_scanner.py for modularity.

Responsibilities:
- Query SQLite for version-matched bugs
- Apply hardware model filtering
- Apply feature/label filtering
- Group results by severity

Performance target: <10ms for typical scan
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import uuid
import logging
import json
import re

from backend.db.utils import get_db_connection

logger = logging.getLogger(__name__)


class DatabaseScanner:
    """
    Fast-path database scanner for known bugs.

    This module handles Path A of the dual-path architecture:
    - Version matching against affected_versions_raw
    - Hardware model filtering (40-60% false positive reduction)
    - Feature/label filtering (additional false positive reduction)
    - Severity grouping for UI display
    """

    def __init__(self, db_path: str):
        """
        Initialize database scanner.

        Args:
            db_path: Path to SQLite vulnerability database
        """
        self.db_path = db_path
        logger.info(f"DatabaseScanner initialized with database: {db_path}")

    def scan_device(
        self,
        platform: str,
        version: str,
        labels: Optional[List[str]] = None,
        hardware_model: Optional[str] = None,
        severity_filter: Optional[List[int]] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Dict:
        """
        Fast scan: Query database for matching bugs.

        Process:
        1. Query all bugs for platform
        2. Filter by version (string matching in affected_versions_raw)
        3. Filter by hardware model if provided (40-60% reduction)
        4. Filter by labels/features if provided (feature-aware)
        5. Group by severity (Critical/High vs Medium/Low)
        6. Return sorted results

        Args:
            platform: Device platform (e.g., "IOS-XE")
            version: Device software version (e.g., "17.3.5")
            labels: Optional list of configured feature labels
            hardware_model: Optional hardware model (e.g., "Cat9200")
            severity_filter: Optional list of severity levels to include
            limit: Optional max results to return
            offset: Pagination offset

        Returns:
            Scan result dict with bugs and metadata

        Performance target: <10ms for typical scan (10-50 results)
        """
        start_time = datetime.now()
        scan_id = f"scan-{uuid.uuid4().hex[:8]}"

        logger.info(
            f"Starting database scan: platform={platform}, version={version}, "
            f"hardware_model={hardware_model}, labels={len(labels) if labels else 0}, "
            f"severity_filter={severity_filter}"
        )

        # Connect to database using SafeSQLiteConnection
        with get_db_connection(self.db_path) as db:
            cursor = db.cursor()

            # Get all bugs for platform
            cursor.execute("""
                SELECT bug_id, headline, summary, severity, affected_versions_raw,
                       status, labels, url, hardware_model, vuln_type
                FROM vulnerabilities
                WHERE platform = ?
            """, (platform,))

            all_bugs = cursor.fetchall()
            total_bugs_checked = len(all_bugs)

        # Normalize user's version for consistent matching
        normalized_version = self._normalize_version(version)
        logger.debug(f"Version normalized: {version} -> {normalized_version}")

        # Step 1: Version matching (strict for both bugs and PSIRTs)
        # Only include if device version is in affected_versions_raw
        version_matches = []
        for bug in all_bugs:
            affected = bug['affected_versions_raw']
            if affected and normalized_version in affected:
                version_matches.append(bug)

        # Step 2: Hardware filtering (if hardware_model provided)
        hardware_matches = version_matches
        hardware_filtered_out = []

        if hardware_model:
            hardware_matches = []
            for bug in version_matches:
                bug_hardware = bug['hardware_model']

                # Include if:
                # 1. Bug has no hardware specified (generic) -> always include
                # 2. Bug hardware matches user's hardware -> include
                if bug_hardware is None or bug_hardware == hardware_model:
                    hardware_matches.append(bug)
                else:
                    hardware_filtered_out.append(bug)

        # Step 3: Feature filtering (if labels provided)
        final_matches = hardware_matches
        filtered_out = []

        if labels:
            feature_matches = []
            for bug in hardware_matches:
                bug_labels_str = bug['labels']

                # Parse labels JSON
                try:
                    bug_labels = json.loads(bug_labels_str) if bug_labels_str else []
                except json.JSONDecodeError:
                    bug_labels = []

                # Check if ANY bug label matches device features
                if bug_labels:
                    matches_feature = any(label in labels for label in bug_labels)
                    if matches_feature:
                        feature_matches.append(bug)
                    else:
                        filtered_out.append(bug)
                else:
                    # No labels = can't determine, keep it (conservative)
                    feature_matches.append(bug)

            final_matches = feature_matches

        # Step 4: Severity filtering (if requested)
        if severity_filter:
            final_matches = [b for b in final_matches if b['severity'] in severity_filter]

        # Group by severity
        critical_high_list = [b for b in final_matches if b['severity'] in (1, 2)]
        medium_low_list = [b for b in final_matches if b['severity'] not in (1, 2)]

        # Convert to API format
        bugs = self._format_bugs(final_matches)

        # Separate bugs from PSIRTs
        final_bugs = [b for b in bugs if b.get('vuln_type') == 'bug']
        final_psirts = [b for b in bugs if b.get('vuln_type') == 'psirt']

        # Calculate critical/high by type
        bug_critical_high = len([b for b in final_bugs if b['severity'] in (1, 2)])
        psirt_critical_high = len([b for b in final_psirts if b['severity'] in (1, 2)])

        # Convert filtered bugs to API format (for display)
        filtered_bugs_list = None
        if labels and filtered_out:
            filtered_bugs_list = self._format_bugs(filtered_out[:10])

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"Database scan complete: scan_id={scan_id}, "
            f"version_matches={len(version_matches)}, "
            f"hardware_matches={len(hardware_matches)} (filtered {len(hardware_filtered_out)}), "
            f"final_matches={len(final_matches)}, query_time={elapsed_ms:.1f}ms"
        )

        return {
            'scan_id': scan_id,
            'platform': platform,
            'version': version,
            'hardware_model': hardware_model,
            'features': labels,
            'total_bugs_checked': total_bugs_checked,
            'version_matches': len(version_matches),
            'hardware_filtered': len(hardware_matches) if hardware_model else None,
            'hardware_filtered_count': len(hardware_filtered_out) if hardware_model else 0,
            'feature_filtered': len(final_matches) if labels else None,
            'critical_high': len(critical_high_list),
            'medium_low': len(medium_low_list),
            'bug_count': len(final_bugs),
            'psirt_count': len(final_psirts),
            'bug_critical_high': bug_critical_high,
            'psirt_critical_high': psirt_critical_high,
            'bugs': bugs,  # Keep combined for backward compatibility
            'filtered_bugs': filtered_bugs_list,
            'source': 'database',
            'query_time_ms': round(elapsed_ms, 2),
            'timestamp': datetime.now()
        }

    def _normalize_version(self, version: str) -> str:
        """
        Normalize version string by removing leading zeros from each part.

        This ensures consistent version matching regardless of format:
        - "17.03.05" -> "17.3.5"
        - "17.04.01" -> "17.4.1"
        - "9.16(4)" -> "9.16(4)" (preserves ASA format)

        Args:
            version: Version string (e.g., "17.03.05")

        Returns:
            Normalized version string (e.g., "17.3.5")
        """
        # For ASA/FTD/NX-OS parenthesis format
        if '(' in version:
            parts = version.split('(')
            base = parts[0]
            suffix = '(' + parts[1] if len(parts) > 1 else ''

            # Normalize base part
            base_parts = [str(int(p)) for p in base.split('.') if p.isdigit()]
            normalized_base = '.'.join(base_parts)

            # Normalize suffix part (inside parenthesis)
            if suffix:
                inner = suffix.strip('()')
                if inner.isdigit():
                    suffix = f"({int(inner)})"

            return normalized_base + suffix
        else:
            # For IOS-XE/XR dot format: "17.03.05" -> "17.3.5"
            parts = version.split('.')
            normalized_parts = []

            for part in parts:
                # Strip letter suffixes if present: "05a" -> "5"
                match = re.match(r'(\d+)', part)
                if match:
                    num = int(match.group(1))
                    normalized_parts.append(str(num))

            return '.'.join(normalized_parts) if normalized_parts else version

    def _format_bugs(self, bug_rows: List[Dict]) -> List[Dict]:
        """
        Convert database rows to API format.

        Args:
            bug_rows: List of database row dicts

        Returns:
            List of formatted bug dicts
        """
        bugs = []
        for bug in bug_rows:
            formatted = {
                'bug_id': bug['bug_id'],
                'severity': bug['severity'],
                'headline': bug['headline'] or '',
                'summary': bug['summary'] or '',
                'status': bug['status'] or 'Unknown',
                'affected_versions': bug['affected_versions_raw'] or '',
                'labels': json.loads(bug['labels']) if bug['labels'] else [],
                'url': bug['url'] or '',
                'vuln_type': (bug['vuln_type'] if 'vuln_type' in bug.keys() else 'bug') or 'bug'  # Default to 'bug' if null
            }
            bugs.append(formatted)
        return bugs

    def get_bug_details(self, bug_id: str) -> Optional[Dict]:
        """
        Get full details for a specific bug.

        Used to expand collapsed Medium/Low results.

        Args:
            bug_id: Bug ID (CSCxxxx)

        Returns:
            Full bug dict or None if not found
        """
        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()
                cursor.execute("""
                    SELECT bug_id, headline, summary, severity, affected_versions_raw,
                           status, labels, url, hardware_model, vuln_type
                    FROM vulnerabilities
                    WHERE bug_id = ?
                """, (bug_id,))

                row = cursor.fetchone()
                if row:
                    return self._format_bugs([row])[0]
                return None
        except Exception as e:
            logger.error(f"Failed to get bug details: {e}")
            return None


# Module-level singleton
_db_scanner_instance = None


def get_db_scanner(db_path: str = None) -> DatabaseScanner:
    """
    Get or create DatabaseScanner singleton.

    Args:
        db_path: Path to SQLite database (required on first call)

    Returns:
        DatabaseScanner instance
    """
    global _db_scanner_instance

    if _db_scanner_instance is None:
        if db_path is None:
            raise ValueError("db_path required on first call to get_db_scanner()")
        _db_scanner_instance = DatabaseScanner(db_path)

    return _db_scanner_instance
