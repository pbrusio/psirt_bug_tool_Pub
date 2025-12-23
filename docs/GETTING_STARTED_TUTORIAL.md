# Getting Started: How to Use the PSIRT Analyzer

**Version:** 1.0 | **Last Updated:** December 17, 2025

This guide walks you through the dual-path architecture and shows you how to leverage each tab effectively.

---

## The "Dual-Path" Concept

Before diving into the tabs, understand that this tool has **two distinct engines**. Knowing which one to use is the key to leveraging the tool effectively.

### Path A: The Database Engine (Speed)

| Attribute | Details |
|-----------|---------|
| **What it is** | Super-fast (<10ms) lookup against a local database of 9,600+ known Cisco bugs/PSIRTs |
| **Response Time** | 1-6ms with filtering |
| **When to use** | Known versions (e.g., "I want to upgrade to 17.10.1") or existing inventory |
| **Best for** | Upgrade planning, bulk scanning, daily posture checks |

### Path B: The AI Engine (Adaptability)

| Attribute | Details |
|-----------|---------|
| **What it is** | Slower (~3s) but smarter LLM analysis that reads unstructured text |
| **Response Time** | 2-3 seconds (with caching: <10ms for known advisories) |
| **When to use** | New security advisory emails, text snippets, zero-day alerts not in the database |
| **Best for** | Incident response, analyzing new PSIRTs, understanding vulnerability context |

---

## UI Flow Implementation

The application is structured into **5 main tabs**. Here is the optimal flow for each:

---

### 1. Security Analysis (The "Incident Response" Tab)

**Flow:** `Paste text` → `AI analyzes it` → `Verify against your devices`

**Use Case:** You receive a frantic email about a "New SSH Vulnerability in IOS-XE".

**How to Leverage:**

1. **Paste the email text** into the summary box
2. The **Sec-8B Model** will predict which features are affected (e.g., `SEC_SSH`, `MGMT_HTTP`)
3. Review the predicted labels and confidence scores
4. **Action:** Immediately run a verify against a device to see if your specific configuration is vulnerable

**Pro Tips:**
- Include as much context as possible in the pasted text
- The AI extracts feature labels even from informal descriptions
- Use this tab for zero-day advisories before they hit the database

---

### 2. Defect Scanner (The "Upgrade Planning" Tab)

**Flow:** `Select Platform` → `Version` → `Hardware` → `Feature Mode`

**Use Case:** You are planning a fleet upgrade to 17.10.1.

**How to Leverage:**

1. Select your target **Platform** (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
2. Enter the target **Version** (e.g., `17.10.1`)
3. **Crucial Step:** Select a **Hardware Model** (e.g., `Cat9300`)
   - This filters out ~25% of irrelevant bugs
4. **Advanced:** Use **Feature Mode**
   - Upload a config snapshot, or
   - Select features from your inventory
   - Filters out 40-80% of false positives

**Pro Tips:**
- Always provide hardware model - it dramatically reduces noise
- Use "Compare Versions" to evaluate upgrade paths
- Export results to CSV for change management documentation

---

### 3. Device Inventory (The "Fleet Management" Tab)

**Flow:** `Sync (ISE) / Discover (SSH)` → `Bulk Scan` → `Report`

**Use Case:** Daily security posture check across your fleet.

**How to Leverage:**

1. **Sync from ISE** to populate your "Source of Truth"
   - Pulls device inventory automatically
2. **Run SSH Discovery** - This is the most powerful feature:
   - Logs into devices
   - Runs `show running-config`
   - **Caches the active features**
3. **Bulk Scan** all devices with feature-aware filtering

**Effect:** Future scans are "Feature-Aware" instantly, without needing to reconnect.

**Pro Tips:**
- Re-run SSH discovery after major config changes
- Use the "Compare Versions" feature for upgrade planning
- Filter by platform/status to focus on high-risk devices

---

### 4. AI Assistant (The "Analyst" Tab)

**Flow:** `Dashboard View` → `Natural Language Query` → `Remediation`

**Use Case:** High-level reporting or deep-dive investigations.

**How to Leverage:**

1. **Dashboard:** Check the "Risk Level" summary immediately upon opening
2. **Ask Questions:** Use natural language queries:
   - "Which devices are most critical?"
   - "Explain why device X is vulnerable to CSCwd12345"
   - "What should I prioritize?"
   - "How many devices are affected by SSH vulnerabilities?"
3. **Reasoning:** The AI can explain the logic of a vulnerability label

**Supported Intents:**
| Query Type | Example |
|------------|---------|
| Prioritization | "What should I fix first?" |
| Risk Assessment | "Which devices are at highest risk?" |
| Explanation | "Why is this device vulnerable?" |
| Statistics | "How many critical bugs in my inventory?" |
| Remediation | "How do I fix CSCxx12345?" |

**Pro Tips:**
- Use the suggested question chips for common queries
- The AI bridges the gap between "it's vulnerable" and "here is why"
- Great for executive summaries and audit reports

---

### 5. System Admin (The "Maintenance" Tab)

**Flow:** `Health Check` → `Cache Stats` → `Offline Updates`

**Use Case:** Air-gapped environments or routine maintenance.

**How to Leverage:**

1. **Health Check:** Verify all services are operational
2. **Cache Management:** Clear cache after updating:
   - AI model changes
   - Taxonomy updates
   - Database refreshes
3. **Offline Update:** For air-gapped systems:
   - Use the drag-and-drop zone
   - Upload new vulnerability database ZIPs

**Pro Tips:**
- Monitor cache hit rates for performance insights
- Clear cache if you see stale predictions
- Use offline updates for secure lab environments

---

## Summary: Best Ways to Leverage

### 1. Filter Aggressively
Always provide **Hardware Model** and **Feature Configs** (via SSH discovery or Snapshots).

| Stage | Bug Count |
|-------|-----------|
| Raw Database | 9,600+ bugs |
| + Hardware Filter | ~7,200 bugs (~25% reduction) |
| + Feature Filter | ~50-500 bugs (40-80% reduction) |

### 2. Use the Right Engine

| Scenario | Use This |
|----------|----------|
| Checking version numbers | **Scanner Tab** (Database) |
| Analyzing raw text advisory | **Security Analysis Tab** (AI) |
| Bulk device scanning | **Device Inventory Tab** (Database) |
| Understanding vulnerability context | **AI Assistant Tab** (AI) |

### 3. Sync Often
- Keep Inventory synced with ISE
- Re-run SSH discovery after major config changes
- This keeps your "Feature Profile" accurate

### 4. Air-Gapped Power
For secure labs without internet:
- Use **Snapshot Form** in Scanner/Analysis tabs
- Use **Offline Updates** in Admin tab
- Full functionality maintained without connectivity

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│                    WHICH TAB SHOULD I USE?                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Got a new advisory email?      → Security Analysis (AI)        │
│  Planning an upgrade?           → Defect Scanner (Database)     │
│  Daily fleet posture check?     → Device Inventory (Database)   │
│  Need to explain to management? → AI Assistant (AI)             │
│  System maintenance?            → System Admin                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Start with Device Inventory** - Sync your devices from ISE or add manually
2. **Run SSH Discovery** - Get feature profiles for accurate scanning
3. **Bulk Scan** - Identify your current exposure
4. **Use AI Assistant** - Get prioritized action items
5. **Plan Upgrades** - Use Scanner with version comparison

For detailed API documentation, see `/docs` endpoint.
