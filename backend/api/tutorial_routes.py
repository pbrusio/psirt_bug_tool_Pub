"""
Tutorial Routes - Interactive Getting Started Guide

Provides an HTML-based tutorial accessible via /api/v1/tutorial
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from .docs_common import get_page_template

router = APIRouter(prefix="/api/v1", tags=["Tutorial"])


TUTORIAL_CONTENT = """
    <h1>Getting Started Tutorial</h1>
    <p class="subtitle">Learn how to leverage the PSIRT Analyzer for maximum effectiveness</p>

    <!-- Dual Path Concept -->
    <h2>The "Dual-Path" Concept</h2>
    <p>Before diving into the tabs, understand that this tool has <strong>two distinct engines</strong>. Knowing which one to use is key:</p>

    <div class="concept-grid">
        <div class="concept-card database">
            <h3>
                <span class="badge speed">&lt;10ms</span>
                Path A: Database Engine
            </h3>
            <div class="stat-row">
                <span class="stat-label">What it is</span>
                <span class="stat-value">Fast lookup</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Database Size</span>
                <span class="stat-value">9,600+ bugs/PSIRTs</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Response Time</span>
                <span class="stat-value">1-6ms with filters</span>
            </div>
            <div class="stat-row" style="border: none;">
                <span class="stat-label">Best For</span>
                <span class="stat-value">Upgrade planning, bulk scanning</span>
            </div>
        </div>

        <div class="concept-card ai">
            <h3>
                <span class="badge smart">~3s</span>
                Path B: AI Engine
            </h3>
            <div class="stat-row">
                <span class="stat-label">What it is</span>
                <span class="stat-value">LLM analysis</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Model</span>
                <span class="stat-value">Foundation-Sec-8B</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Response Time</span>
                <span class="stat-value">~3s (cached: &lt;10ms)</span>
            </div>
            <div class="stat-row" style="border: none;">
                <span class="stat-label">Best For</span>
                <span class="stat-value">New advisories, zero-days</span>
            </div>
        </div>
    </div>

    <!-- Quick Reference -->
    <div class="quick-ref">
        <h3>Which Tab Should I Use?</h3>
        <div class="quick-ref-grid">
            <div class="quick-ref-item">
                <span>Got a new advisory email?</span>
                <span class="ref-arrow">→</span>
                <span class="ref-tab">Security Analysis</span>
            </div>
            <div class="quick-ref-item">
                <span>Planning an upgrade?</span>
                <span class="ref-arrow">→</span>
                <span class="ref-tab">Defect Scanner</span>
            </div>
            <div class="quick-ref-item">
                <span>Daily fleet posture check?</span>
                <span class="ref-arrow">→</span>
                <span class="ref-tab">Device Inventory</span>
            </div>
            <div class="quick-ref-item">
                <span>Need to explain to management?</span>
                <span class="ref-arrow">→</span>
                <span class="ref-tab">AI Assistant</span>
            </div>
            <div class="quick-ref-item">
                <span>System maintenance?</span>
                <span class="ref-arrow">→</span>
                <span class="ref-tab">System Admin</span>
            </div>
        </div>
    </div>

    <!-- Tab Sections -->
    <h2>UI Flow Implementation</h2>

    <!-- Tab 1: Security Analysis -->
    <div class="tab-section">
        <div class="tab-header">
            <div class="tab-number">1</div>
            <div>
                <div class="tab-title">Security Analysis</div>
                <div class="tab-subtitle">The "Incident Response" Tab</div>
            </div>
        </div>
        <div class="tab-content">
            <div class="flow-diagram">
                Paste text <span class="flow-arrow">→</span> AI analyzes it <span class="flow-arrow">→</span> Verify against devices
            </div>

            <div class="use-case">
                <div class="use-case-label">Use Case</div>
                You receive a frantic email about a "New SSH Vulnerability in IOS-XE"
            </div>

            <h4>How to Leverage:</h4>
            <ol>
                <li><strong>Paste the email text</strong> into the summary box</li>
                <li>The <strong>Sec-8B Model</strong> will predict which features are affected (e.g., <code>SEC_SSH</code>, <code>MGMT_HTTP</code>)</li>
                <li><strong>Action:</strong> Immediately run a verify against a device to see if your specific configuration is vulnerable</li>
            </ol>

            <div class="pro-tips">
                <div class="pro-tips-label">Pro Tips</div>
                <ul>
                    <li>Include as much context as possible in the pasted text</li>
                    <li>The AI extracts feature labels even from informal descriptions</li>
                    <li>Use this tab for zero-day advisories before they hit the database</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Tab 2: Defect Scanner -->
    <div class="tab-section">
        <div class="tab-header">
            <div class="tab-number">2</div>
            <div>
                <div class="tab-title">Defect Scanner</div>
                <div class="tab-subtitle">The "Upgrade Planning" Tab</div>
            </div>
        </div>
        <div class="tab-content">
            <div class="flow-diagram">
                Select Platform <span class="flow-arrow">→</span> Version <span class="flow-arrow">→</span> Hardware <span class="flow-arrow">→</span> Feature Mode
            </div>

            <div class="use-case">
                <div class="use-case-label">Use Case</div>
                You are planning a fleet upgrade to 17.10.1
            </div>

            <h4>How to Leverage:</h4>
            <ol>
                <li>Select your target <strong>Platform</strong> (IOS-XE, IOS-XR, ASA, FTD, NX-OS)</li>
                <li>Enter the target <strong>Version</strong> (e.g., <code>17.10.1</code>)</li>
                <li><strong>Crucial Step:</strong> Select a <strong>Hardware Model</strong> (e.g., <code>Cat9300</code>) - filters ~25% of bugs</li>
                <li><strong>Advanced:</strong> Use <strong>Feature Mode</strong> to filter 40-80% of false positives</li>
            </ol>

            <table class="filter-table">
                <thead>
                    <tr>
                        <th>Stage</th>
                        <th>Bug Count</th>
                        <th>Reduction</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Raw Database</td>
                        <td>9,600+ bugs</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>+ Hardware Filter</td>
                        <td>~7,200 bugs</td>
                        <td class="reduction">~25% reduction</td>
                    </tr>
                    <tr>
                        <td>+ Feature Filter</td>
                        <td>~50-500 bugs</td>
                        <td class="reduction">40-80% reduction</td>
                    </tr>
                </tbody>
            </table>

            <div class="pro-tips">
                <div class="pro-tips-label">Pro Tips</div>
                <ul>
                    <li>Always provide hardware model - it dramatically reduces noise</li>
                    <li>Use "Compare Versions" to evaluate upgrade paths</li>
                    <li>Export results to CSV for change management documentation</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Tab 3: Device Inventory -->
    <div class="tab-section">
        <div class="tab-header">
            <div class="tab-number">3</div>
            <div>
                <div class="tab-title">Device Inventory</div>
                <div class="tab-subtitle">The "Fleet Management" Tab</div>
            </div>
        </div>
        <div class="tab-content">
            <div class="flow-diagram">
                Sync (ISE) / Discover (SSH) <span class="flow-arrow">→</span> Bulk Scan <span class="flow-arrow">→</span> Report
            </div>

            <div class="use-case">
                <div class="use-case-label">Use Case</div>
                Daily security posture check across your fleet
            </div>

            <h4>How to Leverage:</h4>
            <ol>
                <li><strong>Sync from ISE</strong> to populate your "Source of Truth"</li>
                <li><strong>Run SSH Discovery</strong> - the most powerful feature:
                    <ul>
                        <li>Logs into devices</li>
                        <li>Runs <code>show running-config</code></li>
                        <li><strong>Caches the active features</strong></li>
                    </ul>
                </li>
                <li><strong>Bulk Scan</strong> all devices with feature-aware filtering</li>
            </ol>

            <div class="pro-tips">
                <div class="pro-tips-label">Pro Tips</div>
                <ul>
                    <li>Re-run SSH discovery after major config changes</li>
                    <li>Use "Compare Versions" for upgrade planning</li>
                    <li>Future scans are <strong>Feature-Aware instantly</strong> without reconnecting</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Tab 4: AI Assistant -->
    <div class="tab-section">
        <div class="tab-header">
            <div class="tab-number">4</div>
            <div>
                <div class="tab-title">AI Assistant</div>
                <div class="tab-subtitle">The "Analyst" Tab</div>
            </div>
        </div>
        <div class="tab-content">
            <div class="flow-diagram">
                Dashboard View <span class="flow-arrow">→</span> Natural Language Query <span class="flow-arrow">→</span> Remediation
            </div>

            <div class="use-case">
                <div class="use-case-label">Use Case</div>
                High-level reporting or deep-dive investigations
            </div>

            <h4>How to Leverage:</h4>
            <ol>
                <li><strong>Dashboard:</strong> Check the "Risk Level" summary immediately</li>
                <li><strong>Ask Questions:</strong> Use natural language queries</li>
                <li><strong>Reasoning:</strong> The AI explains the logic of vulnerability labels</li>
            </ol>

            <h4>Supported Query Types:</h4>
            <table>
                <thead>
                    <tr>
                        <th>Query Type</th>
                        <th>Example</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td>Prioritization</td><td>"What should I fix first?"</td></tr>
                    <tr><td>Risk Assessment</td><td>"Which devices are at highest risk?"</td></tr>
                    <tr><td>Explanation</td><td>"Why is this device vulnerable?"</td></tr>
                    <tr><td>Statistics</td><td>"How many critical bugs in my inventory?"</td></tr>
                    <tr><td>Remediation</td><td>"How do I fix CSCxx12345?"</td></tr>
                </tbody>
            </table>

            <div class="pro-tips">
                <div class="pro-tips-label">Pro Tips</div>
                <ul>
                    <li>Use suggested question chips for common queries</li>
                    <li>Bridges the gap between "it's vulnerable" and "here is why"</li>
                    <li>Great for executive summaries and audit reports</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Tab 5: System Admin -->
    <div class="tab-section">
        <div class="tab-header">
            <div class="tab-number">5</div>
            <div>
                <div class="tab-title">System Admin</div>
                <div class="tab-subtitle">The "Maintenance" Tab</div>
            </div>
        </div>
        <div class="tab-content">
            <div class="flow-diagram">
                Health Check <span class="flow-arrow">→</span> Cache Stats <span class="flow-arrow">→</span> Offline Updates
            </div>

            <div class="use-case">
                <div class="use-case-label">Use Case</div>
                Air-gapped environments or routine maintenance
            </div>

            <h4>How to Leverage:</h4>
            <ol>
                <li><strong>Health Check:</strong> Verify all services are operational</li>
                <li><strong>Cache Management:</strong> Clear cache after model/taxonomy updates</li>
                <li><strong>Offline Update:</strong> Use drag-and-drop for air-gapped systems</li>
            </ol>

            <div class="pro-tips">
                <div class="pro-tips-label">Pro Tips</div>
                <ul>
                    <li>Monitor cache hit rates for performance insights</li>
                    <li>Clear cache if you see stale predictions</li>
                    <li>Use offline updates for secure lab environments</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Summary -->
    <h2>Summary: Best Ways to Leverage</h2>

    <div class="summary-grid">
        <div class="summary-card">
            <h4>1. Filter Aggressively</h4>
            <p>Always provide Hardware Model and Feature Configs (via SSH discovery or Snapshots). The raw database has 9,000+ bugs; filtering reduces this to the ~50 that actually matter.</p>
        </div>
        <div class="summary-card">
            <h4>2. Use the Right Engine</h4>
            <p>Don't use AI for checking version numbers (use Scanner). Don't use Scanner for analyzing raw text advisories (use AI).</p>
        </div>
        <div class="summary-card">
            <h4>3. Sync Often</h4>
            <p>Keep Inventory synced with ISE and re-run SSH discovery after major config changes to keep your "Feature Profile" accurate.</p>
        </div>
        <div class="summary-card">
            <h4>4. Air-Gapped Power</h4>
            <p>If in a secure lab, leverage SnapshotForm (Scanner/Analysis) and Offline Updates (Admin) for full functionality without internet.</p>
        </div>
    </div>

    <a href="/api/v1/docs-hub" class="back-link">← Back to Documentation Hub</a>
"""


@router.get("/tutorial", response_class=HTMLResponse, summary="Interactive Tutorial",
            description="Get the interactive HTML tutorial for using the PSIRT Analyzer")
async def get_tutorial():
    """
    Returns an interactive HTML tutorial that explains:
    - The dual-path architecture (Database vs AI engine)
    - How to use each tab effectively
    - Best practices for filtering and scanning
    - Air-gapped environment support
    """
    return HTMLResponse(content=get_page_template(
        title="Getting Started Tutorial",
        active_page="tutorial",
        content=TUTORIAL_CONTENT,
        page_class="page-tutorial"
    ))


@router.get("/tutorial/json", summary="Tutorial Content (JSON)",
            description="Get the tutorial content in JSON format for programmatic access")
async def get_tutorial_json():
    """
    Returns tutorial content as structured JSON for integration with other systems.
    Useful for displaying tutorial content in the frontend React app.
    """
    return {
        "title": "Getting Started Tutorial",
        "description": "Learn how to leverage the PSIRT Analyzer for maximum effectiveness",
        "sections": [
            {
                "title": "The 'Dual-Path' Concept",
                "content": "Understand the difference between the Database Engine (Path A) and the AI Engine (Path B).",
                "details": {
                    "path_a": {
                        "name": "Database Engine",
                        "speed": "<10ms",
                        "best_for": "Upgrade planning, bulk scanning"
                    },
                    "path_b": {
                        "name": "AI Engine",
                        "speed": "~3s",
                        "best_for": "New advisories, zero-days"
                    }
                }
            },
            {
                "title": "UI Flow Implementation",
                "content": "Detailed guide on how to use each of the 5 main tabs: Security Analysis, Defect Scanner, Device Inventory, AI Assistant, and System Admin."
            }
        ]
    }


@router.get("/tutorial/json", summary="Tutorial Content (JSON)",
            description="Get the tutorial content in JSON format for programmatic access")
async def get_tutorial_json():
    """
    Returns tutorial content as structured JSON for integration with other systems.
    """
    return {
        "title": "PSIRT Analyzer - Getting Started Tutorial",
        "version": "1.0",
        "dual_path_concept": {
            "description": "This tool has two distinct engines. Knowing which one to use is key.",
            "path_a": {
                "name": "Database Engine",
                "speed": "<10ms",
                "description": "Fast lookup against 9,600+ known Cisco bugs/PSIRTs",
                "best_for": ["Known versions", "Upgrade planning", "Bulk scanning"]
            },
            "path_b": {
                "name": "AI Engine",
                "speed": "~3s (cached: <10ms)",
                "description": "LLM analysis that reads unstructured text",
                "best_for": ["New advisory emails", "Zero-day alerts", "Text snippets"]
            }
        },
        "tabs": [
            {
                "number": 1,
                "name": "Security Analysis",
                "subtitle": "The 'Incident Response' Tab",
                "flow": "Paste text → AI analyzes it → Verify against devices",
                "use_case": "You receive a frantic email about a new vulnerability",
                "engine": "AI"
            },
            {
                "number": 2,
                "name": "Defect Scanner",
                "subtitle": "The 'Upgrade Planning' Tab",
                "flow": "Select Platform → Version → Hardware → Feature Mode",
                "use_case": "Planning a fleet upgrade",
                "engine": "Database"
            },
            {
                "number": 3,
                "name": "Device Inventory",
                "subtitle": "The 'Fleet Management' Tab",
                "flow": "Sync (ISE) / Discover (SSH) → Bulk Scan → Report",
                "use_case": "Daily security posture check",
                "engine": "Database"
            },
            {
                "number": 4,
                "name": "AI Assistant",
                "subtitle": "The 'Analyst' Tab",
                "flow": "Dashboard View → Natural Language Query → Remediation",
                "use_case": "High-level reporting or deep-dive investigations",
                "engine": "AI"
            },
            {
                "number": 5,
                "name": "System Admin",
                "subtitle": "The 'Maintenance' Tab",
                "flow": "Health Check → Cache Stats → Offline Updates",
                "use_case": "Air-gapped environments or maintenance",
                "engine": "N/A"
            }
        ],
        "best_practices": [
            {
                "title": "Filter Aggressively",
                "description": "Always provide Hardware Model and Feature Configs to reduce 9,000+ bugs to ~50 relevant ones"
            },
            {
                "title": "Use the Right Engine",
                "description": "Database for version checks, AI for text analysis"
            },
            {
                "title": "Sync Often",
                "description": "Keep ISE synced and re-run SSH discovery after config changes"
            },
            {
                "title": "Air-Gapped Power",
                "description": "Use SnapshotForm and Offline Updates for secure lab environments"
            }
        ],
        "filtering_effectiveness": {
            "raw_database": "9,600+ bugs",
            "with_hardware_filter": "~7,200 bugs (~25% reduction)",
            "with_feature_filter": "~50-500 bugs (40-80% reduction)"
        }
    }
