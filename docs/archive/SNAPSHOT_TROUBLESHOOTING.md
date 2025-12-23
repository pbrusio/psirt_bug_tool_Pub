# Snapshot Verification Troubleshooting Guide

## Issue: JSON parsing not working in UI

### ✅ What We Verified (Working)
1. **Backend API** - `/api/v1/verify-snapshot` endpoint works perfectly
2. **API Test** - Successfully tested with curl (see `test_snapshot_verification.sh`)
3. **Frontend Code** - All components (SnapshotForm, App.tsx, client.ts) are correctly implemented
4. **Types** - TypeScript types match API contract

### 🔍 Common Issues & Solutions

#### 1. UI Not Visible / Hidden

**Symptoms:**
- Snapshot option appears but nothing happens when clicked
- Form doesn't show up
- Buttons are grayed out

**Solution:**
```bash
# Clear Vite cache
cd frontend
rm -rf node_modules/.vite
npm run dev
```

#### 2. JSON Validation Failing

**Symptoms:**
- Paste JSON but "Validate JSON" doesn't work
- Error shows "Invalid JSON" even with valid JSON

**Check:**
1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for JavaScript errors
4. Check Network tab for failed requests

**Valid Snapshot Format:**
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

#### 3. API Request Failing

**Symptoms:**
- Validation works but verification fails
- Network error in console

**Debug Steps:**
1. Check backend is running: `curl http://localhost:8000/api/v1/health`
2. Check analysis was completed (Step 1 must be done first)
3. Open DevTools → Network tab → Filter by "verify-snapshot"
4. Click "Verify with Snapshot" and inspect request/response

#### 4. Dark Mode Issues

**Symptoms:**
- Text not visible
- Form elements missing
- Buttons don't contrast

**Solution:**
```bash
cd frontend
rm -rf node_modules/.vite
npm run dev
```

Then toggle dark mode in the UI (top right corner).

### 🧪 Testing Workflow

#### Step-by-Step Test

1. **Open browser to http://localhost:3000**

2. **Analyze PSIRT** (Step 1):
   ```
   Summary: A vulnerability in the SNMP subsystem allows DoS
   Platform: IOS-XE
   Advisory ID: test-001
   ```
   Click "Analyze PSIRT"

3. **Choose Verification Method** (Step 3):
   - Should see two options: "Live Device" and "Pre-extracted Snapshot"
   - Click "📦 Pre-extracted Snapshot"

4. **Paste Snapshot JSON**:
   - Copy the valid snapshot format above
   - Paste into textarea
   - Click "Validate JSON"
   - Should see green "✓ Snapshot Validated" message

5. **Verify**:
   - Click "Verify with Snapshot"
   - Should see "Step 4: Verification Report"
   - Status should be "POTENTIALLY VULNERABLE" or "LIKELY NOT VULNERABLE"

### 🐛 Browser DevTools Debugging

#### Console Errors to Look For

1. **CORS errors**: Backend proxy should handle this (vite.config.ts)
2. **404 errors**: Check API_BASE_URL in client.ts
3. **Type errors**: Check FeatureSnapshot interface matches backend
4. **React errors**: Check component rendering

#### Network Tab Debugging

1. Open DevTools → Network
2. Filter by "verify-snapshot"
3. Click "Verify with Snapshot"
4. Check:
   - Request URL: Should be `/api/v1/verify-snapshot`
   - Request Method: POST
   - Status Code: 200 OK
   - Request Payload: Contains analysis_id and snapshot object
   - Response: Contains verification_id and overall_status

### 🔧 Manual API Test (Bypass UI)

If UI isn't working, test API directly:

```bash
# Run the test script
bash test_snapshot_verification.sh
```

This will:
1. Analyze a PSIRT
2. Verify with snapshot
3. Print full JSON response

If this works but UI doesn't, the issue is in the frontend.

### 📋 Checklist

- [ ] Backend running on port 8000
- [ ] Frontend running on port 3000
- [ ] Browser DevTools open (F12)
- [ ] Console tab visible
- [ ] Network tab recording
- [ ] Completed Step 1 (Analyze PSIRT) before Step 3
- [ ] Valid JSON pasted (no syntax errors)
- [ ] Clicked "Validate JSON" before "Verify with Snapshot"

### 🆘 Still Not Working?

1. **Check backend logs**:
   ```bash
   # Look for errors in terminal running backend
   # Should see: "Analyzing PSIRT for platform: IOS-XE"
   # Then: "Snapshot verification complete: ..."
   ```

2. **Check frontend console**:
   - Any React errors?
   - Any API errors?
   - Any type mismatches?

3. **Test with curl** (bypass UI completely):
   ```bash
   bash test_snapshot_verification.sh
   ```
   If this works, issue is frontend-only.

4. **Hard refresh browser**:
   - Chrome: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
   - Firefox: Ctrl+F5
   - Clear cache and reload

### 📝 What to Report

If still having issues, provide:

1. **Browser console output** (F12 → Console tab)
2. **Network request details** (F12 → Network tab → verify-snapshot request)
3. **Steps to reproduce**
4. **Expected vs actual behavior**
5. **Screenshot of UI state**

### ✅ Expected Behavior

**After Step 1 (Analyze PSIRT):**
- Green "✓ Analysis complete" message
- "Step 2: Analysis Results" shows predicted labels
- "Step 3: Choose Verification Method" appears

**After Choosing Snapshot Mode:**
- "Step 3: Snapshot Verification" form appears
- Large textarea for JSON input
- "Validate JSON" and "Verify with Snapshot" buttons

**After Pasting Valid JSON and Clicking "Validate JSON":**
- Green "✓ Snapshot Validated" box appears
- Shows: Platform, Extracted time, Feature count, Version
- "Verify with Snapshot" button enabled

**After Clicking "Verify with Snapshot":**
- "Step 4: Verification Report" appears
- Shows overall status (colored badge)
- Lists features present/absent
- Shows evidence section
- "Export as JSON" button available
