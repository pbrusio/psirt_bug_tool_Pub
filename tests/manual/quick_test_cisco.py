#!/usr/bin/env python3
"""
Quick API Test Script
Run this to verify your Cisco API credentials and the fetcher work correctly.
"""

import os
import sys

# Inline credentials for quick test (rotate after!)
os.environ['CISCO_CLIENT_ID'] = 'm73z3pxavt83xsacg93e9scv'
os.environ['CISCO_CLIENT_SECRET'] = 'p9cYhA76xsUfd38yXTYdchg9'

print("=" * 60)
print("🧪 CISCO API QUICK TEST")
print("=" * 60)

# Test 1: OAuth Token
print("\n[1/3] Testing OAuth2 Authentication...")
try:
    import requests
    response = requests.post(
        "https://id.cisco.com/oauth2/default/v1/token",
        data={
            'grant_type': 'client_credentials',
            'client_id': os.environ['CISCO_CLIENT_ID'],
            'client_secret': os.environ['CISCO_CLIENT_SECRET']
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=30
    )
    
    if response.status_code == 200:
        token_data = response.json()
        token = token_data['access_token']
        print(f"   ✅ SUCCESS! Got token (expires in {token_data.get('expires_in', '?')}s)")
        print(f"   Token preview: {token[:20]}...{token[-10:]}")
    else:
        print(f"   ❌ FAILED: HTTP {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        sys.exit(1)
        
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    sys.exit(1)

# Test 2: PSIRT API
print("\n[2/3] Testing PSIRT API (fetching 3 latest advisories)...")
try:
    response = requests.get(
        "https://apix.cisco.com/security/advisories/v2/latest/3",
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        },
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        advisories = data.get('advisories', [])
        print(f"   ✅ SUCCESS! Got {len(advisories)} advisories")
        for adv in advisories[:3]:
            print(f"      - {adv.get('advisoryId')}: {adv.get('advisoryTitle', 'No title')[:50]}...")
    else:
        print(f"   ❌ FAILED: HTTP {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        
except Exception as e:
    print(f"   ❌ ERROR: {e}")

# Test 3: Bug API
print("\n[3/3] Testing Bug API (searching 'security')...")
try:
    response = requests.get(
        "https://apix.cisco.com/bug/v2.0/bugs/keyword/security",
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        },
        params={'page_size': 3},
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        bugs = data.get('bugs', [])
        print(f"   ✅ SUCCESS! Got {len(bugs)} bugs")
        for bug in bugs[:3]:
            print(f"      - {bug.get('bug_id')}: {bug.get('headline', 'No headline')[:50]}...")
    else:
        print(f"   ⚠️  HTTP {response.status_code} (Bug API may require different permissions)")
        print(f"   Response: {response.text[:200]}")
        
except Exception as e:
    print(f"   ⚠️  ERROR: {e}")

print("\n" + "=" * 60)
print("🏁 TEST COMPLETE")
print("=" * 60)
print("\nIf tests passed, run the full pipeline:")
print("  python scripts/cisco_vuln_fetcher.py --mode latest --count 10 -o test_data.json")
print("  python tools/offline_update_packager.py --fetch --days 7 --mock-labeler -o update.zip")
print("\n⚠️  REMEMBER: Rotate your API credentials after testing!")
