"""
Load Labeled Bugs from JSON directly into Vulnerability Database

For JSON format from GPT-4o labeling:
{
  "bug_id": "CSCxx12345",
  "platform": "IOS-XE",
  "summary": "Bug description...",
  "labels_gpt": ["LABEL_1", "LABEL_2"],
  "confidence": "HIGH",
  "severity": "2",
  "affected_versions": "17.10.1 17.12.4",
  "fixed_versions": ""
}
"""

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


class LabeledBugLoader:
    """Load labeled bugs from JSON into vulnerability database"""

    def __init__(self, db_path: str = 'vulnerability_db.sqlite'):
        self.db_path = db_path
        self.conn = None
        self.detector = VersionPatternDetector()

    def connect(self):
        """Connect to database and create schema if needed"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        # Load schema
        schema_path = os.path.join(os.path.dirname(__file__), 'vuln_schema.sql')
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
            self.conn.executescript(schema_sql)

        print(f"✅ Connected to database: {self.db_path}")

    def parse_bug_json(self, bug: Dict) -> Optional[Dict]:
        """
        Parse a bug JSON object into database format.

        Returns:
            Dict with parsed fields or None if invalid
        """
        bug_id = bug.get('bug_id', '').strip()
        if not bug_id:
            return None

        # Extract fields
        platform = bug.get('platform', 'IOS-XE')
        summary = bug.get('summary', '')
        labels = bug.get('labels_gpt', [])
        confidence = bug.get('confidence', 'MEDIUM')
        severity_str = bug.get('severity', '')
        affected_versions_raw = bug.get('affected_versions', '')
        fixed_versions_raw = bug.get('fixed_versions', '')
        status = bug.get('status', 'Unknown')

        # Parse severity
        try:
            severity = int(severity_str) if severity_str else None
        except (ValueError, TypeError):
            severity = None

        # Detect version pattern
        pattern_info = self.detector.detect_pattern(affected_versions_raw)

        # Extract first fixed version (if available)
        fixed_version = None
        if fixed_versions_raw:
            fixed_versions = self.detector.detect_pattern(fixed_versions_raw)
            if fixed_versions['versions']:
                fixed_version = fixed_versions['versions'][0]
            elif fixed_versions['version_min']:
                fixed_version = fixed_versions['version_min']

        # Determine labels_source
        if confidence == 'HIGH':
            labels_source = 'gpt4o_high_confidence'
        elif confidence == 'MEDIUM':
            labels_source = 'gpt4o_medium_confidence'
        else:
            labels_source = 'gpt4o_low_confidence'

        # Extract hardware model from summary
        # Philosophy: "When in doubt, include it" - only extract when confident
        hardware_model = extract_hardware_model(summary, platform=platform)

        return {
            'bug_id': bug_id,
            'vuln_type': 'bug',
            'platform': platform,
            'hardware_model': hardware_model,  # NEW: Hardware filtering
            'severity': severity,
            'headline': summary[:200] if summary else '',  # First 200 chars as headline
            'summary': summary,
            'url': f'https://bst.cisco.com/bugsearch/bug/{bug_id}',
            'status': status,
            'product_series': '',  # Not in labeled JSON
            'affected_versions_raw': affected_versions_raw,
            'version_pattern': pattern_info['pattern'],
            'version_min': pattern_info['version_min'],
            'version_max': pattern_info['version_max'],
            'fixed_version': fixed_version,
            'explicit_versions': pattern_info['versions'],
            'labels': labels,
            'labels_source': labels_source,
            'last_modified': bug.get('timestamp', datetime.now().isoformat())
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
            bug_data['summary'],
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

    def load_bugs_from_json(
        self,
        json_path: str,
        limit: Optional[int] = None,
        skip_duplicates: bool = True
    ):
        """
        Load bugs from JSON file into database.

        Args:
            json_path: Path to labeled bugs JSON file
            limit: Maximum number of bugs to load (for testing)
            skip_duplicates: Skip bugs already in database
        """
        print(f"\n📂 Loading bugs from: {json_path}")
        if limit:
            print(f"⚠️  Limit: {limit} bugs")

        # Load JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            all_bugs = json.load(f)

        print(f"📊 Total bugs in file: {len(all_bugs)}")

        # Track stats
        stats = {
            'total_processed': 0,
            'inserted': 0,
            'skipped_duplicate': 0,
            'skipped_invalid': 0,
            'skipped_no_labels': 0,
            'with_labels': 0,
            'confidence_high': 0,
            'confidence_medium': 0,
            'confidence_low': 0
        }

        # Process bugs
        for i, bug in enumerate(all_bugs):
            if limit and i >= limit:
                break

            stats['total_processed'] += 1

            # Debug first bug
            if i == 0:
                print(f"\n🔍 Debug first bug:")
                print(f"  bug_id: {bug.get('bug_id')}")
                print(f"  labels_gpt: {bug.get('labels_gpt')}")
                print(f"  Has labels: {bool(bug.get('labels_gpt'))}")
                print(f"  Label count: {len(bug.get('labels_gpt', []))}")

            # Skip bugs without labels
            if not bug.get('labels_gpt') or len(bug.get('labels_gpt', [])) == 0:
                stats['skipped_no_labels'] += 1
                continue

            # Parse bug
            bug_data = self.parse_bug_json(bug)
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
                stats['with_labels'] += 1

                # Track confidence
                conf = bug.get('confidence', 'MEDIUM')
                if conf == 'HIGH':
                    stats['confidence_high'] += 1
                elif conf == 'MEDIUM':
                    stats['confidence_medium'] += 1
                else:
                    stats['confidence_low'] += 1

                # Progress indicator
                if stats['inserted'] % 100 == 0:
                    print(f"  ✅ Inserted {stats['inserted']} bugs...")

            except sqlite3.IntegrityError as e:
                print(f"  ❌ Error inserting {bug_data['bug_id']}: {e}")
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
        print("✅ LOADING SUMMARY")
        print("=" * 80)
        print(f"Total processed:        {stats['total_processed']}")
        print(f"Inserted:               {stats['inserted']}")
        print(f"  With labels:          {stats['with_labels']}")
        if stats['inserted'] > 0:
            print(f"  HIGH confidence:      {stats['confidence_high']} ({stats['confidence_high']/stats['inserted']*100:.1f}%)")
            print(f"  MEDIUM confidence:    {stats['confidence_medium']} ({stats['confidence_medium']/stats['inserted']*100:.1f}%)")
            print(f"  LOW confidence:       {stats['confidence_low']}")
        print(f"Skipped (no labels):    {stats['skipped_no_labels']}")
        print(f"Skipped (duplicate):    {stats['skipped_duplicate']}")
        print(f"Skipped (invalid):      {stats['skipped_invalid']}")
        print("=" * 80)

        # Label distribution
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT label, COUNT(*) as count
            FROM label_index
            GROUP BY label
            ORDER BY count DESC
            LIMIT 15
        ''')
        print("\n📊 Top 15 Labels:")
        for row in cursor.fetchall():
            print(f"  {row['label']}: {row['count']}")

        # Pattern distribution
        cursor.execute('''
            SELECT version_pattern, COUNT(*) as count
            FROM vulnerabilities
            GROUP BY version_pattern
            ORDER BY count DESC
        ''')
        print("\n📊 Version Pattern Distribution:")
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

    parser = argparse.ArgumentParser(description='Load labeled bugs from JSON into vulnerability database')
    parser.add_argument('json_file', help='Path to labeled bugs JSON file')
    parser.add_argument('--db', default='vulnerability_db.sqlite',
                        help='Database path (default: vulnerability_db.sqlite)')
    parser.add_argument('--limit', type=int, help='Limit number of bugs to load (for testing)')
    parser.add_argument('--force', action='store_true', help='Force reload, allow duplicates')

    args = parser.parse_args()

    # Create loader
    loader = LabeledBugLoader(db_path=args.db)

    try:
        loader.connect()
        loader.load_bugs_from_json(
            json_path=args.json_file,
            limit=args.limit,
            skip_duplicates=not args.force
        )
    finally:
        loader.close()

    print(f"\n💾 Database saved to: {args.db}")


if __name__ == '__main__':
    main()
