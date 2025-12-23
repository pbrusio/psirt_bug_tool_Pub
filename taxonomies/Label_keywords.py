# CVE-EVAL Label Keywords Dictionary
# Used for:
# 1. Filtering hallucinated labels (remove labels without keyword evidence)
# 2. Calculating per-label confidence scores
# 
# Derived from enriched taxonomy definitions created during 8 enrichment sessions

LABEL_KEYWORDS = {
    # =========================================================================
    # L2 SWITCHING (13 labels)
    # =========================================================================
    'L2_STP': [
        'spanning-tree', 'stp', 'bpdu', 'root bridge', 'portfast', 
        'rapid-pvst', 'mstp', 'mst', 'topology change', 'bridge priority',
        'spanning tree', 'pvst'
    ],
    'L2_EtherChannel': [
        'etherchannel', 'port-channel', 'channel-group', 'load-balance',
        'port channel', 'ether channel', 'lac', 'bundle'
    ],
    'L2_LACP': [
        'lacp', '802.3ad', 'actor', 'partner', 'lacp rate', 
        'link aggregation control', 'lacp fast', 'lacp slow'
    ],
    'L2_PAgP': [
        'pagp', 'port aggregation', 'desirable', 'pagp learn-method'
    ],
    'L2_VLAN_VTP': [
        'vlan', 'vtp', 'trunk', 'native vlan', 'vlan database',
        'vlan pruning', 'vtp domain', 'vtp mode', 'switchport trunk'
    ],
    'L2_PrivateVLAN': [
        'private-vlan', 'pvlan', 'isolated', 'community vlan', 
        'promiscuous', 'private vlan'
    ],
    'L2_UDLD': [
        'udld', 'unidirectional link', 'unidirectional'
    ],
    'L2_REP': [
        'rep ', 'resilient ethernet', 'rep segment', 'rep block'
    ],
    'L2_PTP_gPTP': [
        'ptp', 'precision time', 'gptp', '802.1as', 'boundary clock',
        'transparent clock', '1588', 'ptp domain'
    ],
    'L2_L2ProtocolTunneling': [
        'l2pt', 'protocol tunneling', 'l2 protocol tunnel'
    ],
    'L2_Switchport_Trunk': [
        'switchport mode trunk', 'trunk allowed', 'trunk native',
        'dot1q', 'trunking'
    ],
    'L2_Switchport_Access': [
        'switchport mode access', 'access vlan', 'switchport access'
    ],
    'L2_Dot1Q_Tunnel': [
        'dot1q tunnel', 'q-in-q', '802.1q tunnel', 'qinq', 'dot1q-tunnel'
    ],

    # =========================================================================
    # L3 ROUTING (10 labels)
    # =========================================================================
    'RTE_Static': [
        'static route', 'ip route', 'default route', 'floating static',
        'static routing'
    ],
    'RTE_OSPFv2': [
        'ospf', 'ospfv2', 'lsa', 'spf', 'area 0', 'neighbor adjacency',
        'designated router', 'ospf neighbor', 'link state', 'ospf area'
    ],
    'RTE_OSPF': [
        'ospf', 'lsa', 'spf', 'area 0', 'neighbor adjacency',
        'designated router', 'ospf neighbor', 'link state', 'ospf area'
    ],
    'RTE_OSPFv3': [
        'ospfv3', 'ipv6 ospf', 'ospf v3'
    ],
    'RTE_EIGRP': [
        'eigrp', 'diffusing update', 'dual', 'feasible successor',
        'eigrp neighbor', 'eigrp topology'
    ],
    'RTE_BGP': [
        'bgp', 'autonomous system', 'ebgp', 'ibgp', 'as-path',
        'bgp neighbor', 'bgp prefix', 'bgp peer', 'bgp session',
        'bgp update', 'route reflector'
    ],
    'RTE_BFD': [
        'bfd', 'bidirectional forwarding', 'bfd session', 'bfd neighbor'
    ],
    'RTE_Redistribution_PBR': [
        'redistribute', 'route-map', 'policy-based routing', 'pbr',
        'redistribution'
    ],
    'RTE_CEF': [
        'cef', 'cisco express forwarding', 'adjacency', 'fib',
        'forwarding information base'
    ],
    'RTE_ISIS': [
        'isis', 'is-is', 'intermediate system', 'isis adjacency',
        'isis neighbor', 'net address'
    ],

    # =========================================================================
    # FHRP (3 labels)
    # =========================================================================
    'FHRP_HSRP': [
        'hsrp', 'standby', 'hot standby', 'hsrp group', 'hsrp priority'
    ],
    'FHRP_VRRP': [
        'vrrp', 'virtual router', 'vrrp master', 'vrrp backup', 'vrrp group'
    ],
    'FHRP_GLBP': [
        'glbp', 'gateway load balancing', 'avf', 'avg', 'glbp group'
    ],

    # =========================================================================
    # IP SERVICES (9 labels)
    # =========================================================================
    'IP_DHCP_Server': [
        'dhcp server', 'ip dhcp pool', 'dhcp binding', 'dhcp lease',
        'dhcp excluded'
    ],
    'IP_DHCP_Relay': [
        'dhcp relay', 'ip helper-address', 'giaddr', 'helper address',
        'dhcp forward'
    ],
    'IP_NAT': [
        'nat', 'network address translation', 'inside', 'outside',
        'overload', 'pat', 'nat pool', 'nat translation'
    ],
    'IP_NHRP_DMVPN': [
        'nhrp', 'dmvpn', 'spoke', 'hub', 'multipoint gre', 'mgre',
        'nhrp registration', 'nhrp resolution'
    ],
    'IP_WCCP': [
        'wccp', 'web cache', 'wccp redirect'
    ],
    'IP_Unnumbered': [
        'ip unnumbered', 'unnumbered interface'
    ],
    'IP_PrefixList': [
        'prefix-list', 'ip prefix-list', 'prefix list'
    ],
    'IP_SLA_TWAMP': [
        'ip sla', 'twamp', 'rtt', 'service level', 'sla monitor',
        'sla responder'
    ],
    'IP_Fragmentation': [
        'fragment', 'reassembly', 'mtu', 'fragmentation', 'ip fragment',
        'fragment offset', 'dont fragment'
    ],

    # =========================================================================
    # MULTICAST (3 labels)
    # =========================================================================
    'MCAST_PIM': [
        'pim', 'multicast', 'rendezvous point', 'pim sparse', 'pim dense',
        'pim neighbor', 'mroute', 'multicast routing', ' rp '
    ],
    'MCAST_IGMP_MLD_Snoop': [
        'igmp', 'mld', 'igmp snooping', 'mld snooping', 'querier',
        'igmp group', 'multicast group'
    ],
    'MCAST_SSM': [
        'ssm', 'source-specific multicast', 'igmpv3', 'source specific'
    ],

    # =========================================================================
    # SECURITY (11 labels)
    # =========================================================================
    'SEC_8021X': [
        '802.1x', 'dot1x', 'eap', 'authenticator', 'supplicant', 'eapol'
    ],
    'SEC_MAB': [
        'mab', 'mac authentication bypass', 'mac auth'
    ],
    'SEC_PortSecurity': [
        'port-security', 'mac limit', 'violation', 'port security',
        'secure mac', 'sticky mac'
    ],
    'SEC_DHCP_Snooping': [
        'dhcp snooping', 'ip dhcp snooping', 'dhcp trust', 'snooping trust',
        'dhcp snoop'
    ],
    'SEC_DHCP_SNOOP': [
        'dhcp snooping', 'ip dhcp snooping', 'dhcp trust', 'snooping trust'
    ],
    'SEC_IP_Source_Guard': [
        'ip source guard', 'ipsg', 'ip verify source', 'source guard'
    ],
    'SEC_DAI': [
        'dai', 'dynamic arp inspection', 'arp acl', 'arp inspection',
        'arp validate'
    ],
    'SEC_StormControl': [
        'storm-control', 'broadcast storm', 'multicast storm', 'storm control',
        'traffic storm'
    ],
    'SEC_CoPP': [
        'copp', 'control plane policing', 'control-plane', 'cpp',
        'control plane protection'
    ],
    'SEC_PACL_VACL': [
        'pacl', 'vacl', 'port acl', 'vlan acl', 'vlan access-map'
    ],
    'SEC_BGP_ROUTE_FILTERING': [
        'bgp filter', 'as-path access-list', 'route-map', 'prefix-list',
        'bgp route filter', 'distribute-list'
    ],

    # =========================================================================
    # MANAGEMENT (9 labels)
    # =========================================================================
    'MGMT_SNMP': [
        'snmp', 'mib', 'oid', 'community string', 'snmpv3', 'trap',
        'snmpwalk', 'snmp-server', 'snmpv2', 'snmpv1', 'snmp agent'
    ],
    'MGMT_Syslog': [
        'syslog', 'logging', 'log message', 'severity', 'logging host',
        'logging buffer'
    ],
    'MGMT_NetFlow_FNF': [
        'netflow', 'flexible netflow', 'flow record', 'flow exporter',
        'fnf', 'flow monitor', 'nbar', 'avc'
    ],
    'MGMT_SPAN_ERSPAN': [
        'span', 'rspan', 'erspan', 'monitor session', 'port mirror',
        'port mirroring', 'remote span'
    ],
    'MGMT_LLDP_CDP': [
        'lldp', 'cdp', 'neighbor', 'tlv', 'discovery protocol',
        'cdp neighbor', 'lldp neighbor'
    ],
    'MGMT_AAA_TACACS_RADIUS': [
        'aaa', 'tacacs', 'radius', 'authorization', 'accounting', 
        'tacacs+', 'radius-server', 'aaa server', 'aaa authentication',
        'aaa authorization'
    ],
    'MGMT_SSH_HTTP': [
        'ssh', 'http', 'https', 'web ui', 'webui', 'web interface',
        'web-based', 'ssh server', 'http server', 'management interface'
    ],
    'MGMT_NTP': [
        'ntp', 'network time', 'clock', 'stratum', 'ntp server',
        'ntp peer', 'time synchronization'
    ],
    'MGMT_RPC_NETCONF': [
        'netconf', 'yang', 'restconf', 'rpc', 'xml', 'netconf-yang',
        'yang model'
    ],

    # =========================================================================
    # TRUSTSEC (2 labels)
    # =========================================================================
    'CTS_Base': [
        'cts', 'trustsec', 'sgt', 'security group tag', 'sgacl',
        'security group', 'cts role-based'
    ],
    'CTS_SXP': [
        'sxp', 'sgt exchange', 'sxp connection', 'sxp peer'
    ],

    # =========================================================================
    # HIGH AVAILABILITY (4 labels)
    # =========================================================================
    'HA_StackWise': [
        'stackwise', 'svl', 'stack', 'dual active detection', 'dad',
        'stackwise virtual', 'stack member', 'switch stack'
    ],
    'HA_StackPower': [
        'stack-power', 'power stack', 'poe budget', 'stackpower',
        'power sharing'
    ],
    'HA_Redundancy_SSO': [
        'sso', 'stateful switchover', 'issu', 'redundancy', 'in-service',
        'nonstop', 'switchover', 'active standby'
    ],
    'HA_NSF_GR': [
        'nsf', 'graceful restart', 'non-stop forwarding', 'gr-helper',
        'graceful-restart', 'nonstop forwarding'
    ],

    # =========================================================================
    # SYSTEM (3 labels)
    # =========================================================================
    'SYS_Boot_Upgrade': [
        'boot', 'upgrade', 'install', 'rommon', 'image', 'software update',
        'firmware', 'reload', 'software install', 'bundle', 'reimage',
        'config replace'
    ],
    'SYS_Licensing_Smart': [
        'license', 'smart license', 'cssm', 'cslu', 'smart account',
        'slr', 'license reservation', 'entitlement', 'smart licensing'
    ],
    'SYS_Time_Range_Scheduler': [
        'time-range', 'scheduler', 'periodic', 'time range', 'absolute',
        'time-based'
    ],

    # =========================================================================
    # INTERFACES (3 labels)
    # =========================================================================
    'IF_Physical': [
        'interface', 'gigabitethernet', 'tengigabitethernet', 'transceiver',
        'sfp', 'physical', 'port', 'phy', 'link down', 'link up',
        'hundredgig', 'fortygig'
    ],
    'IF_PortTemplates': [
        'template', 'autoconf', 'source template', 'interface template',
        'built-in template'
    ],
    'IF_Speed_Duplex': [
        'speed', 'duplex', 'auto-negotiation', 'mdi', 'mdix', 'autoneg',
        'half duplex', 'full duplex', 'negotiation'
    ],

    # =========================================================================
    # QOS (5 labels)
    # =========================================================================
    'QOS_MQC_ClassPolicy': [
        'class-map', 'policy-map', 'service-policy', 'mqc', 'match',
        'class map', 'policy map', 'service policy'
    ],
    'QOS_Marking_Trust': [
        'dscp', 'cos', 'marking', 'trust', 'qos', 'ip precedence',
        'mls qos', 'qos marking'
    ],
    'QOS_Queuing_Scheduling': [
        'queue', 'priority', 'bandwidth', 'shape', 'scheduler', 'queuing',
        'scheduling', 'wrr', 'cbwfq', 'llq', 'queue-limit'
    ],
    'QOS_POLICING': [
        'police', 'policer', 'rate-limit', 'policing', 'cir', 'pir',
        'conform', 'exceed', 'violate'
    ],
    'QOS_Police_Priority': [
        'police', 'priority', 'llq', 'low latency', 'priority queue'
    ],

    # =========================================================================
    # APPLICATION HOSTING (1 label)
    # =========================================================================
    'APP_IOx': [
        'iox', 'app-hosting', 'container', 'docker', 'guestshell',
        'application hosting', 'appgig', 'app hosting'
    ],

    # =========================================================================
    # MPLS (3 labels)
    # =========================================================================
    'MPLS_LDP': [
        'ldp', 'label distribution', 'mpls label', 'mpls ldp',
        'ldp neighbor', 'ldp session'
    ],
    'MPLS_STATIC': [
        'mpls static', 'static label', 'static mpls'
    ],
    'MPLS_TE': [
        'mpls te', 'traffic engineering', 'rsvp', 'mpls tunnel',
        'te tunnel', 'explicit path'
    ],

    # =========================================================================
    # VPN (1 label)
    # =========================================================================
    'VPN_IKEv2': [
        'ikev2', 'ike', 'ipsec', 'vpn', 'crypto', 'ikev1',
        'ipsec tunnel', 'crypto map', 'ipsec sa'
    ],

    # =========================================================================
    # SD-WAN (2 labels)
    # =========================================================================
    'SDWAN_UTD': [
        'utd', 'unified threat defense', 'snort', 'ips', 'sd-wan',
        'sdwan', 'threat defense'
    ],
    'SDWAN_Filtering': [
        'sd-wan', 'sdwan', 'packet filter', 'sd-wan acl', 'viptela'
    ],

    # =========================================================================
    # WIRELESS (1 label)
    # =========================================================================
    'WIRELESS_MDNS': [
        'mdns', 'bonjour', 'multicast dns', 'mdns gateway', 'service discovery'
    ],
}


def filter_unsupported_labels(labels: list, summary: str) -> list:
    """
    Remove labels that have no keyword evidence in the summary.
    
    Args:
        labels: List of predicted labels
        summary: Advisory summary text
        
    Returns:
        Filtered list of labels with keyword support
    """
    summary_lower = summary.lower()
    validated = []
    
    for label in labels:
        keywords = LABEL_KEYWORDS.get(label, [])
        if not keywords:
            # No keyword list defined for this label - keep it (be conservative)
            validated.append(label)
        elif any(kw.lower() in summary_lower for kw in keywords):
            # Found supporting evidence - keep it
            validated.append(label)
        # else: no evidence found - drop it
    
    return validated


def calculate_label_confidence(label: str, summary: str) -> float:
    """
    Calculate confidence score for a label based on keyword evidence.
    
    Args:
        label: The predicted label
        summary: Advisory summary text
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    summary_lower = summary.lower()
    keywords = LABEL_KEYWORDS.get(label, [])
    
    if not keywords:
        return 0.5  # Unknown - no keywords defined
    
    # Count keyword matches
    matches = sum(1 for kw in keywords if kw.lower() in summary_lower)
    
    # Count total keyword occurrences
    total_hits = sum(summary_lower.count(kw.lower()) for kw in keywords)
    
    # Calculate keyword coverage
    keyword_coverage = matches / len(keywords) if keywords else 0
    
    # Determine confidence based on evidence strength
    if total_hits >= 10:
        # Very strong evidence (keyword appears many times)
        return min(0.98, 0.85 + keyword_coverage * 0.13)
    elif total_hits >= 5:
        # Strong evidence
        return min(0.95, 0.75 + keyword_coverage * 0.20)
    elif total_hits >= 2:
        # Moderate evidence
        return 0.55 + keyword_coverage * 0.25
    elif total_hits >= 1:
        # Weak evidence
        return 0.35 + keyword_coverage * 0.25
    else:
        # No evidence
        return 0.15


def get_label_evidence(label: str, summary: str) -> dict:
    """
    Get detailed evidence for why a label was assigned.
    
    Args:
        label: The predicted label
        summary: Advisory summary text
        
    Returns:
        Dictionary with evidence details
    """
    summary_lower = summary.lower()
    keywords = LABEL_KEYWORDS.get(label, [])
    
    found_keywords = []
    keyword_counts = {}
    
    for kw in keywords:
        count = summary_lower.count(kw.lower())
        if count > 0:
            found_keywords.append(kw)
            keyword_counts[kw] = count
    
    return {
        'label': label,
        'keywords_checked': len(keywords),
        'keywords_found': len(found_keywords),
        'found_keywords': found_keywords,
        'keyword_counts': keyword_counts,
        'total_hits': sum(keyword_counts.values()),
        'confidence': calculate_label_confidence(label, summary)
    }


# =========================================================================
# BUG COMPONENT MAPPING
# Cisco bugs use internal component names that don't match PSIRT keywords
# This maps Cisco-internal terminology to feature labels
# =========================================================================
BUG_COMPONENT_MAP = {
    # Network Management / YANG / NETCONF
    'yang': 'MGMT_RPC_NETCONF',
    'yang model': 'MGMT_RPC_NETCONF',
    'netconf': 'MGMT_RPC_NETCONF',
    'restconf': 'MGMT_RPC_NETCONF',
    'operational data': 'MGMT_RPC_NETCONF',
    'config model': 'MGMT_RPC_NETCONF',
    'ietf-': 'MGMT_RPC_NETCONF',
    'openconfig': 'MGMT_RPC_NETCONF',
    'cisco-ios-xe-': 'MGMT_RPC_NETCONF',
    'rpc': 'MGMT_RPC_NETCONF',

    # NetFlow / NBAR / AVC
    'nbar': 'MGMT_NetFlow_FNF',
    'avc': 'MGMT_NetFlow_FNF',
    'fnf': 'MGMT_NetFlow_FNF',
    'flow monitor': 'MGMT_NetFlow_FNF',
    'flow record': 'MGMT_NetFlow_FNF',
    'application visibility': 'MGMT_NetFlow_FNF',
    'performance monitor': 'MGMT_NetFlow_FNF',
    'perfmon': 'MGMT_NetFlow_FNF',
    'classification': 'MGMT_NetFlow_FNF',

    # VXLAN / EVPN / NVE
    'nve': 'OVERLAY_VXLAN_EVPN',
    'vxlan': 'OVERLAY_VXLAN_EVPN',
    'evpn': 'OVERLAY_VXLAN_EVPN',
    'fabric': 'OVERLAY_VXLAN_EVPN',
    'vni': 'OVERLAY_VXLAN_EVPN',

    # LISP
    'lisp': 'OVERLAY_LISP',
    'rloc': 'OVERLAY_LISP',
    'eid': 'OVERLAY_LISP',
    'locator': 'OVERLAY_LISP',

    # SD-WAN
    'sdwan': 'SDWAN_UTD',
    'sd-wan': 'SDWAN_UTD',
    'vmanage': 'SDWAN_UTD',
    'vbond': 'SDWAN_UTD',
    'vsmart': 'SDWAN_UTD',
    'vedge': 'SDWAN_UTD',
    'cedge': 'SDWAN_UTD',
    'utd': 'SDWAN_UTD',
    'snort': 'SDWAN_UTD',

    # Policy-Based Routing / Route Maps
    'route-policy': 'RTE_Redistribution_PBR',
    'rpl': 'RTE_Redistribution_PBR',
    'pbr': 'RTE_Redistribution_PBR',
    'prefix-set': 'RTE_Redistribution_PBR',
    'community-set': 'RTE_Redistribution_PBR',
    'route map': 'RTE_Redistribution_PBR',
    'route-map': 'RTE_Redistribution_PBR',

    # BFD
    'bfd': 'RTE_BFD',
    'bidirectional forwarding': 'RTE_BFD',

    # CEF
    'cef': 'RTE_CEF',
    'fib': 'RTE_CEF',
    'adjacency': 'RTE_CEF',
    'forwarding information': 'RTE_CEF',

    # Application Hosting / IOx
    'iox': 'APP_IOx',
    'guestshell': 'APP_IOx',
    'apphosting': 'APP_IOx',
    'app-hosting': 'APP_IOx',
    'container': 'APP_IOx',
    'docker': 'APP_IOx',
    'appgig': 'APP_IOx',

    # Smart Licensing
    'smart license': 'SYS_Licensing_Smart',
    'cssm': 'SYS_Licensing_Smart',
    'cslu': 'SYS_Licensing_Smart',
    'slr': 'SYS_Licensing_Smart',
    'entitlement': 'SYS_Licensing_Smart',

    # Boot / Upgrade
    'rommon': 'SYS_Boot_Upgrade',
    'install': 'SYS_Boot_Upgrade',
    'issu': 'SYS_Boot_Upgrade',
    'software install': 'SYS_Boot_Upgrade',
    'boot': 'SYS_Boot_Upgrade',
    'reimage': 'SYS_Boot_Upgrade',
    'upgrade': 'SYS_Boot_Upgrade',

    # L2 Protocol Tunneling
    'l2pt': 'L2_L2ProtocolTunneling',
    'protocol tunnel': 'L2_L2ProtocolTunneling',

    # VLAN / VTP
    'vlan': 'L2_VLAN_VTP',
    'vtp': 'L2_VLAN_VTP',
    'trunk': 'L2_VLAN_VTP',

    # STP
    'spanning-tree': 'L2_STP',
    'stp': 'L2_STP',
    'bpdu': 'L2_STP',
    'portfast': 'L2_STP',
    'mstp': 'L2_STP',

    # EtherChannel
    'port-channel': 'L2_EtherChannel',
    'etherchannel': 'L2_EtherChannel',
    'channel-group': 'L2_EtherChannel',
    'bundle': 'L2_EtherChannel',

    # LACP
    'lacp': 'L2_LACP',
    '802.3ad': 'L2_LACP',

    # HSRP
    'hsrp': 'FHRP_HSRP',
    'hot standby': 'FHRP_HSRP',
    'standby': 'FHRP_HSRP',

    # VRRP
    'vrrp': 'FHRP_VRRP',
    'virtual router': 'FHRP_VRRP',

    # OSPF
    'ospf': 'RTE_OSPF',
    'lsa': 'RTE_OSPF',
    'spf': 'RTE_OSPF',
    'link state': 'RTE_OSPF',

    # EIGRP
    'eigrp': 'RTE_EIGRP',
    'dual': 'RTE_EIGRP',
    'diffusing update': 'RTE_EIGRP',

    # BGP
    'bgp': 'RTE_BGP',
    'ebgp': 'RTE_BGP',
    'ibgp': 'RTE_BGP',
    'as-path': 'RTE_BGP',

    # ISIS
    'isis': 'RTE_ISIS',
    'is-is': 'RTE_ISIS',

    # MPLS
    'mpls': 'MPLS_LDP',
    'ldp': 'MPLS_LDP',
    'label': 'MPLS_LDP',

    # NAT
    'nat': 'IP_NAT',
    'pat': 'IP_NAT',
    'network address translation': 'IP_NAT',

    # DHCP
    'dhcp server': 'IP_DHCP_Server',
    'dhcp pool': 'IP_DHCP_Server',
    'dhcp relay': 'IP_DHCP_Relay',
    'helper-address': 'IP_DHCP_Relay',

    # SNMP
    'snmp': 'MGMT_SNMP',
    'mib': 'MGMT_SNMP',
    'trap': 'MGMT_SNMP',

    # Syslog
    'syslog': 'MGMT_Syslog',
    'logging': 'MGMT_Syslog',

    # NTP
    'ntp': 'MGMT_NTP',
    'time sync': 'MGMT_NTP',

    # AAA
    'tacacs': 'MGMT_AAA_TACACS_RADIUS',
    'radius': 'MGMT_AAA_TACACS_RADIUS',
    'aaa': 'MGMT_AAA_TACACS_RADIUS',

    # SSH/HTTP
    'ssh': 'MGMT_SSH_HTTP',
    'http': 'MGMT_SSH_HTTP',
    'https': 'MGMT_SSH_HTTP',
    'webui': 'MGMT_SSH_HTTP',

    # QoS
    'qos': 'QOS_Marking_Trust',
    'dscp': 'QOS_Marking_Trust',
    'cos': 'QOS_Marking_Trust',
    'class-map': 'QOS_MQC_ClassPolicy',
    'policy-map': 'QOS_MQC_ClassPolicy',
    'service-policy': 'QOS_MQC_ClassPolicy',
    'police': 'QOS_POLICING',
    'policer': 'QOS_POLICING',
    'queue': 'QOS_Queuing_Scheduling',
    'scheduler': 'QOS_Queuing_Scheduling',

    # Security
    '802.1x': 'SEC_8021X',
    'dot1x': 'SEC_8021X',
    'eap': 'SEC_8021X',
    'mab': 'SEC_MAB',
    'port-security': 'SEC_PortSecurity',
    'dhcp snooping': 'SEC_DHCP_Snooping',
    'dai': 'SEC_DAI',
    'arp inspection': 'SEC_DAI',
    'ip source guard': 'SEC_IP_Source_Guard',
    'copp': 'SEC_CoPP',
    'control plane': 'SEC_CoPP',
    'storm-control': 'SEC_StormControl',

    # TrustSec
    'cts': 'CTS_Base',
    'trustsec': 'CTS_Base',
    'sgt': 'CTS_Base',
    'sxp': 'CTS_SXP',

    # Multicast
    'pim': 'MCAST_PIM',
    'multicast': 'MCAST_PIM',
    'igmp': 'MCAST_IGMP_MLD_Snoop',
    'mld': 'MCAST_IGMP_MLD_Snoop',

    # HA / Redundancy
    'stackwise': 'HA_StackWise',
    'svl': 'HA_StackWise',
    'stack': 'HA_StackWise',
    'sso': 'HA_Redundancy_SSO',
    'switchover': 'HA_Redundancy_SSO',
    'nsf': 'HA_NSF_GR',
    'graceful restart': 'HA_NSF_GR',

    # VPN / Crypto
    'ipsec': 'VPN_IKEv2',
    'ikev2': 'VPN_IKEv2',
    'ike': 'VPN_IKEv2',
    'crypto': 'VPN_IKEv2',
    'vpn': 'VPN_IKEv2',

    # Interfaces
    'transceiver': 'IF_Physical',
    'sfp': 'IF_Physical',
    'phy': 'IF_Physical',
    'link down': 'IF_Physical',
    'link up': 'IF_Physical',
    'interface': 'IF_Physical',
    'speed': 'IF_Speed_Duplex',
    'duplex': 'IF_Speed_Duplex',
    'autoneg': 'IF_Speed_Duplex',
}


def filter_labels_hybrid(labels: list, summary: str, source_type: str = 'psirt') -> list:
    """
    Unified filtering that adapts to source type.

    For PSIRTs: Strict keyword filtering (they are verbose)
    For Bugs: Trust model predictions, validate with component mapping

    Args:
        labels: List of predicted labels
        summary: Advisory/bug summary text
        source_type: 'psirt' or 'bug'

    Returns:
        Filtered list of labels
    """
    if not labels:
        return labels

    if source_type == 'psirt':
        # Strict keyword filtering for PSIRTs (they have verbose descriptions)
        filtered = filter_unsupported_labels(labels, summary)
        # Never return empty - keep first prediction as fallback
        return filtered if filtered else [labels[0]]

    elif source_type == 'bug':
        # For bugs: trust model more, but validate with component mapping
        summary_lower = summary.lower()

        # Find component matches in summary
        component_labels = set()
        for component, label in BUG_COMPONENT_MAP.items():
            if component.lower() in summary_lower:
                component_labels.add(label)

        validated = []
        for label in labels:
            # Keep if: matches component OR is in top 2 predictions
            if label in component_labels:
                validated.append(label)
            elif label in labels[:2]:
                # Trust model's top 2 predictions for bugs
                validated.append(label)

        # Remove duplicates while preserving order
        seen = set()
        result = []
        for label in validated:
            if label not in seen:
                seen.add(label)
                result.append(label)

        # Never return empty
        return result if result else [labels[0]]

    else:
        # Unknown source type - return as-is
        return labels


def validate_with_component_map(labels: list, summary: str) -> tuple[list, set]:
    """
    Validate bug labels against component mapping.
    Returns (validated_labels, component_matches)

    Useful for debugging and understanding why labels were kept/removed.
    """
    summary_lower = summary.lower()

    # Find all component matches
    component_matches = set()
    component_labels = set()
    for component, label in BUG_COMPONENT_MAP.items():
        if component.lower() in summary_lower:
            component_matches.add(component)
            component_labels.add(label)

    # Validate each label
    validated = []
    for label in labels:
        if label in component_labels or label in labels[:2]:
            validated.append(label)

    # Handle empty labels case
    if not validated and labels:
        return [labels[0]], component_matches
    return validated, component_matches


# Quick test
if __name__ == '__main__':
    test_summary = """
    A vulnerability in the Simple Network Management Protocol (SNMP) subsystem 
    of Cisco IOS Software and Cisco IOS XE Software could allow an authenticated, 
    remote attacker to cause a denial of service (DoS) condition. This vulnerability 
    is due to a stack overflow condition in the SNMP subsystem. An attacker could 
    exploit this vulnerability by sending crafted SNMP packets. Note: This 
    vulnerability affects all versions of SNMP including SNMPv1, SNMPv2c, and SNMPv3.
    """
    
    test_labels = ['MGMT_SNMP', 'RTE_OSPF', 'MGMT_RPC_NETCONF']
    
    print("=" * 60)
    print("LABEL KEYWORD FILTER TEST")
    print("=" * 60)
    print(f"\nInput labels: {test_labels}")
    
    filtered = filter_unsupported_labels(test_labels, test_summary)
    print(f"Filtered labels: {filtered}")
    
    print("\n" + "-" * 60)
    print("Evidence for each label:")
    print("-" * 60)
    
    for label in test_labels:
        evidence = get_label_evidence(label, test_summary)
        print(f"\n{label}:")
        print(f"  Keywords found: {evidence['keywords_found']}/{evidence['keywords_checked']}")
        print(f"  Found: {evidence['found_keywords']}")
        print(f"  Total hits: {evidence['total_hits']}")
        print(f"  Confidence: {evidence['confidence']:.2f}")
        print(f"  Verdict: {'✅ KEEP' if label in filtered else '❌ REMOVE'}")