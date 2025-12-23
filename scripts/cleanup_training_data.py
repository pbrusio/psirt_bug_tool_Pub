#!/usr/bin/env python3
"""
CVE-EVAL Data Cleanup Script
============================

This script cleans the training data by:
1. Removing examples with contaminated/mislabeled data
2. Filtering out non-IOS-XE platform examples from IOS-XE labels
3. Deduplicating repeated advisories
4. Relabeling misclassified examples where possible
5. Generating a cleanup report

Based on data quality issues identified during taxonomy enrichment sessions.

Usage:
    python cleanup_training_data.py --input models/labeled_examples.parquet --output models/labeled_examples_cleaned.parquet
    python cleanup_training_data.py --dry-run  # Preview changes without writing
    python cleanup_training_data.py --report   # Generate detailed report only
"""

import argparse
import json
import re
import pandas as pd
import yaml
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional

# =============================================================================
# CONTAMINATION DEFINITIONS (from taxonomy enrichment sessions)
# =============================================================================

# Labels with CRITICALLY contaminated training data (0% valid examples)
# These labels should have ALL their examples removed and re-sourced
CRITICALLY_CONTAMINATED_LABELS = {
    'SYS_Boot_Upgrade',      # All 5 examples are unrelated (AP VLAN, NDFC PnP, WLC CDP, etc.)
    'APP_IOx',               # All 5 examples are DCNM/NDFC REST API bugs, not IOS-XE IOx
    'SEC_CoPP',              # All 5 examples are boot/CLI/web UI bugs, not Control Plane Policing
    'IP_DHCP_Server',        # All 5 examples are mDNS gateway vulnerabilities
    'MGMT_NTP',              # All 5 examples are mDNS gateway vulnerabilities
    'IP_WCCP',               # Single example is AAA/ISE ordering in DNA Center
    'IP_Unnumbered',         # All 5 examples are IPv4 fragmentation/VFR DoS
    'IP_PrefixList',         # All 5 examples are SD-WAN packet filter bypass
    'IP_NHRP_DMVPN',         # All 5 examples are SD-WAN UTD/IPsec tunnel issues
}

# Labels with HIGHLY contaminated data (>50% invalid examples)
HIGHLY_CONTAMINATED_LABELS = {
    'HA_Redundancy_SSO',     # 4/5 examples are WLC CDP DoS or SD-WAN vDaemon
    'MGMT_Syslog',           # All examples are TWAMP server DoS, not syslog
    'MGMT_SNMP',             # 4/5 examples are ASA/FTD/FMC, not IOS-XE
    'MGMT_SSH_HTTP',         # All examples are ISE XSS, AP SSH, DCNM SSRF
    'IF_Physical',           # 4/5 examples are Aironet AP, not IOS-XE switch interfaces
    'QOS_MQC_ClassPolicy',   # 4/5 examples are UTD Snort IPS policy bypass
    'SEC_StormControl',      # Examples include DHCP snooping, wireless AP, mDNS
    'MCAST_PIM',             # 3/5 examples are mDNS gateway vulnerabilities
    'MCAST_SSM',             # Single example is SDA L2 flooding, not SSM
}

# Known mislabeled advisory IDs that appear across multiple wrong labels
MDNS_CONTAMINATED_ADVISORY = 'cisco-sa-wlc-mdns-dos'
MDNS_AFFECTED_LABELS = [
    'IP_DHCP_Server', 'MGMT_NTP', 'MCAST_PIM', 'SEC_StormControl',
    'IF_Physical', 'L2_STP'  # May appear in others
]

# Platform patterns that indicate NON-IOS-XE content
NON_IOSXE_PLATFORM_PATTERNS = [
    r'\bASA\b',
    r'\bFTD\b',
    r'\bFirepower\b',
    r'\bFMC\b',
    r'\bFirepower Management Center\b',
    r'\bISE\b',
    r'\bIdentity Services Engine\b',
    r'\bDCNM\b',
    r'\bNDFC\b',
    r'\bNexus Dashboard\b',
    r'\bNFVIS\b',
    r'\bAironet\b',
    r'\bWLC\b(?!.*IOS-XE)',  # WLC without IOS-XE context
    r'\bWireless LAN Controller\b(?!.*9800)',  # Non-C9800 WLC
    r'\bUCS\b',
    r'\bHyperFlex\b',
    r'\bMeraki\b',
    r'\bWebex\b',
    r'\bDuo\b',
    r'\bUmbrella\b',
    r'\bPrime\s+Infrastructure\b',
    r'\bEPNM\b',
    r'\bCisco Unity\b',
    r'\bCUCM\b',
    r'\bUnified Communications\b',
]

# Specific advisory patterns to remove (known bad data)
ADVISORY_BLACKLIST = [
    'cisco-sa-wlc-mdns-dos',           # mDNS gateway - mislabeled everywhere
    'cisco-sa-twamp-kV4FHugn',         # TWAMP - mislabeled as Syslog
    'cisco-sa-cucm-rce-pqVYwyb',       # CUCM SOAP - not IOS-XE
    'cisco-sa-dcnm-sql-inj-OAQOObP',   # DCNM SQL injection - not IOx
    'cisco-sa-dcnm-api-path-TpTApx2p', # DCNM API - not IOx
    'cisco-sa-ndfc-raci-T46k3jnN',     # NDFC command injection - not IOx
    'cisco-sa-ndfc-cmdinj-UvYZrKfr',   # NDFC command injection - not IOx
    'cisco-sa-epnm-info-disc-PjTZ5r6C',# EPNM info disclosure - not IOx
    'cisco-sa-hyperflex-upload-KtCK8Ugz', # HyperFlex - not IOS-XE
]

# Duplicate advisory patterns (same advisory labeled multiple times)
KNOWN_DUPLICATES = [
    'cisco-sa-quewedge',  # Appears in L2_STP, Switchport_Trunk, Switchport_Access
]

# Labels that should be SUGGESTED for certain patterns (relabeling candidates)
RELABEL_PATTERNS = {
    # Pattern -> Suggested new label
    r'mDNS\s+gateway': 'WIRELESS_MDNS',
    r'SD-WAN.*UTD|UTD.*SD-WAN|Unified Threat Defense': 'SDWAN_UTD',
    r'SD-WAN.*packet\s+filter|packet\s+filter.*SD-WAN': 'SDWAN_Filtering',
    r'TWAMP|Two-Way Active Measurement': 'IP_SLA_TWAMP',
    r'IPv[46]?\s+fragment|VFR|fragment\s+reassembly': 'IP_Fragmentation',
    r'VXLAN|EVPN|overlay': 'OVERLAY_VXLAN_EVPN',
}

# Acronym collision warnings
ACRONYM_COLLISIONS = {
    'DAD': ('HA_StackWise', 'Dual Active Detection - NOT Dynamic ARP Inspection'),
    'DAI': ('SEC_DAI', 'Dynamic ARP Inspection - NOT Dual Active Detection'),
}


# =============================================================================
# CLEANUP FUNCTIONS
# =============================================================================

def load_data(input_path: str) -> pd.DataFrame:
    """Load the training data from parquet file."""
    print(f"📂 Loading data from {input_path}...")
    df = pd.read_parquet(input_path)
    print(f"   Loaded {len(df)} examples")
    return df


def extract_advisory_id(row: pd.Series) -> Optional[str]:
    """Extract advisory ID from row data."""
    # Try common column names
    for col in ['advisoryId', 'advisory_id', 'id', 'cisco_sa']:
        if col in row.index and pd.notna(row[col]):
            return str(row[col])
    
    # Try to extract from summary text
    summary = str(row.get('summary', ''))
    match = re.search(r'cisco-sa-[\w-]+', summary, re.IGNORECASE)
    if match:
        return match.group(0).lower()
    
    return None


def check_platform_contamination(summary: str) -> Tuple[bool, List[str]]:
    """Check if summary contains non-IOS-XE platform indicators."""
    summary_upper = summary.upper()
    found_platforms = []
    
    for pattern in NON_IOSXE_PLATFORM_PATTERNS:
        if re.search(pattern, summary, re.IGNORECASE):
            found_platforms.append(pattern)
    
    return len(found_platforms) > 0, found_platforms


def check_mdns_contamination(summary: str, advisory_id: Optional[str]) -> bool:
    """Check if this is the mDNS gateway advisory."""
    if advisory_id and MDNS_CONTAMINATED_ADVISORY in advisory_id.lower():
        return True
    if 'mdns' in summary.lower() and 'gateway' in summary.lower():
        return True
    return False


def check_blacklisted_advisory(advisory_id: Optional[str]) -> bool:
    """Check if advisory is in the blacklist."""
    if not advisory_id:
        return False
    advisory_lower = advisory_id.lower()
    for blacklisted in ADVISORY_BLACKLIST:
        if blacklisted.lower() in advisory_lower:
            return True
    return False


def suggest_relabel(summary: str) -> Optional[str]:
    """Suggest a new label based on content patterns."""
    for pattern, new_label in RELABEL_PATTERNS.items():
        if re.search(pattern, summary, re.IGNORECASE):
            return new_label
    return None


def get_labels_from_row(row: pd.Series) -> List[str]:
    """Extract labels from row, handling various formats."""
    labels = row.get('labels_list', row.get('labels', []))
    if labels is None:
        return []
    if hasattr(labels, 'tolist'):
        return labels.tolist()
    if isinstance(labels, str):
        try:
            return json.loads(labels)
        except:
            return [labels]
    if isinstance(labels, list):
        return labels
    return []


def analyze_example(row: pd.Series, idx: int) -> Dict:
    """Analyze a single example for contamination issues."""
    summary = str(row.get('summary', ''))
    labels = get_labels_from_row(row)
    advisory_id = extract_advisory_id(row)
    platform = row.get('platform', 'unknown')
    
    issues = []
    severity = 'ok'
    action = 'keep'
    suggested_label = None
    
    # Check 1: Critically contaminated label
    for label in labels:
        if label in CRITICALLY_CONTAMINATED_LABELS:
            issues.append(f"CRITICAL: Label '{label}' has 0% valid training examples")
            severity = 'critical'
            action = 'remove'
    
    # Check 2: Highly contaminated label
    if severity != 'critical':
        for label in labels:
            if label in HIGHLY_CONTAMINATED_LABELS:
                issues.append(f"HIGH: Label '{label}' has >50% invalid training examples")
                severity = 'high'
                action = 'review'
    
    # Check 3: mDNS contamination
    if check_mdns_contamination(summary, advisory_id):
        for label in labels:
            if label in MDNS_AFFECTED_LABELS:
                issues.append(f"MDNS: mDNS gateway advisory mislabeled as '{label}'")
                severity = 'critical'
                action = 'remove'
                suggested_label = 'WIRELESS_MDNS'
    
    # Check 4: Blacklisted advisory
    if check_blacklisted_advisory(advisory_id):
        issues.append(f"BLACKLIST: Advisory '{advisory_id}' is known-bad")
        severity = 'critical'
        action = 'remove'
    
    # Check 5: Platform contamination (for IOS-XE labeled data)
    if platform == 'IOS-XE' or 'IOS-XE' in str(labels):
        is_contaminated, found_platforms = check_platform_contamination(summary)
        if is_contaminated:
            issues.append(f"PLATFORM: Non-IOS-XE content detected: {found_platforms[:2]}")
            if severity not in ['critical']:
                severity = 'high'
                action = 'review'
    
    # Check 6: Suggest relabeling
    suggested = suggest_relabel(summary)
    if suggested and suggested not in labels:
        suggested_label = suggested
        if not issues:
            issues.append(f"SUGGEST: Consider label '{suggested}'")
    
    return {
        'idx': idx,
        'advisory_id': advisory_id,
        'platform': platform,
        'labels': labels,
        'summary_preview': summary[:150] + '...' if len(summary) > 150 else summary,
        'issues': issues,
        'severity': severity,
        'action': action,
        'suggested_label': suggested_label,
    }


def run_cleanup(df: pd.DataFrame, dry_run: bool = False) -> Tuple[pd.DataFrame, Dict]:
    """Run the full cleanup process."""
    print("\n🔍 Analyzing training data for contamination...")
    
    results = {
        'total': len(df),
        'critical': [],
        'high': [],
        'review': [],
        'ok': [],
        'removed': 0,
        'kept': 0,
        'by_label': defaultdict(lambda: {'total': 0, 'removed': 0, 'issues': []}),
        'by_issue_type': defaultdict(int),
    }
    
    rows_to_keep = []
    
    for idx, row in df.iterrows():
        analysis = analyze_example(row, idx)
        labels = analysis['labels']
        
        # Track by label
        for label in labels:
            results['by_label'][label]['total'] += 1
        
        # Track by severity
        if analysis['severity'] == 'critical':
            results['critical'].append(analysis)
            for label in labels:
                results['by_label'][label]['removed'] += 1
                results['by_label'][label]['issues'].append(analysis['issues'])
        elif analysis['severity'] == 'high':
            results['high'].append(analysis)
        elif analysis['action'] == 'review':
            results['review'].append(analysis)
        else:
            results['ok'].append(analysis)
        
        # Track issue types
        for issue in analysis['issues']:
            issue_type = issue.split(':')[0]
            results['by_issue_type'][issue_type] += 1
        
        # Decide whether to keep
        if analysis['action'] == 'remove':
            results['removed'] += 1
        else:
            results['kept'] += 1
            rows_to_keep.append(idx)
    
    # Create cleaned dataframe
    if not dry_run:
        df_cleaned = df.loc[rows_to_keep].copy()
    else:
        df_cleaned = df.copy()
    
    return df_cleaned, results


def generate_report(results: Dict, output_path: str = None) -> str:
    """Generate a detailed cleanup report."""
    lines = []
    lines.append("=" * 80)
    lines.append("CVE-EVAL DATA CLEANUP REPORT")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("=" * 80)
    lines.append("")
    
    # Summary
    lines.append("## SUMMARY")
    lines.append(f"Total examples analyzed: {results['total']}")
    lines.append(f"Examples to REMOVE:      {results['removed']} ({100*results['removed']/results['total']:.1f}%)")
    lines.append(f"Examples to KEEP:        {results['kept']} ({100*results['kept']/results['total']:.1f}%)")
    lines.append("")
    
    # By severity
    lines.append("## BY SEVERITY")
    lines.append(f"🔴 CRITICAL (remove):  {len(results['critical'])}")
    lines.append(f"🟠 HIGH (review):      {len(results['high'])}")
    lines.append(f"🟡 REVIEW (manual):    {len(results['review'])}")
    lines.append(f"🟢 OK (keep):          {len(results['ok'])}")
    lines.append("")
    
    # By issue type
    lines.append("## BY ISSUE TYPE")
    for issue_type, count in sorted(results['by_issue_type'].items(), key=lambda x: -x[1]):
        lines.append(f"  {issue_type}: {count}")
    lines.append("")
    
    # Most affected labels
    lines.append("## MOST AFFECTED LABELS")
    label_stats = [(label, stats['removed'], stats['total']) 
                   for label, stats in results['by_label'].items()
                   if stats['removed'] > 0]
    label_stats.sort(key=lambda x: -x[1])
    
    for label, removed, total in label_stats[:20]:
        pct = 100 * removed / total if total > 0 else 0
        lines.append(f"  {label}: {removed}/{total} removed ({pct:.0f}%)")
    lines.append("")
    
    # Critical examples (first 20)
    lines.append("## CRITICAL EXAMPLES (first 20)")
    for analysis in results['critical'][:20]:
        lines.append(f"\n  [{analysis['idx']}] {analysis['advisory_id'] or 'N/A'}")
        lines.append(f"      Labels: {analysis['labels']}")
        lines.append(f"      Issues: {'; '.join(analysis['issues'])}")
        lines.append(f"      Summary: {analysis['summary_preview'][:100]}...")
    lines.append("")
    
    # Recommendations
    lines.append("## RECOMMENDATIONS")
    lines.append("")
    lines.append("1. IMMEDIATE: Remove all CRITICAL examples (automated by this script)")
    lines.append("")
    lines.append("2. MANUAL REVIEW: Check HIGH severity examples for false positives")
    lines.append("   Export with: --export-review flag")
    lines.append("")
    lines.append("3. NEW LABELS NEEDED:")
    suggested_labels = set()
    for analysis in results['critical'] + results['high']:
        if analysis.get('suggested_label'):
            suggested_labels.add(analysis['suggested_label'])
    for label in sorted(suggested_labels):
        lines.append(f"   - {label}")
    lines.append("")
    lines.append("4. RETRAIN: After cleanup, retrain LoRA adapter on cleaned data")
    lines.append("")
    
    report = '\n'.join(lines)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"📄 Report saved to {output_path}")
    
    return report


def export_review_list(results: Dict, output_path: str):
    """Export HIGH severity examples for manual review."""
    review_data = []
    for analysis in results['high'] + results['review']:
        review_data.append({
            'idx': analysis['idx'],
            'advisory_id': analysis['advisory_id'],
            'labels': analysis['labels'],
            'issues': analysis['issues'],
            'severity': analysis['severity'],
            'suggested_label': analysis['suggested_label'],
            'summary_preview': analysis['summary_preview'],
            'action': '',  # For manual annotation
            'notes': '',   # For manual notes
        })
    
    df_review = pd.DataFrame(review_data)
    df_review.to_csv(output_path, index=False)
    print(f"📋 Review list exported to {output_path} ({len(review_data)} examples)")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Clean CVE-EVAL training data based on taxonomy enrichment findings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes (dry run)
  python cleanup_training_data.py --dry-run

  # Run cleanup and save
  python cleanup_training_data.py --input models/labeled_examples.parquet --output models/labeled_examples_cleaned.parquet

  # Generate report only
  python cleanup_training_data.py --report --report-path cleanup_report.txt

  # Export review list for manual checking
  python cleanup_training_data.py --export-review review_list.csv
        """
    )
    
    parser.add_argument('--input', '-i', 
                        default='models/labeled_examples.parquet',
                        help='Input parquet file path')
    parser.add_argument('--output', '-o',
                        default='models/labeled_examples_cleaned.parquet', 
                        help='Output parquet file path')
    parser.add_argument('--dry-run', '-n', 
                        action='store_true',
                        help='Preview changes without writing files')
    parser.add_argument('--report', '-r',
                        action='store_true',
                        help='Generate detailed report')
    parser.add_argument('--report-path',
                        default='cleanup_report.txt',
                        help='Path for cleanup report')
    parser.add_argument('--export-review',
                        help='Export HIGH severity examples to CSV for manual review')
    parser.add_argument('--verbose', '-v',
                        action='store_true',
                        help='Print detailed progress')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("CVE-EVAL DATA CLEANUP")
    print("=" * 60)
    
    # Load data
    df = load_data(args.input)
    
    # Run cleanup
    df_cleaned, results = run_cleanup(df, dry_run=args.dry_run)
    
    # Generate report
    if args.report or args.dry_run:
        report = generate_report(results, args.report_path if args.report else None)
        if args.dry_run:
            print("\n" + report)
    
    # Export review list
    if args.export_review:
        export_review_list(results, args.export_review)
    
    # Save cleaned data
    if not args.dry_run:
        print(f"\n💾 Saving cleaned data to {args.output}...")
        df_cleaned.to_parquet(args.output, index=False)
        print(f"✅ Saved {len(df_cleaned)} examples (removed {results['removed']})")
    else:
        print(f"\n[DRY RUN] Would save {len(df_cleaned)} examples to {args.output}")
        print(f"[DRY RUN] Would remove {results['removed']} examples")
    
    # Summary
    print("\n" + "=" * 60)
    print("CLEANUP COMPLETE")
    print("=" * 60)
    print(f"Original:  {results['total']} examples")
    print(f"Removed:   {results['removed']} examples ({100*results['removed']/results['total']:.1f}%)")
    print(f"Remaining: {results['kept']} examples")
    print("")
    print("Next steps:")
    print("  1. Review the cleanup report")
    print("  2. Manually check HIGH severity examples if needed")
    print("  3. Regenerate CoT dataset: python scripts/prepare_cot_dataset.py")
    print("  4. Retrain LoRA adapter on cleaned data")


if __name__ == '__main__':
    main()
