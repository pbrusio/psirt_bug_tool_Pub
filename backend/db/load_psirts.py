import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path('vulnerability_db.sqlite')
PSIRTS_JSON_PATH = Path('output/psirts.json')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_psirts():
    if not PSIRTS_JSON_PATH.exists():
        logger.error(f"PSIRT file not found: {PSIRTS_JSON_PATH}")
        return

    logger.info(f"Loading PSIRTs from {PSIRTS_JSON_PATH}")
    
    with open(PSIRTS_JSON_PATH, 'r') as f:
        try:
            psirts = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")
            return

    conn = get_db_connection()
    cursor = conn.cursor()

    inserted = 0
    skipped = 0
    errors = 0

    for item in psirts:
        try:
            # Extract fields
            bug_id = item.get('advisoryId')
            summary = item.get('summary', '')
            platform = item.get('platform', 'Unknown')
            
            # Metadata
            meta = item.get('_meta', {})
            severity_str = meta.get('severity', 'Medium')
            
            # Map severity string to int
            severity_map = {
                'Critical': 1,
                'High': 2,
                'Medium': 3,
                'Low': 4,
                'Informational': 4
            }
            severity = severity_map.get(severity_str, 3)
            
            published = meta.get('first_published', datetime.now().isoformat())
            url = meta.get('url', '')

            # Insert into vulnerabilities table
            # PSIRTs often don't have structured affected_versions in this JSON, 
            # so we might leave it empty, or if present, use it.
            # Ideally, we should fetch version data, but for now we load what we have.
            
            cursor.execute('''
                INSERT INTO vulnerabilities (
                    bug_id, headline, summary,
                    platform, severity, status,
                    vuln_type, url,
                    last_modified, affected_versions_raw, version_pattern
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bug_id) DO UPDATE SET
                    summary = excluded.summary,
                    vuln_type = excluded.vuln_type,
                    last_modified = CURRENT_TIMESTAMP
            ''', (
                bug_id,
                summary[:100] + "...",  # Headline as truncated summary
                summary,
                platform,
                severity,
                'Open', # Status
                'psirt', # vuln_type
                url,
                datetime.now().isoformat(),
                '', # affected_versions_raw (empty for PSIRT if unknown)
                'UNKNOWN' # version_pattern
            ))
            
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1 # Update counted as skip for now or we can track updates

        except Exception as e:
            logger.error(f"Error inserting PSIRT {item.get('advisoryId')}: {e}")
            errors += 1

    conn.commit()
    conn.close()
    
    logger.info(f"Analysis Complete: Inserted/Updated: {inserted}, Errors: {errors}")

if __name__ == "__main__":
    load_psirts()
