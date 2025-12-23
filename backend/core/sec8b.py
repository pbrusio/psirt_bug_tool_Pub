"""
SEC-8B wrapper for API
Wraps the existing PSIRTVerificationPipeline for FastAPI usage

Backend Options (set via PSIRT_BACKEND env var):
- auto: Auto-detect platform (default) - MLX on Mac, Transformers+PEFT on Linux
- mlx: MLX-LM with LoRA adapter (71% accuracy, Mac only)
- transformers_local: HuggingFace Transformers + PEFT (57% accuracy, Linux/CUDA/CPU)
- transformers: HuggingFace Transformers with FewShot (legacy, no adapter)
"""
import sys
from pathlib import Path

# Add parent directory to path to import existing modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from predict_and_verify import PSIRTVerificationPipeline
import uuid
from datetime import datetime

# Confidence thresholds (from architecture doc Section 6)
FAISS_SIMILARITY_THRESHOLD = 0.70  # Below this, mark as needs_review


class SEC8BAnalyzer:
    """Wrapper for SEC-8B analysis pipeline"""

    def __init__(self):
        import os
        # Default to 'auto' for platform auto-detection
        # - Mac: Uses MLX backend with LoRA adapter (~71% accuracy)
        # - Linux/CUDA: Uses Transformers + PEFT adapter (~57% accuracy)
        # - Linux/CPU: Uses Transformers + PEFT adapter (~57% accuracy)
        backend = os.getenv('PSIRT_BACKEND', 'auto')
        model = os.getenv('SEC8B_MODEL', 'foundation-sec-8b')
        self.pipeline = PSIRTVerificationPipeline(backend=backend, model_name=model)

    def analyze_psirt(self, summary: str, platform: str, advisory_id: str = None) -> dict:
        """
        Analyze PSIRT with SEC-8B

        Args:
            summary: PSIRT summary text
            platform: Platform (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
            advisory_id: Optional advisory ID for exact matching

        Returns:
            {
                'analysis_id': str,
                'psirt_summary': str,
                'platform': str,
                'advisory_id': str,
                'predicted_labels': List[str],
                'confidence': float,
                'config_regex': List[str],
                'show_commands': List[str],
                'timestamp': datetime
            }
        """
        # Run SEC-8B analysis (with exact match or few-shot)
        result = self.pipeline.process_psirt(summary, platform, advisory_id=advisory_id)

        # Extract data from result
        predicted_labels = result['predicted_labels']

        # Flatten config_checks to just patterns
        config_regex = [check['pattern'] for check in result['config_checks']]

        # Flatten show_commands to just commands
        show_commands = [cmd['command'] for cmd in result['show_commands']]

        # Generate unique analysis ID
        analysis_id = str(uuid.uuid4())

        # Extract confidence from result (FAISS similarity score)
        confidence = result.get('confidence', 0.0)

        # Apply FAISS threshold to determine needs_review and confidence_source
        if confidence < FAISS_SIMILARITY_THRESHOLD:
            needs_review = True
            confidence_source = 'heuristic'
        else:
            needs_review = False
            confidence_source = 'model'

        return {
            'analysis_id': analysis_id,
            'psirt_summary': summary,
            'platform': platform,
            'advisory_id': advisory_id,
            'predicted_labels': predicted_labels,
            'confidence': confidence,
            'config_regex': config_regex,
            'show_commands': show_commands,
            'needs_review': needs_review,
            'confidence_source': confidence_source,
            'timestamp': datetime.now()
        }


# Global singleton instance
_analyzer_instance = None

def get_analyzer():
    """Get or create SEC-8B analyzer singleton"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = SEC8BAnalyzer()
    return _analyzer_instance
