#!/usr/bin/env python3
"""
Test device verification with real PSIRTs from dataset
"""
import pandas as pd
import json
from device_verifier import DeviceConnector, PSIRTVerifier


def load_psirts_from_dataset(platform='IOS-XE', limit=5):
    """Load PSIRTs from enriched dataset"""
    df = pd.read_csv('output/enriched_gemini_with_labels.csv')
    df_platform = df[df['platform'] == platform].copy()

    # Filter for PSIRTs with labels
    df_labeled = df_platform[df_platform['labels'] != '[]'].copy()

    psirts = []
    for idx, row in df_labeled.head(limit).iterrows():
        try:
            psirt = {
                'bug_id': row['advisoryId'],
                'summary': row['summary'],
                'platform': row['platform'],
                'cve': eval(row['cves']) if pd.notna(row['cves']) else [],
                'labels': eval(row['labels']) if pd.notna(row['labels']) else [],
                'config_regex': eval(row['config_regex']) if pd.notna(row['config_regex']) else [],
                'show_cmds': eval(row['show_cmds']) if pd.notna(row['show_cmds']) else [],
                'fixed_versions': eval(row['fixed_versions']) if pd.notna(row['fixed_versions']) else [],
                'product_names': eval(row['productNames']) if pd.notna(row['productNames']) else [],  # NEW: Add product names
                'affected_versions': None,
                'fixed_version': None
            }
            psirts.append(psirt)
        except Exception as e:
            print(f"  ⚠️  Error parsing PSIRT {row['advisoryId']}: {e}")
            continue

    return psirts


def main():
    """Test device verification with real PSIRTs"""

    print("="*80)
    print("DEVICE PSIRT VERIFICATION TEST")
    print("="*80)

    # Device credentials
    DEVICE = {
        'host': '192.168.0.33',
        'username': 'admin',
        'password': 'Pa22word',
        'device_type': 'cisco_ios'
    }

    try:
        # Connect to device
        print("\n🔌 Connecting to device...")
        connector = DeviceConnector(**DEVICE)
        connector.connect()

        # Get device info
        hostname = connector.get_hostname()
        version = connector.get_version()
        print(f"📱 Device: {hostname}")
        print(f"📦 Version: {version}")

        # Load PSIRTs from dataset
        print("\n📋 Loading PSIRTs from dataset...")
        psirts = load_psirts_from_dataset('IOS-XE', limit=10)
        print(f"  Loaded {len(psirts)} PSIRTs")

        # Verify each PSIRT
        verifier = PSIRTVerifier(connector)
        results = []

        for i, psirt in enumerate(psirts, 1):
            print(f"\n{'='*80}")
            print(f"Testing PSIRT {i}/{len(psirts)}")
            result = verifier.verify_psirt(psirt)
            results.append(result)

        # Summary
        print(f"\n{'='*80}")
        print("📊 OVERALL SUMMARY")
        print(f"{'='*80}")

        vulnerable_count = sum(1 for r in results if r['overall_status'] == 'VULNERABLE')
        not_vulnerable_count = len(results) - vulnerable_count

        print(f"\nTotal PSIRTs tested: {len(results)}")
        print(f"🚨 VULNERABLE: {vulnerable_count}")
        print(f"✅ NOT VULNERABLE: {not_vulnerable_count}")

        if vulnerable_count > 0:
            print(f"\n⚠️  VULNERABLE PSIRTs:")
            for r in results:
                if r['overall_status'] == 'VULNERABLE':
                    print(f"  - {r['psirt_id']}")
                    print(f"    Features: {', '.join(r['features_present'])}")

        # Save results
        output_file = 'device_verification_results.json'
        with open(output_file, 'w') as f:
            json.dump({
                'device': hostname,
                'device_version': version,
                'psirts_tested': len(results),
                'vulnerable_count': vulnerable_count,
                'not_vulnerable_count': not_vulnerable_count,
                'results': results
            }, f, indent=2)

        print(f"\n💾 Detailed results saved to {output_file}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        connector.disconnect()


if __name__ == '__main__':
    main()
