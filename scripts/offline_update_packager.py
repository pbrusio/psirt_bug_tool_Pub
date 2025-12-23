#!/usr/bin/env python3
"""
Integrated Offline Update Packager
==================================
Enhanced version that can automatically fetch fresh vulnerability data
from Cisco APIs before running the labeling pipeline.

Features:
- Direct Cisco API integration (PSIRT + Bug APIs)
- Automatic OAuth2 token management  
- Compatible with TransformersPSIRTLabeler
- Supports both online (API fetch) and offline (file input) modes

Usage:
    # Online mode - fetch and label
    python offline_update_packager_v2.py --fetch --days 7 --output update.zip
    
    # Offline mode - use existing files  
    python offline_update_packager_v2.py --psirts data.json --output update.zip
    
    # Mock mode for testing
    python offline_update_packager_v2.py --mock --output test.zip
"""

import os
import sys
import json
import argparse
import logging
import zipfile
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

# Add parent to path for local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import the fetcher (may not be available in all environments)
try:
    from scripts.cisco_vuln_fetcher import VulnerabilityFetcher, VulnerabilityItem, load_config
    FETCHER_AVAILABLE = True
except ImportError as e:
    print(f"DEBUG: Import failed: {e}")
    FETCHER_AVAILABLE = False
    
# Try to import the labeler
try:
    from transformers_inference import TransformersPSIRTLabeler
    LABELER_AVAILABLE = True
except ImportError:
    LABELER_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockLabeler:
    """Mock labeler for testing without GPU/model."""
    def predict_labels(self, summary: str, platform: str = 'IOS-XE') -> Dict:
        return {
            'predicted_labels': ['MOCK_LABEL'],
            'confidence': 0.95,
            'rationale': 'Mock prediction for testing'
        }


class MockFetcher:
    """Mock fetcher for testing without API credentials."""
    def fetch_all(self, days: int = 7, bug_keywords: List[str] = None) -> Dict:
        return {
            'psirts': [
                VulnerabilityItem(
                    advisoryId="cisco-sa-mock-001",
                    summary="A vulnerability in the BGP implementation of Cisco IOS XE could allow denial of service.",
                    platform="IOS-XE",
                    type="PSIRT",
                    severity="High"
                ),
                VulnerabilityItem(
                    advisoryId="cisco-sa-mock-002", 
                    summary="A vulnerability in the IPsec VPN feature of Cisco ASA could allow remote code execution.",
                    platform="ASA",
                    type="PSIRT",
                    severity="Critical"
                )
            ],
            'bugs': [
                VulnerabilityItem(
                    advisoryId="CSCmock12345",
                    summary="Memory leak in OSPF process causes router reload",
                    platform="IOS-XR",
                    type="BUG",
                    severity="3"
                )
            ],
            'metadata': {'fetch_date': datetime.now().isoformat()}
        }


@dataclass  
class EnrichedItem:
    """Item enriched with AI-predicted labels."""
    advisoryId: str
    summary: str
    platform: str
    type: str
    predicted_labels: List[str]
    confidence: float
    rationale: str
    severity: Optional[str] = None
    cves: Optional[List[str]] = None
    url: Optional[str] = None


class IntegratedPackager:
    """
    Integrated pipeline for fetching, labeling, and packaging vulnerability data.
    """
    
    def __init__(self, 
                 use_mock_fetcher: bool = False,
                 use_mock_labeler: bool = False,
                 model_name: str = "foundation-sec-8b"):
        """
        Initialize the packager.
        
        Args:
            use_mock_fetcher: Use mock data instead of real API calls
            use_mock_labeler: Use mock labeler instead of real model
            model_name: Name of the labeling model to use
        """
        self.use_mock_fetcher = use_mock_fetcher
        self.use_mock_labeler = use_mock_labeler
        self.model_name = model_name
        
        # Initialize fetcher
        if use_mock_fetcher:
            logger.info("🎭 Using MOCK fetcher")
            self.fetcher = MockFetcher()
        elif FETCHER_AVAILABLE:
            try:
                config = load_config()
                self.fetcher = VulnerabilityFetcher(
                    config['client_id'], 
                    config['client_secret']
                )
                logger.info("✅ Cisco API fetcher initialized")
            except Exception as e:
                logger.warning(f"⚠️ Could not initialize fetcher: {e}")
                logger.info("   Falling back to mock fetcher")
                self.fetcher = MockFetcher()
                self.use_mock_fetcher = True
        else:
            logger.warning("⚠️ cisco_vuln_fetcher not available, using mock")
            self.fetcher = MockFetcher()
            self.use_mock_fetcher = True
            
        # Initialize labeler
        if use_mock_labeler:
            logger.info("🎭 Using MOCK labeler")
            self.labeler = MockLabeler()
        elif LABELER_AVAILABLE:
            try:
                logger.info(f"🧠 Loading labeling model: {model_name}")
                self.labeler = TransformersPSIRTLabeler(model_name=model_name)
                logger.info("✅ Labeler initialized")
            except Exception as e:
                logger.warning(f"⚠️ Could not initialize labeler: {e}")
                logger.info("   Falling back to mock labeler")
                self.labeler = MockLabeler()
                self.use_mock_labeler = True
        else:
            logger.warning("⚠️ TransformersPSIRTLabeler not available, using mock")
            self.labeler = MockLabeler()
            self.use_mock_labeler = True
            
    def fetch_data(self, days: int = 7, 
                   bug_keywords: Optional[List[str]] = None) -> List[Dict]:
        """
        Fetch fresh vulnerability data from Cisco APIs.
        
        Args:
            days: Number of days to look back
            bug_keywords: Keywords to search for bugs
            
        Returns:
            List of vulnerability items in standard format
        """
        logger.info("=" * 60)
        logger.info("📡 PHASE 1: DATA INGESTION")
        logger.info("=" * 60)
        
        if bug_keywords is None:
            bug_keywords = ['security', 'vulnerability', 'denial of service']
            
        results = self.fetcher.fetch_all(days=days, bug_keywords=bug_keywords)
        
        # Combine and normalize to dict format
        items = []
        
        for psirt in results.get('psirts', []):
            if isinstance(psirt, VulnerabilityItem):
                items.append(asdict(psirt))
            else:
                items.append(psirt)
                
        for bug in results.get('bugs', []):
            if isinstance(bug, VulnerabilityItem):
                items.append(asdict(bug))
            else:
                items.append(bug)
                
        logger.info(f"   📥 Fetched {len(items)} total items")
        logger.info(f"      - PSIRTs: {len(results.get('psirts', []))}")
        logger.info(f"      - Bugs: {len(results.get('bugs', []))}")
        
        return items
        
    def load_from_file(self, filepath: str) -> List[Dict]:
        """Load vulnerability data from a JSON file."""
        logger.info(f"📂 Loading data from {filepath}")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        # Handle different formats
        if isinstance(data, list):
            return data
        elif 'items' in data:
            return data['items']
        elif 'psirts' in data or 'bugs' in data:
            items = []
            items.extend(data.get('psirts', []))
            items.extend(data.get('bugs', []))
            return items
        else:
            raise ValueError(f"Unknown data format in {filepath}")
            
    def label_items(self, items: List[Dict]) -> List[EnrichedItem]:
        """
        Run AI labeling on all items.
        
        Args:
            items: List of vulnerability items to label
            
        Returns:
            List of enriched items with predicted labels
        """
        logger.info("=" * 60)
        logger.info("🧠 PHASE 2: AI LABELING")
        logger.info("=" * 60)
        
        enriched = []
        total = len(items)
        
        for i, item in enumerate(items, 1):
            advisory_id = item.get('advisoryId', 'Unknown')
            summary = item.get('summary', '')
            platform = item.get('platform', 'IOS-XE')
            
            if not summary:
                logger.warning(f"   ⚠️ [{advisory_id}] No summary, skipping")
                continue
                
            try:
                # Get prediction from labeler
                result = self.labeler.predict_labels(summary, platform=platform)
                
                # DEBUG: Log if empty
                if not result.get('predicted_labels'):
                    logger.warning(f"   ⚠️ Raw result for {advisory_id}: {result}")
                
                enriched_item = EnrichedItem(
                    advisoryId=advisory_id,
                    summary=summary,
                    platform=platform,
                    type=item.get('type', 'PSIRT'),
                    predicted_labels=result.get('predicted_labels', []),
                    confidence=result.get('confidence', 0.0),
                    rationale=result.get('rationale', ''),
                    severity=item.get('severity'),
                    cves=item.get('cves'),
                    url=item.get('url')
                )
                
                enriched.append(enriched_item)
                
                # Progress logging
                labels_str = ', '.join(enriched_item.predicted_labels[:3])
                logger.info(f"   [{i}/{total}] {advisory_id} → [{labels_str}]")
                
            except Exception as e:
                logger.error(f"   ❌ [{advisory_id}] Labeling failed: {e}")
                
        logger.info(f"   ✅ Successfully labeled {len(enriched)}/{total} items")
        return enriched
        
    def create_package(self, 
                       enriched_items: List[EnrichedItem],
                       output_path: str,
                       include_raw: bool = True) -> str:
        """
        Create the final update package (ZIP file).
        
        Args:
            enriched_items: List of labeled items
            output_path: Path for output ZIP file
            include_raw: Include raw data alongside labeled data
            
        Returns:
            Path to created ZIP file
        """
        logger.info("=" * 60)
        logger.info("📦 PHASE 3: PACKAGING")
        logger.info("=" * 60)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        staging_dir = f"vuln_update_{timestamp}"
        
        # Create staging directories
        os.makedirs(f"{staging_dir}/data", exist_ok=True)
        os.makedirs(f"{staging_dir}/reports", exist_ok=True)
        
        # Save enriched data
        enriched_data = [asdict(item) for item in enriched_items]
        with open(f"{staging_dir}/data/labeled_vulnerabilities.json", 'w') as f:
            json.dump(enriched_data, f, indent=2)
            
        # Create manifest
        manifest = {
            "package_version": "2.0",
            "created_at": timestamp,
            "item_count": len(enriched_items),
            "psirt_count": sum(1 for i in enriched_items if i.type == "PSIRT"),
            "bug_count": sum(1 for i in enriched_items if i.type == "BUG"),
            "model_used": self.model_name,
            "mock_mode": self.use_mock_labeler,
            "platforms": list(set(i.platform for i in enriched_items)),
            "label_distribution": self._compute_label_distribution(enriched_items)
        }
        
        with open(f"{staging_dir}/manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
            
        # Create summary report
        report = self._generate_report(enriched_items, manifest)
        with open(f"{staging_dir}/reports/summary.md", 'w') as f:
            f.write(report)
            
        # Create ZIP
        if output_path.endswith('.zip'):
            output_path = output_path[:-4]
            
        shutil.make_archive(output_path, 'zip', staging_dir)
        final_path = f"{output_path}.zip"
        
        # Cleanup staging
        shutil.rmtree(staging_dir)
        
        logger.info(f"   📦 Package created: {final_path}")
        logger.info(f"   📊 Contains {len(enriched_items)} labeled items")
        
        return final_path
        
    def _compute_label_distribution(self, items: List[EnrichedItem]) -> Dict[str, int]:
        """Compute distribution of predicted labels."""
        dist = {}
        for item in items:
            for label in item.predicted_labels:
                dist[label] = dist.get(label, 0) + 1
        return dict(sorted(dist.items(), key=lambda x: -x[1]))
        
    def _generate_report(self, items: List[EnrichedItem], manifest: Dict) -> str:
        """Generate a markdown summary report."""
        report = f"""# Vulnerability Update Package Report

## Overview
- **Generated:** {manifest['created_at']}
- **Total Items:** {manifest['item_count']}
- **PSIRTs:** {manifest['psirt_count']}
- **Bugs:** {manifest['bug_count']}
- **Model:** {manifest['model_used']}

## Platform Distribution
"""
        
        platform_dist = {}
        for item in items:
            platform_dist[item.platform] = platform_dist.get(item.platform, 0) + 1
            
        for platform, count in sorted(platform_dist.items(), key=lambda x: -x[1]):
            report += f"- **{platform}:** {count} items\n"
            
        report += "\n## Label Distribution (Top 20)\n"
        label_dist = manifest['label_distribution']
        for label, count in list(label_dist.items())[:20]:
            report += f"- `{label}`: {count}\n"
            
        report += "\n## Sample Items\n"
        for item in items[:5]:
            report += f"""
### {item.advisoryId}
- **Type:** {item.type}
- **Platform:** {item.platform}
- **Severity:** {item.severity or 'N/A'}
- **Labels:** {', '.join(item.predicted_labels)}
- **Confidence:** {item.confidence:.2%}

> {item.summary[:200]}...
"""
            
        return report
        
    def run(self, 
            fetch: bool = False,
            days: int = 7,
            input_file: Optional[str] = None,
            output: str = "vuln_update.zip",
            bug_keywords: Optional[List[str]] = None) -> str:
        """
        Run the complete pipeline.
        
        Args:
            fetch: If True, fetch fresh data from APIs
            days: Days to look back when fetching
            input_file: Path to input JSON file (if not fetching)
            output: Output ZIP file path
            bug_keywords: Keywords for bug search
            
        Returns:
            Path to created package
        """
        logger.info("🚀 INTEGRATED VULNERABILITY UPDATE PACKAGER")
        logger.info("=" * 60)
        
        # Phase 1: Get data
        if fetch:
            items = self.fetch_data(days=days, bug_keywords=bug_keywords)
        elif input_file:
            items = self.load_from_file(input_file)
        else:
            raise ValueError("Must specify --fetch or --input")
            
        if not items:
            logger.error("❌ No data to process!")
            return None
            
        # Phase 2: Label
        enriched = self.label_items(items)
        
        if not enriched:
            logger.error("❌ No items were labeled successfully!")
            return None
            
        # Phase 3: Package
        package_path = self.create_package(enriched, output)
        
        logger.info("=" * 60)
        logger.info("✅ PIPELINE COMPLETE")
        logger.info(f"   Output: {package_path}")
        logger.info("=" * 60)
        
        return package_path


def main():
    parser = argparse.ArgumentParser(
        description="Integrated Vulnerability Update Packager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch fresh data and create package
  python offline_update_packager_v2.py --fetch --days 7 -o update.zip
  
  # Use existing data file
  python offline_update_packager_v2.py --input vuln_data.json -o update.zip
  
  # Test mode (no API, no GPU)
  python offline_update_packager_v2.py --mock -o test.zip
  
  # Custom bug keywords
  python offline_update_packager_v2.py --fetch --keywords "memory leak" "crash" -o update.zip
        """
    )
    
    # Data source options
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--fetch', action='store_true',
                              help="Fetch fresh data from Cisco APIs")
    source_group.add_argument('--input', '-i', type=str,
                              help="Path to input JSON file")
    source_group.add_argument('--mock', action='store_true',
                              help="Use mock data for testing")
    
    # Fetch options
    parser.add_argument('--days', type=int, default=7,
                        help="Days to look back when fetching (default: 7)")
    parser.add_argument('--keywords', nargs='+',
                        default=['security', 'vulnerability'],
                        help="Bug search keywords")
    
    # Model options
    parser.add_argument('--model', type=str, default='foundation-sec-8b',
                        help="Labeling model name")
    parser.add_argument('--mock-labeler', action='store_true',
                        help="Use mock labeler (no GPU required)")
    
    # Output options
    parser.add_argument('--output', '-o', type=str, default='vuln_update.zip',
                        help="Output ZIP file path")
    
    # Environment
    parser.add_argument('--env', type=str, default='.env',
                        help="Path to .env file")
    
    args = parser.parse_args()
    
    # Load environment
    if args.env and os.path.exists(args.env):
        from dotenv import load_dotenv
        load_dotenv(args.env)
    
    # Determine modes
    use_mock_fetcher = args.mock
    use_mock_labeler = args.mock or args.mock_labeler
    
    try:
        packager = IntegratedPackager(
            use_mock_fetcher=use_mock_fetcher,
            use_mock_labeler=use_mock_labeler,
            model_name=args.model
        )
        
        result = packager.run(
            fetch=args.fetch or args.mock,
            days=args.days,
            input_file=args.input,
            output=args.output,
            bug_keywords=args.keywords
        )
        
        if result:
            print(f"\n✅ Success! Package created: {result}")
        else:
            print("\n❌ Pipeline failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
