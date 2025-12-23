#!/usr/bin/env python3
"""
One-Time PSIRT Version Data Fetcher
====================================
Fetches affected version information for PSIRTs in the database that are
missing version data. Uses the existing Cisco openVuln API infrastructure.

This is a ONE-TIME migration script to populate affected_versions_raw for
existing PSIRTs in the database.

Usage:
    python scripts/fetch_psirt_versions.py                    # Dry run (inspect only)
    python scripts/fetch_psirt_versions.py --apply            # Apply updates to DB
    python scripts/fetch_psirt_versions.py --sample 5         # Fetch 5 PSIRTs for testing
    python scripts/fetch_psirt_versions.py --inspect-one cisco-sa-xxx  # Inspect one advisory

Author: Generated for PSIRT Version Data Population Task
Date: 2025-12-16
"""

import os
import sys
import json
import sqlite3
import logging
import argparse
import re
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.cisco_vuln_fetcher import (
    CiscoAuthManager,
    CiscoPSIRTClient,
    RateLimiter,
    CiscoAPIError,
    load_config
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PSIRTVersionInfo:
    """Extracted version information for a PSIRT."""
    advisory_id: str
    affected_versions_raw: str  # Space-separated versions
    fixed_versions_raw: str     # Space-separated fixed versions
    version_pattern: str        # EXPLICIT, RANGE, etc.
    extraction_method: str      # How we extracted the versions
    raw_product_data: Optional[str] = None  # JSON of raw API data for debugging


def extract_cisco_versions(text: str) -> Set[str]:
    """
    Extract Cisco IOS/IOS-XE/IOS-XR version strings from text.

    Patterns recognized:
    - 17.10.1, 17.3.5a, 16.12.4
    - IOS XE 17.10.1
    - Release 17.3
    - 7.x versions for IOS-XR
    """
    versions = set()

    # Pattern for Cisco IOS/IOS-XE versions: XX.YY.ZZ or XX.YY.ZZa
    iosxe_pattern = r'\b(1[567]\.\d{1,2}\.\d{1,2}[a-z]?)\b'
    matches = re.findall(iosxe_pattern, text, re.IGNORECASE)
    versions.update(matches)

    # Pattern for IOS-XR versions: 7.X.Y, 6.X.Y
    iosxr_pattern = r'\b([67]\.\d{1,2}\.\d{1,2})\b'
    matches = re.findall(iosxr_pattern, text, re.IGNORECASE)
    versions.update(matches)

    # Pattern for ASA versions: 9.X.Y
    asa_pattern = r'\b(9\.\d{1,2}\.\d{1,2})\b'
    matches = re.findall(asa_pattern, text, re.IGNORECASE)
    versions.update(matches)

    # Pattern for NX-OS versions: 9.X(Y), 10.X(Y)
    nxos_pattern = r'\b([789]|10)\.\d{1,2}\(\d+\)\b'
    matches = re.findall(nxos_pattern, text, re.IGNORECASE)
    versions.update(matches)

    return versions


def parse_advisory_for_versions(advisory: Dict) -> PSIRTVersionInfo:
    """
    Parse a raw advisory API response to extract version information.

    The Cisco API response typically contains:
    - productNames: List of affected product names (may include version info)
    - cves: CVE identifiers
    - advisoryId: The cisco-sa-xxx identifier
    - firstFixed: Sometimes contains version info

    We also look in the bugIDs field which may link to bugs with version data.
    """
    advisory_id = advisory.get('advisoryId', 'unknown')

    affected_versions = set()
    fixed_versions = set()
    extraction_methods = []

    # Method 1: Extract from productNames
    product_names = advisory.get('productNames', []) or []
    if isinstance(product_names, str):
        product_names = [product_names]

    for product in product_names:
        versions = extract_cisco_versions(str(product))
        if versions:
            affected_versions.update(versions)
            extraction_methods.append('productNames')

    # Method 2: Extract from summary/title
    summary = advisory.get('summary', '') or ''
    title = advisory.get('advisoryTitle', '') or ''
    text_versions = extract_cisco_versions(f"{title} {summary}")
    if text_versions:
        affected_versions.update(text_versions)
        extraction_methods.append('summary/title')

    # Method 3: Check firstFixed field
    first_fixed = advisory.get('firstFixed', '') or ''
    if first_fixed:
        fixed_vers = extract_cisco_versions(str(first_fixed))
        if fixed_vers:
            fixed_versions.update(fixed_vers)
            extraction_methods.append('firstFixed')

    # Method 4: Check ciscoBugIDs for patterns (some have version info)
    bug_ids = advisory.get('ciscoBugIDs', []) or advisory.get('bugIDs', []) or []
    if isinstance(bug_ids, str):
        bug_ids = [bug_ids]

    # Method 5: Check the entire raw response for version patterns
    raw_text = json.dumps(advisory)
    all_versions = extract_cisco_versions(raw_text)

    # Versions found in raw that weren't in specific fields
    additional = all_versions - affected_versions - fixed_versions
    if additional:
        affected_versions.update(additional)
        extraction_methods.append('raw_response')

    # Determine version pattern
    if affected_versions:
        version_pattern = 'EXPLICIT'
    else:
        version_pattern = 'UNKNOWN'

    return PSIRTVersionInfo(
        advisory_id=advisory_id,
        affected_versions_raw=' '.join(sorted(affected_versions)),
        fixed_versions_raw=' '.join(sorted(fixed_versions)),
        version_pattern=version_pattern,
        extraction_method=', '.join(set(extraction_methods)) if extraction_methods else 'none',
        raw_product_data=json.dumps(product_names)[:500] if product_names else None
    )


def get_psirts_without_versions(db_path: str) -> List[Tuple[str, str]]:
    """
    Get list of PSIRTs that are missing version data.

    Returns:
        List of (advisory_id, platform) tuples
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find PSIRTs with empty or NULL affected_versions_raw
    cursor.execute("""
        SELECT bug_id, platform
        FROM vulnerabilities
        WHERE vuln_type = 'psirt'
        AND (affected_versions_raw IS NULL OR length(affected_versions_raw) = 0)
        ORDER BY platform, bug_id
    """)

    results = cursor.fetchall()
    conn.close()

    return results


def update_psirt_version(
    db_path: str,
    advisory_id: str,
    affected_versions_raw: str,
    version_pattern: str,
    dry_run: bool = True
) -> bool:
    """
    Update a single PSIRT's version data in the database.

    Args:
        db_path: Path to SQLite database
        advisory_id: The cisco-sa-xxx identifier
        affected_versions_raw: Space-separated version string
        version_pattern: EXPLICIT, RANGE, etc.
        dry_run: If True, don't actually modify the database

    Returns:
        True if update was successful (or would be in dry run)
    """
    if dry_run:
        logger.info(f"   [DRY RUN] Would update {advisory_id}: '{affected_versions_raw[:50]}...'")
        return True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE vulnerabilities
            SET affected_versions_raw = ?,
                version_pattern = ?
            WHERE bug_id = ? AND vuln_type = 'psirt'
        """, (affected_versions_raw, version_pattern, advisory_id))

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected > 0:
            logger.info(f"   [UPDATED] {advisory_id}: '{affected_versions_raw[:50]}...'")
            return True
        else:
            logger.warning(f"   [NOT FOUND] {advisory_id} not found in database")
            return False

    except Exception as e:
        logger.error(f"   [ERROR] Failed to update {advisory_id}: {e}")
        return False


def inspect_advisory(client: CiscoPSIRTClient, advisory_id: str):
    """
    Fetch and display the full raw API response for an advisory.
    Useful for understanding the data structure.
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"INSPECTING ADVISORY: {advisory_id}")
    logger.info(f"{'='*60}")

    try:
        advisory = client.get_by_advisory_id(advisory_id)
        if advisory:
            print(json.dumps(advisory, indent=2))

            # Also show extracted versions
            version_info = parse_advisory_for_versions(advisory)
            print(f"\n--- EXTRACTED VERSION INFO ---")
            print(f"Affected versions: {version_info.affected_versions_raw}")
            print(f"Fixed versions: {version_info.fixed_versions_raw}")
            print(f"Pattern: {version_info.version_pattern}")
            print(f"Extraction method: {version_info.extraction_method}")
        else:
            logger.warning(f"No data returned for {advisory_id}")
    except CiscoAPIError as e:
        logger.error(f"API error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch version data for PSIRTs missing affected_versions_raw",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run - see what would be updated
  python scripts/fetch_psirt_versions.py

  # Apply updates to database
  python scripts/fetch_psirt_versions.py --apply

  # Test with just 5 PSIRTs
  python scripts/fetch_psirt_versions.py --sample 5

  # Inspect one advisory's raw API response
  python scripts/fetch_psirt_versions.py --inspect-one cisco-sa-20231018-iosxe-webui

  # Use specific database
  python scripts/fetch_psirt_versions.py --db /path/to/vulnerability_db.sqlite
        """
    )

    parser.add_argument('--db', type=str, default='vulnerability_db.sqlite',
                        help="Path to SQLite database")
    parser.add_argument('--apply', action='store_true',
                        help="Apply updates to database (default is dry run)")
    parser.add_argument('--sample', type=int, default=0,
                        help="Only process N PSIRTs (for testing)")
    parser.add_argument('--inspect-one', type=str,
                        help="Fetch and display raw API response for one advisory")
    parser.add_argument('--env', type=str, default='.env',
                        help="Path to .env file with API credentials")
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Show more detailed output")

    args = parser.parse_args()

    # Load API credentials
    if args.env and os.path.exists(args.env):
        from dotenv import load_dotenv
        load_dotenv(args.env)

    try:
        config = load_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please set CISCO_CLIENT_ID and CISCO_CLIENT_SECRET in .env file")
        sys.exit(1)

    # Initialize API client
    auth = CiscoAuthManager(config['client_id'], config['client_secret'])
    rate_limiter = RateLimiter(min_interval=2.0)  # 2 seconds between requests
    client = CiscoPSIRTClient(auth, rate_limiter)

    # Handle single advisory inspection
    if args.inspect_one:
        inspect_advisory(client, args.inspect_one)
        return

    # Check database exists
    if not os.path.exists(args.db):
        logger.error(f"Database not found: {args.db}")
        sys.exit(1)

    # Get PSIRTs without version data
    logger.info(f"\n{'='*60}")
    logger.info("PSIRT VERSION DATA FETCHER")
    logger.info(f"{'='*60}")
    logger.info(f"Database: {args.db}")
    logger.info(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")

    psirts = get_psirts_without_versions(args.db)
    logger.info(f"Found {len(psirts)} PSIRTs without version data")

    if args.sample > 0:
        psirts = psirts[:args.sample]
        logger.info(f"Processing sample of {len(psirts)} PSIRTs")

    if not psirts:
        logger.info("No PSIRTs need version data. Exiting.")
        return

    # Process each PSIRT
    stats = {
        'processed': 0,
        'updated': 0,
        'no_versions': 0,
        'api_errors': 0
    }

    logger.info(f"\nProcessing {len(psirts)} PSIRTs...")
    logger.info("-" * 40)

    for i, (advisory_id, platform) in enumerate(psirts, 1):
        logger.info(f"[{i}/{len(psirts)}] {advisory_id} ({platform})")

        try:
            # Fetch advisory from API
            advisory = client.get_by_advisory_id(advisory_id)

            if not advisory:
                logger.warning(f"   No data returned from API for {advisory_id}")
                stats['api_errors'] += 1
                continue

            # Extract version information
            version_info = parse_advisory_for_versions(advisory)

            if args.verbose:
                logger.info(f"   Extraction method: {version_info.extraction_method}")
                logger.info(f"   Affected: {version_info.affected_versions_raw[:80] if version_info.affected_versions_raw else 'none'}")

            if version_info.affected_versions_raw:
                # Update database
                success = update_psirt_version(
                    args.db,
                    advisory_id,
                    version_info.affected_versions_raw,
                    version_info.version_pattern,
                    dry_run=not args.apply
                )
                if success:
                    stats['updated'] += 1
            else:
                logger.info(f"   No versions extracted for {advisory_id}")
                stats['no_versions'] += 1

            stats['processed'] += 1

        except CiscoAPIError as e:
            logger.error(f"   API error for {advisory_id}: {e}")
            stats['api_errors'] += 1
            continue

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Processed: {stats['processed']}")
    logger.info(f"Updated: {stats['updated']}")
    logger.info(f"No versions found: {stats['no_versions']}")
    logger.info(f"API errors: {stats['api_errors']}")

    if not args.apply:
        logger.info("\n[DRY RUN] No changes were made. Use --apply to update database.")
    else:
        logger.info(f"\n[APPLIED] Updated {stats['updated']} PSIRTs in database.")


if __name__ == "__main__":
    main()
