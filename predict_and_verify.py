#!/usr/bin/env python3
"""
Complete pipeline: PSIRT → SEC-8B labels → Config verification commands

Backend Options:
- auto: Auto-detect platform (default) - MLX on Mac, Transformers+PEFT on Linux
- mlx: MLX-LM with LoRA v3 adapter (71% accuracy, Mac only)
- transformers_local: HuggingFace Transformers + PEFT (57% accuracy, Linux/CUDA/CPU)
- transformers: HuggingFace Transformers with FewShot (legacy, no adapter)
"""
import yaml
import json


def detect_platform():
    """
    Auto-detect the best inference backend for the current platform.

    Returns:
        str: 'mlx' for Mac/MPS, 'transformers_local' for Linux/CUDA/CPU
    """
    import sys

    # Check for Mac/MPS (MLX works best on Apple Silicon)
    if sys.platform == 'darwin':
        try:
            import torch
            if torch.backends.mps.is_available():
                print("🔍 Platform detection: Mac with MPS → using MLX backend")
                return 'mlx'
        except ImportError:
            pass

        # Even without torch, try MLX on Mac
        try:
            import mlx
            print("🔍 Platform detection: Mac (MLX available) → using MLX backend")
            return 'mlx'
        except ImportError:
            pass

    # Check for CUDA
    try:
        import torch
        if torch.cuda.is_available():
            print(f"🔍 Platform detection: CUDA available ({torch.cuda.get_device_name(0)}) → using Transformers+PEFT")
            return 'transformers_local'
    except ImportError:
        pass

    # Fallback to CPU with Transformers
    print("🔍 Platform detection: CPU fallback → using Transformers+PEFT")
    return 'transformers_local'


class PSIRTVerificationPipeline:
    def __init__(self, backend='auto', model_name='foundation-sec-8b'):
        # Auto-detect platform if requested
        if backend == 'auto':
            backend = detect_platform()

        self.backend = backend

        # Initialize Labeler based on backend
        if backend == 'mlx':
            from mlx_inference import MLXPSIRTLabeler
            print(f"🚀 Initializing MLX backend with LoRA adapter (~71% accuracy)...")
            self.labeler = MLXPSIRTLabeler()  # Uses models/adapters/mlx_v1
        elif backend == 'transformers_local':
            from transformers_inference import TransformersPSIRTLabeler
            print(f"🚀 Initializing Transformers backend with PEFT adapter (~57% accuracy)...")
            self.labeler = TransformersPSIRTLabeler(model_name=model_name)
        else:
            from fewshot_inference import FewShotPSIRTLabeler
            print("🚀 Initializing Transformers backend (legacy, no adapter)...")
            self.labeler = FewShotPSIRTLabeler()

        # Load taxonomy with full metadata (config_regex, show_cmds)
        print("📖 Loading taxonomy metadata for config commands...")
        self.taxonomy_metadata = {}
        self._load_taxonomy_metadata('taxonomies/features.yml', 'IOS-XE')
        self._load_taxonomy_metadata('taxonomies/features_iosxr.yml', 'IOS-XR')
        self._load_taxonomy_metadata('taxonomies/features_asa.yml', 'ASA')
        self._load_taxonomy_metadata('taxonomies/features_asa.yml', 'FTD')
        self._load_taxonomy_metadata('taxonomies/features_nxos.yml', 'NX-OS')
        print(f"✅ Loaded metadata for {sum(len(p) for p in self.taxonomy_metadata.values())} labels")

    def _load_taxonomy_metadata(self, filepath, platform):
        """Load full taxonomy with config_regex and show_cmds"""
        try:
            with open(filepath, 'r') as f:
                features = yaml.safe_load(f)

            # Index by label for fast lookup
            self.taxonomy_metadata[platform] = {}
            for feature in features:
                self.taxonomy_metadata[platform][feature['label']] = {
                    'domain': feature.get('domain', 'Unknown'),
                    'config_regex': feature.get('presence', {}).get('config_regex', []),
                    'show_cmds': feature.get('presence', {}).get('show_cmds', []),
                    'docs': feature.get('docs', {})
                }
        except FileNotFoundError:
            print(f"⚠️  Warning: {filepath} not found")
            self.taxonomy_metadata[platform] = {}

    def generate_verification_commands(self, labels, platform):
        """Map predicted labels to config verification commands"""
        verification = {
            'config_checks': [],
            'show_commands': [],
            'domains': []
        }

        platform_taxonomy = self.taxonomy_metadata.get(platform, {})

        for label in labels:
            metadata = platform_taxonomy.get(label)
            if not metadata:
                print(f"⚠️  Warning: Label '{label}' not found in {platform} taxonomy")
                continue

            # Add domain
            if metadata['domain'] not in verification['domains']:
                verification['domains'].append(metadata['domain'])

            # Add config regex patterns
            for pattern in metadata['config_regex']:
                verification['config_checks'].append({
                    'label': label,
                    'pattern': pattern,
                    'description': f"Check if {label} is configured"
                })

            # Add show commands
            for cmd in metadata['show_cmds']:
                verification['show_commands'].append({
                    'label': label,
                    'command': cmd,
                    'description': f"Verify {label} on device"
                })

        return verification

    def process_psirt(self, psirt_summary, platform, advisory_id=None):
        """Complete workflow: PSIRT → Labels → Verification Commands

        Args:
            psirt_summary: PSIRT summary text
            platform: Platform (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
            advisory_id: Optional advisory ID for exact matching
        """
        print(f"\n{'='*80}")
        print(f"🔍 Processing PSIRT")
        print(f"{'='*80}")
        print(f"Platform: {platform}")
        if advisory_id:
            print(f"Advisory ID: {advisory_id}")
        print(f"Summary: {psirt_summary}")

        # Step 1: Predict labels (exact match or few-shot)
        print(f"\n📊 Predicting labels with SEC-8B...")
        result = self.labeler.predict_labels(psirt_summary, platform, advisory_id=advisory_id)
        predicted_labels = result['predicted_labels']

        print(f"✅ Predicted Labels: {predicted_labels}")

        # Step 2: Map labels to verification commands
        print(f"\n🔧 Generating verification commands...")
        verification = self.generate_verification_commands(predicted_labels, platform)

        # Step 3: Format output
        output = {
            'psirt_summary': psirt_summary,
            'platform': platform,
            'predicted_labels': predicted_labels,
            'confidence': result.get('confidence', 0.0),
            'domains': verification['domains'],
            'config_checks': verification['config_checks'],
            'show_commands': verification['show_commands'],
            'retrieved_examples': [
                {
                    'summary': ex['summary'][:80] + '...',
                    'labels': ex['labels']
                }
                for ex in result.get('retrieved_examples', [])[:3]
            ]
        }

        return output

    def display_results(self, output):
        """Pretty print results"""
        print(f"\n{'='*80}")
        print(f"📋 VERIFICATION INSTRUCTIONS")
        print(f"{'='*80}")

        print(f"\n🏷️  Labels: {', '.join(output['predicted_labels'])}")
        print(f"📂 Domains: {', '.join(output['domains'])}")

        print(f"\n🔍 Configuration Checks:")
        print(f"{'─'*80}")
        for i, check in enumerate(output['config_checks'], 1):
            print(f"{i}. [{check['label']}] Pattern: {check['pattern']}")

        print(f"\n💻 Device Verification Commands:")
        print(f"{'─'*80}")
        unique_cmds = list(dict.fromkeys([c['command'] for c in output['show_commands']]))
        for i, cmd in enumerate(unique_cmds, 1):
            print(f"{i}. {cmd}")

        print(f"\n📚 Based on similar PSIRTs:")
        for i, ex in enumerate(output['retrieved_examples'], 1):
            print(f"  {i}. {ex['summary']}")
            print(f"     Labels: {ex['labels']}")

        print(f"\n{'='*80}")


# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='PSIRT Verification Pipeline')
    parser.add_argument('--backend', choices=['auto', 'mlx', 'transformers_local', 'transformers'], default='auto',
                       help='Inference backend: auto (default, detects platform), mlx (Mac), transformers_local (Linux/CUDA), transformers (legacy)')
    parser.add_argument('--model', default='foundation-sec-8b', help='Model name (for transformers backends)')
    args = parser.parse_args()

    pipeline = PSIRTVerificationPipeline(backend=args.backend, model_name=args.model)

    # Test cases
    test_cases = [
        {
            'summary': 'A vulnerability in the SSH server of Cisco IOS XE Software could allow an unauthenticated remote attacker to cause a denial of service condition',
            'platform': 'IOS-XE'
        },
        {
            'summary': 'VPN IPSec tunnel establishment fails when using IKEv2 with certificate authentication on ASA',
            'platform': 'ASA'
        },
        {
            'summary': 'SNMP community string exposure in configuration backup files for NX-OS switches',
            'platform': 'NX-OS'
        }
    ]

    print("\n" + "="*80)
    print("🚀 PSIRT VERIFICATION PIPELINE - DEMONSTRATION")
    print("="*80)

    results = []
    for test in test_cases:
        result = pipeline.process_psirt(test['summary'], test['platform'])
        pipeline.display_results(result)
        results.append(result)

    # Save results
    print(f"\n💾 Saving results to verification_output.json...")
    with open('verification_output.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("✅ Results saved!")

    print(f"\n{'='*80}")
    print("🎯 NEXT STEPS:")
    print("="*80)
    print("1. Take the 'show_commands' from above")
    print("2. SSH into the affected device")
    print("3. Run each show command")
    print("4. Parse output for config_regex patterns")
    print("5. Determine if vulnerable feature is configured")
    print("="*80)
