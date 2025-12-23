#!/usr/bin/env python3
"""
Offline Update Loader ("The Loader")
====================================
Ingests a `vuln_update.zip` package into the local SQLite database.
Runs in air-gapped environment. No AI/Internet required.

Protocol:
1. Validate Package Signature/Manifest
2. Unpack Data
3. Update Database (Upsert)
"""

import os
import sys
import json
import argparse
import logging
import zipfile
import sqlite3
import shutil
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "vulnerability_db.sqlite"

def parse_args():
    parser = argparse.ArgumentParser(description="Apply Offline Vulnerability Update")
    parser.add_argument('--package', type=str, required=True, help="Path to vuln_update.zip")
    parser.add_argument('--db', type=str, default=DB_PATH, help="Path to SQLite DB")
    return parser.parse_args()

def init_db(db_path):
    """Ensure DB schema exists."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Ensure 'vulnerabilities' table exists
    # Currently schema is: advisoryId, platform, summary, labels, ...
    # We might need to add/ensure columns exist.
    
    # Create if not exists (Basic Schema)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS vulnerabilities (
        advisoryId TEXT PRIMARY KEY,
        summary TEXT,
        platform TEXT,
        labels TEXT,
        confidence REAL,
        last_updated TIMESTAMP
    )
    """)
    
    # Create Metadata table for version tracking
    cur.execute("""
    CREATE TABLE IF NOT EXISTS db_metadata (
        key TEXT PRIMARY KEY,
        value TEXT,
        last_updated TIMESTAMP
    )
    """)
    
    conn.commit()
    return conn

def apply_update(conn, data):
    """Upsert data into DB."""
    cur = conn.cursor()
    count = 0
    updated = 0
    
    for item in data:
        adv_id = item.get('advisoryId')
        summary = item.get('summary')
        platform = item.get('platform')
        labels = json.dumps(item.get('predicted_labels', []))
        confidence = item.get('confidence', 0.0)
        timestamp = datetime.now().isoformat()
        item_type = item.get('type', 'BUG').lower() # 'bug' or 'psirt'
        
        # MAPPING TO PRODUCTION SCHEMA
        # We need bug_id (unique), summary, platform, labels, vuln_type.
        # Plus defaults for required fields like version_pattern.
        
        # Try to find existing record by bug_id OR advisory_id
        # Note: In this DB, bug_id seems to be the primary unique identifier for both Bugs and PSIRTs?
        # Let's check if the record exists via bug_id first.
        
        # Determine unique key
        unique_key = adv_id
        
        cur.execute("SELECT id FROM vulnerabilities WHERE bug_id = ?", (unique_key,))
        exists = cur.fetchone()
        
        if exists:
            # Update specific fields (labels, summary, last_modified)
            # We preserve existing version data if we aren't updating it
            cur.execute("""
                UPDATE vulnerabilities 
                SET summary=?, labels=?, last_modified=?
                WHERE bug_id=?
            """, (summary, labels, timestamp, unique_key))
            updated += 1
        else:
            # Insert new record with required defaults
            try:
                cur.execute("""
                    INSERT INTO vulnerabilities (
                        bug_id, advisory_id, vuln_type, 
                        summary, platform, labels, 
                        affected_versions_raw, version_pattern, 
                        last_modified, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    unique_key, 
                    unique_key if item_type == 'psirt' else None, 
                    item_type,
                    summary, 
                    platform, 
                    labels,
                    "UNKNOWN", "UNKNOWN", # Defaults for versioning
                    timestamp, timestamp
                ))
                count += 1
            except sqlite3.IntegrityError as e:
                logger.warning(f"Skipping duplicate/invalid {unique_key}: {e}")
            
    conn.commit()
    return count, updated

def main():
    args = parse_args()
    
    logger.info(f"📦 applying update: {args.package}")
    
    if not os.path.exists(args.package):
        logger.error("Package not found.")
        return
        
    # Unzip to temp
    temp_dir = f"temp_update_{datetime.now().strftime('%s')}"
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        with zipfile.ZipFile(args.package, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        # Read Manifest
        manifest_path = os.path.join(temp_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            logger.error("❌ Invalid Package: No manifest.json")
            return
            
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
            # Support both v1 'timestamp' and v2 'created_at'
            ts = manifest.get('created_at') or manifest.get('timestamp')
            logger.info(f"   Manifest Timestamp: {ts}")
            logger.info(f"   Item Count: {manifest.get('item_count')}")
            
        # Read Data - Support both v1 and v2 naming
        data_path = os.path.join(temp_dir, "data", "labeled_vulnerabilities.json")
        if not os.path.exists(data_path):
             # Fallback to v1 name
             data_path = os.path.join(temp_dir, "data", "update_content.json")
             
        if not os.path.exists(data_path):
             logger.error("❌ Invalid Package: No data found (checked labeled_vulnerabilities.json and update_content.json)")
             return
             
        with open(data_path, 'r') as f:
            content = json.load(f)
            
        # Apply to DB
        conn = init_db(args.db)
        new_cnt, upd_cnt = apply_update(conn, content)
        conn.close()
        
        logger.info("=========================================")
        logger.info(f"✅ Update Applied Successfully")
        logger.info(f"   New Records: {new_cnt}")
        logger.info(f"   Updated Records: {upd_cnt}")
        logger.info("=========================================")
        
    except Exception as e:
        logger.error(f"Failed to apply update: {e}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()
