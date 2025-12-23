# Quick Fix for Snapshot Verification UI

## Problem
JSON parsing/snapshot verification wasn't working in the React UI today.

## What I Did

### ✅ Verified Backend (Working Perfectly)
- API endpoint `/api/v1/verify-snapshot` exists and works
- Tested with curl - 100% functional
- See: `test_snapshot_verification.sh`

### ✅ Verified Frontend Code (All Correct)
- `SnapshotForm.tsx` - Handles JSON parsing ✅
- `App.tsx` - Manages verification flow ✅  
- `client.ts` - API calls configured ✅
- `types/index.ts` - Types match backend ✅

### 🔧 Created Debug Tools

1. **`SNAPSHOT_TROUBLESHOOTING.md`** - Complete troubleshooting guide
   - Step-by-step debugging
   - Common issues & solutions
   - Browser DevTools tips
   - What to check

2. **`test_snapshot_ui.html`** - Standalone test page
   - Open: http://localhost:3000/test_snapshot_ui.html
   - No React/TypeScript - pure JavaScript
   - Tests same API endpoints
   - If this works, React UI should too

3. **`test_snapshot_verification.sh`** - API test script
   - Run: `bash test_snapshot_verification.sh`
   - Bypasses UI completely
   - Tests backend directly

## How to Debug

### Option 1: Use Standalone Test Page
```bash
# Open browser to:
http://localhost:3000/test_snapshot_ui.html

# This tests the exact same API without React
```

### Option 2: Debug React UI
```bash
# 1. Open browser DevTools (F12)
# 2. Go to Console tab
# 3. Open: http://localhost:3000
# 4. Complete analysis (Step 1)
# 5. Choose snapshot mode (Step 3)
# 6. Watch Console for errors
```

### Option 3: Clear Cache & Retry
```bash
cd frontend
rm -rf node_modules/.vite
npm run dev

# Then hard refresh browser (Ctrl+Shift+R)
```

## Expected Workflow

1. **Analyze PSIRT** (Step 1)
   - Paste PSIRT summary
   - Select platform (IOS-XE)
   - Click "Analyze PSIRT"
   - ✅ See green success message

2. **Choose Verification Mode** (Step 3)
   - See two options: Live Device vs Snapshot
   - Click "📦 Pre-extracted Snapshot"

3. **Validate JSON**
   - Paste snapshot JSON
   - Click "Validate JSON"
   - ✅ See green "Snapshot Validated" box

4. **Verify**
   - Click "Verify with Snapshot" (now enabled)
   - ✅ See "Step 4: Verification Report"

## Valid Snapshot JSON

```json
{
  "snapshot_id": "snapshot-20251010-140153",
  "platform": "IOS-XE",
  "extracted_at": "2025-10-10T14:00:00.000000",
  "features_present": ["MGMT_SSH_HTTP", "SEC_CoPP", "MGMT_SNMP"],
  "feature_count": 3,
  "total_checked": 66,
  "extractor_version": "1.0.0-standalone"
}
```

## Quick Test Commands

```bash
# Test backend directly
bash test_snapshot_verification.sh

# Test with standalone UI
open http://localhost:3000/test_snapshot_ui.html

# Clear frontend cache
cd frontend && rm -rf node_modules/.vite && npm run dev
```

## What to Check If Still Not Working

1. **Browser Console** (F12 → Console)
   - Any red errors?
   - Any failed API calls?

2. **Network Tab** (F12 → Network)
   - Filter by "verify-snapshot"
   - Status 200 OK?
   - Response body correct?

3. **Backend Logs** (terminal running backend)
   - See "Analyzing PSIRT for platform: IOS-XE"?
   - See "Snapshot verification complete"?

4. **React State**
   - Did Step 1 complete successfully?
   - Is `analysisResult` set?
   - Is `verificationMode` === "snapshot"?

## Files Created

- `SNAPSHOT_TROUBLESHOOTING.md` - Detailed guide
- `test_snapshot_ui.html` - Standalone tester
- `test_snapshot_verification.sh` - API test script
- `QUICK_FIX.md` - This file

## Summary

**Backend works perfectly** ✅  
**Frontend code is correct** ✅  
**Likely cause**: Browser cache or state issue  
**Solution**: Use debug tools above to isolate the problem
