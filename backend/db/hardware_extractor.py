#!/usr/bin/env python3
"""
Hardware Model Extraction from Bug/PSIRT Text

Extracts hardware platform identifiers from bug headlines/summaries to enable
hardware-based filtering. Conservative approach: only extract when confident.

Philosophy: "When in doubt, include it"
- NULL hardware_model = generic bug (applies to all hardware)
- Specific hardware_model = only applies to that hardware family
- Better to miss an extraction than create false negatives

Usage:
    from backend.db.hardware_extractor import extract_hardware_model

    text = "Cat9300 switch crashes with VXLAN traffic"
    hardware = extract_hardware_model(text)  # Returns: "Cat9300"
"""

import re
from typing import Optional


# Hardware pattern definitions by platform
# Format: (regex_pattern, normalized_name)
# Patterns are ordered by specificity (most specific first)

HARDWARE_PATTERNS_IOSXE = [
    # Catalyst 9000 Series - Campus Switches
    # Match: "Cat9200", "Catalyst 9200", "C9200", "C9200L", "9200CX", etc.
    (r'\b(?:Cat(?:alyst)?[\s-]?9200|C9200)[A-Z]{0,2}(?:-[A-Z0-9]+)?\b', 'Cat9200'),
    (r'\b(?:Cat(?:alyst)?[\s-]?9300|C9300)[A-Z]{0,2}(?:-[A-Z0-9]+)?\b', 'Cat9300'),
    (r'\b(?:Cat(?:alyst)?[\s-]?9400|C9400)[A-Z]{0,2}(?:-[A-Z0-9]+)?\b', 'Cat9400'),
    (r'\b(?:Cat(?:alyst)?[\s-]?9500|C9500)[A-Z]{0,2}(?:-[A-Z0-9]+)?\b', 'Cat9500'),
    (r'\b(?:Cat(?:alyst)?[\s-]?9600|C9600)[A-Z]{0,2}(?:-[A-Z0-9]+)?\b', 'Cat9600'),

    # Catalyst 9800 - Wireless Controllers
    (r'\b(?:Cat(?:alyst)?[\s-]?9800|C9800)[A-Z]{0,2}(?:-[A-Z0-9]+)?\b', 'Cat9800'),

    # Catalyst 8000 - SD-WAN/Edge
    (r'\bC8200(?:[A-Z]{0,2})?(?:-[A-Z0-9]+)?\b', 'C8200'),
    (r'\bC8300(?:[A-Z]{0,2})?(?:-[A-Z0-9]+)?\b', 'C8300'),
    (r'\bC8500(?:[A-Z]{0,2})?(?:-[A-Z0-9]+)?\b', 'C8500'),
    (r'\bC8000[Vv]\b', 'C8000V'),  # Virtual

    # ISR 4000 - Legacy but supported until 2030
    (r'\bISR[\s-]?4[0-9]{3}[KkXx]?\b', 'ISR4K'),

    # ASR 1000 - Aggregation (sometimes runs IOS-XE)
    (r'\bASR[\s-]?1[KkXx]\b', 'ASR1K'),  # ASR1K (shorthand)
    (r'\bASR[\s-]?1[0-9]{3}[KkXx]?\b', 'ASR1K'),  # ASR1001, ASR1002, etc.

    # CSR 1000v - Virtual
    (r'\bCSR[\s-]?1000[Vv]\b', 'CSR1000v'),
]

HARDWARE_PATTERNS_IOSXR = [
    # NCS Series
    (r'\bNCS[\s-]?540\b', 'NCS540'),
    (r'\bNCS[\s-]?560\b', 'NCS560'),
    (r'\bNCS[\s-]?5500\b', 'NCS5500'),
    (r'\bNCS[\s-]?5700\b', 'NCS5700'),

    # Cisco 8000 Series (IOS-XR)
    (r'\b(?:Cisco[\s-])?8[0-9]{3}\b(?!V)', 'C8000'),  # Exclude C8000V (that's IOS-XE)

    # ASR 9000 Series
    (r'\bASR[\s-]?9[KkXx]\b', 'ASR9K'),  # ASR9K (shorthand)
    (r'\bASR[\s-]?9[0-9]{3}[KkXx]?\b', 'ASR9K'),  # ASR9001, ASR9006, etc.
]

HARDWARE_PATTERNS_NXOS = [
    # Nexus 9000 Series
    (r'\bNexus[\s-]?9300\b', 'N9K-9300'),
    (r'\bNexus[\s-]?9500R\b', 'N9K-9500R'),  # More specific first
    (r'\bNexus[\s-]?9500\b', 'N9K-9500'),
    (r'\bN9K[\s-]?9300\b', 'N9K-9300'),
    (r'\bN9K[\s-]?9500\b', 'N9K-9500'),

    # Nexus 3000 Series
    (r'\bNexus[\s-]?3[0-9]{3}\b', 'N3K'),
    (r'\bN3K\b', 'N3K'),

    # MDS 9000 Series (SAN)
    (r'\bMDS[\s-]?9[0-9]{3}\b', 'MDS9K'),
]

HARDWARE_PATTERNS_FTD = [
    # Secure Firewall 3100 Series (current)
    (r'\b(?:Secure[\s-]?Firewall[\s-]?|FP)?31(?:05|10|20|30|40)\b', 'FP3100'),

    # Firepower 4100 Series (EOS Jan 2026)
    (r'\b(?:Firepower[\s-]?)?4[0-9]{3}\b', 'FP4100'),

    # Firepower 9300 Series (EOS Mar 2026)
    (r'\b(?:Firepower[\s-]?)?9300\b', 'FP9300'),

    # Legacy format "FTD 4110" or shorthand "FP4120"
    (r'\b(?:FTD|FP)[\s-]?31[0-9]{2}\b', 'FP3100'),
    (r'\b(?:FTD|FP)[\s-]?4[0-9]{3}\b', 'FP4100'),
    (r'\b(?:FTD|FP)[\s-]?9300\b', 'FP9300'),
]

# Platform-to-pattern mapping
PLATFORM_PATTERNS = {
    'IOS-XE': HARDWARE_PATTERNS_IOSXE,
    'IOS-XR': HARDWARE_PATTERNS_IOSXR,
    'NX-OS': HARDWARE_PATTERNS_NXOS,
    'FTD': HARDWARE_PATTERNS_FTD,
    'ASA': [],  # ASA typically doesn't have model-specific bugs in same way
}


def extract_hardware_model(text: str, platform: str = None) -> Optional[str]:
    """
    Extract normalized hardware model from bug/PSIRT text.

    Args:
        text: Bug headline + summary combined, or just headline
        platform: Optional platform hint (IOS-XE, IOS-XR, etc.)
                 If provided, only searches patterns for that platform.
                 If None, searches all platforms (slower, may have ambiguity).

    Returns:
        Normalized hardware model (e.g., 'Cat9200', 'ASR9K', 'FP3100')
        or None if no hardware detected (generic bug)

    Examples:
        >>> extract_hardware_model("Cat9300 switch crashes with VXLAN", "IOS-XE")
        'Cat9300'

        >>> extract_hardware_model("C9200L-24T memory leak in SNMP", "IOS-XE")
        'Cat9200'

        >>> extract_hardware_model("Generic IOS-XE SSH vulnerability", "IOS-XE")
        None
    """
    if not text:
        return None

    # Determine which patterns to search
    if platform and platform in PLATFORM_PATTERNS:
        patterns_to_search = PLATFORM_PATTERNS[platform]
    else:
        # Search all platforms (less efficient, but works)
        patterns_to_search = []
        for platform_patterns in PLATFORM_PATTERNS.values():
            patterns_to_search.extend(platform_patterns)

    # Search for hardware patterns (case-insensitive)
    for pattern, normalized_name in patterns_to_search:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return normalized_name

    # No hardware detected - this is a generic bug
    return None


def extract_hardware_model_from_show_version(show_version_output: str) -> Optional[str]:
    """
    Extract hardware model from 'show version' output.

    This is used for live device verification to auto-detect hardware platform.

    Args:
        show_version_output: Output of 'show version' command

    Returns:
        Normalized hardware model or None

    Example IOS-XE patterns:
        "Cisco IOS Software [Amsterdam], Catalyst L3 Switch Software (CAT9300-UNIVERSALK9-M)"
        → Hardware: Cat9300

        "cisco C9200L-24T-4G (X86_64_LINUX_IOSD-UNIVERSALK9-M)"
        → Hardware: Cat9200
    """
    if not show_version_output:
        return None

    # Pattern 1: CAT9XXX in software image name
    match = re.search(r'CAT([0-9]{4}[A-Z]*)-', show_version_output, re.IGNORECASE)
    if match:
        model = match.group(1)
        # Normalize to series level (9200, 9300, etc.)
        series = model[:4]  # Take first 4 digits
        return f"Cat{series}"

    # Pattern 2a: Catalyst 8000 Series (C8200, C8300, C8500, C8000V) - Check BEFORE generic C9xxx
    match = re.search(r'cisco\s+(C8[0-9]{3}[A-Z]*)', show_version_output, re.IGNORECASE)
    if match:
        model = match.group(1)
        # C8200, C8300, C8500, C8000V
        if model[:5].upper() == 'C8000':
            return 'C8000V' if model.upper().endswith('V') else 'C8000'
        else:
            series = model[:5]  # C8200, C8300, C8500
            return series.upper()

    # Pattern 2b: cisco C9XXX in platform line (Catalyst 9000 series)
    match = re.search(r'cisco\s+(C9[0-9]{3}[A-Z]*)', show_version_output, re.IGNORECASE)
    if match:
        model = match.group(1)[1:]  # Remove 'C' prefix
        series = model[:4]  # 9200, 9300, etc.
        return f"Cat{series}"

    # Pattern 3: ASR in model name (both shorthand like "ASR9K" and full like "ASR9001")
    # Check shorthand first (ASR9K, ASR1K)
    match = re.search(r'\bASR([19])[KkXx]\b', show_version_output, re.IGNORECASE)
    if match:
        series = match.group(1)
        return f'ASR{series}K'

    # Check full model numbers (ASR9001, ASR1002, etc.)
    match = re.search(r'\bASR([19])[0-9]{3}\b', show_version_output, re.IGNORECASE)
    if match:
        series = match.group(1)
        return f'ASR{series}K'

    # Pattern 4: ISR in model name
    match = re.search(r'\bISR4[0-9]{3}\b', show_version_output, re.IGNORECASE)
    if match:
        return 'ISR4K'

    # Pattern 5: NCS Series (IOS-XR)
    match = re.search(r'\bNCS[\s-]?(540|560|5500|5700)\b', show_version_output, re.IGNORECASE)
    if match:
        return f"NCS{match.group(1)}"

    # Pattern 6: Cisco 8000 Series IOS-XR (without C prefix)
    match = re.search(r'\bcisco\s+8[0-9]{3}\b', show_version_output, re.IGNORECASE)
    if match:
        return 'C8000'

    # Pattern 7: Firepower (FTD)
    match = re.search(r'\bFirepower\s+(31[0-9]{2}|4[0-9]{3}|9300)\b', show_version_output, re.IGNORECASE)
    if match:
        model = match.group(1)
        if model.startswith('31'):
            return 'FP3100'
        elif model.startswith('4'):
            return 'FP4100'
        elif model.startswith('93'):
            return 'FP9300'

    return None


def get_hardware_display_name(hardware_model: str) -> str:
    """
    Convert normalized hardware model to display name for UI.

    Args:
        hardware_model: Normalized model (e.g., 'Cat9200', 'ASR9K')

    Returns:
        Human-readable name (e.g., 'Catalyst 9200 Series')
    """
    display_names = {
        # IOS-XE
        'Cat9200': 'Catalyst 9200 Series',
        'Cat9300': 'Catalyst 9300 Series',
        'Cat9400': 'Catalyst 9400 Series',
        'Cat9500': 'Catalyst 9500 Series',
        'Cat9600': 'Catalyst 9600 Series',
        'Cat9800': 'Catalyst 9800 Series (Wireless)',
        'C8200': 'Catalyst 8200 Series',
        'C8300': 'Catalyst 8300 Series',
        'C8500': 'Catalyst 8500 Series',
        'C8000V': 'Catalyst 8000V (Virtual)',
        'ISR4K': 'ISR 4000 Series',
        'ASR1K': 'ASR 1000 Series',
        'CSR1000v': 'CSR 1000v (Virtual)',

        # IOS-XR
        'NCS540': 'NCS 540 Series',
        'NCS560': 'NCS 560 Series',
        'NCS5500': 'NCS 5500 Series',
        'NCS5700': 'NCS 5700 Series',
        'C8000': 'Cisco 8000 Series',
        'ASR9K': 'ASR 9000 Series',

        # NX-OS
        'N9K-9300': 'Nexus 9300 Series',
        'N9K-9500': 'Nexus 9500 Series',
        'N9K-9500R': 'Nexus 9500R Series',
        'N3K': 'Nexus 3000 Series',
        'MDS9K': 'MDS 9000 Series',

        # FTD
        'FP3100': 'Secure Firewall 3100 Series',
        'FP4100': 'Firepower 4100 Series',
        'FP9300': 'Firepower 9300 Series',
    }

    return display_names.get(hardware_model, hardware_model)


def get_hardware_choices_for_platform(platform: str) -> list[tuple[Optional[str], str]]:
    """
    Get hardware choices for a platform (for UI dropdown).

    Args:
        platform: Platform name (IOS-XE, IOS-XR, etc.)

    Returns:
        List of (value, label) tuples for dropdown
    """
    hardware_by_platform = {
        'IOS-XE': [
            (None, 'Any Hardware (Generic Bugs Only)'),
            ('Cat9200', 'Catalyst 9200 Series'),
            ('Cat9300', 'Catalyst 9300 Series'),
            ('Cat9400', 'Catalyst 9400 Series'),
            ('Cat9500', 'Catalyst 9500 Series'),
            ('Cat9600', 'Catalyst 9600 Series'),
            ('Cat9800', 'Catalyst 9800 Series (Wireless)'),
            ('C8200', 'Catalyst 8200 Series'),
            ('C8300', 'Catalyst 8300 Series'),
            ('C8500', 'Catalyst 8500 Series'),
            ('C8000V', 'Catalyst 8000V (Virtual)'),
            ('ISR4K', 'ISR 4000 Series'),
            ('ASR1K', 'ASR 1000 Series'),
            ('CSR1000v', 'CSR 1000v (Virtual)'),
        ],
        'IOS-XR': [
            (None, 'Any Hardware (Generic Bugs Only)'),
            ('NCS540', 'NCS 540 Series'),
            ('NCS560', 'NCS 560 Series'),
            ('NCS5500', 'NCS 5500 Series'),
            ('NCS5700', 'NCS 5700 Series'),
            ('C8000', 'Cisco 8000 Series'),
            ('ASR9K', 'ASR 9000 Series'),
        ],
        'NX-OS': [
            (None, 'Any Hardware (Generic Bugs Only)'),
            ('N9K-9300', 'Nexus 9300 Series'),
            ('N9K-9500', 'Nexus 9500 Series'),
            ('N9K-9500R', 'Nexus 9500R Series'),
            ('N3K', 'Nexus 3000 Series'),
            ('MDS9K', 'MDS 9000 Series'),
        ],
        'FTD': [
            (None, 'Any Hardware (Generic Bugs Only)'),
            ('FP3100', 'Secure Firewall 3100 Series'),
            ('FP4100', 'Firepower 4100 Series'),
            ('FP9300', 'Firepower 9300 Series'),
        ],
        'ASA': [
            (None, 'Any Hardware (Generic Bugs Only)'),
            # ASA typically doesn't have hardware-specific bugs
        ],
    }

    return hardware_by_platform.get(platform, [(None, 'Any Hardware (Generic Bugs Only)')])


if __name__ == '__main__':
    """Test cases for hardware extraction."""

    test_cases = [
        # IOS-XE
        ('Cat9300 switch crashes with VXLAN', 'IOS-XE', 'Cat9300'),
        ('C9200L-24T memory leak in SNMP', 'IOS-XE', 'Cat9200'),
        ('Catalyst 9400 dual-sup failover issue', 'IOS-XE', 'Cat9400'),
        ('ASR1K IPsec stateful HA on dual-RP', 'IOS-XE', 'ASR1K'),
        ('C8300 SD-WAN tunnel flapping', 'IOS-XE', 'C8300'),
        ('Generic IOS-XE SSH vulnerability', 'IOS-XE', None),  # No hardware

        # IOS-XR
        ('NCS5500 BGP convergence slow', 'IOS-XR', 'NCS5500'),
        ('ASR9K MPLS TE tunnel down', 'IOS-XR', 'ASR9K'),

        # NX-OS
        ('Nexus 9300 VXLAN forwarding issue', 'NX-OS', 'N9K-9300'),

        # FTD
        ('Firepower 3110 memory exhaustion', 'FTD', 'FP3100'),
        ('FP4120 HA synchronization failure', 'FTD', 'FP4100'),
    ]

    print("Testing hardware extraction...\n")
    passed = 0
    failed = 0

    for text, platform, expected in test_cases:
        result = extract_hardware_model(text, platform)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1
        result_str = str(result) if result else 'None'
        expected_str = str(expected) if expected else 'None'
        print(f"{status} '{text[:50]:50s}' → {result_str:10s} (expected: {expected_str})")

    print(f"\n📊 Results: {passed} passed, {failed} failed")
