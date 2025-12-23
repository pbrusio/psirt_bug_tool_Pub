#!/usr/bin/env python3
"""
Test Hardware Auto-Detection from 'show version' Output

Tests Phase 4: Hardware auto-detection functionality
"""

from backend.db.hardware_extractor import extract_hardware_model_from_show_version


def test_hardware_autodetect():
    """Test hardware auto-detection with sample 'show version' outputs"""

    print("=" * 70)
    print("HARDWARE AUTO-DETECTION TEST (Phase 4)")
    print("=" * 70)
    print()

    test_cases = [
        # IOS-XE Test Cases
        {
            'name': 'Catalyst 9300 Switch',
            'platform': 'IOS-XE',
            'output': """
Cisco IOS XE Software, Version 17.10.1
Cisco IOS Software [Cupertino], Catalyst L3 Switch Software (CAT9K_IOSXE), Version 17.10.1, RELEASE SOFTWARE (fc5)
Technical Support: http://www.cisco.com/techsupport
Copyright (c) 1986-2023 by Cisco Systems, Inc.
Compiled Tue 07-Nov-23 15:24 by mcpre

ROM: IOS-XE ROMMON
Switch01 uptime is 1 week, 2 days, 3 hours, 15 minutes
Uptime for this control processor is 1 week, 2 days, 3 hours, 17 minutes
System returned to ROM by reload
System image file is "flash:packages.conf"
Last reload reason: Reload Command

This product contains cryptographic features and is subject to United
States and local country laws governing import, export, transfer and
use. Delivery of Cisco cryptographic products does not imply
third-party authority to import, export, distribute or use encryption.
Importers, exporters, distributors and users are responsible for
compliance with U.S. and local country laws. By using this product you
agree to comply with applicable laws and regulations. If you are unable
to comply with U.S. and local laws, return this product immediately.

A summary of U.S. laws governing Cisco cryptographic products may be found at:
http://www.cisco.com/wwl/export/crypto/tool/stqrg.html

If you require further assistance please contact us by sending email to
export@cisco.com.

License Level: network-advantage
License Type: Smart License
Next reload license Level: network-advantage

cisco C9300-24T (X86) processor (revision V00) with 1388186K/6147K bytes of memory.
Processor board ID FCW2301D123
2048K bytes of non-volatile configuration memory.
16777216K bytes of physical memory.
1638400K bytes of Crash Files at crashinfo:.
11264000K bytes of Flash at flash:.
0K bytes of WebUI ODM Files at webui:.

Base Ethernet MAC Address          : 70:ea:1a:2b:3c:4d
Motherboard Assembly Number        : 73-17954-06
Motherboard Serial Number          : FOC23010ABC
Model Revision Number              : V00
Motherboard Revision Number        : A0
Model Number                       : C9300-24T
System Serial Number               : FCW2301D123

            """,
            'expected': 'Cat9300'
        },
        {
            'name': 'Catalyst 9200 Switch',
            'platform': 'IOS-XE',
            'output': """
Cisco IOS Software [Cupertino], Catalyst L3 Switch Software (CAT9K_LITE_IOSXE), Version 17.9.3, RELEASE SOFTWARE (fc1)

cisco C9200L-24T-4G (ARM64) processor (revision V0) with 1379132K/6147K bytes of memory.
Processor board ID JAE25050ABC
            """,
            'expected': 'Cat9200'
        },
        {
            'name': 'ASR 9000 Router',
            'platform': 'IOS-XR',
            'output': """
Cisco IOS XR Software, Version 7.5.2
Copyright (c) 2013-2022 by Cisco Systems, Inc.

ROM: System Bootstrap, Version 1.45

Router uptime is 3 weeks, 2 days, 12 hours, 45 minutes
System image file is "disk0:asr9k-mini-x64-7.5.2"

cisco ASR9K Series (Intel 686 F6M14S4) processor with 12582912K bytes of memory.
            """,
            'expected': 'ASR9K'
        },
        {
            'name': 'NCS 5500 Router',
            'platform': 'IOS-XR',
            'output': """
Cisco IOS XR Software, Version 7.4.1
cisco NCS-5500 () processor with 33554432K bytes of memory.
            """,
            'expected': 'NCS5500'
        },
        {
            'name': 'Generic IOS-XE Device (no specific hardware)',
            'platform': 'IOS-XE',
            'output': """
Cisco IOS XE Software, Version 17.3.5
Cisco IOS Software, Version 17.3.5, RELEASE SOFTWARE (fc1)

System uptime is 5 days, 12 hours, 30 minutes
            """,
            'expected': None
        },
        {
            'name': 'Catalyst 9800 Wireless Controller',
            'platform': 'IOS-XE',
            'output': """
Cisco IOS XE Software, Version 17.6.3
Cisco IOS Software [Cupertino], C9800 Software (C9800-WLCIOSXE-BUNDLE), Version 17.6.3, RELEASE SOFTWARE (fc4)

cisco C9800-40-K9 (X86) processor (revision V0) with 7798516K/6147K bytes of memory.
Processor board ID FCW2245G0AB
            """,
            'expected': 'Cat9800'
        },
        {
            'name': 'Cisco 8200 Series',
            'platform': 'IOS-XE',
            'output': """
Cisco IOS XE Software, Version 17.8.1a
Cisco IOS Software [Dublin], Cisco c8200 Software (C8200-UNIVERSALK9-M), Version 17.8.1a, RELEASE SOFTWARE (fc1)

cisco C8200-1N-4T (X86) processor with 1779559K/6147K bytes of memory.
            """,
            'expected': 'C8200'
        },
    ]

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['name']}")
        print("-" * 70)

        detected = extract_hardware_model_from_show_version(test['output'])
        expected = test['expected']

        if detected == expected:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1

        print(f"  Expected: {expected}")
        print(f"  Detected: {detected}")
        print(f"  {status}")
        print()

    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 70)

    if failed == 0:
        print("\n✅ All hardware auto-detection tests PASSED!")
        print("\nPhase 4 COMPLETE - Hardware auto-detection working correctly!")
        return True
    else:
        print(f"\n❌ {failed} tests FAILED - review patterns in hardware_extractor.py")
        return False


if __name__ == '__main__':
    import sys
    success = test_hardware_autodetect()
    sys.exit(0 if success else 1)
