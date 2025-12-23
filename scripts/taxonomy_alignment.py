#!/usr/bin/env python3
"""
Taxonomy Alignment Script
=========================

Phase A: Add missing labels to features.yml to align with evaluation test set
Phase B: Add new labels identified during contamination cleanup

Usage:
    python scripts/taxonomy_alignment.py --dry-run    # Preview changes
    python scripts/taxonomy_alignment.py --apply      # Apply changes
"""

import yaml
import argparse
from pathlib import Path
from datetime import datetime

# ============================================================================
# PHASE A: Labels missing from taxonomy but present in test set
# ============================================================================

# These are naming inconsistencies or genuinely missing labels
PHASE_A_LABELS = [
    {
        'label': 'MPLS_LDP',
        'domain': 'MPLS',
        'description': 'Applies to vulnerabilities in Label Distribution Protocol (LDP) for MPLS, including LDP session establishment, label binding/withdrawal, targeted LDP, and LDP-IGP synchronization. Use for bugs affecting LDP neighbor relationships, label space management, or LDP DoS conditions. Do NOT use for MPLS forwarding issues unrelated to LDP signaling.',
        'config_regex': [r'^mpls\s+ldp\b', r'^mpls\s+label\s+protocol\s+ldp\b'],
        'show_cmds': ['show mpls ldp neighbor', 'show mpls ldp bindings'],
    },
    {
        'label': 'MPLS_STATIC',
        'domain': 'MPLS',
        'description': 'Applies to vulnerabilities in static MPLS label assignment, including manual label bindings, static cross-connects, and static LSPs. Use for bugs where statically configured labels cause forwarding failures or security bypasses. Do NOT use for LDP or RSVP-TE signaled labels.',
        'config_regex': [r'^mpls\s+static\s+binding\b', r'^\s*label\s+\d+\b'],
        'show_cmds': ['show mpls static binding', 'show mpls forwarding-table'],
    },
    {
        'label': 'MPLS_TE',
        'domain': 'MPLS',
        'description': 'Applies to vulnerabilities in MPLS Traffic Engineering, including RSVP-TE signaling, explicit paths, bandwidth constraints, fast-reroute (FRR), and auto-tunnel. Use for TE tunnel establishment failures, path computation issues, or TE-related DoS. Do NOT use for basic MPLS forwarding without TE.',
        'config_regex': [r'^mpls\s+traffic-eng\b', r'^interface\s+Tunnel\d+.*tunnel\s+mode\s+mpls\b'],
        'show_cmds': ['show mpls traffic-eng tunnels', 'show mpls traffic-eng topology'],
    },
    {
        'label': 'RTE_OSPF',
        'domain': 'Routing',
        'description': 'Generic OSPF label covering both OSPFv2 and OSPFv3 when version is not specified. Applies to vulnerabilities in OSPF protocol operations affecting any version. For version-specific issues, prefer RTE_OSPFv2 or RTE_OSPFv3. Use when advisory mentions "OSPF" without specifying version.',
        'config_regex': [r'^router\s+ospf\b', r'^router\s+ospfv3\b'],
        'show_cmds': ['show ip ospf', 'show ospfv3'],
    },
    {
        'label': 'RTE_ISIS',
        'domain': 'Routing',
        'description': 'Applies to vulnerabilities in Intermediate System to Intermediate System (IS-IS) routing protocol, including LSP processing, adjacency formation, area/level hierarchy, and IS-IS for MPLS TE. Use for bugs in IS-IS packet parsing, flooding, or SPF calculation. Do NOT use for OSPF issues.',
        'config_regex': [r'^router\s+isis\b', r'^\s*isis\s+circuit-type\b'],
        'show_cmds': ['show isis neighbors', 'show isis database'],
    },
    {
        'label': 'SEC_DHCP_SNOOP',
        'domain': 'Security',
        'description': 'Alias for SEC_DHCP_Snooping. Applies to DHCP snooping security feature vulnerabilities including binding table manipulation, trust port bypass, rate limiting failures, and DHCP starvation attacks. Use when advisory uses "DHCP Snoop" or "DHCP Snooping" terminology.',
        'config_regex': [r'^ip\s+dhcp\s+snooping\b'],
        'show_cmds': ['show ip dhcp snooping', 'show ip dhcp snooping binding'],
    },
    {
        'label': 'SEC_BGP_ROUTE_FILTERING',
        'domain': 'Security',
        'description': 'Applies to vulnerabilities in BGP route filtering mechanisms including prefix-lists, route-maps, AS-path filters, community filters, and RPKI validation for route origin security. Use for bugs that allow unauthorized route injection, filter bypass, or route hijacking. Do NOT use for general BGP protocol issues.',
        'config_regex': [r'^ip\s+prefix-list\b.*neighbor', r'^route-map\b.*bgp'],
        'show_cmds': ['show ip bgp neighbors', 'show ip prefix-list'],
    },
    {
        'label': 'QOS_POLICING',
        'domain': 'QoS',
        'description': 'Applies to vulnerabilities in traffic policing (rate limiting) mechanisms, including single-rate/dual-rate policers, token bucket algorithms, conform/exceed/violate actions. Use for bugs where traffic is not correctly rate-limited or policed. Closely related to QOS_MQC_ClassPolicy.',
        'config_regex': [r'^\s*police\s+(rate|cir|pir)\b', r'^\s*police\s+\d+\b'],
        'show_cmds': ['show policy-map interface', 'show class-map'],
    },
    {
        'label': 'QOS_Police_Priority',
        'domain': 'QoS',
        'description': 'Applies to vulnerabilities affecting QoS priority queuing combined with policing, including priority queue bandwidth enforcement, strict priority scheduling, and low-latency queuing (LLQ). Use when bug involves interaction between priority scheduling and rate limiting.',
        'config_regex': [r'^\s*priority\s+(level|percent)\b', r'^\s*bandwidth\s+remaining\b'],
        'show_cmds': ['show policy-map interface', 'show queuing interface'],
    },
    {
        'label': 'SYS_Time_Range_Scheduler',
        'domain': 'System',
        'description': 'Applies to vulnerabilities in time-range definitions and time-based schedulers, including periodic ACL activation, Kron scheduler, and time-based access control. Use for bugs where time-based policies fail to activate/deactivate correctly.',
        'config_regex': [r'^time-range\b', r'^kron\s+policy-list\b'],
        'show_cmds': ['show time-range', 'show kron schedule'],
    },
    {
        'label': 'VPN_IKEv2',
        'domain': 'VPN',
        'description': 'Applies to vulnerabilities in IKEv2 protocol implementation, including IKE_SA_INIT, IKE_AUTH, CREATE_CHILD_SA exchanges, certificate authentication, and EAP methods. Use for IKEv2-specific bugs. Do NOT use for IKEv1 or generic IPsec issues.',
        'config_regex': [r'^crypto\s+ikev2\b', r'^crypto\s+ikev2\s+(profile|proposal|policy)\b'],
        'show_cmds': ['show crypto ikev2 sa', 'show crypto ikev2 session'],
    },
    {
        'label': 'MGMT_RPC_NETCONF',
        'domain': 'Management',
        'description': 'Applies to vulnerabilities in NETCONF/RESTCONF/gRPC management interfaces, including XML/YANG parsing, RPC operations, notification subscriptions, and programmable interface exploits. Use for bugs in network programmability interfaces. Do NOT use for traditional CLI or SNMP.',
        'config_regex': [r'^netconf\s+ssh\b', r'^restconf\b', r'^gnmi\b'],
        'show_cmds': ['show netconf-yang sessions', 'show platform software yang-management'],
    },
]

# ============================================================================
# PHASE B: New labels identified during contamination cleanup
# ============================================================================

PHASE_B_LABELS = [
    {
        'label': 'WIRELESS_MDNS',
        'domain': 'Wireless',
        'description': 'Applies to vulnerabilities in mDNS gateway functionality on Wireless LAN Controllers (WLC), including mDNS service discovery, mDNS packet parsing, gateway DoS conditions, and service advertisement bugs. Use for C9800 and AireOS WLC mDNS issues. Do NOT use for wired mDNS.',
        'config_regex': [r'^mdns-sd\s+gateway\b', r'^wireless\s+mdns\b'],
        'show_cmds': ['show mdns-sd service-list', 'show wireless mdns-sd statistics'],
    },
    {
        'label': 'SDWAN_UTD',
        'domain': 'SD-WAN',
        'description': 'Applies to vulnerabilities in SD-WAN Unified Threat Defense (UTD) module, including Snort IPS engine, URL filtering, AMP integration, and security policy enforcement on SD-WAN edge devices. Use for UTD-specific bugs on vEdge/cEdge platforms.',
        'config_regex': [r'^utd\s+engine\b', r'^policy\s+security\b.*utd'],
        'show_cmds': ['show utd engine standard status', 'show sdwan utd dataplane'],
    },
    {
        'label': 'SDWAN_Filtering',
        'domain': 'SD-WAN',
        'description': 'Applies to vulnerabilities in SD-WAN centralized packet filtering and access control, including data policy ACL bypass, application-aware routing policy bypass, and SD-WAN security policy enforcement failures. Use for filter/ACL bypass on SD-WAN fabric.',
        'config_regex': [r'^policy\s+data-policy\b', r'^policy\s+access-list\b'],
        'show_cmds': ['show sdwan policy access-list', 'show sdwan policy data-policy'],
    },
    {
        'label': 'IP_SLA_TWAMP',
        'domain': 'IP Services',
        'description': 'Applies to vulnerabilities in IP SLA (Service Level Agreement) probes and TWAMP (Two-Way Active Measurement Protocol) responders, including probe processing, timestamp manipulation, and measurement protocol DoS. Use for performance monitoring protocol bugs.',
        'config_regex': [r'^ip\s+sla\s+\d+\b', r'^ip\s+sla\s+responder\b', r'^ip\s+sla\s+twamp\b'],
        'show_cmds': ['show ip sla statistics', 'show ip sla responder'],
    },
    {
        'label': 'IP_Fragmentation',
        'domain': 'IP Services',
        'description': 'Applies to vulnerabilities in IPv4/IPv6 fragment reassembly, including Virtual Fragment Reassembly (VFR), fragment offset attacks, overlapping fragment handling, and reassembly buffer exhaustion. Use for fragment-specific DoS or bypass attacks.',
        'config_regex': [r'^ip\s+virtual-reassembly\b', r'^ipv6\s+virtual-reassembly\b'],
        'show_cmds': ['show ip virtual-reassembly', 'show ipv6 virtual-reassembly'],
    },
]

def load_taxonomy(filepath: str) -> list:
    """Load existing taxonomy"""
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def save_taxonomy(filepath: str, features: list):
    """Save updated taxonomy"""
    with open(filepath, 'w') as f:
        yaml.dump(features, f, default_flow_style=False, allow_unicode=True, width=120, sort_keys=False)

def format_label_entry(label_def: dict) -> dict:
    """Format a label definition to match existing taxonomy structure"""
    return {
        'label': label_def['label'],
        'domain': label_def['domain'],
        'presence': {
            'config_regex': label_def.get('config_regex', []),
            'show_cmds': label_def.get('show_cmds', []),
        },
        'docs': {'anchors': []},
        'description': label_def['description'],
    }

def main():
    parser = argparse.ArgumentParser(description='Align taxonomy with test set')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--apply', action='store_true', help='Apply changes to taxonomy')
    parser.add_argument('--taxonomy', default='taxonomies/features.yml', help='Path to taxonomy file')
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Please specify --dry-run or --apply")
        return

    print("=" * 70)
    print("TAXONOMY ALIGNMENT")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    # Load current taxonomy
    features = load_taxonomy(args.taxonomy)
    existing_labels = {f['label'] for f in features}
    print(f"\nExisting labels in taxonomy: {len(existing_labels)}")

    # Track changes
    added_phase_a = []
    added_phase_b = []
    skipped = []

    # Phase A: Add missing labels from test set
    print("\n" + "-" * 70)
    print("PHASE A: Labels from evaluation test set")
    print("-" * 70)

    for label_def in PHASE_A_LABELS:
        label = label_def['label']
        if label in existing_labels:
            skipped.append((label, 'Already exists'))
            print(f"  SKIP: {label} (already exists)")
        else:
            if args.apply:
                features.append(format_label_entry(label_def))
            added_phase_a.append(label)
            print(f"  ADD:  {label} ({label_def['domain']})")

    # Phase B: Add new labels from contamination analysis
    print("\n" + "-" * 70)
    print("PHASE B: New labels from contamination cleanup")
    print("-" * 70)

    for label_def in PHASE_B_LABELS:
        label = label_def['label']
        if label in existing_labels:
            skipped.append((label, 'Already exists'))
            print(f"  SKIP: {label} (already exists)")
        else:
            if args.apply:
                features.append(format_label_entry(label_def))
            added_phase_b.append(label)
            print(f"  ADD:  {label} ({label_def['domain']})")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Phase A labels added: {len(added_phase_a)}")
    print(f"Phase B labels added: {len(added_phase_b)}")
    print(f"Skipped (existing):   {len(skipped)}")
    print(f"Total labels after:   {len(existing_labels) + len(added_phase_a) + len(added_phase_b)}")

    if args.apply:
        # Backup original
        backup_path = args.taxonomy + '.backup'
        import shutil
        shutil.copy(args.taxonomy, backup_path)
        print(f"\nBackup saved to: {backup_path}")

        # Save updated taxonomy
        save_taxonomy(args.taxonomy, features)
        print(f"Updated taxonomy saved to: {args.taxonomy}")
    else:
        print("\n[DRY RUN] No changes applied. Use --apply to save changes.")

    # Special cases to flag
    print("\n" + "-" * 70)
    print("SPECIAL NOTES")
    print("-" * 70)
    print("1. SEC_DHCP_SNOOP is an alias for SEC_DHCP_Snooping (both now valid)")
    print("2. RTE_OSPF is generic; prefer RTE_OSPFv2/RTE_OSPFv3 when version is known")
    print("3. MGMT_RPC_NETCONF replaces 'MGMT_RPC / NETCONF' (no spaces/slashes)")
    print("4. Test set may need updating to use canonical label names")

if __name__ == '__main__':
    main()
