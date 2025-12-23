"""
Documentation Hub Routes - Central navigation for all interactive docs

Provides:
- /api/v1/docs-hub - Central documentation navigation page
- Shared styles for consistent look across all docs
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from .docs_common import get_page_template

router = APIRouter(prefix="/api/v1", tags=["Documentation"])


DOCS_HUB_CONTENT = """
        <h1>Documentation Hub</h1>
        <p class="subtitle">Everything you need to use, administer, and develop with the PSIRT Analyzer</p>

        <!-- Quick Stats -->
        <div class="status-section">
            <h3>System Overview</h3>
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-value">9,600+</div>
                    <div class="status-label">Bugs & PSIRTs</div>
                </div>
                <div class="status-item">
                    <div class="status-value">5</div>
                    <div class="status-label">Platforms</div>
                </div>
                <div class="status-item">
                    <div class="status-value">&lt;10ms</div>
                    <div class="status-label">Scan Speed</div>
                </div>
                <div class="status-item">
                    <div class="status-value">141</div>
                    <div class="status-label">Feature Labels</div>
                </div>
                <div class="status-item">
                    <div class="status-value">~71%</div>
                    <div class="status-label">Model Accuracy</div>
                </div>
            </div>
        </div>

        <!-- Main Documentation Cards -->
        <h2>Documentation</h2>
        <div class="docs-grid">
            <a href="/api/v1/tutorial" class="doc-card tutorial">
                <div class="doc-icon">🎓</div>
                <div class="doc-title">Getting Started Tutorial</div>
                <div class="doc-desc">Learn the dual-path architecture, how to use each tab, and best practices for effective vulnerability scanning.</div>
                <div class="doc-tags">
                    <span class="tag">Beginner</span>
                    <span class="tag">UI Guide</span>
                    <span class="tag">Best Practices</span>
                </div>
            </a>

            <a href="/api/v1/admin-guide" class="doc-card admin">
                <div class="doc-icon">⚙️</div>
                <div class="doc-title">Admin Guide</div>
                <div class="doc-desc">Data pipelines, loading bugs/PSIRTs, FAISS index management, taxonomy configuration, and air-gapped deployments.</div>
                <div class="doc-tags">
                    <span class="tag">Data Ops</span>
                    <span class="tag">Maintenance</span>
                    <span class="tag">Air-Gapped</span>
                </div>
            </a>

            <a href="/api/v1/setup-guide" class="doc-card setup">
                <div class="doc-icon">🛠️</div>
                <div class="doc-title">Setup Guide</div>
                <div class="doc-desc">Hardware requirements, installation steps, platform detection (MLX vs CUDA), model setup, and verification.</div>
                <div class="doc-tags">
                    <span class="tag">Installation</span>
                    <span class="tag">Mac/Linux</span>
                    <span class="tag">Troubleshooting</span>
                </div>
            </a>

            <a href="/api/v1/api-reference" class="doc-card api">
                <div class="doc-icon">📡</div>
                <div class="doc-title">API Reference</div>
                <div class="doc-desc">Interactive Swagger UI with all endpoints, request/response schemas, and try-it-out functionality.</div>
                <div class="doc-tags">
                    <span class="tag">REST API</span>
                    <span class="tag">Swagger</span>
                    <span class="tag">Interactive</span>
                </div>
            </a>

            <a href="/api/v1/redoc" class="doc-card arch">
                <div class="doc-icon">📖</div>
                <div class="doc-title">ReDoc</div>
                <div class="doc-desc">Alternative API documentation view with a clean, three-panel layout. Great for reading and exploring the API schema.</div>
                <div class="doc-tags">
                    <span class="tag">REST API</span>
                    <span class="tag">ReDoc</span>
                    <span class="tag">Schema</span>
                </div>
            </a>
        </div>

        <!-- Quick Links -->
        <div class="quick-links">
            <h3>Quick Links</h3>
            <div class="quick-grid">
                <a href="/api/v1/system/health" class="quick-item">
                    <span class="quick-icon">💚</span>
                    <span class="quick-label">System Health</span>
                </a>
                <a href="/api/v1/system/stats/database" class="quick-item">
                    <span class="quick-icon">📊</span>
                    <span class="quick-label">Database Stats</span>
                </a>
                <a href="/api/v1/inventory/stats" class="quick-item">
                    <span class="quick-icon">📦</span>
                    <span class="quick-label">Inventory Stats</span>
                </a>
                <a href="http://localhost:3000" class="quick-item">
                    <span class="quick-icon">🖥️</span>
                    <span class="quick-label">Frontend UI</span>
                </a>
            </div>
        </div>

        <!-- Platform Support -->
        <h2>Platform Support</h2>
        <table>
            <thead>
                <tr>
                    <th>Platform</th>
                    <th>Inference Backend</th>
                    <th>Adapter Location</th>
                    <th>Accuracy</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Mac (Apple Silicon)</td>
                    <td>MLX</td>
                    <td><code>models/adapters/mlx_v1/</code></td>
                    <td>~71%</td>
                </tr>
                <tr>
                    <td>Linux (NVIDIA GPU)</td>
                    <td>Transformers + PEFT</td>
                    <td><code>models/adapters/cuda_v1/</code></td>
                    <td>~57%</td>
                </tr>
                <tr>
                    <td>Linux (CPU)</td>
                    <td>Transformers + PEFT</td>
                    <td><code>models/adapters/cuda_v1/</code></td>
                    <td>~57%</td>
                </tr>
            </tbody>
        </table>

        <div class="tip">
            <div class="tip-label">Auto-Detection</div>
            The system automatically detects your platform and loads the appropriate adapter. No configuration needed!
        </div>
"""


@router.get("/docs-hub", response_class=HTMLResponse, summary="Documentation Hub",
            description="Central navigation page for all interactive documentation")
async def get_docs_hub():
    """
    Returns the documentation hub - a central navigation page with links to:
    - Getting Started Tutorial
    - Admin Guide
    - Setup Guide
    - API Reference (Swagger)
    - Quick links to system health and stats
    """
    return HTMLResponse(content=get_page_template(
        title="Documentation Hub",
        active_page="hub",
        content=DOCS_HUB_CONTENT,
        page_class="page-hub"
    ))
