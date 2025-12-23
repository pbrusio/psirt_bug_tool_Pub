# Changelog v4.2

**Release Date:** December 19, 2025
**Branch:** `alpha/4.2`
**Previous Version:** `alpha/v4.1`

---

## Summary

Version 4.2 introduces a **unified interactive documentation system** with consistent navigation across all docs, **platform-aware System Health checks** for multi-platform support (Mac/Linux), and **improved test infrastructure** for cross-platform testing.

---

## New Features

### 1. Unified Documentation System

A complete interactive documentation hub accessible via the API with consistent styling and navigation.

**New Endpoints:**

| Endpoint | Description |
|----------|-------------|
| `/api/v1/docs-hub` | Central navigation hub with quick links and system stats |
| `/api/v1/tutorial` | Getting Started tutorial (updated with nav) |
| `/api/v1/admin-guide` | Admin Guide - data pipelines & maintenance |
| `/api/v1/setup-guide` | Setup Guide - installation for Mac/Linux |
| `/api/v1/api-reference` | Swagger UI with navigation bar |
| `/api/v1/redoc` | ReDoc with navigation bar |

**Convenience Redirects:**
- `/docs` → `/api/v1/api-reference`
- `/redoc` → `/api/v1/redoc`

**Features:**
- Consistent dark theme styling across Hub, Tutorial, Admin Guide, Setup Guide
- Unified navigation bar on all pages (including Swagger/ReDoc)
- Quick links to system health, database stats, inventory
- Platform support table showing Mac (MLX) vs Linux (CUDA) compatibility
- Screenshots captured in `docs/images/`

**New Files:**
- `backend/api/docs_hub_routes.py` - Documentation hub endpoint
- `backend/api/admin_guide_routes.py` - Admin guide endpoint
- `backend/api/setup_guide_routes.py` - Setup guide endpoint
- `docs/images/docs_hub_ui.png` - Screenshot
- `docs/images/admin_guide_ui.png` - Screenshot
- `docs/images/setup_guide_ui.png` - Screenshot
- `docs/images/fastapi_docs_ui.png` - Screenshot

### 2. Platform-Aware System Health

The System Health tray now correctly detects and reports platform-specific adapter status.

**Changes to `backend/api/system_routes.py`:**
- Added `_detect_inference_platform()` function
- Detects Mac (MLX/MPS), Linux (CUDA), or CPU-only environments
- Checks for correct platform-specific adapter:
  - Mac: `models/adapters/mlx_v1/`
  - Linux: `models/adapters/cuda_v1/`
- Health endpoint now returns platform details in response

**Changes to `frontend/src/components/SystemAdmin.tsx`:**
- Updated model details display to show:
  - Platform (CUDA, MLX, CPU)
  - Backend (transformers+peft, mlx)
  - Adapter path and existence status
  - Device info (GPU name if applicable)

### 3. Improved Test Infrastructure

**New Test File:**
- `tests/unit/test_platform_detection.py` - 16 tests for platform detection logic

**Updated Test Files:**
- `tests/architecture/helpers.py` - Platform-aware test utilities
- `tests/architecture/test_refactor.py` - Updated for cross-platform compatibility

**New Test Fixtures:**
- `tests/fixtures/psirt_corpus.json` - Golden-path PSIRT test corpus

---

## Files Changed

### Backend
| File | Change |
|------|--------|
| `backend/app.py` | Added docs routes, custom Swagger/ReDoc with nav bar |
| `backend/api/system_routes.py` | Platform-aware health detection |
| `backend/api/tutorial_routes.py` | Added navigation bar |
| `backend/api/admin_guide_routes.py` | **NEW** - Admin guide HTML endpoint |
| `backend/api/setup_guide_routes.py` | **NEW** - Setup guide HTML endpoint |
| `backend/api/docs_hub_routes.py` | **NEW** - Documentation hub endpoint |

### Frontend
| File | Change |
|------|--------|
| `frontend/src/components/SystemAdmin.tsx` | Platform-aware health display |

### Documentation
| File | Change |
|------|--------|
| `docs/ADMIN_GUIDE.md` | Added reference to HTML version |
| `docs/API_AND_FEATURES.md` | Added section 9.5 for documentation endpoints |
| `docs/SETUP_GUIDE.md` | Updated for multi-platform |
| `docs/ARCHITECTURE_AND_WORKFLOW.md` | Platform detection updates |
| `docs/DATA_FLOW_DOCUMENTATION.md` | Updated flows |
| `docs/FILE_STRUCTURE.md` | Added new files |
| `CLAUDE.md` | Updated for v4.2 changes |

### Tests
| File | Change |
|------|--------|
| `tests/unit/test_platform_detection.py` | **NEW** - Platform detection tests |
| `tests/architecture/helpers.py` | Cross-platform test utilities |
| `tests/architecture/test_refactor.py` | Platform-aware updates |
| `tests/fixtures/psirt_corpus.json` | **NEW** - Test fixture |

### Configuration
| File | Change |
|------|--------|
| `.gitignore` | Added exceptions for required files |

### Assets
| File | Change |
|------|--------|
| `docs/images/docs_hub_ui.png` | **NEW** - Screenshot |
| `docs/images/admin_guide_ui.png` | **NEW** - Screenshot |
| `docs/images/setup_guide_ui.png` | **NEW** - Screenshot |
| `docs/images/fastapi_docs_ui.png` | **NEW** - Screenshot |
| `models/embedder_info.json` | **NEW** - Required FAISS config |

---

## Gitignore Updates

Added exceptions to track required files that were previously ignored:

```gitignore
# Required model config files
!models/embedder_info.json

# Required test fixtures
!tests/fixtures/*.json
```

**Why these files are required:**
- `models/embedder_info.json` - Required for FAISS similarity search. Without this, PSIRT analysis fails with 500 errors.
- `tests/fixtures/psirt_corpus.json` - Required for architecture tests. Contains golden-path PSIRT test corpus.

---

## Breaking Changes

None. All changes are additive and backwards compatible.

---

## Migration Notes

No migration required. Simply pull the new branch and restart the backend.

```bash
git checkout alpha/4.2
# Restart backend
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

---

## API Documentation Access

After starting the backend, access documentation at:

| URL | Description |
|-----|-------------|
| http://localhost:8000/api/v1/docs-hub | Documentation Hub |
| http://localhost:8000/api/v1/tutorial | Getting Started |
| http://localhost:8000/api/v1/admin-guide | Admin Guide |
| http://localhost:8000/api/v1/setup-guide | Setup Guide |
| http://localhost:8000/api/v1/api-reference | Swagger UI |
| http://localhost:8000/api/v1/redoc | ReDoc |

---

## Contributors

- Platform-aware system health implementation
- Unified documentation system with navigation
- Cross-platform test infrastructure improvements
