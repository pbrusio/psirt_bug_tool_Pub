#!/usr/bin/env python3
"""
Enrichment utility for "headline-only" bugs.

Supports two sources:
- API mode: uses Cisco Bug API via cisco_vuln_fetcher helpers
- Mock mode: reads bug_id -> description mappings from a JSON/JSONL file (for testing/offline)

Default behavior:
- Finds vulnerabilities with headline present and summary empty/NULL
- Attempts to fetch a richer summary
- Updates the database (unless --no-db-write is set)
- Logs per-bug results to a JSONL file
"""

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure repo root on sys.path for backend/db/utils and scripts/cisco_vuln_fetcher
import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from backend.db.utils import get_db_connection  # type: ignore

logger = logging.getLogger("enrich_bugs")


def load_targets(db_path: str, limit: Optional[int] = None, force: bool = False) -> List[Dict]:
    """Fetch bugs with headline but empty summary."""
    query = """
        SELECT bug_id, advisory_id, platform, headline, summary
        FROM vulnerabilities
        WHERE headline IS NOT NULL
          AND (summary IS NULL OR summary = '')
    """
    if force:
        # If force, include rows even if summary present (for overwrite), caller decides
        query = """
            SELECT bug_id, advisory_id, platform, headline, summary
            FROM vulnerabilities
            WHERE headline IS NOT NULL
        """

    if limit:
        query += f" LIMIT {int(limit)}"

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def chunked(seq: List, size: int) -> List[List]:
    """Yield chunks of the sequence."""
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def load_mock_descriptions(mock_file: Path) -> Dict[str, str]:
    """Load bug_id -> description mapping from JSON or JSONL."""
    if not mock_file.exists():
        raise FileNotFoundError(f"Mock file not found: {mock_file}")

    mapping: Dict[str, str] = {}
    if mock_file.suffix.lower() == ".jsonl":
        with mock_file.open() as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    bug_id = obj.get("bug_id")
                    desc = obj.get("description") or obj.get("summary")
                    if bug_id and desc:
                        mapping[bug_id] = desc
                except json.JSONDecodeError:
                    continue
    else:
        data = json.loads(mock_file.read_text())
        if isinstance(data, dict):
            mapping = {k: str(v) for k, v in data.items()}
        elif isinstance(data, list):
            for obj in data:
                if not isinstance(obj, dict):
                    continue
                bug_id = obj.get("bug_id") or obj.get("id")
                desc = obj.get("description") or obj.get("summary")
                if bug_id and desc:
                    mapping[bug_id] = desc
    return mapping


def fetch_descriptions_api(bug_ids: List[str]) -> Dict[str, str]:
    """Fetch bug descriptions via Cisco Bug API."""
    try:
        from scripts.cisco_vuln_fetcher import CiscoBugClient, CiscoAuthManager, load_config  # type: ignore
    except Exception as e:
        raise RuntimeError(f"Could not import cisco_vuln_fetcher: {e}")

    cfg = load_config()
    auth = CiscoAuthManager(cfg["client_id"], cfg["client_secret"])
    client = CiscoBugClient(auth)

    details = client.get_bug_details(bug_ids)
    mapping: Dict[str, str] = {}
    for bug in details:
        bug_id = bug.get("bug_id") or bug.get("id")
        desc = bug.get("description") or bug.get("release_note") or bug.get("headline")
        if bug_id and desc:
            mapping[bug_id] = desc
    return mapping


def update_bug_summary(
    db_path: str,
    updates: List[Tuple[str, str]],
) -> None:
    """Persist summaries to DB."""
    now = datetime.now().isoformat()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        for bug_id, summary in updates:
            cursor.execute(
                """
                UPDATE vulnerabilities
                SET summary = ?, last_modified = ?
                WHERE bug_id = ?
                """,
                (summary, now, bug_id),
            )


def ensure_log_dir(log_path: Path) -> None:
    if log_path.parent.exists():
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)


def write_log_line(log_path: Path, record: Dict) -> None:
    with log_path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def process_batch(
    batch: List[Dict],
    mode: str,
    mock_map: Dict[str, str],
) -> Dict[str, Optional[str]]:
    """Fetch descriptions for a batch and return bug_id -> description (or None)."""
    bug_ids = [row["bug_id"] for row in batch]

    if mode == "mock":
        return {bid: mock_map.get(bid) for bid in bug_ids}
    elif mode == "api":
        try:
            return fetch_descriptions_api(bug_ids)
        except Exception as e:
            logger.error(f"API fetch failed for batch: {e}")
            return {bid: None for bid in bug_ids}
    else:
        raise ValueError(f"Unsupported mode: {mode}")


def main():
    parser = argparse.ArgumentParser(description="Enrich headline-only bugs with descriptions.")
    parser.add_argument("--db-path", default="vulnerability_db.sqlite", help="Path to SQLite DB")
    parser.add_argument("--batch-size", type=int, default=25, help="Batch size for fetches")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit on targets")
    parser.add_argument("--mode", choices=["api", "mock"], default="api", help="Fetch mode")
    parser.add_argument("--mock-file", type=str, help="Mock JSON/JSONL file with bug_id->description")
    parser.add_argument("--log-file", type=str, default="output/enrichment_logs/enrich_run.jsonl")
    parser.add_argument("--no-db-write", action="store_true", help="Do not write updates to DB")
    parser.add_argument("--force", action="store_true", help="Process even if summary present (overwrite)")
    parser.add_argument("--min-length", type=int, default=30, help="Minimum description length to accept")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    logger.info("🚀 Enrichment run starting")
    logger.info(f"DB: {args.db_path} | mode: {args.mode} | batch: {args.batch_size}")

    mock_map: Dict[str, str] = {}
    if args.mode == "mock":
        if not args.mock_file:
            parser.error("--mock-file is required in mock mode")
        mock_map = load_mock_descriptions(Path(args.mock_file))
        logger.info(f"Loaded {len(mock_map)} mock descriptions")

    targets = load_targets(args.db_path, args.limit, args.force)
    if not targets:
        logger.info("No targets found. Exiting.")
        return

    logger.info(f"Found {len(targets)} target bugs to enrich")

    log_path = Path(args.log_file)
    ensure_log_dir(log_path)

    updated = 0
    skipped = 0
    failed = 0
    total = len(targets)

    for batch in chunked(targets, args.batch_size):
        desc_map = process_batch(batch, args.mode, mock_map)
        updates: List[Tuple[str, str]] = []

        for row in batch:
            bug_id = row["bug_id"]
            headline = row.get("headline") or ""
            desc = desc_map.get(bug_id)

            status = "failed"
            reason = None

            if not desc:
                failed += 1
                reason = "no_description"
            else:
                desc_str = desc.strip()
                # Basic validation: ensure it's longer than the headline and above threshold
                if len(desc_str) < args.min_length or len(desc_str) <= len(headline or ""):
                    skipped += 1
                    status = "skipped"
                    reason = "too_short"
                else:
                    status = "updated"
                    updates.append((bug_id, desc_str))
                    updated += 1

            write_log_line(
                log_path,
                {
                    "bug_id": bug_id,
                    "status": status,
                    "reason": reason,
                    "source": args.mode,
                    "summary_len": len(desc.strip()) if desc else 0,
                },
            )

        if updates and not args.no_db_write:
            update_bug_summary(args.db_path, updates)
            logger.info(f"Batch updated {len(updates)} bugs")

    logger.info("✅ Enrichment complete")
    logger.info(f"Totals: updated={updated}, skipped={skipped}, failed={failed}, total={total}")


if __name__ == "__main__":
    main()
