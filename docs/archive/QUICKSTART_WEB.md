# PSIRT Analyzer Web Interface - Quick Start Guide

## Overview

Complete web-based PSIRT vulnerability analysis system with React frontend and FastAPI backend.

## Architecture

```
Frontend (React)          Backend (FastAPI)           ML Pipeline
─────────────────         ─────────────────           ───────────
http://localhost:3000  →  http://localhost:8000   →   SEC-8B Model
                                                        FAISS Index
                                                        SSH Verification
```

## Prerequisites

- Python 3.10+ with venv
- Node.js 18+ and npm
- SEC-8B model and FAISS index (in `models/`)
- Backend dependencies installed

## Quick Start

### 1. Start Backend (Terminal 1)

```bash
cd /path/to/cve_EVAL_V2
bash backend/run_server.sh
```

**Expected output:**
```
🚀 Starting PSIRT Analysis API...
📡 Server: http://localhost:8000
📚 Docs: http://localhost:8000/docs

INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Start Frontend (Terminal 2)

```bash
cd /path/to/cve_EVAL_V2/frontend

# First time only: Install dependencies
npm install

# Start dev server
npm run dev
```

**Expected output:**
```
VITE v5.4.20  ready in 87 ms

➜  Local:   http://localhost:3000/
➜  Network: use --host to expose
```

### 3. Access Web Interface

Open browser: **http://localhost:3000**

## Usage Flow

### Step 1: Analyze PSIRT

1. Select platform (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
2. Optionally enter advisory ID (e.g., `cisco-sa-iox-dos-95Fqnf7b`)
3. Paste PSIRT summary text
4. Click **"Analyze PSIRT"**
5. Wait for SEC-8B inference (~3-5 seconds)
6. View predicted labels with confidence scores

**Example PSIRT:**
```
A vulnerability in the IOx application hosting subsystem of Cisco IOS XE
Software could allow an authenticated, remote attacker to cause a denial
of service (DoS) condition on an affected device.
```

**Result:**
- Predicted Labels: `APP_IOx`
- Config Regex: `^iox$`, `^app-hosting...`
- Show Commands: `show iox`, `show app-hosting list`

### Step 2: Review Analysis

- Expand config regex patterns (what to search for in configs)
- Expand show commands (what to run on devices)
- Review PSIRT summary
- Click **"Proceed to Device Verification"**

### Step 3: Connect to Device

1. Enter device IP/hostname (e.g., `192.168.0.33`)
2. Enter SSH username (e.g., `admin`)
3. Enter SSH password
4. Optionally expand **Advanced Options**:
   - Enter bug/advisory ID
   - Enter affected product versions (for version matching)
5. Click **"Connect & Verify Device"**
6. Wait for SSH connection and verification (~10-60 seconds)

**Note:** Credentials are NOT stored. Connection timeout: 5 minutes.

### Step 4: View Verification Report

**Vulnerability Status:**
- 🔴 **VULNERABLE** - Version affected AND feature present
- ✅ **NOT VULNERABLE** - Version not affected OR feature absent
- ⚠️ **ERROR** - Connection failed or error occurred

**Report Sections:**
- Device info (hostname, version, platform)
- Version check (affected/not affected with reason)
- Feature detection (present/absent labels)
- Analysis reasoning
- Command evidence (collapsible)

**Export:**
- Click **"Export as JSON"** to download results

## API Endpoints

### Backend REST API

**Base URL:** http://localhost:8000/api/v1

1. **Health Check**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

2. **Analyze PSIRT**
   ```bash
   curl -X POST http://localhost:8000/api/v1/analyze-psirt \
     -H "Content-Type: application/json" \
     -d '{
       "summary": "A vulnerability in...",
       "platform": "IOS-XE",
       "advisory_id": "cisco-sa-xxx"
     }'
   ```

3. **Verify Device**
   ```bash
   curl -X POST http://localhost:8000/api/v1/verify-device \
     -H "Content-Type: application/json" \
     -d '{
       "analysis_id": "uuid-from-analysis",
       "device": {
         "host": "192.168.0.33",
         "username": "admin",
         "password": "Pa22word"
       },
       "psirt_metadata": {
         "bug_id": "cisco-sa-xxx"
       }
     }'
   ```

### API Documentation

**Swagger UI:** http://localhost:8000/docs
- Interactive API documentation
- Test endpoints directly in browser
- View request/response schemas

## Troubleshooting

### Backend Won't Start

**Problem:** `ImportError: attempted relative import with no known parent package`

**Solution:**
```bash
# Must run from project root with run script
bash backend/run_server.sh
# NOT: python backend/app.py
```

### Frontend Won't Connect to Backend

**Problem:** `Network Error` or `Failed to fetch`

**Check:**
1. Backend is running: `curl http://localhost:8000/api/v1/health`
2. Proxy configuration in `frontend/vite.config.ts`:
   ```typescript
   proxy: {
     '/api': {
       target: 'http://localhost:8000',
       changeOrigin: true,
     }
   }
   ```

### Device Verification Fails

**Common Issues:**

1. **SSH timeout**
   - Check device is reachable: `ping 192.168.0.33`
   - Check SSH is enabled: `telnet 192.168.0.33 22`

2. **Authentication failed**
   - Verify credentials
   - Check SSH key-based auth is disabled (password auth required)

3. **Connection refused**
   - Device firewall blocking connection
   - SSH not enabled on device

### SEC-8B Model Not Loading

**Problem:** Backend crashes on startup with model errors

**Check:**
1. Model files exist: `ls models/`
2. FAISS index exists: `ls models/faiss_index.bin`
3. Python dependencies installed: `pip list | grep transformers`

**Rebuild FAISS index:**
```bash
source venv/bin/activate
python build_faiss_index.py
```

## File Locations

```
cve_EVAL_V2/
├── backend/
│   ├── app.py                  # FastAPI application
│   ├── api/routes.py           # API endpoints
│   ├── core/sec8b.py           # SEC-8B inference
│   └── core/verifier.py        # Device verification
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # Main React app
│   │   ├── components/         # UI components
│   │   ├── api/client.ts       # API client
│   │   └── types/index.ts      # TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── models/
│   ├── faiss_index.bin         # FAISS retrieval index
│   └── labeled_examples.parquet # Training examples
└── features.yml                # IOS-XE taxonomy
```

## Configuration

### Backend Environment

Edit `backend/core/config.py`:

```python
# SEC-8B Model
MODEL_NAME = "CiscoSec/Foundation-Sec-8B"
QUANTIZATION_BITS = 8  # 4 or 8

# FAISS
FAISS_INDEX_PATH = "models/faiss_index.bin"
NUM_EXAMPLES = 5  # Few-shot examples

# Device Verification
SSH_TIMEOUT = 300  # 5 minutes
```

### Frontend Environment

Create `frontend/.env.local`:

```bash
# Override default API URL
VITE_API_URL=http://localhost:8000/api/v1
```

## Performance

### Expected Response Times

- **PSIRT Analysis:** 3-5 seconds (SEC-8B 8-bit inference)
- **Device Verification:** 10-60 seconds (SSH connection + commands)
- **Page Load:** <100ms (local dev server)

### Optimization Tips

1. **Use 8-bit quantization** (better accuracy than 4-bit)
2. **Reduce NUM_EXAMPLES** to 3 for faster inference
3. **Cache FAISS index** in memory (already done)

## Security Notes

### Development

- ✅ CORS enabled for localhost
- ✅ Credentials not logged
- ✅ Input validation on all forms

### Production (Future)

- 🔲 Use HTTPS for all connections
- 🔲 Add authentication (JWT tokens)
- 🔲 Rate limiting (10 req/min per IP)
- 🔲 Encrypt credentials at rest (optional save feature)
- 🔲 Audit logging

## Next Steps

### For Users

1. Analyze a real PSIRT from Cisco
2. Verify your network devices
3. Export results for documentation
4. Provide feedback on label accuracy

### For Developers

1. Add export to PDF/CSV
2. Implement saved credentials (encrypted)
3. Add historical results view
4. Build batch processing (upload CSV of PSIRTs)
5. Add dark mode toggle
6. Write unit tests

## Support

### Documentation

- Frontend: `frontend/README.md`
- Backend: `backend/README.md`
- Implementation: `FRONTEND_IMPLEMENTATION.md`
- Project: `CLAUDE.md`

### Logs

**Backend logs:**
```bash
# View real-time logs
tail -f backend/logs/app.log
```

**Frontend logs:**
- Open browser DevTools (F12)
- Check Console tab for errors
- Check Network tab for API requests

### API Documentation

Visit http://localhost:8000/docs for:
- Complete API reference
- Request/response schemas
- Interactive testing

## Summary

**To start the application:**

```bash
# Terminal 1: Backend
bash backend/run_server.sh

# Terminal 2: Frontend
cd frontend && npm run dev

# Browser
http://localhost:3000
```

That's it! The complete PSIRT analysis system is now running with a user-friendly web interface.

---

**Questions?** Check `FRONTEND_IMPLEMENTATION.md` for detailed implementation notes.
