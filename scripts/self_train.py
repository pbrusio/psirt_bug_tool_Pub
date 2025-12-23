#!/usr/bin/env python3
"""
Self-Training Engine for Vulnerability Labeling

Uses Foundation-Sec-8B with FAISS RAG to label unlabeled vulnerabilities.
The FAISS index contains ~2,654 labeled examples from data/Labeled_Bugs/
which serve as the "teacher" for predicting labels on the backlog.

Usage:
  # Dry run (50 samples, no DB writes)
  python scripts/self_train.py --sample 50 --no-db-write --verbose

  # Full run (overnight)
  python scripts/self_train.py --threshold 0.85 --output models/silver_labels.parquet

  # Chunked run (restartable)
  python scripts/self_train.py --limit 1000 --offset 0
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3

# Optional imports - check availability
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("Warning: pandas not available, will use JSON output instead of parquet")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Self-training labeler for vulnerability database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run with 50 samples
  python scripts/self_train.py --sample 50 --no-db-write --verbose

  # Full production run
  python scripts/self_train.py --threshold 0.85

  # Resume from offset
  python scripts/self_train.py --limit 1000 --offset 2000
        """
    )

    parser.add_argument('--db-path', default='vulnerability_db.sqlite',
                        help='Path to SQLite database (default: vulnerability_db.sqlite)')
    parser.add_argument('--output', default='models/silver_labels.parquet',
                        help='Output path for silver labels (default: models/silver_labels.parquet)')
    parser.add_argument('--bronze-log', default='output/self_train_bronze.jsonl',
                        help='Output path for bronze labels (default: output/self_train_bronze.jsonl)')
    parser.add_argument('--threshold', type=float, default=0.85,
                        help='Confidence threshold for silver labels (default: 0.85)')
    parser.add_argument('--bronze-threshold', type=float, default=0.50,
                        help='Minimum confidence to log as bronze (default: 0.50)')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Commit to DB every N silver records (default: 100)')
    parser.add_argument('--sample', type=int, default=None,
                        help='Only process N samples (for dry runs)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit query to N records (for chunked runs)')
    parser.add_argument('--offset', type=int, default=0,
                        help='Skip first N records (for resume/chunked runs)')
    parser.add_argument('--no-db-write', action='store_true',
                        help='Do not write to database (dry run mode)')
    parser.add_argument('--verbose', action='store_true',
                        help='Print per-row predictions')
    parser.add_argument('--state-file', default='output/self_train_state.json',
                        help='State file for resume capability')

    return parser.parse_args()


def load_taxonomy():
    """Load valid labels from YAML taxonomy files (authoritative source)"""
    try:
        import yaml
    except ImportError:
        print("Warning: PyYAML not available, taxonomy validation disabled")
        return {}

    taxonomy_files = {
        'IOS-XE': PROJECT_ROOT / 'taxonomies' / 'features.yml',
        'IOS-XR': PROJECT_ROOT / 'taxonomies' / 'features_iosxr.yml',
        'ASA': PROJECT_ROOT / 'taxonomies' / 'features_asa.yml',
        'FTD': PROJECT_ROOT / 'taxonomies' / 'features_asa.yml',  # FTD uses ASA taxonomy
        'NX-OS': PROJECT_ROOT / 'taxonomies' / 'features_nxos.yml',
    }

    platform_labels = {}
    all_labels = set()

    for platform, filepath in taxonomy_files.items():
        if not filepath.exists():
            print(f"  Warning: {filepath} not found, skipping {platform}")
            platform_labels[platform] = set()
            continue

        with open(filepath) as f:
            features = yaml.safe_load(f)

        labels = {feat['label'] for feat in features}
        platform_labels[platform] = labels
        all_labels.update(labels)
        print(f"  {platform}: {len(labels)} labels")

    print(f"Loaded taxonomy: {len(all_labels)} total labels across {len(platform_labels)} platforms")
    return platform_labels


def get_unlabeled_bugs(db_path, limit=None, offset=0):
    """Query unlabeled bugs from database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT bug_id, advisory_id, platform, summary, headline
        FROM vulnerabilities
        WHERE labels_source = 'unlabeled'
           OR labels_source IS NULL
           OR labels = ''
           OR labels = '[]'
        ORDER BY bug_id
    """

    if limit:
        query += f" LIMIT {limit}"
    if offset:
        query += f" OFFSET {offset}"

    cursor.execute(query)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return rows


def get_total_unlabeled_count(db_path):
    """Get total count of unlabeled bugs"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM vulnerabilities
        WHERE labels_source = 'unlabeled'
           OR labels_source IS NULL
           OR labels = ''
           OR labels = '[]'
    """)
    count = cursor.fetchone()[0]
    conn.close()
    return count


def enforce_taxonomy(predicted_labels, platform, platform_labels):
    """Filter out any labels not in the platform's taxonomy"""
    if not platform_labels:
        return predicted_labels  # No taxonomy loaded, skip validation

    # Get valid labels for this platform
    valid_for_platform = platform_labels.get(platform, set())

    # If platform not found, accept all labels from any platform
    if not valid_for_platform:
        all_labels = set()
        for labels in platform_labels.values():
            all_labels.update(labels)
        valid_for_platform = all_labels

    valid = [l for l in predicted_labels if l in valid_for_platform]
    invalid = [l for l in predicted_labels if l not in valid_for_platform]

    if invalid:
        print(f"  Filtered out invalid labels: {invalid}")

    return valid


def grade_prediction(confidence, predicted_labels, silver_threshold, bronze_threshold):
    """Grade a prediction as silver, bronze, or skip"""
    if confidence >= silver_threshold and len(predicted_labels) > 0:
        return 'silver'
    elif confidence >= bronze_threshold and len(predicted_labels) > 0:
        return 'bronze'
    else:
        return 'skip'


def save_state(state_file, last_bug_id, processed, silver_count, bronze_count):
    """Save progress state for resume capability"""
    state = {
        'last_bug_id': last_bug_id,
        'processed': processed,
        'silver_count': silver_count,
        'bronze_count': bronze_count,
        'timestamp': datetime.utcnow().isoformat()
    }
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def write_silver_to_db(db_path, silver_batch):
    """Write silver labels to database"""
    if not silver_batch:
        return

    # Use SafeSQLiteConnection if available, otherwise basic connection
    try:
        from backend.db.utils import SafeSQLiteConnection
        conn_context = SafeSQLiteConnection(db_path)
    except ImportError:
        # Fallback to basic connection
        class BasicConnection:
            def __init__(self, path):
                self.path = path
                self.conn = None
            def __enter__(self):
                self.conn = sqlite3.connect(self.path, timeout=30)
                return self.conn
            def __exit__(self, *args):
                if self.conn:
                    self.conn.commit()
                    self.conn.close()
        conn_context = BasicConnection(db_path)

    with conn_context as conn:
        cursor = conn.cursor()
        for record in silver_batch:
            cursor.execute("""
                UPDATE vulnerabilities
                SET labels = ?, labels_source = ?, reasoning = ?
                WHERE bug_id = ?
            """, (
                json.dumps(record['labels']),
                'self_trained_v1',
                record.get('reasoning', ''),
                record['bug_id']
            ))
        conn.commit()


def write_bronze_log(bronze_log_path, record):
    """Append a bronze record to JSONL log"""
    os.makedirs(os.path.dirname(bronze_log_path), exist_ok=True)
    with open(bronze_log_path, 'a') as f:
        f.write(json.dumps(record) + '\n')


def write_silver_output(output_path, silver_records):
    """Write silver records to parquet or JSON"""
    if not silver_records:
        print("No silver records to write")
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if HAS_PANDAS and output_path.endswith('.parquet'):
        df = pd.DataFrame(silver_records)
        df.to_parquet(output_path, index=False)
        print(f"Wrote {len(silver_records)} silver records to {output_path}")
    else:
        # Fallback to JSON
        json_path = output_path.replace('.parquet', '.json')
        with open(json_path, 'w') as f:
            json.dump(silver_records, f, indent=2)
        print(f"Wrote {len(silver_records)} silver records to {json_path}")


def main():
    args = parse_args()

    print("=" * 60)
    print("  Self-Training Engine for Vulnerability Labeling")
    print("=" * 60)
    print()

    # Validate paths
    if not os.path.exists(args.db_path):
        print(f"Error: Database not found: {args.db_path}")
        print("Run from project root directory.")
        sys.exit(1)

    # Load taxonomy (platform-specific labels from YAML files)
    platform_labels = load_taxonomy()

    # Get total count
    total_unlabeled = get_total_unlabeled_count(args.db_path)
    print(f"Total unlabeled bugs in database: {total_unlabeled}")

    # Determine how many to process
    process_count = args.sample if args.sample else (args.limit if args.limit else total_unlabeled)
    print(f"Will process: {process_count} bugs (offset: {args.offset})")
    print(f"Silver threshold: {args.threshold}")
    print(f"Bronze threshold: {args.bronze_threshold}")
    print(f"DB writes: {'DISABLED (dry run)' if args.no_db_write else 'ENABLED'}")
    print()

    # Load the labeler (this takes ~45-60s for model loading)
    print("Loading FewShotPSIRTLabeler (SEC-8B + FAISS)...")
    print("This may take 45-60 seconds for model initialization...")
    start_load = time.time()

    try:
        from fewshot_inference import FewShotPSIRTLabeler
        labeler = FewShotPSIRTLabeler()
    except Exception as e:
        print(f"Error loading labeler: {e}")
        print("Make sure you're running from the project root and models are available.")
        sys.exit(1)

    load_time = time.time() - start_load
    print(f"Labeler loaded in {load_time:.1f}s")
    print()

    # Get bugs to process
    limit = args.sample if args.sample else args.limit
    bugs = get_unlabeled_bugs(args.db_path, limit=limit, offset=args.offset)
    print(f"Fetched {len(bugs)} bugs to process")
    print()

    if not bugs:
        print("No unlabeled bugs found. Nothing to do.")
        return

    # Initialize counters and storage
    silver_records = []
    silver_batch = []  # For DB writes
    bronze_count = 0
    skip_count = 0
    error_count = 0
    confidences = []

    start_time = time.time()

    print("Starting predictions...")
    print("-" * 60)

    for i, bug in enumerate(bugs, 1):
        bug_id = bug['bug_id']
        platform = bug['platform']
        summary = bug['summary'] or bug['headline'] or ''
        advisory_id = bug.get('advisory_id')

        if not summary.strip():
            if args.verbose:
                print(f"[{i}/{len(bugs)}] {bug_id}: SKIP (no summary)")
            skip_count += 1
            continue

        try:
            # Run prediction
            result = labeler.predict_labels(
                psirt_summary=summary,
                platform=platform,
                advisory_id=advisory_id,
                k=5,
                max_new_tokens=300
            )

            predicted_labels = result.get('predicted_labels', [])
            confidence = result.get('confidence', 0.0)
            source = result.get('source', 'few_shot')
            similarity_scores = result.get('similarity_scores', [])
            reasoning = result.get('reasoning', '')

            # Enforce taxonomy (platform-specific)
            predicted_labels = enforce_taxonomy(predicted_labels, platform, platform_labels)

            # Grade the prediction
            grade = grade_prediction(
                confidence, predicted_labels,
                args.threshold, args.bronze_threshold
            )

            confidences.append(confidence)

            if args.verbose:
                grade_symbol = {'silver': '+', 'bronze': '~', 'skip': '-'}[grade]
                print(f"[{i}/{len(bugs)}] {bug_id} ({platform}): {grade_symbol} "
                      f"conf={confidence:.3f} labels={predicted_labels}")

            if grade == 'silver':
                record = {
                    'bug_id': bug_id,
                    'advisory_id': advisory_id,
                    'platform': platform,
                    'labels': predicted_labels,
                    'reasoning': reasoning,
                    'confidence': confidence,
                    'source': source,
                    'labels_source': 'self_trained_v1',
                    'timestamp': datetime.utcnow().isoformat()
                }
                silver_records.append(record)
                silver_batch.append(record)

                # Batch write to DB
                if not args.no_db_write and len(silver_batch) >= args.batch_size:
                    write_silver_to_db(args.db_path, silver_batch)
                    silver_batch = []

            elif grade == 'bronze':
                bronze_count += 1
                bronze_record = {
                    'bug_id': bug_id,
                    'platform': platform,
                    'summary': summary[:500],
                    'predicted_labels': predicted_labels,
                    'reasoning': reasoning,
                    'confidence': confidence,
                    'similarity_scores': similarity_scores[:3],
                    'timestamp': datetime.utcnow().isoformat()
                }
                write_bronze_log(args.bronze_log, bronze_record)

            else:
                skip_count += 1

        except Exception as e:
            error_count += 1
            if args.verbose:
                print(f"[{i}/{len(bugs)}] {bug_id}: ERROR - {e}")
            continue

        # Progress logging every 50 items
        if i % 50 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed
            eta = (len(bugs) - i) / rate / 3600 if rate > 0 else 0
            avg_conf = sum(confidences) / len(confidences) if confidences else 0

            print(f"\n[Progress] {i}/{len(bugs)} ({100*i/len(bugs):.1f}%)")
            print(f"  Silver: {len(silver_records)}, Bronze: {bronze_count}, "
                  f"Skip: {skip_count}, Errors: {error_count}")
            print(f"  Avg confidence: {avg_conf:.3f}")
            print(f"  Rate: {rate:.2f}/sec, ETA: {eta:.2f}h\n")

            # Save state
            save_state(args.state_file, bug_id, i, len(silver_records), bronze_count)

    # Final batch write
    if not args.no_db_write and silver_batch:
        write_silver_to_db(args.db_path, silver_batch)

    # Write silver output file
    write_silver_output(args.output, silver_records)

    # Final stats
    elapsed = time.time() - start_time
    avg_conf = sum(confidences) / len(confidences) if confidences else 0

    print()
    print("=" * 60)
    print("  Self-Training Complete")
    print("=" * 60)
    print()
    print(f"Processed: {len(bugs)}")
    print(f"Silver (>={args.threshold}): {len(silver_records)} ({100*len(silver_records)/len(bugs):.1f}%)")
    print(f"Bronze ({args.bronze_threshold}-{args.threshold}): {bronze_count} ({100*bronze_count/len(bugs):.1f}%)")
    print(f"Skipped: {skip_count}")
    print(f"Errors: {error_count}")
    print(f"Average confidence: {avg_conf:.3f}")
    print()
    print(f"Elapsed time: {elapsed/60:.1f} minutes ({elapsed/3600:.2f} hours)")
    print(f"Rate: {len(bugs)/elapsed:.2f} bugs/second")
    print()
    print(f"Silver output: {args.output}")
    print(f"Bronze log: {args.bronze_log}")
    if args.no_db_write:
        print("\nNote: --no-db-write was set, database was NOT updated")
    else:
        print(f"\nDatabase updated: {len(silver_records)} bugs now have labels_source='self_trained_v1'")


if __name__ == '__main__':
    main()
