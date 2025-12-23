#!/usr/bin/env python3
"""
IOS-XE Feature Extractor - STANDALONE Air-Gapped Version
=========================================================

Extracts IOS-XE feature presence from device configs WITHOUT capturing sensitive data.
This is a SINGLE-FILE standalone script with embedded taxonomy - no external dependencies!

✅ No YAML files needed
✅ No PyYAML library needed
✅ Works completely offline
✅ Only requires Python 3.6+

Output: Sanitized JSON snapshot with feature labels only (no IPs, passwords, hostnames, configs)

Usage:
    # From SSH-enabled device (requires netmiko)
    python extract_iosxe_features_standalone.py --host 192.168.1.1 --username admin --output snapshot.json

    # From offline config file (NO external dependencies!)
    python extract_iosxe_features_standalone.py --config running-config.txt --output snapshot.json

    # With password in command (not recommended)
    python extract_iosxe_features_standalone.py --config running-config.txt --output snapshot.json
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import getpass

# Optional: netmiko for live device SSH (not required for offline mode)
try:
    from netmiko import ConnectHandler
    NETMIKO_AVAILABLE = True
except ImportError:
    NETMIKO_AVAILABLE = False

# ============================================================================
# EMBEDDED IOS-XE TAXONOMY (66 features)
# ============================================================================
# This data is embedded so the script works offline without external files

IOSXE_FEATURES = [
  {
    "label": "L2_STP",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": [
        "^spanning-tree\\s+mode\\b",
        "^spanning-tree\\s+(vlan|mst)\\b",
        "^\\s*spanning-tree\\s+(portfast|port-priority|bpdu)\\b"
      ],
      "show_cmds": ["show spanning-tree"]
    }
  },
  {
    "label": "L2_EtherChannel",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": [
        "^interface\\s+port-channel\\b",
        "^\\s*channel-group\\s+\\d+\\s+(mode|active|on)\\b"
      ],
      "show_cmds": ["show etherchannel summary"]
    }
  },
  {
    "label": "L2_LACP",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": ["\\blacp\\s+(rate|system-priority|port-priority)\\b"],
      "show_cmds": ["show lacp"]
    }
  },
  {
    "label": "L2_PAgP",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": ["\\bpagp\\s+(port-priority|learn-method)\\b"],
      "show_cmds": ["show pagp"]
    }
  },
  {
    "label": "L2_VLAN_VTP",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": ["^vlan\\s+\\d+\\b", "^vtp\\s+mode\\b"],
      "show_cmds": ["show vlan", "show vtp status"]
    }
  },
  {
    "label": "L2_PrivateVLAN",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": ["^private-vlan\\b", "\\bbridge-domain\\b"],
      "show_cmds": ["show interfaces private-vlan mapping"]
    }
  },
  {
    "label": "L2_UDLD",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": ["^udld\\s+(enable|aggressive)\\b", "^udld\\s+port\\b"],
      "show_cmds": ["show udld"]
    }
  },
  {
    "label": "L2_REP",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": ["^rep\\s+(segment|preempt|admin vlan)\\b"],
      "show_cmds": ["show rep topology"]
    }
  },
  {
    "label": "L2_PTP_gPTP",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": ["^ptp\\s+(profile|priority1|priority2|role|ip dscp)\\b"],
      "show_cmds": ["show ptp brief"]
    }
  },
  {
    "label": "L2_L2ProtocolTunneling",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": ["^l2protocol-tunnel\\b", "dot1q[- ]tunnel"],
      "show_cmds": ["show l2protocol-tunnel"]
    }
  },
  {
    "label": "L2_Switchport_Trunk",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": ["^switchport\\s+mode\\s+trunk\\b", "^switchport\\s+trunk\\b"],
      "show_cmds": ["show interfaces switchport"]
    }
  },
  {
    "label": "L2_Switchport_Access",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": ["^switchport\\s+mode\\s+access\\b", "^switchport\\s+access\\s+vlan\\b"],
      "show_cmds": ["show interfaces switchport"]
    }
  },
  {
    "label": "L2_Dot1Q_Tunnel",
    "domain": "L2 Switching",
    "presence": {
      "config_regex": ["dot1q[- ]tunnel"],
      "show_cmds": ["show dot1q-tunnel"]
    }
  },
  {
    "label": "RTE_Static",
    "domain": "L3 Routing",
    "presence": {
      "config_regex": ["^ip\\s+route\\s", "^ipv6\\s+route\\s"],
      "show_cmds": ["show ip route static"]
    }
  },
  {
    "label": "RTE_OSPFv2",
    "domain": "L3 Routing",
    "presence": {
      "config_regex": ["^router\\s+ospf\\b", "\\bip\\s+ospf\\b"],
      "show_cmds": ["show ip ospf"]
    }
  },
  {
    "label": "RTE_OSPFv3",
    "domain": "L3 Routing",
    "presence": {
      "config_regex": ["^router\\s+ospfv3\\b", "^ipv6\\s+router\\s+ospf\\b"],
      "show_cmds": ["show ospfv3"]
    }
  },
  {
    "label": "RTE_EIGRP",
    "domain": "L3 Routing",
    "presence": {
      "config_regex": ["^router\\s+eigrp\\b", "^\\s*ip\\s+eigrp\\b", "^interface.*\\n.*\\s+ip\\s+eigrp\\b"],
      "show_cmds": ["show ip eigrp neighbors"]
    }
  },
  {
    "label": "RTE_BGP",
    "domain": "L3 Routing",
    "presence": {
      "config_regex": ["^router\\s+bgp\\b"],
      "show_cmds": ["show ip bgp summary"]
    }
  },
  {
    "label": "RTE_BFD",
    "domain": "L3 Routing",
    "presence": {
      "config_regex": ["^\\s*bfd\\s+(interval|template)\\b", "ip route .* bfd", "ipv6 route .* bfd", "^interface.*\\n.*\\s+bfd\\s+interval"],
      "show_cmds": ["show bfd neighbors"]
    }
  },
  {
    "label": "RTE_Redistribution_PBR",
    "domain": "L3 Routing",
    "presence": {
      "config_regex": ["^route-map\\b", "^redistribute\\b"],
      "show_cmds": ["show route-map"]
    }
  },
  {
    "label": "RTE_CEF",
    "domain": "L3 Routing",
    "presence": {
      "config_regex": ["^ip\\s+cef\\b", "^ipv6\\s+cef\\b"],
      "show_cmds": ["show ip cef"]
    }
  },
  {
    "label": "FHRP_HSRP",
    "domain": "L3/FHRP",
    "presence": {
      "config_regex": ["^\\s*standby\\s+\\d+\\b", "^standby\\s+version\\b"],
      "show_cmds": ["show standby"]
    }
  },
  {
    "label": "FHRP_VRRP",
    "domain": "L3/FHRP",
    "presence": {
      "config_regex": ["^\\s*vrrp\\s+\\d+\\b"],
      "show_cmds": ["show vrrp"]
    }
  },
  {
    "label": "FHRP_GLBP",
    "domain": "L3/FHRP",
    "presence": {
      "config_regex": ["^\\s*glbp\\s+\\d+\\b"],
      "show_cmds": ["show glbp"]
    }
  },
  {
    "label": "IP_DHCP_Server",
    "domain": "IP Services",
    "presence": {
      "config_regex": ["^ip\\s+dhcp\\s+pool\\b", "^ipv6\\s+dhcp\\s+pool\\b"],
      "show_cmds": ["show ip dhcp binding"]
    }
  },
  {
    "label": "IP_DHCP_Relay",
    "domain": "IP Services",
    "presence": {
      "config_regex": ["^ip\\s+helper-address\\b", "^ipv6\\s+dhcp\\s+relay\\b"],
      "show_cmds": ["show running-config | sec (dhcp|helper)"]
    }
  },
  {
    "label": "IP_NAT",
    "domain": "IP Services",
    "presence": {
      "config_regex": ["^ip\\s+nat\\s+(inside|outside|pool|translation)\\b"],
      "show_cmds": ["show ip nat translations"]
    }
  },
  {
    "label": "IP_NHRP_DMVPN",
    "domain": "IP Services",
    "presence": {
      "config_regex": ["^ip\\s+nhrp\\s+(map|network-id|nhs)\\b"],
      "show_cmds": ["show ip nhrp"]
    }
  },
  {
    "label": "IP_WCCP",
    "domain": "IP Services",
    "presence": {
      "config_regex": ["^ip\\s+wccp\\b"],
      "show_cmds": ["show ip wccp"]
    }
  },
  {
    "label": "IP_Unnumbered",
    "domain": "IP Services",
    "presence": {
      "config_regex": ["^ip\\s+unnumbered\\b"],
      "show_cmds": ["show running-config | sec ip unnumbered"]
    }
  },
  {
    "label": "IP_PrefixList",
    "domain": "IP Services",
    "presence": {
      "config_regex": ["^ip\\s+prefix-list\\b", "^ipv6\\s+prefix-list\\b"],
      "show_cmds": ["show ip prefix-list"]
    }
  },
  {
    "label": "MCAST_PIM",
    "domain": "Multicast",
    "presence": {
      "config_regex": ["^ip\\s+pim\\s", "^ipv6\\s+pim\\s"],
      "show_cmds": ["show ip pim neighbor"]
    }
  },
  {
    "label": "MCAST_IGMP_MLD_Snoop",
    "domain": "Multicast",
    "presence": {
      "config_regex": ["^ip\\s+igmp\\s+snooping\\b", "^ipv6\\s+mld\\s+snooping\\b"],
      "show_cmds": ["show ip igmp snooping", "show ipv6 mld snooping"]
    }
  },
  {
    "label": "MCAST_SSM",
    "domain": "Multicast",
    "presence": {
      "config_regex": ["\\bssm-map\\b"],
      "show_cmds": ["show running-config | inc ssm-map"]
    }
  },
  {
    "label": "QOS_MQC_ClassPolicy",
    "domain": "QoS",
    "presence": {
      "config_regex": ["^class-map\\b", "^policy-map\\b", "^\\s*service-policy\\b"],
      "show_cmds": ["show policy-map interface"]
    }
  },
  {
    "label": "QOS_Marking_Trust",
    "domain": "QoS",
    "presence": {
      "config_regex": ["^mls\\s+qos\\s+trust\\b", "^mls\\s+qos\\b"],
      "show_cmds": ["show mls qos interface"]
    }
  },
  {
    "label": "QOS_Queuing_Scheduling",
    "domain": "QoS",
    "presence": {
      "config_regex": ["\\bpriority-queue\\b", "\\bwrr-queue\\b", "\\bbandwidth\\b"],
      "show_cmds": ["show policy-map interface"]
    }
  },
  {
    "label": "SEC_8021X",
    "domain": "Security",
    "presence": {
      "config_regex": ["^dot1x\\s", "^aaa\\s+authentication\\s+dot1x\\b"],
      "show_cmds": ["show dot1x all"]
    }
  },
  {
    "label": "SEC_MAB",
    "domain": "Security",
    "presence": {
      "config_regex": ["^mab\\b"],
      "show_cmds": ["show authentication sessions"]
    }
  },
  {
    "label": "SEC_PortSecurity",
    "domain": "Security",
    "presence": {
      "config_regex": ["^switchport\\s+port-security\\b"],
      "show_cmds": ["show port-security"]
    }
  },
  {
    "label": "SEC_DHCP_Snooping",
    "domain": "Security",
    "presence": {
      "config_regex": ["^ip\\s+dhcp\\s+snooping\\b"],
      "show_cmds": ["show ip dhcp snooping"]
    }
  },
  {
    "label": "SEC_IP_Source_Guard",
    "domain": "Security",
    "presence": {
      "config_regex": ["^ip\\s+verify\\s+source\\b"],
      "show_cmds": ["show ip verify source"]
    }
  },
  {
    "label": "SEC_DAI",
    "domain": "Security",
    "presence": {
      "config_regex": ["^ip\\s+arp\\s+inspection\\b"],
      "show_cmds": ["show ip arp inspection"]
    }
  },
  {
    "label": "SEC_StormControl",
    "domain": "Security",
    "presence": {
      "config_regex": ["^storm-control\\b"],
      "show_cmds": ["show storm-control"]
    }
  },
  {
    "label": "SEC_CoPP",
    "domain": "Security",
    "presence": {
      "config_regex": ["^control-plane\\b", "^policy-map\\s+control-plane\\b"],
      "show_cmds": ["show policy-map control-plane"]
    }
  },
  {
    "label": "SEC_PACL_VACL",
    "domain": "Security",
    "presence": {
      "config_regex": ["^ip\\s+access-list\\b", "^ipv6\\s+access-list\\b", "\\bvlan\\s+access-map\\b"],
      "show_cmds": ["show access-lists"]
    }
  },
  {
    "label": "CTS_Base",
    "domain": "TrustSec",
    "presence": {
      "config_regex": ["^cts\\s+(enable|role-based|authorization|sxp)\\b"],
      "show_cmds": ["show cts", "show cts role-based"]
    }
  },
  {
    "label": "CTS_SXP",
    "domain": "TrustSec",
    "presence": {
      "config_regex": ["^cts\\s+sxp\\b"],
      "show_cmds": ["show cts sxp connections"]
    }
  },
  {
    "label": "MGMT_SNMP",
    "domain": "Management",
    "presence": {
      "config_regex": ["^snmp-server\\b"],
      "show_cmds": ["show snmp user", "show snmp group"]
    }
  },
  {
    "label": "MGMT_Syslog",
    "domain": "Management",
    "presence": {
      "config_regex": ["^logging\\s+(host|buffered)\\b"],
      "show_cmds": ["show logging"]
    }
  },
  {
    "label": "MGMT_NetFlow_FNF",
    "domain": "Management",
    "presence": {
      "config_regex": ["^flow\\s+(exporter|monitor|record)\\b"],
      "show_cmds": ["show flow monitor"]
    }
  },
  {
    "label": "MGMT_SPAN_ERSPAN",
    "domain": "Management",
    "presence": {
      "config_regex": ["^monitor\\s+session\\b", "\\berspan\\b"],
      "show_cmds": ["show monitor session"]
    }
  },
  {
    "label": "MGMT_LLDP_CDP",
    "domain": "Management",
    "presence": {
      "config_regex": ["^lldp\\s+run\\b", "^cdp\\s+run\\b"],
      "show_cmds": ["show lldp neighbors", "show cdp neighbors"]
    }
  },
  {
    "label": "MGMT_AAA_TACACS_RADIUS",
    "domain": "Management",
    "presence": {
      "config_regex": ["^aaa\\s+new-model\\b", "^tacacs-server\\b", "^radius-server\\b"],
      "show_cmds": ["show aaa servers"]
    }
  },
  {
    "label": "MGMT_SSH_HTTP",
    "domain": "Management",
    "presence": {
      "config_regex": ["^ip\\s+ssh\\b", "^ip\\s+http\\b"],
      "show_cmds": ["show ip ssh"]
    }
  },
  {
    "label": "MGMT_NTP",
    "domain": "Management",
    "presence": {
      "config_regex": ["^ntp\\s+server\\b", "^clock\\s+timezone\\b"],
      "show_cmds": ["show ntp associations"]
    }
  },
  {
    "label": "HA_StackWise",
    "domain": "HA",
    "presence": {
      "config_regex": ["^switch\\s+\\d+\\s+priority\\b", "\\bstackwise\\b"],
      "show_cmds": ["show switch"]
    }
  },
  {
    "label": "HA_StackPower",
    "domain": "HA",
    "presence": {
      "config_regex": ["^stack-power\\b"],
      "show_cmds": ["show stack-power"]
    }
  },
  {
    "label": "HA_Redundancy_SSO",
    "domain": "HA",
    "presence": {
      "config_regex": ["^redundancy\\s+mode\\s+sso\\b"],
      "show_cmds": ["show redundancy"]
    }
  },
  {
    "label": "HA_NSF_GR",
    "domain": "HA",
    "presence": {
      "config_regex": ["\\bnsf\\b", "graceful-restart"],
      "show_cmds": ["show ip ospf", "show ip bgp"]
    }
  },
  {
    "label": "SYS_Boot_Upgrade",
    "domain": "System",
    "presence": {
      "config_regex": ["^boot\\s+system\\b", "^software\\s+install\\b"],
      "show_cmds": ["show version"]
    }
  },
  {
    "label": "SYS_Licensing_Smart",
    "domain": "System",
    "presence": {
      "config_regex": ["^license\\s+smart\\b", "^telemetry\\b"],
      "show_cmds": ["show license all"]
    }
  },
  {
    "label": "IF_Physical",
    "domain": "Interfaces",
    "presence": {
      "config_regex": ["^interface\\s+(GigabitEthernet|TenGigabitEthernet)\\b"],
      "show_cmds": ["show interfaces status"]
    }
  },
  {
    "label": "IF_PortTemplates",
    "domain": "Interfaces",
    "presence": {
      "config_regex": ["^template\\s+\\S+"],
      "show_cmds": ["show running-config | sec template"]
    }
  },
  {
    "label": "IF_Speed_Duplex",
    "domain": "Interfaces",
    "presence": {
      "config_regex": ["\\bspeed\\b", "\\bduplex\\b", "negotiation\\s+auto"],
      "show_cmds": ["show interfaces"]
    }
  },
  {
    "label": "APP_IOx",
    "domain": "Application Hosting",
    "presence": {
      "config_regex": [
        "^iox$",
        "^app-hosting\\s+(deploy|activate|start)\\b",
        "^interface\\s+AppGigabitEthernet\\b",
        "^interface\\s+VirtualPortGroup\\b"
      ],
      "show_cmds": [
        "show iox",
        "show app-hosting list",
        "show app-hosting detail",
        "show running-config | include iox"
      ]
    }
  }
]


# ============================================================================
# Feature Extraction Logic
# ============================================================================

class FeatureExtractor:
    """Extract features from IOS-XE config using embedded taxonomy"""

    def __init__(self):
        """Initialize with embedded IOS-XE taxonomy"""
        self.platform = 'IOS-XE'
        self.features = IOSXE_FEATURES
        print(f"✅ Loaded {len(self.features)} IOS-XE features (embedded)")

    def extract_from_config(self, config_text: str) -> Dict:
        """
        Extract features from config text

        Args:
            config_text: Device running configuration

        Returns:
            Dict with snapshot data (NO sensitive info)
        """
        print(f"\n🔍 Scanning configuration for IOS-XE features...")

        features_present = []
        features_checked = 0

        for feature in self.features:
            label = feature.get('label')
            domain = feature.get('domain')
            presence = feature.get('presence', {})
            config_regexes = presence.get('config_regex', [])

            if not config_regexes or not label:
                continue

            features_checked += 1

            # Test if any regex pattern matches
            feature_detected = False
            for pattern in config_regexes:
                try:
                    if re.search(pattern, config_text, re.MULTILINE | re.IGNORECASE):
                        feature_detected = True
                        break
                except re.error as e:
                    print(f"  ⚠️  Invalid regex for {label}: {e}")
                    continue

            if feature_detected:
                features_present.append(label)
                print(f"  ✓ {label} ({domain})")

        snapshot = {
            "snapshot_id": f"snapshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "platform": self.platform,
            "extracted_at": datetime.now().isoformat(),
            "features_present": sorted(features_present),
            "feature_count": len(features_present),
            "total_checked": features_checked,
            "extractor_version": "1.0.0-standalone"
        }

        print(f"\n📊 Summary: {len(features_present)}/{features_checked} features detected")
        return snapshot


# ============================================================================
# Device Connector (Optional - requires netmiko)
# ============================================================================

class DeviceConnector:
    """Connect to live device via SSH (requires netmiko)"""

    def __init__(self, host: str, username: str, password: str,
                 device_type: str = 'cisco_ios', port: int = 22):
        if not NETMIKO_AVAILABLE:
            raise RuntimeError("netmiko library not installed. Install with: pip install netmiko")

        self.device_params = {
            'device_type': device_type,
            'host': host,
            'username': username,
            'password': password,
            'port': port,
        }
        self.connection = None

    def connect(self):
        """Establish SSH connection"""
        print(f"🔌 Connecting to {self.device_params['host']}...")
        self.connection = ConnectHandler(**self.device_params)
        print("✅ Connected successfully")

    def disconnect(self):
        """Close SSH connection"""
        if self.connection:
            self.connection.disconnect()
            print("🔌 Disconnected")

    def get_running_config(self) -> str:
        """Retrieve running configuration"""
        print("📥 Downloading running configuration...")
        config = self.connection.send_command("show running-config", read_timeout=120)
        print(f"✅ Retrieved {len(config)} characters")
        return config


# ============================================================================
# Extraction Functions
# ============================================================================

def extract_from_live_device(host: str, username: str, password: str,
                             device_type: str = 'cisco_ios') -> Dict:
    """
    Extract features from live device via SSH

    Args:
        host: Device IP/hostname
        username: SSH username
        password: SSH password
        device_type: Netmiko device type

    Returns:
        Feature snapshot dict
    """
    connector = DeviceConnector(host, username, password, device_type)

    try:
        connector.connect()
        config = connector.get_running_config()

        # Extract features
        extractor = FeatureExtractor()
        snapshot = extractor.extract_from_config(config)

        return snapshot

    finally:
        connector.disconnect()


def extract_from_config_file(config_file: str) -> Dict:
    """
    Extract features from offline config file

    Args:
        config_file: Path to running-config file

    Returns:
        Feature snapshot dict
    """
    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    print(f"📂 Reading config from: {config_path}")
    with open(config_path, 'r') as f:
        config = f.read()

    print(f"✅ Loaded {len(config)} characters")

    # Extract features
    extractor = FeatureExtractor()
    snapshot = extractor.extract_from_config(config)

    return snapshot


def save_snapshot(snapshot: Dict, output_file: str):
    """Save snapshot to JSON file"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(snapshot, f, indent=2)

    print(f"\n💾 Snapshot saved to: {output_path}")
    print(f"📄 File size: {output_path.stat().st_size} bytes")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Extract IOS-XE features without capturing sensitive data (STANDALONE - no external files needed!)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Live device (requires netmiko - prompt for password)
  python extract_iosxe_features_standalone.py --host 192.168.1.1 --username admin -o snapshot.json

  # Offline config file (NO external dependencies!)
  python extract_iosxe_features_standalone.py --config running-config.txt -o snapshot.json

Features:
  ✅ Single file - no YAML files needed
  ✅ No PyYAML library needed
  ✅ Works completely offline
  ✅ 66 IOS-XE features embedded
  ✅ Only Python 3.6+ required
        """
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--host', help='Device IP/hostname (live mode - requires netmiko)')
    mode_group.add_argument('--config', help='Config file path (offline mode - no dependencies!)')

    # Common options
    parser.add_argument('-o', '--output', required=True,
                       help='Output snapshot file (JSON)')

    # Live mode options
    parser.add_argument('--username', help='SSH username (required for live mode)')
    parser.add_argument('--password', help='SSH password (prompt if not provided)')
    parser.add_argument('--device-type', default='cisco_ios',
                       help='Netmiko device type (default: cisco_ios)')

    args = parser.parse_args()

    # Validate arguments
    if args.host and not args.username:
        parser.error("--username required for live device mode")

    try:
        print("="*80)
        print("🚀 IOS-XE Feature Extractor v1.0.0 (STANDALONE)")
        print("="*80)

        # Live device mode
        if args.host:
            if not NETMIKO_AVAILABLE:
                print("\n❌ ERROR: Live device mode requires netmiko library")
                print("   Install with: pip install netmiko")
                print("   OR use offline mode: --config running-config.txt")
                return 1

            # Get password
            if args.password:
                password = args.password
            else:
                password = getpass.getpass(f"Password for {args.username}@{args.host}: ")

            snapshot = extract_from_live_device(
                host=args.host,
                username=args.username,
                password=password,
                device_type=args.device_type
            )

        # Offline config mode
        else:
            snapshot = extract_from_config_file(config_file=args.config)

        # Save snapshot
        save_snapshot(snapshot, args.output)

        print("\n✅ Feature extraction complete!")
        print(f"📊 {snapshot['feature_count']} features detected")
        print(f"🔒 No sensitive data captured")
        print(f"📦 Standalone mode - no external files needed")

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
