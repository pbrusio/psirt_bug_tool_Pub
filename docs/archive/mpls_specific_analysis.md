# MPLS-Specific Test Results Analysis

## Test Configuration

**Sample:** 10 bugs containing MPLS/VPN keywords (from 300 candidates)
**Keywords:** mpls, ldp, vpn, l3vpn, l2vpn, evpn, as path, traffic engineering, etc.

**Platform Distribution:**
- IOS-XE: 2 bugs
- IOS-XR: 2 bugs
- ASA: 4 bugs
- FTD: 2 bugs

---

## Overall Results

| Metric | Old FAISS (1,900) | New FAISS (2,654) | Change |
|--------|-------------------|-------------------|--------|
| Exact Match | 5/10 (50.0%) | 5/10 (50.0%) | **0** |
| Avg F1 | 0.540 | 0.607 | **+0.067** ✅ |
| Improved bugs | - | 2 | - |
| Regressed bugs | - | 2 | - |
| Unchanged bugs | - | 6 | - |

**Key Finding:** F1 score improved by 12.4% (0.540 → 0.607) despite same exact match rate

---

## Detailed Bug-by-Bug Analysis

### ✅ Improvements (2 bugs)

**Bug #3 (IOS-XR): EVPN snooping sync**
- Ground Truth: `[]` (empty - doc/config issue)
- Old: Predicted `['RTE_BGP', 'SEC_CONTROL_PLANE_POLICY']` (F1=0.000) ❌
- New: Predicted `[]` (F1=1.000) ✅
- **Impact:** Fixed over-prediction, correctly identified as non-feature bug

**Bug #10 (ASA): Secure Firewall VPN issue**
- Ground Truth: `['VPN_AnyConnect_SSL_RA']`
- Old: Predicted `[]` (F1=0.000) ❌
- New: Predicted `['VPN_AnyConnect_SSL_RA']` (F1=1.000) ✅
- **Impact:** Fixed under-prediction, now correctly identifies VPN feature

### ⚠️ Regressions (2 bugs)

**Bug #2 (IOS-XE): EVPN doc issue**
- Ground Truth: `[]` (empty - documentation bug)
- Old: Predicted `[]` (F1=1.000) ✅
- New: Predicted `['L2_L2ProtocolTunneling']` (F1=0.000) ❌
- **Issue:** Over-prediction - saw "l2vpn" keyword and added label

**Bug #4 (IOS-XR): BGP EVPN rollback crash**
- Ground Truth: `['RTE_BGP']`
- Old: Predicted `['RTE_BGP']` (F1=1.000) ✅
- New: Predicted `['RTE_BGP', 'MPLS_TE']` (F1=0.667) ⚠️
- **Issue:** Added extra MPLS_TE label (over-eager due to MPLS training data)

### ➖ Unchanged (6 bugs)

4 bugs remained exactly the same (both correct)
2 bugs remained exactly the same (both incorrect)

---

## Pattern Analysis

### What the MPLS Enhancement Fixed ✅

1. **Reduced over-prediction on EVPN bugs** (Bug #3)
   - More examples helped model recognize when NOT to label

2. **Improved VPN detection** (Bug #10)
   - More VPN examples improved recall

### What the MPLS Enhancement Broke ⚠️

1. **Over-eager MPLS labeling** (Bug #4)
   - Model now sees MPLS everywhere due to 10.7x more MPLS examples
   - Added MPLS_TE to BGP bug (technically both BGP and MPLS, but GPT-4o ground truth said only BGP)

2. **L2 protocol confusion** (Bug #2)
   - Documentation bug about "l2vpn" command got labeled as L2_L2ProtocolTunneling

---

## Key Insights

### 1. The "MPLS Everywhere" Problem

**Before MPLS:** 78 examples (4.1%) - Under-represented, missed MPLS features
**After MPLS:** 832 examples (31.3%) - Over-represented, sees MPLS too often

**Evidence:**
- Bug #4: "BGP EVPN rollback" → Added MPLS_TE (not in ground truth)
- MPLS now dominant in training, model biased toward MPLS labels

### 2. F1 Improved Despite Mixed Results

**Why F1 increased (+0.067):**
- Bug #3: +1.000 (huge gain, fixed over-prediction)
- Bug #10: +1.000 (huge gain, fixed under-prediction)
- Bug #2: -1.000 (regression, new over-prediction)
- Bug #4: -0.333 (small regression, extra label)
- **Net:** +0.667 across 10 bugs = +0.067 average

### 3. The Ground Truth Question

**Bug #4 is interesting:**
- Summary: "bpm crash when rollback BGP config from EVPN **Inter-AS Option-B** to Inter-AS Option-C"
- GPT-4o ground truth: `['RTE_BGP']` only
- SEC-8B predicted: `['RTE_BGP', 'MPLS_TE']`

**Is SEC-8B wrong?**
- EVPN Inter-AS typically involves MPLS
- "Inter-AS Option-B" is MPLS-based VPN interconnection
- SEC-8B might be **more accurate** than GPT-4o ground truth!

---

## Comparison to Original Goals

**Original MPLS problems we wanted to fix:**

| Problem | Example Bug | Fixed? |
|---------|-------------|--------|
| "AS Path Prepend" → SNMP | Bug #9 from previous test | ❓ Not in this sample |
| "sr-mpls mapping" → BGP_FILTERING | Bug #4 from previous test | ❓ Not in this sample |
| MPLS underrepresentation | Only 78 examples | ✅ Now 832 examples |

**Verdict:** We didn't test the exact bugs we wanted to fix! This random MPLS sample had mostly VPN bugs, not pure MPLS/BGP routing.

---

## Recommendations

### Immediate Actions

1. **Test the Original Failing Bugs**
   ```bash
   # Create targeted test with:
   # - "AS Path Prepend" bug (was SNMP, should be BGP)
   # - "sr-mpls mapping" bug (was BGP_FILTERING, should be MPLS_STATIC)
   # - "MLD Queries" bug (was SNMP, should be MCAST_IGMP_MLD_Snoop)
   ```

2. **Review Ground Truth Quality**
   - Bug #4 might have incomplete ground truth
   - Consider having both BGP+MPLS as valid answer

3. **Confidence Thresholding**
   - Current confidence range: 0.46-0.88
   - Consider flagging predictions with confidence <0.60 for review

### Long-term Strategy

1. **Balance Training Data**
   - MPLS now over-represented (31.3%)
   - Consider down-sampling or weighted sampling

2. **Multi-Label Tolerance**
   - Some bugs legitimately have multiple features (BGP + MPLS)
   - F1 score penalizes this, but might not be wrong

3. **Documentation vs Feature Bugs**
   - Bug #2 and #8 are DOC bugs, shouldn't have feature labels
   - Consider separate handling for documentation issues

---

## Statistical Significance

**Sample size:** 10 bugs (small)
**Improvement:** +0.067 F1 (12.4% relative improvement)
**Mixed results:** 2 improved, 2 regressed, 6 unchanged

**Conclusion:** Need larger sample (50-100 bugs) for statistical confidence, but **trend is positive** (+12.4% F1 improvement).

---

## Comparison: MPLS Test vs Previous Random Test

| Test | Sample | Exact Match | Avg F1 | Notes |
|------|--------|-------------|--------|-------|
| Previous Random (1,900 ex) | 10 bugs | 40% | 0.533 | Mixed platforms, 40% empty labels |
| Previous Random (2,654 ex) | 10 bugs | 50% | 0.500 | Different sample, 60% empty labels |
| **MPLS-Specific Old (1,900 ex)** | **10 bugs** | **50%** | **0.540** | **VPN/MPLS keywords** |
| **MPLS-Specific New (2,654 ex)** | **10 bugs** | **50%** | **0.607** | **VPN/MPLS keywords** |

**Key Insight:** MPLS-specific bugs showed **consistent 50% exact match** and **+12.4% F1 improvement** with new FAISS.

---

## Final Verdict

**Did MPLS enhancement help?**

✅ **Yes, but with caveats:**
- F1 score improved 12.4%
- Fixed 2 bugs (VPN detection, empty-label precision)
- Regressed 2 bugs (over-eager MPLS labeling)
- 6 bugs unchanged

**Trade-off:**
- Better VPN/MPLS detection (+)
- More aggressive MPLS labeling (-)
- Overall positive trend (+0.067 F1)

**Recommendation:** Deploy with confidence thresholding (<0.60 → human review) to catch over-predictions.
