"""
Admin Guide Routes - Data Pipelines & System Maintenance Guide

Provides an HTML-based admin guide accessible via /api/v1/admin-guide
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from .docs_common import get_page_template

router = APIRouter(prefix="/api/v1", tags=["Admin Guide"])


ADMIN_GUIDE_CONTENT = """
    <h1>Admin Guide</h1>
    <p class="subtitle">Data Pipelines & System Maintenance</p>

    <!-- Navigation -->
    <div class="nav-grid">
        <a href="#data-stack" class="nav-card">
            <div class="nav-title">Data Stack</div>
            <div class="nav-desc">What powers everything</div>
        </a>
        <a href="#loading-bugs" class="nav-card">
            <div class="nav-title">Loading Bugs</div>
            <div class="nav-desc">Import from CSV</div>
        </a>
        <a href="#loading-psirts" class="nav-card">
            <div class="nav-title">Loading PSIRTs</div>
            <div class="nav-desc">Import security advisories</div>
        </a>
        <a href="#faiss-index" class="nav-card">
            <div class="nav-title">FAISS Index</div>
            <div class="nav-desc">Training data & similarity</div>
        </a>
        <a href="#taxonomy" class="nav-card">
            <div class="nav-title">Taxonomy</div>
            <div class="nav-desc">Feature label management</div>
        </a>
        <a href="#air-gapped" class="nav-card">
            <div class="nav-title">Air-Gapped</div>
            <div class="nav-desc">Offline deployments</div>
        </a>
    </div>

    <!-- Origin Story -->
    <h2>The Origin Story</h2>
    <p>This project evolved through three distinct phases:</p>

    <div class="data-stack">
        <div class="stack-layer">
            <div class="stack-title"><span class="badge">Phase 1</span> The Labeling Problem</div>
            <p><strong>Challenge:</strong> Cisco publishes thousands of bugs and PSIRTs. Matching them to your devices requires understanding which features they affect.</p>
            <p><strong>Solution:</strong> Train an LLM to read summaries and output feature labels (e.g., <code>MGMT_SSH</code>, <code>SEC_ACL</code>).</p>
        </div>
        <div class="stack-layer">
            <div class="stack-title"><span class="badge">Phase 2</span> The Speed Problem</div>
            <p><strong>Challenge:</strong> LLM inference takes 2-4 seconds per query. Scanning 9,000+ bugs would take hours.</p>
            <p><strong>Solution:</strong> Pre-compute labels and store in SQLite. Now scans complete in <10ms.</p>
        </div>
        <div class="stack-layer">
            <div class="stack-title"><span class="badge">Phase 3</span> The Accuracy Problem</div>
            <p><strong>Challenge:</strong> Generic LLMs hallucinate labels. "SSH vulnerability" might get tagged <code>VOIP_SIP</code>.</p>
            <p><strong>Solution:</strong> Fine-tune Foundation-Sec-8B with LoRA on 2,654 labeled examples. Build FAISS index for semantic retrieval.</p>
        </div>
    </div>

    <!-- Data Stack -->
    <h2 id="data-stack">The Data Stack</h2>

    <div class="data-stack">
        <div class="stack-layer external">
            <div class="stack-title"><span class="badge external">External</span> Data Sources</div>
            <ul>
                <li>Cisco Bug Search Tool → <code>bugs/*.csv</code> (20,000+ bugs)</li>
                <li>Cisco Security Advisories → <code>output/psirts.json</code> (88 PSIRTs)</li>
                <li>Human Labeling → <code>golden_dataset.csv</code> (2,654 examples)</li>
            </ul>
        </div>
        <div class="stack-layer processing">
            <div class="stack-title"><span class="badge processing">Processing</span> Data Pipeline</div>
            <ul>
                <li><code>load_bugs.py</code> → Parse CSV, detect version patterns</li>
                <li><code>load_psirts.py</code> → Parse JSON, map severity</li>
                <li><code>build_faiss_index.py</code> → Embed summaries, create vector store</li>
            </ul>
        </div>
        <div class="stack-layer runtime">
            <div class="stack-title"><span class="badge runtime">Runtime</span> Active Assets</div>
            <ul>
                <li><code>vulnerability_db.sqlite</code> → 9,617 bugs + 88 PSIRTs</li>
                <li><code>models/faiss_index.bin</code> → 2,654 embedded examples</li>
                <li><code>models/adapters/</code> → Platform-specific LoRA weights</li>
                <li><code>taxonomies/features*.yml</code> → 141 feature definitions</li>
            </ul>
        </div>
    </div>

    <!-- Path 1: Loading Bugs -->
    <div class="path-section" id="loading-bugs">
        <div class="path-header">
            <div class="path-number">1</div>
            <div>
                <div class="path-title">Loading Bug Data</div>
                <div class="path-subtitle">Import from Cisco Bug Search CSV</div>
            </div>
        </div>
        <div class="path-content">
            <p><strong>Scenario:</strong> You have a new CSV export from Cisco Bug Search Tool.</p>

            <h4>Steps:</h4>
            <ol>
                <li>Place the CSV in the project directory</li>
                <li>Run the loader with platform specification:</li>
            </ol>

            <div class="command-block">
                <span class="prompt">$</span> python backend/db/load_bugs.py Cat9Kbugs_IOSXE_17.csv --platform IOS-XE
            </div>

            <ol start="3">
                <li>Verify the load:</li>
            </ol>

            <div class="command-block">
                <span class="prompt">$</span> python backend/db/get_last_update.py
            </div>

            <div class="tip">
                <div class="tip-label">Tip</div>
                <strong>Incremental Updates:</strong> The loader skips duplicates by default. Re-running with the same CSV is safe and fast.
            </div>

            <h4>Expected CSV Columns:</h4>
            <table>
                <thead>
                    <tr><th>Column</th><th>Purpose</th></tr>
                </thead>
                <tbody>
                    <tr><td><code>BUG Id</code></td><td>CSCxxx12345 identifier</td></tr>
                    <tr><td><code>BUG headline</code></td><td>Short description</td></tr>
                    <tr><td><code>Bug Severity</code></td><td>1=Critical, 2=High, 3=Medium, 4=Low</td></tr>
                    <tr><td><code>Known Affected Release(s)</code></td><td>Version strings (e.g., "17.10.1 17.11.2")</td></tr>
                    <tr><td><code>Known Fixed Releases</code></td><td>First fixed version</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- Path 2: Loading PSIRTs -->
    <div class="path-section" id="loading-psirts">
        <div class="path-header">
            <div class="path-number">2</div>
            <div>
                <div class="path-title">Loading PSIRT Data</div>
                <div class="path-subtitle">Import Cisco Security Advisories</div>
            </div>
        </div>
        <div class="path-content">
            <p><strong>Scenario:</strong> You want to add new Cisco Security Advisories.</p>

            <h4>Steps:</h4>
            <ol>
                <li>Export PSIRTs to <code>output/psirts.json</code> (see Cisco API docs)</li>
                <li>Run the PSIRT loader:</li>
            </ol>

            <div class="command-block">
                <span class="prompt">$</span> python backend/db/load_psirts.py
            </div>

            <div class="warning">
                <div class="warning-label">Important</div>
                PSIRTs require platform assignment. The loader reads the <code>platform</code> field from JSON. Ensure your export includes platform metadata.
            </div>

            <h4>JSON Structure:</h4>
            <pre><code>{
  "advisoryId": "cisco-sa-2024-iosxe-webui",
  "summary": "A vulnerability in the web UI...",
  "platform": "IOS-XE",
  "_meta": {
    "severity": "Critical",
    "first_published": "2024-10-16",
    "url": "https://sec.cloudapps.cisco.com/..."
  }
}</code></pre>
        </div>
    </div>

    <!-- Path 3: FAISS Index -->
    <div class="path-section" id="faiss-index">
        <div class="path-header">
            <div class="path-number">3</div>
            <div>
                <div class="path-title">Training Data & FAISS Index</div>
                <div class="path-subtitle">Few-shot retrieval system</div>
            </div>
        </div>
        <div class="path-content">
            <p><strong>Scenario:</strong> You've labeled new examples and want to improve few-shot retrieval.</p>

            <h4>Pipeline Flow:</h4>
            <pre><code>golden_dataset.csv  →  build_faiss_index.py  →  models/faiss_index.bin
     (2,654 rows)                                 (vector store)
         ↓
models/labeled_examples.parquet
     (metadata store)</code></pre>

            <h4>Steps:</h4>
            <ol>
                <li>Ensure <code>golden_dataset.csv</code> is current</li>
                <li>Rebuild the index:</li>
            </ol>

            <div class="command-block">
                <span class="prompt">$</span> python scripts/build_faiss_index.py --input golden_dataset.csv
            </div>

            <ol start="3">
                <li>Verify output:</li>
            </ol>

            <div class="command-block">
                <span class="prompt">$</span> ls -lh models/faiss_index.bin<br>
                <span class="prompt">$</span> ls -lh models/labeled_examples.parquet
            </div>

            <div class="tip">
                <div class="tip-label">Tip</div>
                The FAISS index powers "Tier 2" caching. When a new PSIRT comes in, we search for semantically similar examples and use their labels as few-shot context.
            </div>
        </div>
    </div>

    <!-- Path 4: Taxonomy -->
    <div class="path-section" id="taxonomy">
        <div class="path-header">
            <div class="path-number">4</div>
            <div>
                <div class="path-title">Feature Taxonomy Management</div>
                <div class="path-subtitle">Label definitions and detection patterns</div>
            </div>
        </div>
        <div class="path-content">
            <p><strong>Scenario:</strong> You need to add a new feature label or update detection patterns.</p>

            <h4>Taxonomy Files:</h4>
            <pre><code>taxonomies/
├── features.yml      # IOS-XE (primary)
├── features_iosxr.yml
├── features_asa.yml
├── features_nxos.yml
└── features_ftd.yml</code></pre>

            <h4>Label Definition Structure:</h4>
            <pre><code>- label: NEW_FEATURE_LABEL
  domain: Security
  presence:
    config_regex:
      - ^crypto\\s+new-feature\\b
      - ^\\s*new-feature\\s+enable\\b
    show_cmds:
      - show new-feature status
  description: >
    Applies to vulnerabilities affecting the new feature.
    Use when the bug mentions X, Y, or Z.</code></pre>

            <div class="warning">
                <div class="warning-label">Important</div>
                The <code>config_regex</code> patterns power <strong>Feature Filtering</strong> in the Defect Scanner. When a device config is uploaded, we match these patterns to determine which features are enabled.
            </div>
        </div>
    </div>

    <!-- Path 5: Air-Gapped -->
    <div class="path-section" id="air-gapped">
        <div class="path-header">
            <div class="path-number">5</div>
            <div>
                <div class="path-title">Air-Gapped Deployments</div>
                <div class="path-subtitle">Offline update packages</div>
            </div>
        </div>
        <div class="path-content">
            <p><strong>Scenario:</strong> You need to update a system with no internet access.</p>

            <h4>Creating an Update Package:</h4>
            <div class="command-block">
                <span class="prompt">#</span> On connected system<br>
                <span class="prompt">$</span> cp vulnerability_db.sqlite update_package/<br>
                <span class="prompt">$</span> cp models/faiss_index.bin update_package/<br>
                <span class="prompt">$</span> shasum -a 256 update_package/* > update_package/checksums.txt<br>
                <span class="prompt">$</span> zip -r update_v3.1_20251218.zip update_package/
            </div>

            <h4>Labeled Update Package Format:</h4>
            <pre><code>update_20251218/
├── labeled_update.jsonl    # One JSON object per line
├── manifest.json           # Package metadata
└── SHA256SUMS             # Optional checksums</code></pre>

            <h4>Applying on Air-Gapped System:</h4>
            <ol>
                <li>Transfer ZIP via approved method</li>
                <li>Navigate to System Admin tab in UI</li>
                <li>Use "Offline Update" feature - drag and drop the ZIP file</li>
                <li>Verify SHA256 hash matches</li>
                <li>Click "Apply Update"</li>
            </ol>

            <div class="warning">
                <div class="warning-label">Critical</div>
                <strong>Version Data is Critical.</strong> Without version data, bugs/PSIRTs cannot be matched to devices. Ensure your export includes:
                <ul>
                    <li><code>affected_versions</code>: List or string of affected versions</li>
                    <li><code>fixed_version</code>: First fixed release (recommended)</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Quick Reference -->
    <div class="quick-ref">
        <h3>Quick Reference: Data Pipelines</h3>
        <div class="ref-grid">
            <div class="ref-item">
                <span>Bug CSV</span>
                <span class="ref-arrow">→</span>
                <span><code>load_bugs.py --platform IOS-XE</code></span>
            </div>
            <div class="ref-item">
                <span>PSIRT JSON</span>
                <span class="ref-arrow">→</span>
                <span><code>load_psirts.py</code></span>
            </div>
            <div class="ref-item">
                <span>Golden Dataset</span>
                <span class="ref-arrow">→</span>
                <span><code>build_faiss_index.py</code></span>
            </div>
            <div class="ref-item">
                <span>Device Config</span>
                <span class="ref-arrow">→</span>
                <span>SSH Discovery or Sidecar Extractor</span>
            </div>
        </div>
    </div>

    <!-- Key Files Reference -->
    <h2>Key Files Reference</h2>
    <table>
        <thead>
            <tr><th>File</th><th>Purpose</th><th>Update Frequency</th></tr>
        </thead>
        <tbody>
            <tr><td><code>vulnerability_db.sqlite</code></td><td>Main vulnerability store</td><td>Weekly (bug imports)</td></tr>
            <tr><td><code>models/faiss_index.bin</code></td><td>Semantic search index</td><td>Monthly (after labeling)</td></tr>
            <tr><td><code>models/adapters/</code></td><td>Platform-specific LoRA weights</td><td>Per training cycle</td></tr>
            <tr><td><code>models/embedder_info.json</code></td><td>FAISS embedder config</td><td>Rarely (model change)</td></tr>
            <tr><td><code>taxonomies/features*.yml</code></td><td>Feature detection patterns</td><td>As needed</td></tr>
        </tbody>
    </table>

    <div class="link-row">
        <a href="/api/v1/docs-hub" class="back-link">← Documentation Hub</a>
        <a href="/api/v1/tutorial" class="link-secondary">Getting Started Tutorial</a>
        <a href="/api/v1/setup-guide" class="link-secondary">Setup Guide</a>
    </div>
"""


@router.get("/admin-guide", response_class=HTMLResponse, summary="Admin Guide",
            description="Interactive HTML admin guide for data pipelines and system maintenance")
async def get_admin_guide():
    """
    Returns an interactive HTML admin guide that explains:
    - The data stack architecture
    - Data loading pipelines (Bugs, PSIRTs)
    - FAISS index maintenance
    - Taxonomy management
    - Air-gapped deployment handling
    """
    return HTMLResponse(content=get_page_template(
        title="Admin Guide",
        active_page="admin",
        content=ADMIN_GUIDE_CONTENT,
        page_class="page-admin"
    ))


@router.get("/admin-guide/json", summary="Admin Guide (JSON)",
            description="Get the admin guide content in JSON format for programmatic access")
async def get_admin_guide_json():
    """
    Returns admin guide content as structured JSON for integration with other systems.
    """
    return {
        "title": "PSIRT Analyzer - Admin Guide",
        "version": "1.0",
        "data_stack": {
            "external_sources": [
                {"name": "Cisco Bug Search Tool", "output": "bugs/*.csv", "count": "20,000+ bugs"},
                {"name": "Cisco Security Advisories", "output": "output/psirts.json", "count": "88 PSIRTs"},
                {"name": "Human Labeling", "output": "golden_dataset.csv", "count": "2,654 examples"}
            ],
            "processing_layer": [
                {"script": "load_bugs.py", "purpose": "Parse CSV, detect version patterns"},
                {"script": "load_psirts.py", "purpose": "Parse JSON, map severity"},
                {"script": "build_faiss_index.py", "purpose": "Embed summaries, create vector store"}
            ],
            "runtime_assets": [
                {"file": "vulnerability_db.sqlite", "content": "9,617 bugs + 88 PSIRTs"},
                {"file": "models/faiss_index.bin", "content": "2,654 embedded examples"},
                {"file": "models/adapters/", "content": "Platform-specific LoRA weights"},
                {"file": "taxonomies/features*.yml", "content": "141 feature definitions"}
            ]
        },
        "data_pipelines": [
            {
                "name": "Loading Bugs",
                "source": "Cisco Bug Search CSV",
                "command": "python backend/db/load_bugs.py file.csv --platform IOS-XE",
                "required_columns": ["BUG Id", "BUG headline", "Bug Severity", "Known Affected Release(s)"]
            },
            {
                "name": "Loading PSIRTs",
                "source": "Cisco Security API JSON",
                "command": "python backend/db/load_psirts.py",
                "required_fields": ["advisoryId", "summary", "platform"]
            },
            {
                "name": "FAISS Index",
                "source": "golden_dataset.csv",
                "command": "python scripts/build_faiss_index.py --input golden_dataset.csv",
                "outputs": ["models/faiss_index.bin", "models/labeled_examples.parquet"]
            }
        ],
        "key_files": [
            {"file": "vulnerability_db.sqlite", "purpose": "Main vulnerability store", "update_frequency": "Weekly"},
            {"file": "models/faiss_index.bin", "purpose": "Semantic search index", "update_frequency": "Monthly"},
            {"file": "models/adapters/", "purpose": "LoRA weights", "update_frequency": "Per training"},
            {"file": "models/embedder_info.json", "purpose": "FAISS config", "update_frequency": "Rarely"},
            {"file": "taxonomies/features*.yml", "purpose": "Feature patterns", "update_frequency": "As needed"}
        ],
        "air_gapped": {
            "package_structure": ["labeled_update.jsonl", "manifest.json", "SHA256SUMS"],
            "apply_steps": [
                "Transfer ZIP via approved method",
                "Navigate to System Admin tab",
                "Use Offline Update feature",
                "Verify SHA256 hash",
                "Click Apply Update"
            ]
        }
    }
