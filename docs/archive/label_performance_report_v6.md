# Per-Label Performance Report

Generated: 2025-12-12T08:19:22.371533

## Overall Metrics

| Metric | Value |
|--------|-------|
| Exact Match | 47.3% |
| Partial Match | 55.9% |
| Avg F1 | 0.530 |
| Avg Precision | 0.545 |
| Avg Recall | 0.527 |
| Total Test Examples | 93 |

## Per-Label Performance

Status: GAP=no training data, FAIL=has data but 0 recall, LOW=F1<0.3, MED=0.3-0.7, OK=F1>=0.7

| Label | Precision | Recall | F1 | Train | Test | TP | FP | FN | Status |
|-------|-----------|--------|-----|-------|------|----|----|----|----|
| RTE_Static | 0.00 | 0.00 | 0.00 | 44 | 2 | 0 | 0 | 2 | FAIL |
| SEC_MAB | 0.00 | 0.00 | 0.00 | 42 | 2 | 0 | 0 | 2 | FAIL |
| HA_Redundancy_SSO | 0.00 | 0.00 | 0.00 | 45 | 3 | 0 | 1 | 3 | FAIL |
| VPN_IKEv2 | 0.00 | 0.00 | 0.00 | 15 | 1 | 0 | 0 | 1 | FAIL |
| MGMT_RPC / NETCONF | 0.00 | 0.00 | 0.00 | 68 | 2 | 0 | 0 | 2 | FAIL |
| HA_StackPower | 0.00 | 0.00 | 0.00 | 10 | 1 | 0 | 1 | 1 | FAIL |
| SYS_Licensing_Smart | 0.00 | 0.00 | 0.00 | 63 | 3 | 0 | 2 | 3 | FAIL |
| RTE_OSPF | 0.00 | 0.00 | 0.00 | 105 | 4 | 0 | 0 | 4 | FAIL |
| CTS_Base | 0.00 | 0.00 | 0.00 | 53 | 1 | 0 | 0 | 1 | FAIL |
| SEC_BGP_ROUTE_FILTERING | 0.00 | 0.00 | 0.00 | 166 | 4 | 0 | 0 | 4 | FAIL |
| MPLS_TE | 0.00 | 0.00 | 0.00 | 35 | 3 | 0 | 1 | 3 | FAIL |
| MPLS_STATIC | 0.11 | 1.00 | 0.20 | 15 | 1 | 1 | 8 | 0 | LOW |
| IF_Physical | 0.33 | 0.17 | 0.22 | 196 | 6 | 1 | 2 | 5 | LOW |
| SYS_Boot_Upgrade | 1.00 | 0.14 | 0.25 | 0 | 7 | 1 | 0 | 6 | LOW |
| QOS_MQC_ClassPolicy | 1.00 | 0.25 | 0.40 | 39 | 4 | 1 | 0 | 3 | MED |
| MGMT_AAA_TACACS_RADIUS | 0.40 | 0.40 | 0.40 | 148 | 5 | 2 | 3 | 3 | MED |
| RTE_CEF | 0.33 | 1.00 | 0.50 | 103 | 1 | 1 | 2 | 0 | MED |
| QOS_POLICING | 1.00 | 0.33 | 0.50 | 20 | 3 | 1 | 0 | 2 | MED |
| MGMT_SNMP | 0.67 | 0.40 | 0.50 | 891 | 5 | 2 | 1 | 3 | MED |
| MGMT_SPAN_ERSPAN | 0.33 | 1.00 | 0.50 | 25 | 1 | 1 | 2 | 0 | MED |
| L2_EtherChannel | 0.40 | 1.00 | 0.57 | 49 | 2 | 2 | 3 | 0 | MED |
| RTE_Redistribution_PBR | 0.67 | 0.67 | 0.67 | 53 | 3 | 2 | 1 | 1 | MED |
| MGMT_NetFlow_FNF | 1.00 | 0.50 | 0.67 | 57 | 4 | 2 | 0 | 2 | MED |
| SEC_PACL_VACL | 1.00 | 0.50 | 0.67 | 46 | 2 | 1 | 0 | 1 | MED |
| SEC_8021X | 1.00 | 0.50 | 0.67 | 104 | 2 | 1 | 0 | 1 | MED |
| MCAST_PIM | 0.67 | 0.67 | 0.67 | 37 | 3 | 2 | 1 | 1 | MED |
| RTE_EIGRP | 1.00 | 0.50 | 0.67 | 18 | 2 | 1 | 0 | 1 | MED |
| RTE_ISIS | 1.00 | 0.50 | 0.67 | 46 | 2 | 1 | 0 | 1 | MED |
| L2_L2ProtocolTunneling | 0.50 | 1.00 | 0.67 | 10 | 2 | 2 | 2 | 0 | MED |
| L2_Switchport_Trunk | 0.50 | 1.00 | 0.67 | 24 | 1 | 1 | 1 | 0 | MED |
| L2_STP | 0.67 | 1.00 | 0.80 | 30 | 2 | 2 | 1 | 0 | OK |
| MGMT_SSH_HTTP | 1.00 | 0.75 | 0.86 | 217 | 8 | 6 | 0 | 2 | OK |
| RTE_BGP | 1.00 | 0.78 | 0.88 | 332 | 9 | 7 | 0 | 2 | OK |
| QOS_Marking_Trust | 1.00 | 1.00 | 1.00 | 8 | 1 | 1 | 0 | 0 | OK |
| IP_NAT | 1.00 | 1.00 | 1.00 | 40 | 2 | 2 | 0 | 0 | OK |
| MGMT_LLDP_CDP | 1.00 | 1.00 | 1.00 | 34 | 1 | 1 | 0 | 0 | OK |
| IF_PortTemplates | 1.00 | 1.00 | 1.00 | 67 | 1 | 1 | 0 | 0 | OK |
| SYS_Time_Range_Scheduler | 1.00 | 1.00 | 1.00 | 6 | 2 | 2 | 0 | 0 | OK |
| QOS_Police_Priority | 1.00 | 1.00 | 1.00 | 11 | 2 | 2 | 0 | 0 | OK |
| RTE_BFD | 1.00 | 1.00 | 1.00 | 23 | 2 | 2 | 0 | 0 | OK |
| SEC_PortSecurity | 1.00 | 1.00 | 1.00 | 17 | 1 | 1 | 0 | 0 | OK |
| MGMT_Syslog | 1.00 | 1.00 | 1.00 | 101 | 1 | 1 | 0 | 0 | OK |
| L2_PTP_gPTP | 1.00 | 1.00 | 1.00 | 12 | 1 | 1 | 0 | 0 | OK |
| SEC_DHCP_SNOOP | 1.00 | 1.00 | 1.00 | 8 | 1 | 1 | 0 | 0 | OK |
| L2_VLAN_VTP | 1.00 | 1.00 | 1.00 | 53 | 5 | 5 | 0 | 0 | OK |
| L2_PAgP | 1.00 | 1.00 | 1.00 | 6 | 1 | 1 | 0 | 0 | OK |
| MPLS_LDP | 1.00 | 1.00 | 1.00 | 52 | 1 | 1 | 0 | 0 | OK |
| L2_Switchport_Access | 1.00 | 1.00 | 1.00 | 13 | 1 | 1 | 0 | 0 | OK |

## Labels Needing Attention

### FAIL: Labels with training data but 0% recall

- **RTE_Static**: 44 training, 2 test, recall=0
- **SEC_MAB**: 42 training, 2 test, recall=0
- **HA_Redundancy_SSO**: 45 training, 3 test, recall=0
- **VPN_IKEv2**: 15 training, 1 test, recall=0
- **MGMT_RPC / NETCONF**: 68 training, 2 test, recall=0
- **HA_StackPower**: 10 training, 1 test, recall=0
- **SYS_Licensing_Smart**: 63 training, 3 test, recall=0
- **RTE_OSPF**: 105 training, 4 test, recall=0
- **CTS_Base**: 53 training, 1 test, recall=0
- **SEC_BGP_ROUTE_FILTERING**: 166 training, 4 test, recall=0
- **MPLS_TE**: 35 training, 3 test, recall=0

### LOW: Labels with F1 < 0.3

- **MPLS_STATIC**: F1=0.20, precision=0.11, recall=1.00
- **IF_Physical**: F1=0.22, precision=0.33, recall=0.17
- **SYS_Boot_Upgrade**: F1=0.25, precision=1.00, recall=0.14

## Recommendations

2. **Investigate** 11 labels that have training data but aren't being predicted
3. **Improve** 3 labels with low F1 scores
