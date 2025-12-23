"""
Bug CSV Loader for Vulnerability Database

Loads bugs from CSV file and inserts into SQLite database with:
- Version pattern detection
- Label integration from training data
- Normalized version indexing
- Progress tracking
"""

import csv
import json
import sqlite3
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.core.version_patterns import VersionPatternDetector, VersionInfo
from backend.db.hardware_extractor import extract_hardware_model


class BugLoader:
    """Load bugs from CSV into vulnerability database"""

    def __init__(self, db_path: str = 'vulnerability_db.sqlite'):
        self.db_path = db_path
        self.conn = None
        self.detector = VersionPatternDetector()
        self.labels_cache = {}  # Cache for labels lookup

    def connect(self):
        """Connect to database and create schema if needed"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        # Load schema
        schema_path = os.path.join(os.path.dirname(__file__), 'vuln_schema.sql')
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
            self.conn.executescript(schema_sql)

        print(f"Connected to database: {self.db_path}")

    def load_labels_from_training_data(self, training_csv_path: str):
        """
        Load labels from training data CSV into cache.

        Structure: bug_id, platform, summary, labels, labels_source, ...
        """
        print(f"\nLoading labels from: {training_csv_path}")

        try:
            with open(training_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0

                for row in reader:
                    bug_id = row.get('bug_id', '').strip()
                    labels_str = row.get('labels', '[]').strip()
                    labels_source = row.get('labels_source', 'unknown').strip()

                    # Parse labels JSON
                    try:
                        labels = json.loads(labels_str)
                    except json.JSONDecodeError:
                        labels = []

                    # Only cache bugs with actual labels
                    if bug_id and bug_id != 'N/A' and labels:
                        self.labels_cache[bug_id] = {
                            'labels': labels,
                            'labels_source': labels_source
                        }
                        count += 1

            print(f"Loaded labels for {count} bugs")

        except FileNotFoundError:
            print(f"Warning: Training data file not found: {training_csv_path}")
            print("Continuing without labels...")

    def parse_bug_row(self, row: Dict, platform: str = 'IOS-XE') -> Optional[Dict]:
        """
        Parse a bug CSV row into database format.

        Args:
            row: CSV row dict
            platform: Platform name (IOS-XE, IOS-XR, ASA, FTD, NX-OS)

        Returns:
            Dict with parsed fields or None if invalid
        """
        bug_id = row.get('BUG Id', '').strip()
        if not bug_id:
            return None

        # Extract fields
        headline = row.get('BUG headline', '').strip()
        url = row.get('URL', '').strip()
        status = row.get('Bug Status', '').strip()
        severity_str = row.get('Bug Severity', '').strip()
        product_series = row.get('Product - Series', '').strip()
        affected_versions_raw = row.get('Known Affected Release(s)', '').strip()
        fixed_releases_raw = row.get('Known Fixed Releases', '').strip()
        last_modified = row.get('Last Modified', '').strip()

        # Parse severity
        try:
            severity = int(severity_str) if severity_str else None
        except ValueError:
            severity = None

        # Detect version pattern
        pattern_info = self.detector.detect_pattern(affected_versions_raw)

        # Extract first fixed version (if available)
        fixed_version = None
        if fixed_releases_raw:
            # Parse first version from fixed releases
            fixed_versions = self.detector.detect_pattern(fixed_releases_raw)
            if fixed_versions['versions']:
                fixed_version = fixed_versions['versions'][0]
            elif fixed_versions['version_min']:
                fixed_version = fixed_versions['version_min']

        # Get labels from cache
        label_info = self.labels_cache.get(bug_id, {'labels': [], 'labels_source': 'unlabeled'})

        # Extract hardware model from headline
        # Philosophy: "When in doubt, include it" - only extract when confident
        hardware_model = extract_hardware_model(headline, platform=platform)

        return {
            'bug_id': bug_id,
            'vuln_type': 'bug',
            'platform': platform,
            'hardware_model': hardware_model,  # NEW: Hardware filtering
            'severity': severity,
            'headline': headline,
            'url': url,
            'status': status,
            'product_series': product_series,
            'affected_versions_raw': affected_versions_raw,
            'version_pattern': pattern_info['pattern'],
            'version_min': pattern_info['version_min'],
            'version_max': pattern_info['version_max'],
            'fixed_version': fixed_version,
            'explicit_versions': pattern_info['versions'],
            'labels': label_info['labels'],
            'labels_source': label_info['labels_source'],
            'last_modified': last_modified
        }

    def insert_vulnerability(self, bug_data: Dict) -> int:
        """
        Insert bug into database with indexes.

        Returns:
            vulnerability_id (rowid)
        """
        cursor = self.conn.cursor()

        # Insert main vulnerability record
        cursor.execute('''
            INSERT INTO vulnerabilities (
                bug_id, advisory_id, vuln_type, severity, headline, summary,
                url, status, platform, product_series, hardware_model,
                affected_versions_raw, version_pattern, version_min, version_max,
                fixed_version, labels, labels_source, last_modified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            bug_data['bug_id'],
            None,  # advisory_id (bugs don't have this)
            bug_data['vuln_type'],
            bug_data['severity'],
            bug_data['headline'],
            None,  # summary (not in bug CSV)
            bug_data['url'],
            bug_data['status'],
            bug_data['platform'],
            bug_data['product_series'],
            bug_data.get('hardware_model'),  # NEW: Hardware filtering
            bug_data['affected_versions_raw'],
            bug_data['version_pattern'],
            bug_data['version_min'],
            bug_data['version_max'],
            bug_data['fixed_version'],
            json.dumps(bug_data['labels']),
            bug_data['labels_source'],
            bug_data['last_modified']
        ))

        vuln_id = cursor.lastrowid

        # Insert version index entries (for EXPLICIT versions)
        for version_str in bug_data['explicit_versions']:
            version_info = self.detector.parse_version(version_str)
            if version_info:
                cursor.execute('''
                    INSERT INTO version_index (
                        vulnerability_id, version_normalized,
                        version_major, version_minor, version_patch
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    vuln_id,
                    str(version_info),
                    version_info.major,
                    version_info.minor,
                    version_info.patch
                ))

        # Insert label index entries
        for label in bug_data['labels']:
            cursor.execute('''
                INSERT INTO label_index (vulnerability_id, label)
                VALUES (?, ?)
            ''', (vuln_id, label))

        return vuln_id

    def load_bugs_from_csv(
        self,
        bugs_csv_path: str,
        training_csv_path: str,
        platform: str = 'IOS-XE',
        limit: Optional[int] = None,
        skip_duplicates: bool = True
    ):
        """
        Load bugs from CSV file into database.

        Args:
            bugs_csv_path: Path to bugs CSV file
            training_csv_path: Path to training data CSV (for labels)
            platform: Platform name (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
            limit: Maximum number of bugs to load (for testing)
            skip_duplicates: Skip bugs already in database
        """
        print(f"\nLoading bugs from: {bugs_csv_path}")
        print(f"Platform: {platform}")
        if limit:
            print(f"Limit: {limit} bugs")

        # Load labels first
        self.load_labels_from_training_data(training_csv_path)

        # Track stats
        stats = {
            'total_processed': 0,
            'inserted': 0,
            'skipped_duplicate': 0,
            'skipped_invalid': 0,
            'with_labels': 0,
            'without_labels': 0
        }

        # Load bugs
        with open(bugs_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break

                stats['total_processed'] += 1

                # Parse row
                bug_data = self.parse_bug_row(row, platform=platform)
                if not bug_data:
                    stats['skipped_invalid'] += 1
                    continue

                # Check for duplicates
                if skip_duplicates:
                    cursor = self.conn.cursor()
                    cursor.execute('SELECT id FROM vulnerabilities WHERE bug_id = ?', (bug_data['bug_id'],))
                    if cursor.fetchone():
                        stats['skipped_duplicate'] += 1
                        continue

                # Insert bug
                try:
                    self.insert_vulnerability(bug_data)
                    stats['inserted'] += 1

                    if bug_data['labels']:
                        stats['with_labels'] += 1
                    else:
                        stats['without_labels'] += 1

                    # Progress indicator
                    if stats['inserted'] % 100 == 0:
                        print(f"  Inserted {stats['inserted']} bugs...")

                except sqlite3.IntegrityError as e:
                    print(f"  Error inserting {bug_data['bug_id']}: {e}")
                    stats['skipped_duplicate'] += 1

        # Commit all changes
        self.conn.commit()

        # Update metadata
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE db_metadata
            SET value = ?, updated_at = ?
            WHERE key = 'last_update'
        ''', (datetime.now().isoformat(), datetime.now().isoformat()))

        cursor.execute('''
            UPDATE db_metadata
            SET value = ?, updated_at = ?
            WHERE key = 'total_vulnerabilities'
        ''', (str(stats['inserted']), datetime.now().isoformat()))

        self.conn.commit()

        # Print summary
        print("\n" + "=" * 80)
        print("LOADING SUMMARY")
        print("=" * 80)
        print(f"Total processed:     {stats['total_processed']}")
        print(f"Inserted:            {stats['inserted']}")
        print(f"  With labels:       {stats['with_labels']}")
        print(f"  Without labels:    {stats['without_labels']}")
        print(f"Skipped (duplicate): {stats['skipped_duplicate']}")
        print(f"Skipped (invalid):   {stats['skipped_invalid']}")
        print("=" * 80)

        # Pattern distribution
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT version_pattern, COUNT(*) as count
            FROM vulnerabilities
            GROUP BY version_pattern
        ''')
        print("\nVersion Pattern Distribution:")
        for row in cursor.fetchall():
            print(f"  {row['version_pattern']}: {row['count']}")

        print()

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Load bugs from CSV into vulnerability database')
    parser.add_argument('bugs_csv', help='Path to bugs CSV file')
    parser.add_argument('--platform', default='IOS-XE',
                        choices=['IOS-XE', 'IOS-XR', 'ASA', 'FTD', 'NX-OS'],
                        help='Platform name (default: IOS-XE)')
    parser.add_argument('--training-csv', default='training_data_bugs_20251008_142230.csv',
                        help='Path to training data CSV (default: training_data_bugs_20251008_142230.csv)')
    parser.add_argument('--db', default='vulnerability_db.sqlite',
                        help='Database path (default: vulnerability_db.sqlite)')
    parser.add_argument('--limit', type=int, help='Limit number of bugs to load (for testing)')
    parser.add_argument('--force', action='store_true', help='Force reload, allow duplicates')

    args = parser.parse_args()

    # Create loader
    loader = BugLoader(db_path=args.db)

    try:
        loader.connect()
        loader.load_bugs_from_csv(
            bugs_csv_path=args.bugs_csv,
            training_csv_path=args.training_csv,
            platform=args.platform,
            limit=args.limit,
            skip_duplicates=not args.force
        )
    finally:
        loader.close()

    print(f"\nDatabase saved to: {args.db}")


if __name__ == '__main__':
    main()
