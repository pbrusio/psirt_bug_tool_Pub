"""
Incremental Update System for Vulnerability Database

Tracks last update timestamp and only inserts new/modified bugs.
Uses db_metadata table to store last update date.
"""

import sqlite3
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.db.load_bugs import BugLoader


class IncrementalUpdater:
    """
    Handles incremental updates to vulnerability database.

    Workflow:
    1. Check last update timestamp from db_metadata
    2. Load only bugs modified after last update
    3. Update metadata with new timestamp
    """

    def __init__(self, db_path: str = 'vulnerability_db.sqlite'):
        self.db_path = db_path
        self.loader = BugLoader(db_path)

    def get_last_update(self) -> str:
        """
        Get last update timestamp from database.

        Returns:
            ISO timestamp string or '' if never updated
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM db_metadata WHERE key = 'last_update'")
        row = cursor.fetchone()

        conn.close()

        if row and row['value']:
            return row['value']
        else:
            return ''

    def update_last_update(self, timestamp: str):
        """
        Update last update timestamp in database.

        Args:
            timestamp: ISO timestamp string
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE db_metadata
            SET value = ?, updated_at = ?
            WHERE key = 'last_update'
        ''', (timestamp, timestamp))

        conn.commit()
        conn.close()

    def incremental_load(
        self,
        bugs_csv_path: str,
        training_csv_path: str = 'training_data_bugs_20251008_142230.csv'
    ):
        """
        Perform incremental load of bugs.

        Only loads bugs that:
        - Don't already exist in database (by bug_id)
        - OR have been modified since last update

        Args:
            bugs_csv_path: Path to bugs CSV file
            training_csv_path: Path to training data CSV (for labels)
        """
        last_update = self.get_last_update()

        if last_update:
            print(f"Last update: {last_update}")
            print("Loading only new/modified bugs since last update...")
        else:
            print("No previous updates found. Performing initial load...")

        # Use loader with skip_duplicates=True (default)
        self.loader.connect()
        self.loader.load_bugs_from_csv(
            bugs_csv_path=bugs_csv_path,
            training_csv_path=training_csv_path,
            skip_duplicates=True  # Skip bugs already in DB
        )
        self.loader.close()

        # Update timestamp
        now = datetime.now().isoformat()
        self.update_last_update(now)

        print(f"\nUpdate complete. New timestamp: {now}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Incremental update of vulnerability database')
    parser.add_argument('bugs_csv', help='Path to bugs CSV file')
    parser.add_argument('--training-csv', default='training_data_bugs_20251008_142230.csv',
                        help='Path to training data CSV (default: training_data_bugs_20251008_142230.csv)')
    parser.add_argument('--db', default='vulnerability_db.sqlite',
                        help='Database path (default: vulnerability_db.sqlite)')

    args = parser.parse_args()

    updater = IncrementalUpdater(db_path=args.db)
    updater.incremental_load(
        bugs_csv_path=args.bugs_csv,
        training_csv_path=args.training_csv
    )


if __name__ == '__main__':
    main()
