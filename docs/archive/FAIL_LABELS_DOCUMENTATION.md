# FAIL Labels Documentation

Generated: 2025-12-12T08:19:57.312870

## Summary

These labels have training data but 0% recall. The model is predicting
other labels instead, indicating the CoT reasoning was learned without
proper taxonomy definitions.

| Label | Train Examples | Test Examples | What Model Predicts |
|-------|---------------|---------------|---------------------|
| RTE_Static | 44 | 2 | MPLS_STATIC(1), MPLS_TE(1) |
| SEC_MAB | 42 | 2 | MGMT_AAA_TACACS_RADIUS(2) |
| HA_Redundancy_SSO | 45 | 3 | SYS_Licensing_Smart(1) |
| VPN_IKEv2 | 15 | 1 | MPLS_STATIC(1) |
| MGMT_RPC / NETCONF | 68 | 2 | MGMT_SNMP(1) |
| HA_StackPower | 10 | 1 | L2_L2ProtocolTunneling(1) |
| SYS_Licensing_Smart | 63 | 3 | MPLS_STATIC(1), IP_PrefixList(1), L2_UDLD(1) |
| RTE_OSPF | 105 | 4 | MPLS_STATIC(2), RTE_BGP(1), MCAST_PIM(1) |
| CTS_Base | 53 | 1 | (empty predictions) |
| SEC_BGP_ROUTE_FILTERING | 166 | 4 | MPLS_STATIC(2), MCAST_IGMP_MLD_Snoop(1), L2_STP(1) |
| MPLS_TE | 35 | 3 | MPLS_STATIC(1), MCAST_PIM(1), MCAST_IGMP_MLD_Snoop(1) |

## Detailed Examples by Label

### RTE_Static

**Training examples:** 44
**Test examples:** 2

**Example 24:**
- Truth: ['RTE_Static']
- Predicted: ['MPLS_STATIC', 'MPLS_TE']
- Raw output snippet: `['MPLS_STATIC', 'MPLS_TE']...`

**Example 86:**
- Truth: ['RTE_Static', 'CTS_Base']
- Predicted: []
- Raw output snippet: `['MGMT_RPC / NETCONF']...`

### SEC_MAB

**Training examples:** 42
**Test examples:** 2

**Example 66:**
- Truth: ['MGMT_AAA_TACACS_RADIUS', 'SEC_MAB']
- Predicted: ['MGMT_AAA_TACACS_RADIUS']
- Raw output snippet: `['MGMT_AAA_TACACS_RADIUS']...`

**Example 78:**
- Truth: ['SEC_MAB']
- Predicted: ['MGMT_AAA_TACACS_RADIUS']
- Raw output snippet: `['MGMT_AAA_TACACS_RADIUS']...`

### HA_Redundancy_SSO

**Training examples:** 45
**Test examples:** 3

**Example 17:**
- Truth: ['MGMT_AAA_TACACS_RADIUS', 'SYS_Boot_Upgrade', 'HA_Redundancy_SSO']
- Predicted: []
- Raw output snippet: `['MGMT_RPC / NETCONF']...`

**Example 26:**
- Truth: ['SYS_Boot_Upgrade', 'HA_Redundancy_SSO']
- Predicted: ['SYS_Licensing_Smart']
- Raw output snippet: `['SYS_Licensing_Smart']...`

**Example 72:**
- Truth: ['HA_Redundancy_SSO']
- Predicted: []
- Raw output snippet: `['MGMT_RPC / NETCONF']...`

### VPN_IKEv2

**Training examples:** 15
**Test examples:** 1

**Example 36:**
- Truth: ['VPN_IKEv2']
- Predicted: ['MPLS_STATIC']
- Raw output snippet: `['MPLS_STATIC']...`

### MGMT_RPC / NETCONF

**Training examples:** 68
**Test examples:** 2

**Example 64:**
- Truth: ['MGMT_RPC / NETCONF']
- Predicted: ['MGMT_SNMP']
- Raw output snippet: `['MGMT_SNMP']...`

**Example 68:**
- Truth: ['MGMT_RPC / NETCONF']
- Predicted: []
- Raw output snippet: `['MGMT_RPC / NETCONF']...`

### HA_StackPower

**Training examples:** 10
**Test examples:** 1

**Example 61:**
- Truth: ['IF_Physical', 'HA_StackPower']
- Predicted: ['L2_L2ProtocolTunneling']
- Raw output snippet: `['L2_L2ProtocolTunneling']...`

### SYS_Licensing_Smart

**Training examples:** 63
**Test examples:** 3

**Example 23:**
- Truth: ['SYS_Licensing_Smart']
- Predicted: ['MPLS_STATIC']
- Raw output snippet: `['MPLS_STATIC']...`

**Example 39:**
- Truth: ['SYS_Licensing_Smart']
- Predicted: ['IP_PrefixList']
- Raw output snippet: `['IP_PrefixList']...`

**Example 56:**
- Truth: ['SYS_Boot_Upgrade', 'SYS_Licensing_Smart']
- Predicted: ['L2_UDLD']
- Raw output snippet: `['L2_UDLD']...`

### RTE_OSPF

**Training examples:** 105
**Test examples:** 4

**Example 1:**
- Truth: ['RTE_BGP', 'RTE_OSPF']
- Predicted: ['MPLS_STATIC']
- Raw output snippet: `['MPLS_STATIC']...`

**Example 7:**
- Truth: ['RTE_BGP', 'RTE_OSPF']
- Predicted: ['RTE_BGP']
- Raw output snippet: `['RTE_BGP']...`

**Example 45:**
- Truth: ['MPLS_TE', 'RTE_OSPF']
- Predicted: ['MCAST_PIM', 'MCAST_IGMP_MLD_Snoop']
- Raw output snippet: `['MCAST_PIM', 'MCAST_IGMP_MLD_Snoop']...`

**Example 76:**
- Truth: ['RTE_OSPF']
- Predicted: ['MPLS_STATIC']
- Raw output snippet: `['MPLS_STATIC']...`

### CTS_Base

**Training examples:** 53
**Test examples:** 1

**Example 86:**
- Truth: ['RTE_Static', 'CTS_Base']
- Predicted: []
- Raw output snippet: `['MGMT_RPC / NETCONF']...`

### SEC_BGP_ROUTE_FILTERING

**Training examples:** 166
**Test examples:** 4

**Example 10:**
- Truth: ['SEC_BGP_ROUTE_FILTERING']
- Predicted: ['MPLS_STATIC']
- Raw output snippet: `['MPLS_STATIC']...`

**Example 15:**
- Truth: ['SEC_BGP_ROUTE_FILTERING']
- Predicted: ['MCAST_IGMP_MLD_Snoop', 'L2_STP']
- Raw output snippet: `['MCAST_IGMP_MLD_Snoop', 'L2_STP']...`

**Example 65:**
- Truth: ['SEC_BGP_ROUTE_FILTERING']
- Predicted: ['L2_L2ProtocolTunneling']
- Raw output snippet: `['L2_L2ProtocolTunneling']...`

**Example 81:**
- Truth: ['SEC_BGP_ROUTE_FILTERING']
- Predicted: ['MPLS_STATIC']
- Raw output snippet: `['MPLS_STATIC']...`

### MPLS_TE

**Training examples:** 35
**Test examples:** 3

**Example 32:**
- Truth: ['MPLS_TE']
- Predicted: ['MPLS_STATIC']
- Raw output snippet: `['MPLS_STATIC']...`

**Example 45:**
- Truth: ['MPLS_TE', 'RTE_OSPF']
- Predicted: ['MCAST_PIM', 'MCAST_IGMP_MLD_Snoop']
- Raw output snippet: `['MCAST_PIM', 'MCAST_IGMP_MLD_Snoop']...`

**Example 49:**
- Truth: ['MPLS_TE']
- Predicted: ['L2_EtherChannel']
- Raw output snippet: `['L2_EtherChannel']...`

## Root Cause Analysis

The root cause is that CoT reasoning was synthesized by GPT-4o WITHOUT
the enriched taxonomy definitions that are now injected at inference time.

**Training-Inference Mismatch:**
- At training time: Model saw generic reasoning without semantic guidance
- At inference time: Model receives taxonomy definitions but doesn't use them
- Result: Model learned wrong associations (e.g., 'MPLS' → RTE_BGP)

## Remediation Plan

1. **Re-synthesize CoT** for examples containing FAIL labels
   - Use `scripts/synthesize_reasoning_gemini.py` with --inject-definitions flag
   - Focus on the 11 FAIL labels listed above

2. **Verify corrected reasoning** manually for a sample

3. **Retrain** LoRA adapter on corrected dataset

4. **Re-evaluate** to confirm FAIL labels improve