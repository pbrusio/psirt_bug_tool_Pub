"""
Setup Guide Routes - Installation and Configuration Guide

Provides an HTML-based setup guide accessible via /api/v1/setup-guide
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from .docs_common import get_page_template

router = APIRouter(prefix="/api/v1", tags=["Setup Guide"])


SETUP_GUIDE_CONTENT = """
    <style>
        /* Setup Guide Specific Styles */
        .platform-tabs {
            display: flex;
            gap: 0.5rem;
            margin: 1.5rem 0 1rem;
        }

        .platform-tab {
            padding: 0.75rem 1.5rem;
            border-radius: 8px 8px 0 0;
            background: var(--bg-card);
            color: var(--text-secondary);
            border: 1px solid var(--border-color);
            border-bottom: none;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
        }

        .platform-tab:hover {
            background: var(--bg-secondary);
            color: var(--text-primary);
        }

        .platform-tab.active {
            background: var(--bg-secondary);
            color: var(--accent-green);
            border-color: var(--accent-green);
        }

        .platform-content {
            background: var(--bg-secondary);
            border-radius: 0 12px 12px 12px;
            padding: 1.5rem;
            border: 1px solid var(--border-color);
            margin-bottom: 1.5rem;
        }
    </style>

    <h1>Setup Guide</h1>
    <p class="subtitle">Installation, configuration, and verification for Mac and Linux</p>

    <!-- Platform Detection -->
    <div class="success">
        <div class="success-label">Auto-Detection</div>
        The system automatically detects your platform and loads the appropriate inference backend:
        <ul>
            <li><strong>Mac (Apple Silicon)</strong> → MLX backend with <code>models/adapters/mlx_v1/</code></li>
            <li><strong>Linux (NVIDIA GPU)</strong> → Transformers+PEFT with <code>models/adapters/cuda_v1/</code></li>
            <li><strong>Linux (CPU)</strong> → Transformers+PEFT with CPU fallback</li>
        </ul>
    </div>

    <!-- Hardware Requirements -->
    <h2>Hardware Requirements</h2>

    <div class="req-grid">
        <div class="req-card">
            <div class="req-title">Mac (Recommended)</div>
            <div class="req-value">Apple Silicon M1/M2/M3 with 32GB+ RAM</div>
        </div>
        <div class="req-card">
            <div class="req-title">Linux (NVIDIA)</div>
            <div class="req-value">CUDA GPU with 13GB+ VRAM</div>
        </div>
        <div class="req-card">
            <div class="req-title">Linux (CPU)</div>
            <div class="req-value">32GB+ RAM (slower inference)</div>
        </div>
        <div class="req-card">
            <div class="req-title">Storage</div>
            <div class="req-value">10GB+ for models and database</div>
        </div>
    </div>

    <!-- Step 1: Clone & Setup -->
    <div class="step-section">
        <div class="step-header">
            <div class="step-number">1</div>
            <div class="step-title">Clone & Environment Setup</div>
        </div>
        <div class="step-content">
            <h4>Mac (Apple Silicon)</h4>
            <div class="command-block">
                <span class="prompt">$</span> git clone git@github.com:pbrusio/cve_EVAL_V2.git<br>
                <span class="prompt">$</span> cd cve_EVAL_V2<br>
                <span class="prompt">$</span> ./setup_mac_env.sh
            </div>

            <h4>Linux</h4>
            <div class="command-block">
                <span class="prompt">$</span> git clone git@github.com:pbrusio/cve_EVAL_V2.git<br>
                <span class="prompt">$</span> cd cve_EVAL_V2<br>
                <span class="prompt">$</span> ./setup_env.sh<br>
                <span class="prompt">$</span> source venv/bin/activate<br>
                <span class="prompt">$</span> pip install peft  <span class="comment"># Required for CUDA adapter</span>
            </div>
        </div>
    </div>

    <!-- Step 2: Verify Files -->
    <div class="step-section">
        <div class="step-header">
            <div class="step-number">2</div>
            <div class="step-title">Verify Required Files</div>
        </div>
        <div class="step-content">
            <p>Check that all critical files exist:</p>

            <div class="command-block">
                <span class="comment"># Database</span><br>
                <span class="prompt">$</span> ls -lh vulnerability_db.sqlite<br><br>
                <span class="comment"># FAISS index and embedder config</span><br>
                <span class="prompt">$</span> ls -lh models/faiss_index.bin<br>
                <span class="prompt">$</span> ls -lh models/embedder_info.json<br><br>
                <span class="comment"># Platform adapter (check yours)</span><br>
                <span class="prompt">$</span> ls -la models/adapters/mlx_v1/   <span class="comment"># Mac</span><br>
                <span class="prompt">$</span> ls -la models/adapters/cuda_v1/  <span class="comment"># Linux</span>
            </div>

            <div class="warning">
                <div class="warning-label">Critical Files</div>
                <ul>
                    <li><code>models/embedder_info.json</code> - Required for FAISS similarity search</li>
                    <li><code>tests/fixtures/psirt_corpus.json</code> - Required for architecture tests</li>
                </ul>
                If missing, API calls will fail with 500 errors.
            </div>
        </div>
    </div>

    <!-- Step 3: Start Backend -->
    <div class="step-section">
        <div class="step-header">
            <div class="step-number">3</div>
            <div class="step-title">Start Backend Server</div>
        </div>
        <div class="step-content">
            <h4>Mac</h4>
            <div class="command-block">
                <span class="prompt">$</span> source venv_mac/bin/activate<br>
                <span class="prompt">$</span> python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
            </div>

            <h4>Linux</h4>
            <div class="command-block">
                <span class="prompt">$</span> source venv/bin/activate<br>
                <span class="prompt">$</span> python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
            </div>

            <div class="tip">
                <div class="tip-label">Expected Output</div>
                You should see platform detection message:
                <pre><code>🔍 Platform detection: CUDA available (NVIDIA GeForce RTX ...) → using Transformers+PEFT</code></pre>
                or for Mac:
                <pre><code>🔍 Platform detection: Mac with MPS → using MLX backend</code></pre>
            </div>
        </div>
    </div>

    <!-- Step 4: Start Frontend -->
    <div class="step-section">
        <div class="step-header">
            <div class="step-number">4</div>
            <div class="step-title">Start Frontend (Optional)</div>
        </div>
        <div class="step-content">
            <div class="command-block">
                <span class="prompt">$</span> cd frontend<br>
                <span class="prompt">$</span> npm install<br>
                <span class="prompt">$</span> npm run dev
            </div>

            <p>Access points:</p>
            <ul>
                <li><strong>Frontend UI:</strong> <a href="http://localhost:3000" style="color: var(--accent-blue)">http://localhost:3000</a></li>
                <li><strong>API Docs:</strong> <a href="/docs" style="color: var(--accent-blue)">http://localhost:8000/docs</a></li>
                <li><strong>Documentation Hub:</strong> <a href="/api/v1/docs-hub" style="color: var(--accent-blue)">http://localhost:8000/api/v1/docs-hub</a></li>
            </ul>
        </div>
    </div>

    <!-- Step 5: Verify -->
    <div class="step-section">
        <div class="step-header">
            <div class="step-number">5</div>
            <div class="step-title">Verify Installation</div>
        </div>
        <div class="step-content">
            <h4>Health Check</h4>
            <div class="command-block">
                <span class="prompt">$</span> curl http://localhost:8000/api/v1/system/health | python3 -m json.tool
            </div>

            <p>Expected response shows <code>"status": "healthy"</code> with platform detection:</p>
            <pre><code>{
    "status": "healthy",
    "model": {
        "status": "healthy",
        "platform": "cuda",
        "backend": "transformers+peft",
        "device_info": "CUDA (NVIDIA GeForce RTX ...)",
        "adapter_exists": true
    }
}</code></pre>

            <h4>Run Tests</h4>
            <div class="command-block">
                <span class="prompt">$</span> pytest tests/ -v<br>
                <span class="comment"># Expected: 175+ tests passing</span>
            </div>
        </div>
    </div>

    <!-- Verification Checklist -->
    <div class="checklist">
        <h3>Verification Checklist</h3>
        <div class="check-item">
            <span class="check-icon">✓</span>
            <span>Database exists: <code>vulnerability_db.sqlite</code></span>
        </div>
        <div class="check-item">
            <span class="check-icon">✓</span>
            <span>FAISS index exists: <code>models/faiss_index.bin</code></span>
        </div>
        <div class="check-item">
            <span class="check-icon">✓</span>
            <span>Embedder config exists: <code>models/embedder_info.json</code></span>
        </div>
        <div class="check-item">
            <span class="check-icon">✓</span>
            <span>Platform adapter exists (mlx_v1 or cuda_v1)</span>
        </div>
        <div class="check-item">
            <span class="check-icon">✓</span>
            <span>Health endpoint returns "healthy"</span>
        </div>
        <div class="check-item">
            <span class="check-icon">✓</span>
            <span>All tests pass (175+)</span>
        </div>
    </div>

    <!-- Troubleshooting -->
    <h2>Troubleshooting</h2>

    <table>
        <thead>
            <tr><th>Issue</th><th>Solution</th></tr>
        </thead>
        <tbody>
            <tr>
                <td>500 error on PSIRT analysis</td>
                <td>Check <code>models/embedder_info.json</code> exists</td>
            </tr>
            <tr>
                <td>Tests failing in architecture/</td>
                <td>Check <code>tests/fixtures/psirt_corpus.json</code> exists</td>
            </tr>
            <tr>
                <td>System Health shows "degraded"</td>
                <td>Check platform adapter exists at correct path</td>
            </tr>
            <tr>
                <td>ModuleNotFoundError: peft</td>
                <td>Run <code>pip install peft</code> on Linux</td>
            </tr>
            <tr>
                <td>ModuleNotFoundError: mlx</td>
                <td>MLX only works on Mac - system will use CPU fallback</td>
            </tr>
            <tr>
                <td>CUDA out of memory</td>
                <td>Need GPU with 13GB+ VRAM, or use CPU fallback</td>
            </tr>
        </tbody>
    </table>

    <div class="link-row">
        <a href="/api/v1/docs-hub" class="back-link">← Documentation Hub</a>
        <a href="/api/v1/tutorial" class="link-secondary">Getting Started Tutorial</a>
        <a href="/api/v1/admin-guide" class="link-secondary">Admin Guide</a>
    </div>
"""


@router.get("/setup-guide", response_class=HTMLResponse, summary="Setup Guide",
            description="Interactive HTML setup guide for installation and configuration")
async def get_setup_guide():
    """
    Returns an interactive HTML setup guide that explains:
    - Hardware requirements for Mac and Linux
    - Installation steps
    - Platform detection (MLX vs CUDA)
    - Verification procedures
    - Troubleshooting common issues
    """
    return HTMLResponse(content=get_page_template(
        title="Setup Guide",
        active_page="setup",
        content=SETUP_GUIDE_CONTENT,
        page_class="page-setup"
    ))


@router.get("/setup-guide/json", summary="Setup Guide (JSON)",
            description="Get the setup guide content in JSON format for programmatic access")
async def get_setup_guide_json():
    """
    Returns setup guide content as structured JSON for integration with other systems.
    """
    return {
        "title": "PSIRT Analyzer - Setup Guide",
        "version": "1.0",
        "platforms": {
            "mac": {
                "name": "Mac (Apple Silicon)",
                "requirements": "M1/M2/M3 with 32GB+ RAM",
                "backend": "MLX",
                "adapter_path": "models/adapters/mlx_v1/",
                "accuracy": "~71%"
            },
            "linux_cuda": {
                "name": "Linux (NVIDIA GPU)",
                "requirements": "CUDA GPU with 13GB+ VRAM",
                "backend": "Transformers + PEFT",
                "adapter_path": "models/adapters/cuda_v1/",
                "accuracy": "~57%"
            },
            "linux_cpu": {
                "name": "Linux (CPU)",
                "requirements": "32GB+ RAM",
                "backend": "Transformers + PEFT (CPU)",
                "adapter_path": "models/adapters/cuda_v1/",
                "accuracy": "~57%"
            }
        },
        "required_files": [
            {"path": "vulnerability_db.sqlite", "purpose": "Main vulnerability database"},
            {"path": "models/faiss_index.bin", "purpose": "Similarity search index"},
            {"path": "models/embedder_info.json", "purpose": "FAISS embedder configuration"},
            {"path": "models/adapters/mlx_v1/", "purpose": "Mac adapter (MLX format)"},
            {"path": "models/adapters/cuda_v1/", "purpose": "Linux adapter (PEFT format)"},
            {"path": "tests/fixtures/psirt_corpus.json", "purpose": "Test fixtures"}
        ],
        "verification_steps": [
            "Check database exists",
            "Check FAISS index exists",
            "Check embedder config exists",
            "Check platform adapter exists",
            "Run health check endpoint",
            "Run test suite (175+ tests)"
        ],
        "endpoints": {
            "health": "/api/v1/system/health",
            "api_docs": "/docs",
            "frontend": "http://localhost:3000"
        }
    }


@router.get("/setup-guide/json", summary="Setup Guide (JSON)",
            description="Get the setup guide content in JSON format for programmatic access")
async def get_setup_guide_json():
    """
    Returns setup guide content as structured JSON for integration with other systems.
    """
    return {
        "title": "PSIRT Analyzer - Setup Guide",
        "version": "1.0",
        "platforms": {
            "mac": {
                "name": "Mac (Apple Silicon)",
                "requirements": "M1/M2/M3 with 32GB+ RAM",
                "backend": "MLX",
                "adapter_path": "models/adapters/mlx_v1/",
                "accuracy": "~71%"
            },
            "linux_cuda": {
                "name": "Linux (NVIDIA GPU)",
                "requirements": "CUDA GPU with 13GB+ VRAM",
                "backend": "Transformers + PEFT",
                "adapter_path": "models/adapters/cuda_v1/",
                "accuracy": "~57%"
            },
            "linux_cpu": {
                "name": "Linux (CPU)",
                "requirements": "32GB+ RAM",
                "backend": "Transformers + PEFT (CPU)",
                "adapter_path": "models/adapters/cuda_v1/",
                "accuracy": "~57%"
            }
        },
        "required_files": [
            {"path": "vulnerability_db.sqlite", "purpose": "Main vulnerability database"},
            {"path": "models/faiss_index.bin", "purpose": "Similarity search index"},
            {"path": "models/embedder_info.json", "purpose": "FAISS embedder configuration"},
            {"path": "models/adapters/mlx_v1/", "purpose": "Mac adapter (MLX format)"},
            {"path": "models/adapters/cuda_v1/", "purpose": "Linux adapter (PEFT format)"},
            {"path": "tests/fixtures/psirt_corpus.json", "purpose": "Test fixtures"}
        ],
        "verification_steps": [
            "Check database exists",
            "Check FAISS index exists",
            "Check embedder config exists",
            "Check platform adapter exists",
            "Run health check endpoint",
            "Run test suite (175+ tests)"
        ],
        "endpoints": {
            "health": "/api/v1/system/health",
            "api_docs": "/docs",
            "frontend": "http://localhost:3000"
        }
    }
