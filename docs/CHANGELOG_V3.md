# Changelog

## Version 4.1

**Release Date:** December 19, 2025
**Branch:** `alpha/v4.1` (promoted from `alpha/v4.0`)

This release adds automatic platform detection, eliminating the need to manually specify MLX vs Transformers backend.

### Highlights

- **Auto-Detect Platform** - Backend now defaults to `auto`, automatically selecting MLX on Mac and Transformers+PEFT on Linux
- **Simplified Configuration** - No need to set `PSIRT_BACKEND` environment variable in most cases
- **Backwards Compatible** - Explicit backend selection (`mlx`, `transformers_local`) still works

### Platform Detection Logic

```
Backend Startup (PSIRT_BACKEND=auto)
    │
    ├─► Mac (sys.platform == 'darwin')
    │   ├─► MPS available → MLX backend (~71% accuracy)
    │   └─► MLX importable → MLX backend
    │
    ├─► Linux/CUDA available → Transformers+PEFT (~57% accuracy)
    │
    └─► Fallback → Transformers+PEFT (~57% accuracy)
```

### Key Changes

- `predict_and_verify.py`: Added `detect_platform()` function, default backend changed to `auto`
- `backend/core/sec8b.py`: Default `PSIRT_BACKEND` changed from `mlx` to `auto`
- `docs/SETUP_GUIDE.md`: Added comprehensive CUDA/Linux troubleshooting guide

### CUDA/Linux Troubleshooting

For step-by-step CUDA verification and common error solutions, see [SETUP_GUIDE.md#cudalinux-troubleshooting](SETUP_GUIDE.md#cudalinux-troubleshooting).

---

## Version 4.0

**Release Date:** December 19, 2025
**Branch:** `alpha/v4.0` (promoted from `alpha/v3.1`)

This release adds multi-platform support with platform-specific LoRA adapters, enabling fresh clones to work on both Mac (MLX) and Linux (CUDA/CPU).

### Highlights

- **Multi-Platform Adapter Architecture** - MLX adapter for Mac (~71%), CUDA adapter for Linux (~57%)
- **PEFT Integration** - `transformers_inference.py` now loads LoRA adapters via HuggingFace PEFT
- **Shared Data Files** - Cross-platform data (FAISS, parquet, SQLite) used by both platforms
- **Test Suite Improvements** - All 159 tests passing with updated intent classification tests

### New Directory Structure

```
models/adapters/
├── mlx_v1/                    # Mac adapter (MLX format)
│   ├── adapter_config.json
│   └── adapters.safetensors
├── cuda_v1/                   # Linux adapter (PEFT format)
│   ├── adapter_config.json
│   └── adapter_model.safetensors
└── registry.yaml              # Adapter metadata and defaults
```

### Platform Detection

| Platform | Framework | Adapter | Accuracy | Inference File |
|----------|-----------|---------|----------|----------------|
| Mac (MPS) | MLX | `mlx_v1/` | ~71% | `mlx_inference.py` |
| Linux (CUDA) | Transformers + PEFT | `cuda_v1/` | ~57% | `transformers_inference.py` |
| Linux (CPU) | Transformers + PEFT | `cuda_v1/` | ~57% | `transformers_inference.py` |

### Key Changes

- `transformers_inference.py`: Added PEFT adapter loading, platform detection
- `.gitignore`: Updated to track production adapters while excluding training artifacts
- `predict_and_verify.py`: Fixed `KeyError: 'retrieved_examples'` on exact matches
- `backend/api/models.py`: Added `min_length=1` validation for summary field
- `tests/unit/test_reasoning_engine.py`: Updated intent classification tests

### Breaking Changes

None - backwards compatible with v3.x deployments.

### Migration

No migration required. Fresh clones will include all adapters and shared data files.

---

## Version 3.0

**Release Date:** December 15, 2025
**Branch:** `alpha/v3.0` (promoted from `alpha/v2.4`)

This release represents a major milestone with comprehensive AI reasoning capabilities, system administration features, version comparison tools, and significant frontend/backend schema alignment fixes.

---

## Highlights

- **AI Reasoning Layer** - Transform the local LLM from "backup labeler" to "reasoning engine"
- **System Administration UI** - Offline updates, health monitoring, cache management
- **Version Comparison** - Upgrade planning with risk assessment
- **Bug Terminology Migration** - Consistent "bugs" terminology throughout
- **Critical Bug Fixes** - Fixed Compare Versions crash and modal rendering issues

---

## New Features

### AI Reasoning Layer (2025-12-15)

The reasoning layer enables the fine-tuned Foundation-Sec-8B model to provide contextual analysis beyond simple label assignment.

#### New Endpoints

| Endpoint | Purpose | Latency |
|----------|---------|---------|
| `POST /api/v1/reasoning/explain` | Explain why labels apply to a PSIRT | 2-4s |
| `POST /api/v1/reasoning/remediate` | Generate remediation CLI commands | 3-5s |
| `POST /api/v1/reasoning/ask` | Natural language vulnerability queries | 3-6s |
| `GET /api/v1/reasoning/summary` | Executive security posture summary | 5-10s |

#### Key Capabilities

- **Hybrid Intent Classification** - Rule-based patterns + LLM fallback for query routing
- **Device Context Injection** - Answers consider your specific inventory
- **Taxonomy-Aware Explanations** - Uses label definitions and anti-definitions
- **Rate Limiting** - Per-endpoint limits (30/20/20/10 requests/minute)

#### Example Usage

```bash
# Why is this PSIRT tagged with these labels?
curl -X POST "http://localhost:8000/api/v1/reasoning/explain" \
  -H "Content-Type: application/json" \
  -d '{"psirt_id": "cisco-sa-20231018-iosxe-webui", "platform": "IOS-XE"}'

# Ask in plain English
curl -X POST "http://localhost:8000/api/v1/reasoning/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "Which of my switches are vulnerable to SSH bugs?"}'
```

#### Implementation Files

- `backend/core/reasoning_engine.py` - Core reasoning logic
- `backend/api/reasoning_routes.py` - FastAPI endpoints
- `tests/unit/test_reasoning_engine.py` - Unit tests
- `tests/integration/test_reasoning_api.py` - Integration tests

---

### System Administration UI (2025-12-14)

New System tab in the frontend providing administrative capabilities for air-gapped deployments.

#### Features

1. **Offline Vulnerability Updates**
   - Drag-and-drop ZIP package upload
   - SHA256 hash verification for transfer integrity
   - Import progress with detailed statistics (inserted/updated/skipped)
   - Validation-only mode to preview changes

2. **Health Monitoring**
   - Real-time system status dashboard
   - Database connectivity checks
   - Cache status monitoring

3. **Database Statistics**
   - Total vulnerabilities by platform
   - Labeled vs unlabeled counts
   - Database size tracking
   - Last update timestamp

4. **Cache Management**
   - View cache statistics (entries, hit rates)
   - Clear specific caches (psirt, scan) or all caches

#### New Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/system/update/offline` | POST | Upload & apply update package |
| `/api/v1/system/update/validate` | POST | Validate package without applying |
| `/api/v1/system/stats/database` | GET | Database statistics |
| `/api/v1/system/health` | GET | System health status |
| `/api/v1/system/cache/clear` | POST | Clear caches |
| `/api/v1/system/cache/stats` | GET | Cache statistics |

---

### Version Comparison (2025-12-14)

Compare vulnerabilities between software versions for upgrade planning.

#### Use Cases

- **Upgrade Planning** - What bugs will be fixed by upgrading?
- **Downgrade Risk** - What new bugs would I get?
- **Version Selection** - Compare multiple target versions

#### API Endpoint

```bash
POST /api/v1/inventory/compare-versions
{
    "platform": "IOS-XE",
    "current_version": "17.9.1",
    "target_version": "17.12.1",
    "hardware_model": "Cat9300",    # optional
    "features": ["MGMT_SSH_HTTP"]   # optional
}
```

#### Response Includes

- `fixed_in_upgrade` - Bugs fixed by upgrading
- `new_in_upgrade` - Bugs introduced by upgrading
- `still_present` - Bugs present in both versions
- `upgrade_recommendation` - Risk assessment with:
  - `risk_level`: LOW / MEDIUM / HIGH
  - `risk_score`: 0-100
  - `recommendation`: Human-readable guidance

#### Risk Assessment Logic

| Condition | Risk Level |
|-----------|------------|
| Net bugs reduced, no new critical | LOW |
| Net bugs same or minor increase | MEDIUM |
| New critical bugs introduced | HIGH |

---

## Bug Fixes

### Critical: Compare Versions Crash (2025-12-15)

**Issue:** Compare Versions feature showed blank white screen due to React crash.

**Root Causes:**
1. Backend response keys didn't match frontend expectations
2. Frontend `Bug` interface didn't match backend schema
3. Modal templates used wrong field names (`vuln.title` vs `bug.headline`)

**Fixes Applied:**

| Component | Before | After |
|-----------|--------|-------|
| Response key | `fixed_bugs` | `fixed_in_upgrade` |
| Response key | `new_bugs` | `new_in_upgrade` |
| Response key | `unchanged_bugs` | `still_present` |
| Response key | `recommendation` (string) | `upgrade_recommendation` (object) |
| Bug field | `title` | `headline` |
| Bug field | `severity` (string) | `severity` (number) |
| Bug field | `fixed_versions` (array) | `affected_versions` (string) |

### Fixed: AI Assistant Bug Count (2025-12-15)

**Issue:** Security Posture Summary showed 9,725 (entire database) instead of bugs affecting inventory.

**Fix:** Aligned backend response key `bugs_affecting_inventory` → `total_advisories` to match API schema.

### Fixed: View Details Modal Crash (2025-12-15)

**Issue:** TypeScript errors when opening scan details modal.

**Fix:** Updated modal templates to use correct Bug interface fields and severity helper functions.

---

## Breaking Changes

### API Response Schema Changes

The `/api/v1/inventory/compare-versions` endpoint response schema has changed:

```diff
{
-   "current_version": {...},
+   "current_version_scan": {...},
-   "target_version": {...},
+   "target_version_scan": {...},
-   "fixed_bugs": [...],
+   "fixed_in_upgrade": [...],
-   "new_bugs": [...],
+   "new_in_upgrade": [...],
-   "unchanged_bugs": [...],
+   "still_present": [...],
-   "recommendation": "string",
+   "upgrade_recommendation": {
+       "risk_level": "LOW|MEDIUM|HIGH",
+       "risk_score": 0-100,
+       "recommendation": "string"
+   }
}
```

### Bug Object Schema

The `Bug` object returned from scan endpoints now uses consistent naming:

```diff
{
    "bug_id": "CSCxxx12345",
-   "title": "Bug title",
+   "headline": "Bug headline",
-   "severity": "Critical",
+   "severity": 1,
-   "fixed_versions": ["17.12.1", "17.13.1"],
+   "affected_versions": "17.10.1 17.11.2 17.12.3",
    "summary": "...",
    "labels": [...]
}
```

---

## Improvements

### Terminology Standardization

Migrated from "vulnerabilities" to "bugs" terminology throughout:

- UI labels updated (Security Analyzer, Bug Scanner, etc.)
- API response fields consistent
- Documentation updated

### Frontend Type Safety

- Added `getSeverityColor()` and `getSeverityLabel()` helper functions
- Proper handling of numeric severity values (1=Critical, 2=High, 3=Medium, 4=Low)
- Bug interface aligned with backend schema

### Documentation

- Added comprehensive work log system
- Updated ARCHITECTURE_AND_WORKFLOW.md with reasoning layer
- Updated API_AND_FEATURES.md with new endpoints
- Created this CHANGELOG_V3.md

---

## Database

No schema changes in v3.0. Database remains backward compatible.

| Table | Records | Notes |
|-------|---------|-------|
| vulnerabilities | 9,586 | 4 platforms |
| device_inventory | varies | ISE sync |
| scan_results | varies | Full scan storage |

---

## Dependencies

### New Dependencies

None added in v3.0.

### Updated Versions

No version updates required.

---

## Migration Guide

### From v2.4 to v3.0

1. **Pull latest code:**
   ```bash
   git fetch origin
   git checkout alpha/v3.0
   ```

2. **Rebuild frontend:**
   ```bash
   cd frontend && npm install && npm run build
   ```

3. **Update API consumers:**
   If you have scripts calling `/compare-versions`, update to new response schema (see Breaking Changes).

4. **Clear browser cache:**
   The frontend bundles have changed. Clear browser cache or hard refresh.

---

## Known Issues

1. **Rate limiting not enforced** - Reasoning endpoints have documented rate limits but enforcement is pending.

2. **Bulk scan progress** - `/scan-all` endpoint progress tracking needs WebSocket upgrade for real-time updates.

---

## Contributors

- Development and bug fixes: December 2025 sprint
- AI Reasoning Layer design and implementation
- System Administration UI implementation
- Documentation and changelog

---

## Full Commit History

See git log for complete commit history:
```bash
git log alpha/v2.4..alpha/v3.0 --oneline
```
