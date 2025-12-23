# Per-Label Performance Report

Generated: 2025-12-12T07:59:46.682342

## Overall Metrics

| Metric | Value |
|--------|-------|
| Exact Match | 39.4% |
| Partial Match | 48.5% |
| Avg F1 | 0.453 |
| Avg Precision | 0.476 |
| Avg Recall | 0.446 |
| Total Test Examples | 99 |

## Per-Label Performance

Status: GAP=no training data, FAIL=has data but 0 recall, LOW=F1<0.3, MED=0.3-0.7, OK=F1>=0.7

| Label | Precision | Recall | F1 | Train | Test | TP | FP | FN | Status |
|-------|-----------|--------|-----|-------|------|----|----|----|----|
| IP_DHCP_Server | 0.00 | 0.00 | 0.00 | 0 | 1 | 0 | 1 | 1 | GAP |
| SEC_CoPP | 0.00 | 0.00 | 0.00 | 0 | 10 | 0 | 0 | 10 | GAP |
| SYS_Time_Range_Scheduler | 0.00 | 0.00 | 0.00 | 6 | 2 | 0 | 0 | 2 | FAIL |
| MPLS_LDP | 0.00 | 0.00 | 0.00 | 52 | 1 | 0 | 0 | 1 | FAIL |
| QOS_POLICING | 0.00 | 0.00 | 0.00 | 20 | 3 | 0 | 0 | 3 | FAIL |
| MGMT_RPC / NETCONF | 0.00 | 0.00 | 0.00 | 68 | 2 | 0 | 0 | 2 | FAIL |
| VPN_IKEv2 | 0.00 | 0.00 | 0.00 | 15 | 1 | 0 | 0 | 1 | FAIL |
| RTE_Static | 0.00 | 0.00 | 0.00 | 44 | 2 | 0 | 0 | 2 | FAIL |
| QOS_Police_Priority | 0.00 | 0.00 | 0.00 | 11 | 2 | 0 | 0 | 2 | FAIL |
| MPLS_TE | 0.00 | 0.00 | 0.00 | 35 | 3 | 0 | 0 | 3 | FAIL |
| SEC_DHCP_SNOOP | 0.00 | 0.00 | 0.00 | 8 | 1 | 0 | 0 | 1 | FAIL |
| HA_StackPower | 0.00 | 0.00 | 0.00 | 10 | 1 | 0 | 1 | 1 | FAIL |
| CTS_Base | 0.00 | 0.00 | 0.00 | 53 | 1 | 0 | 0 | 1 | FAIL |
| RTE_OSPF | 0.00 | 0.00 | 0.00 | 105 | 4 | 0 | 0 | 4 | FAIL |
| HA_Redundancy_SSO | 0.00 | 0.00 | 0.00 | 45 | 3 | 0 | 1 | 3 | FAIL |
| MPLS_STATIC | 0.00 | 0.00 | 0.00 | 15 | 1 | 0 | 0 | 1 | FAIL |
| RTE_ISIS | 0.00 | 0.00 | 0.00 | 46 | 2 | 0 | 0 | 2 | FAIL |
| SYS_Licensing_Smart | 0.00 | 0.00 | 0.00 | 63 | 3 | 0 | 2 | 3 | FAIL |
| SEC_BGP_ROUTE_FILTERING | 0.00 | 0.00 | 0.00 | 166 | 4 | 0 | 0 | 4 | FAIL |
| MGMT_SPAN_ERSPAN | 0.08 | 1.00 | 0.14 | 25 | 1 | 1 | 12 | 0 | LOW |
| IF_Physical | 0.33 | 0.17 | 0.22 | 196 | 6 | 1 | 2 | 5 | LOW |
| SYS_Boot_Upgrade | 1.00 | 0.14 | 0.25 | 0 | 7 | 1 | 0 | 6 | LOW |
| MGMT_AAA_TACACS_RADIUS | 0.25 | 0.60 | 0.35 | 148 | 5 | 3 | 9 | 2 | MED |
| QOS_MQC_ClassPolicy | 1.00 | 0.25 | 0.40 | 39 | 4 | 1 | 0 | 3 | MED |
| RTE_CEF | 0.25 | 1.00 | 0.40 | 103 | 1 | 1 | 3 | 0 | MED |
| MCAST_PIM | 0.29 | 0.67 | 0.40 | 37 | 3 | 2 | 5 | 1 | MED |
| L2_EtherChannel | 0.33 | 1.00 | 0.50 | 49 | 2 | 2 | 4 | 0 | MED |
| SEC_8021X | 1.00 | 0.50 | 0.67 | 104 | 2 | 1 | 0 | 1 | MED |
| SEC_PACL_VACL | 1.00 | 0.50 | 0.67 | 46 | 2 | 1 | 0 | 1 | MED |
| L2_L2ProtocolTunneling | 0.50 | 1.00 | 0.67 | 10 | 2 | 2 | 2 | 0 | MED |
| RTE_Redistribution_PBR | 0.67 | 0.67 | 0.67 | 53 | 3 | 2 | 1 | 1 | MED |
| SEC_MAB | 1.00 | 0.50 | 0.67 | 42 | 2 | 1 | 0 | 1 | MED |
| RTE_EIGRP | 1.00 | 0.50 | 0.67 | 18 | 2 | 1 | 0 | 1 | MED |
| MGMT_Syslog | 0.50 | 1.00 | 0.67 | 101 | 1 | 1 | 1 | 0 | MED |
| QOS_Marking_Trust | 0.50 | 1.00 | 0.67 | 8 | 1 | 1 | 1 | 0 | MED |
| L2_Switchport_Trunk | 0.50 | 1.00 | 0.67 | 24 | 1 | 1 | 1 | 0 | MED |
| MGMT_NetFlow_FNF | 0.75 | 0.75 | 0.75 | 57 | 4 | 3 | 1 | 1 | OK |
| MGMT_SSH_HTTP | 0.70 | 0.88 | 0.78 | 217 | 8 | 7 | 3 | 1 | OK |
| RTE_BGP | 0.78 | 0.78 | 0.78 | 332 | 9 | 7 | 2 | 2 | OK |
| L2_STP | 0.67 | 1.00 | 0.80 | 30 | 2 | 2 | 1 | 0 | OK |
| IP_NAT | 0.67 | 1.00 | 0.80 | 40 | 2 | 2 | 1 | 0 | OK |
| MGMT_SNMP | 0.71 | 1.00 | 0.83 | 891 | 5 | 5 | 2 | 0 | OK |
| SEC_PortSecurity | 1.00 | 1.00 | 1.00 | 17 | 1 | 1 | 0 | 0 | OK |
| L2_PAgP | 1.00 | 1.00 | 1.00 | 6 | 1 | 1 | 0 | 0 | OK |
| L2_PTP_gPTP | 1.00 | 1.00 | 1.00 | 12 | 1 | 1 | 0 | 0 | OK |
| IF_PortTemplates | 1.00 | 1.00 | 1.00 | 67 | 1 | 1 | 0 | 0 | OK |
| L2_Switchport_Access | 1.00 | 1.00 | 1.00 | 13 | 1 | 1 | 0 | 0 | OK |
| RTE_BFD | 1.00 | 1.00 | 1.00 | 23 | 2 | 2 | 0 | 0 | OK |
| L2_VLAN_VTP | 1.00 | 1.00 | 1.00 | 53 | 5 | 5 | 0 | 0 | OK |
| MGMT_LLDP_CDP | 1.00 | 1.00 | 1.00 | 34 | 1 | 1 | 0 | 0 | OK |

## Labels Needing Attention

### GAP: Labels in test set with NO training data

- **IP_DHCP_Server**: 1 test examples, 0 training examples
- **SEC_CoPP**: 10 test examples, 0 training examples

### FAIL: Labels with training data but 0% recall

- **SYS_Time_Range_Scheduler**: 6 training, 2 test, recall=0
- **MPLS_LDP**: 52 training, 1 test, recall=0
- **QOS_POLICING**: 20 training, 3 test, recall=0
- **MGMT_RPC / NETCONF**: 68 training, 2 test, recall=0
- **VPN_IKEv2**: 15 training, 1 test, recall=0
- **RTE_Static**: 44 training, 2 test, recall=0
- **QOS_Police_Priority**: 11 training, 2 test, recall=0
- **MPLS_TE**: 35 training, 3 test, recall=0
- **SEC_DHCP_SNOOP**: 8 training, 1 test, recall=0
- **HA_StackPower**: 10 training, 1 test, recall=0
- **CTS_Base**: 53 training, 1 test, recall=0
- **RTE_OSPF**: 105 training, 4 test, recall=0
- **HA_Redundancy_SSO**: 45 training, 3 test, recall=0
- **MPLS_STATIC**: 15 training, 1 test, recall=0
- **RTE_ISIS**: 46 training, 2 test, recall=0
- **SYS_Licensing_Smart**: 63 training, 3 test, recall=0
- **SEC_BGP_ROUTE_FILTERING**: 166 training, 4 test, recall=0

### LOW: Labels with F1 < 0.3

- **MGMT_SPAN_ERSPAN**: F1=0.14, precision=0.08, recall=1.00
- **IF_Physical**: F1=0.22, precision=0.33, recall=0.17
- **SYS_Boot_Upgrade**: F1=0.25, precision=1.00, recall=0.14

## Recommendations

1. **Add training data** for 2 labels with no examples
2. **Investigate** 17 labels that have training data but aren't being predicted
3. **Improve** 3 labels with low F1 scores
