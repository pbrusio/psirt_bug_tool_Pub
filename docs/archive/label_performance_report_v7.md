# Per-Label Performance Report

Generated: 2025-12-12T09:35:31.906131

## Overall Metrics

| Metric | Value |
|--------|-------|
| Exact Match | 54.8% |
| Partial Match | 67.7% |
| Avg F1 | 0.636 |
| Avg Precision | 0.663 |
| Avg Recall | 0.629 |
| Total Test Examples | 93 |

## Per-Label Performance

Status: GAP=no training data, FAIL=has data but 0 recall, LOW=F1<0.3, MED=0.3-0.7, OK=F1>=0.7

| Label | Precision | Recall | F1 | Train | Test | TP | FP | FN | Status |
|-------|-----------|--------|-----|-------|------|----|----|----|----|
| QOS_Marking_Trust | 0.00 | 0.00 | 0.00 | 8 | 1 | 0 | 0 | 1 | FAIL |
| MPLS_LDP | 0.00 | 0.00 | 0.00 | 52 | 1 | 0 | 0 | 1 | FAIL |
| MGMT_SPAN_ERSPAN | 0.00 | 0.00 | 0.00 | 25 | 1 | 0 | 0 | 1 | FAIL |
| MGMT_AAA_TACACS_RADIUS | 0.00 | 0.00 | 0.00 | 148 | 5 | 0 | 0 | 5 | FAIL |
| MPLS_TE | 0.00 | 0.00 | 0.00 | 35 | 3 | 0 | 0 | 3 | FAIL |
| SEC_BGP_ROUTE_FILTERING | 0.00 | 0.00 | 0.00 | 166 | 4 | 0 | 1 | 4 | FAIL |
| HA_StackPower | 0.00 | 0.00 | 0.00 | 10 | 1 | 0 | 0 | 1 | FAIL |
| VPN_IKEv2 | 0.00 | 0.00 | 0.00 | 15 | 1 | 0 | 0 | 1 | FAIL |
| MGMT_RPC / NETCONF | 0.00 | 0.00 | 0.00 | 68 | 2 | 0 | 0 | 2 | FAIL |
| RTE_OSPF | 0.00 | 0.00 | 0.00 | 105 | 4 | 0 | 0 | 4 | FAIL |
| SYS_Licensing_Smart | 0.14 | 0.33 | 0.20 | 63 | 3 | 1 | 6 | 2 | LOW |
| SYS_Boot_Upgrade | 0.50 | 0.14 | 0.22 | 0 | 7 | 1 | 1 | 6 | LOW |
| CTS_Base | 0.25 | 1.00 | 0.40 | 53 | 1 | 1 | 3 | 0 | MED |
| HA_Redundancy_SSO | 1.00 | 0.33 | 0.50 | 45 | 3 | 1 | 0 | 2 | MED |
| RTE_ISIS | 0.50 | 0.50 | 0.50 | 46 | 2 | 1 | 1 | 1 | MED |
| QOS_POLICING | 1.00 | 0.33 | 0.50 | 20 | 3 | 1 | 0 | 2 | MED |
| IF_PortTemplates | 0.33 | 1.00 | 0.50 | 67 | 1 | 1 | 2 | 0 | MED |
| L2_L2ProtocolTunneling | 0.50 | 1.00 | 0.67 | 10 | 2 | 2 | 2 | 0 | MED |
| RTE_BGP | 0.67 | 0.67 | 0.67 | 332 | 9 | 6 | 3 | 3 | MED |
| SEC_PACL_VACL | 1.00 | 0.50 | 0.67 | 46 | 2 | 1 | 0 | 1 | MED |
| RTE_Redistribution_PBR | 0.67 | 0.67 | 0.67 | 53 | 3 | 2 | 1 | 1 | MED |
| L2_Switchport_Trunk | 0.50 | 1.00 | 0.67 | 24 | 1 | 1 | 1 | 0 | MED |
| RTE_Static | 1.00 | 0.50 | 0.67 | 44 | 2 | 1 | 0 | 1 | MED |
| RTE_CEF | 0.50 | 1.00 | 0.67 | 103 | 1 | 1 | 1 | 0 | MED |
| MGMT_SNMP | 1.00 | 0.60 | 0.75 | 891 | 5 | 3 | 0 | 2 | OK |
| MCAST_PIM | 1.00 | 0.67 | 0.80 | 37 | 3 | 2 | 0 | 1 | OK |
| L2_EtherChannel | 0.67 | 1.00 | 0.80 | 49 | 2 | 2 | 1 | 0 | OK |
| IF_Physical | 0.83 | 0.83 | 0.83 | 196 | 6 | 5 | 1 | 1 | OK |
| MGMT_SSH_HTTP | 1.00 | 0.75 | 0.86 | 217 | 8 | 6 | 0 | 2 | OK |
| MGMT_NetFlow_FNF | 1.00 | 0.75 | 0.86 | 57 | 4 | 3 | 0 | 1 | OK |
| L2_VLAN_VTP | 1.00 | 0.80 | 0.89 | 53 | 5 | 4 | 0 | 1 | OK |
| IP_NAT | 1.00 | 1.00 | 1.00 | 40 | 2 | 2 | 0 | 0 | OK |
| L2_PAgP | 1.00 | 1.00 | 1.00 | 6 | 1 | 1 | 0 | 0 | OK |
| L2_PTP_gPTP | 1.00 | 1.00 | 1.00 | 12 | 1 | 1 | 0 | 0 | OK |
| RTE_BFD | 1.00 | 1.00 | 1.00 | 23 | 2 | 2 | 0 | 0 | OK |
| RTE_EIGRP | 1.00 | 1.00 | 1.00 | 18 | 2 | 2 | 0 | 0 | OK |
| MGMT_Syslog | 1.00 | 1.00 | 1.00 | 101 | 1 | 1 | 0 | 0 | OK |
| SEC_MAB | 1.00 | 1.00 | 1.00 | 42 | 2 | 2 | 0 | 0 | OK |
| SYS_Time_Range_Scheduler | 1.00 | 1.00 | 1.00 | 6 | 2 | 2 | 0 | 0 | OK |
| MPLS_STATIC | 1.00 | 1.00 | 1.00 | 15 | 1 | 1 | 0 | 0 | OK |
| SEC_8021X | 1.00 | 1.00 | 1.00 | 104 | 2 | 2 | 0 | 0 | OK |
| L2_Switchport_Access | 1.00 | 1.00 | 1.00 | 13 | 1 | 1 | 0 | 0 | OK |
| L2_STP | 1.00 | 1.00 | 1.00 | 30 | 2 | 2 | 0 | 0 | OK |
| SEC_PortSecurity | 1.00 | 1.00 | 1.00 | 17 | 1 | 1 | 0 | 0 | OK |
| QOS_Police_Priority | 1.00 | 1.00 | 1.00 | 11 | 2 | 2 | 0 | 0 | OK |
| MGMT_LLDP_CDP | 1.00 | 1.00 | 1.00 | 34 | 1 | 1 | 0 | 0 | OK |
| SEC_DHCP_SNOOP | 1.00 | 1.00 | 1.00 | 8 | 1 | 1 | 0 | 0 | OK |
| QOS_MQC_ClassPolicy | 1.00 | 1.00 | 1.00 | 39 | 4 | 4 | 0 | 0 | OK |

## Labels Needing Attention

### FAIL: Labels with training data but 0% recall

- **QOS_Marking_Trust**: 8 training, 1 test, recall=0
- **MPLS_LDP**: 52 training, 1 test, recall=0
- **MGMT_SPAN_ERSPAN**: 25 training, 1 test, recall=0
- **MGMT_AAA_TACACS_RADIUS**: 148 training, 5 test, recall=0
- **MPLS_TE**: 35 training, 3 test, recall=0
- **SEC_BGP_ROUTE_FILTERING**: 166 training, 4 test, recall=0
- **HA_StackPower**: 10 training, 1 test, recall=0
- **VPN_IKEv2**: 15 training, 1 test, recall=0
- **MGMT_RPC / NETCONF**: 68 training, 2 test, recall=0
- **RTE_OSPF**: 105 training, 4 test, recall=0

### LOW: Labels with F1 < 0.3

- **SYS_Licensing_Smart**: F1=0.20, precision=0.14, recall=0.33
- **SYS_Boot_Upgrade**: F1=0.22, precision=0.50, recall=0.14

## Recommendations

2. **Investigate** 10 labels that have training data but aren't being predicted
3. **Improve** 2 labels with low F1 scores
