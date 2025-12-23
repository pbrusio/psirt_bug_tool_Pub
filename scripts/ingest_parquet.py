
import pandas as pd
import sqlite3
import json
import uuid
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.db.load_labeled_bugs_json import LabeledBugLoader

def ingest_parquet(parquet_path: str, db_path: str):
    """Ingest parquet data into sqlite db"""
    print(f"Loading {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    print(f"Found {len(df)} records")

    loader = LabeledBugLoader(db_path)
    loader.connect()

    count = 0
    skipped = 0
    
    # Pre-check if DB is already populated to avoid duplicate work if not forced
    cursor = loader.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vulnerabilities")
    existing_count = cursor.fetchone()[0]
    if existing_count > 0:
        print(f"Database already contains {existing_count} records.")
        # Proceeding anyway to ensure our test set is there, but LabeledBugLoader skips duplicates

    for _, row in df.iterrows():
        # Map parquet columns to LabeledBugLoader expected format
        try:
            # Handle numpy arrays/lists for labels
            labels = row['labels_list']
            if hasattr(labels, 'tolist'):
                labels = labels.tolist()
            elif isinstance(labels, str):
                # Try to parse if string
                try:
                    labels = json.loads(labels.replace("'", '"'))
                except:
                    labels = []
            
            if not labels:
                continue

            bug_data = {
                'bug_id': row['advisoryId'],
                'platform': row['platform'],
                'summary': row['summary'],
                'labels_gpt': labels,
                'confidence': 'HIGH', # Assuming training data is high confidence
                'severity': '3', # Default
                'affected_versions': '', 
                'fixed_versions': '',
                'status': 'Open',
                'timestamp': datetime.now().isoformat()
            }
            
            # Use the internal parsing logic
            parsed_bug = loader.parse_bug_json(bug_data)
            
            if parsed_bug:
                # Add advisory_id since it's a PSIRT
                parsed_bug['advisory_id'] = row['advisoryId']
                
                # Check duplicate
                cursor.execute('SELECT id FROM vulnerabilities WHERE bug_id = ?', (parsed_bug['bug_id'],))
                if cursor.fetchone():
                    skipped += 1
                    continue

                loader.insert_vulnerability(parsed_bug)
                count += 1
                
                if count % 100 == 0:
                    print(f"Inserted {count} records...")

        except Exception as e:
            print(f"Error processing row: {e}")
            continue

    loader.conn.commit()
    loader.close()
    print(f"Finished. Inserted: {count}, Skipped (dup): {skipped}")

if __name__ == "__main__":
    ingest_parquet('models/labeled_examples.parquet', 'vulnerability_db.sqlite')
