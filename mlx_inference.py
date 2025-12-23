#!/usr/bin/env python3
"""
MLX-based inference pipeline with LoRA adapter support for Foundation-Sec-8B.

This module provides Chain-of-Thought (CoT) reasoning capabilities using
a fine-tuned LoRA adapter trained on security advisory labeling.

Supports two modes:
- Full precision (32GB+ RAM): Uses base model + LoRA adapter (~71% accuracy)
- Low-RAM mode (16GB): Uses 4-bit quantized model (~65% accuracy)

Usage:
    from mlx_inference import MLXPSIRTLabeler

    labeler = MLXPSIRTLabeler()  # Auto-detects mode from config
    result = labeler.predict_labels("SSH vulnerability...", "IOS-XE")
    print(result['reasoning'])
    print(result['predicted_labels'])
"""

import json
import os
import re
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any

import mlx.core as mx
from mlx_lm import load, generate
from sentence_transformers import SentenceTransformer
import faiss
import pandas as pd

# Get project root (where mlx_inference.py lives)
PROJECT_ROOT = Path(__file__).parent

# Adapter path - matches registry.yaml and transformers_inference.py pattern
MLX_ADAPTER_PATH = str(PROJECT_ROOT / "models/adapters/mlx_v1")

# Low-RAM mode paths (absolute, based on project root)
LOWRAM_CONFIG_PATH = PROJECT_ROOT / "models/lowram_config.json"
QUANTIZED_MODEL_PATH = PROJECT_ROOT / "models/foundation-sec-8b-4bit"


def detect_lowram_mode() -> bool:
    """
    Detect if low-RAM mode should be used.

    Checks (in order):
    1. LOWRAM_MODE environment variable
    2. Existence of lowram_config.json
    3. Existence of quantized model directory
    """
    # Check env var first (explicit override)
    if os.getenv("LOWRAM_MODE", "").lower() in ("true", "1", "yes"):
        return True

    # Check for config file (created by setup_mac_lowram.sh)
    if LOWRAM_CONFIG_PATH.exists():
        return True

    # Check if quantized model exists
    if QUANTIZED_MODEL_PATH.exists():
        return True

    return False

# Import keyword-based label filtering
import sys
# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from taxonomies.Label_keywords import (
    filter_unsupported_labels,
    filter_labels_hybrid,
    calculate_label_confidence,
    get_label_evidence,
    validate_with_component_map
)


def filter_overpredictions(predicted_labels: List[str], summary: str) -> List[str]:
    """
    Filter known false positive patterns based on empirical analysis.

    Patterns identified from evaluation (achieving 71% exact match):
    1. SYS_Licensing_Smart: Triggered by boot/upgrade, privilege, hardware keywords
    2. L2_LACP: Over-predicted for CoPP/QoS issues
    3. L2_Switchport_Trunk: Over-predicted when 'trunk' appears in error messages
    """
    filtered = predicted_labels.copy()
    summary_lower = summary.lower()

    # SYS_Licensing_Smart over-prediction filter
    if 'SYS_Licensing_Smart' in filtered:
        boot_indicators = ['configure replace', 'config replace', 'reimage', 'partition', 'ssd',
                          'rommon', 'install mode', 'bundle mode']
        mgmt_indicators = ['tcl', 'privilege', 'escalation', 'rbac',
                          'role-based', 'interpreter', 'tool command']
        hw_indicators = ['fan', 'sensor', 'temperature', 'power supply',
                        'hotswap', 'inlet']

        has_false_indicator = any(ind in summary_lower for ind in
                                  boot_indicators + mgmt_indicators + hw_indicators)

        if has_false_indicator:
            licensing_keywords = ['license', 'smart account', 'cssm', 'cslu',
                                 'slr', 'registration', 'entitlement', 'smart licensing']
            has_licensing = any(kw in summary_lower for kw in licensing_keywords)

            if not has_licensing:
                filtered.remove('SYS_Licensing_Smart')

    # L2_LACP over-prediction filter: Remove when CoPP/QoS context with no LACP keywords
    if 'L2_LACP' in filtered:
        copp_qos_context = 'copp' in summary_lower or 'control plane' in summary_lower
        has_lacp_keywords = any(kw in summary_lower for kw in ['lacp', 'port-channel', 'lag', 'aggregat'])
        if copp_qos_context and not has_lacp_keywords:
            filtered.remove('L2_LACP')

    # L2_Switchport_Trunk over-prediction filter:
    # Remove when 'trunk' only appears in error message context (e.g., "before switching to mode trunk")
    # and the actual issue is about access port or port-security
    if 'L2_Switchport_Trunk' in filtered:
        has_portsecurity = 'SEC_PortSecurity' in filtered or 'port-security' in summary_lower
        has_access_mode = 'L2_Switchport_Access' in filtered or 'mode access' in summary_lower
        # Only remove if trunk appears in "switching to mode trunk" context (error message)
        trunk_in_error_context = 'switching to mode trunk' in summary_lower or 'before switching to' in summary_lower
        if has_portsecurity and has_access_mode and trunk_in_error_context:
            filtered.remove('L2_Switchport_Trunk')

    return filtered


class MLXPSIRTLabeler:
    """
    PSIRT labeler using MLX with optional LoRA adapter for CoT reasoning.

    Supports two modes:
    - Full precision (32GB+ RAM): Base model + LoRA adapter (~71% accuracy)
    - Low-RAM mode (16GB): 4-bit quantized model (~65% accuracy)
    """

    def __init__(
        self,
        model_id: str = "fdtn-ai/Foundation-Sec-8B",
        adapter_path: Optional[str] = MLX_ADAPTER_PATH,
        use_cot: bool = True,
        force_lowram: Optional[bool] = None
    ):
        """
        Initialize the MLX PSIRT Labeler.

        Args:
            model_id: HuggingFace model ID or local path
            adapter_path: Path to LoRA adapter (e.g., "adapters/pilot_cot_v1")
            use_cot: Whether to use Chain-of-Thought prompting
            force_lowram: Override auto-detection (True=use quantized, False=use full)
        """
        print("🚀 Initializing MLX PSIRT Labeler...")

        # Detect low-RAM mode
        self.lowram_mode = force_lowram if force_lowram is not None else detect_lowram_mode()

        if self.lowram_mode:
            # Low-RAM mode: use quantized model, no adapter
            print("📉 Low-RAM mode detected (16GB Mac)")
            print(f"   Using 4-bit quantized model for reduced memory usage")

            if not QUANTIZED_MODEL_PATH.exists():
                raise FileNotFoundError(
                    f"Quantized model not found at {QUANTIZED_MODEL_PATH}. "
                    f"Run ./setup_mac_lowram.sh to create it."
                )

            self.model_id = str(QUANTIZED_MODEL_PATH)
            self.adapter_path = None  # Quantized models don't use adapters
            self.use_cot = use_cot

            print(f"\n📥 Loading quantized model: {QUANTIZED_MODEL_PATH}")
            self.model, self.tokenizer = load(str(QUANTIZED_MODEL_PATH))
            print("✅ Quantized model loaded (~65% accuracy, ~8GB RAM)")

        else:
            # Full precision mode: base model + adapter
            self.model_id = model_id
            self.adapter_path = adapter_path
            self.use_cot = use_cot

            print(f"\n📥 Loading model: {model_id}")
            if adapter_path:
                print(f"   🔧 With LoRA adapter: {adapter_path}")
                self.model, self.tokenizer = load(model_id, adapter_path=adapter_path)
            else:
                self.model, self.tokenizer = load(model_id)
            print("✅ Model loaded (~71% accuracy, ~32GB RAM)")

        # Load FAISS index and embedder for retrieval
        self._load_embedder_and_index()

        # Load taxonomies
        self._load_taxonomies()

    def _load_embedder_and_index(self):
        """Load sentence embedder and FAISS index for retrieval"""
        print("\n📚 Loading sentence embedder...")
        with open('models/embedder_info.json', 'r') as f:
            embedder_info = json.load(f)
        self.embedder = SentenceTransformer(embedder_info['model_name'])
        print("✅ Embedder loaded")

        print("\n🔍 Loading FAISS index...")
        self.index = faiss.read_index('models/faiss_index.bin')
        # Use symlink that points to current versioned file (v2_20251212, 7065 vectors)
        self.labeled_examples = pd.read_parquet('models/labeled_examples.parquet')
        if self.index.ntotal != len(self.labeled_examples):
            print(f"⚠️  WARNING: FAISS index ({self.index.ntotal}) != parquet ({len(self.labeled_examples)})")
        print(f"✅ Index loaded ({self.index.ntotal} examples)")

    def _load_taxonomies(self):
        """Load platform-specific label taxonomies WITH DESCRIPTIONS"""
        print("\n📖 Loading feature taxonomies...")
        self.taxonomy = {}           # label list for validation
        self.taxonomy_defs = {}      # label -> description for prompts

        taxonomy_files = {
            'IOS-XE': 'taxonomies/features.yml',
            'IOS-XR': 'taxonomies/features_iosxr.yml',
            'ASA': 'taxonomies/features_asa.yml',
            'FTD': 'taxonomies/features_asa.yml',
            'NX-OS': 'taxonomies/features_nxos.yml',
        }

        for platform, filepath in taxonomy_files.items():
            try:
                with open(filepath, 'r') as f:
                    features = yaml.safe_load(f)
                # Extract BOTH labels AND descriptions
                self.taxonomy[platform] = [f['label'] for f in features]
                self.taxonomy_defs[platform] = {
                    f['label']: f.get('description', f"Label for {f['label']}")
                    for f in features
                }
            except FileNotFoundError:
                print(f"⚠️  Warning: {filepath} not found, skipping {platform}")
                self.taxonomy[platform] = []
                self.taxonomy_defs[platform] = {}

        # Load anti-definition rules (what labels should NOT be used for)
        self._load_anti_definitions()

        total_labels = sum(len(labels) for labels in self.taxonomy.values())
        print(f"✅ Taxonomies loaded ({len(self.taxonomy)} platforms, {total_labels} total labels)")
        print(f"   📚 Descriptions loaded for semantic guidance")

    def _load_anti_definitions(self):
        """Load anti-definition rules from taxonomy_anti_definitions.yml"""
        self.anti_defs = {}
        anti_def_path = Path('transfer_package/taxonomy_anti_definitions.yml')

        if anti_def_path.exists():
            try:
                with open(anti_def_path, 'r') as f:
                    self.anti_defs = yaml.safe_load(f) or {}
                print(f"   ⚠️  Anti-definitions loaded ({len(self.anti_defs)} labels with exclusion rules)")
            except Exception as e:
                print(f"   ⚠️  Warning: Could not load anti-definitions: {e}")
        else:
            print(f"   ℹ️  No anti-definitions file found at {anti_def_path}")

    def _suggest_labels_from_keywords(self, summary: str, platform: str, max_labels: int = 3) -> List[str]:
        """
        Fallback: Suggest labels based on keyword evidence when CoT parsing fails.

        This is a safety net for edge cases where the model generates reasoning
        but fails to output labels in the expected format.

        Args:
            summary: Advisory summary text
            platform: Target platform
            max_labels: Maximum labels to suggest

        Returns:
            List of suggested labels based on keyword matches
        """
        from taxonomies.Label_keywords import LABEL_KEYWORDS

        summary_lower = summary.lower()
        valid_labels = set(self.taxonomy.get(platform, []))

        # Score each label by number of keyword matches
        label_scores = {}
        for label, keywords in LABEL_KEYWORDS.items():
            if label not in valid_labels:
                continue

            matches = sum(1 for kw in keywords if kw.lower() in summary_lower)
            if matches > 0:
                label_scores[label] = matches

        # Sort by score and return top N
        sorted_labels = sorted(label_scores.items(), key=lambda x: -x[1])
        return [label for label, score in sorted_labels[:max_labels]]

    def _build_taxonomy_context(self, platform: str, max_desc_len: int = 80) -> str:
        """Build compact definition list for prompt with semantic guidance.

        Args:
            platform: Target platform
            max_desc_len: Max chars per description (default 80 to fit context window)
        """
        defs = self.taxonomy_defs.get(platform, {})
        lines = []

        for label in self.taxonomy.get(platform, []):
            description = defs.get(label, f"Label for {label}")

            # Extract the key part - first sentence or up to first period
            first_sentence = description.split('.')[0] if '.' in description else description

            # Find "Do NOT use" guidance if present
            do_not_idx = description.find("Do NOT use")
            do_not_guidance = ""
            if do_not_idx > 0:
                # Extract short "Do NOT use" guidance
                do_not_part = description[do_not_idx:do_not_idx+60]
                if '.' in do_not_part:
                    do_not_guidance = " " + do_not_part.split('.')[0] + "."

            # Truncate first sentence if too long
            if len(first_sentence) > max_desc_len:
                first_sentence = first_sentence[:max_desc_len] + "..."

            # Combine
            desc_compact = first_sentence + do_not_guidance

            # Add anti-definition from separate file if available (higher priority)
            anti_info = self.anti_defs.get(label, {})
            if anti_info and 'exclusions' in anti_info:
                # Just use the first exclusion, shortened
                exclusion = anti_info['exclusions'][0][:80] if anti_info['exclusions'] else ""
                if exclusion:
                    lines.append(f"- {label}: {desc_compact} EXCLUSION: {exclusion}")
                else:
                    lines.append(f"- {label}: {desc_compact}")
            else:
                lines.append(f"- {label}: {desc_compact}")

        return '\n'.join(lines)

    def exact_match_lookup(self, advisory_id: str, platform: Optional[str] = None) -> Optional[Dict]:
        """Check for exact match in training data"""
        if not advisory_id:
            return None

        id_column = 'advisoryId' if 'advisoryId' in self.labeled_examples.columns else 'id'
        matches = self.labeled_examples[self.labeled_examples[id_column] == advisory_id]

        if platform:
            matches = matches[matches['platform'] == platform]

        if len(matches) == 0:
            return None

        row = matches.iloc[0]
        labels = row['labels_list']
        if hasattr(labels, 'tolist'):
            labels = labels.tolist()

        return {
            'labels': labels,
            'summary': row['summary'],
            'platform': row['platform'],
            'source': row.get('source', 'training_data'),
            'reasoning': row.get('reasoning', f"Exact match from training data")
        }

    def retrieve_similar_examples(self, query_text: str, platform: Optional[str] = None, k: int = 5):
        """Retrieve similar examples from FAISS index"""
        query_embedding = self.embedder.encode([query_text])
        distances, indices = self.index.search(query_embedding.astype('float32'), k=min(k*3, self.index.ntotal))

        similarities = 1 / (1 + distances[0])

        examples = []
        similarity_scores = []

        for idx, similarity in zip(indices[0], similarities):
            row = self.labeled_examples.iloc[idx]
            if platform and row['platform'] != platform:
                continue

            labels = row['labels_list']
            if hasattr(labels, 'tolist'):
                labels = labels.tolist()

            examples.append({
                'summary': row['summary'],
                'platform': row['platform'],
                'labels': labels,
                'reasoning': row.get('reasoning', None)
            })
            similarity_scores.append(float(similarity))

            if len(examples) >= k:
                break

        return examples, similarity_scores

    def build_cot_prompt(self, psirt_summary: str, platform: str) -> str:
        """Build Chain-of-Thought prompt for inference WITH taxonomy definitions"""
        taxonomy_context = self._build_taxonomy_context(platform)

        prompt = f"""### Instruction:
You are a Cisco security expert. Analyze this advisory and assign taxonomy labels.

TAXONOMY DEFINITIONS (use these to select the correct label):
{taxonomy_context}

CRITICAL RULES:
1. Pay attention to "Do NOT use" constraints in definitions
2. Select labels that match the ROOT CAUSE, not symptoms
3. Maximum 3 labels per advisory
4. If unsure between two similar labels, read their descriptions carefully

OUTPUT FORMAT (you MUST follow this exactly):
Reasoning: <1-2 sentences explaining which feature is affected>
Labels: ["LABEL_1", "LABEL_2"]

### Input:
Platform: {platform}
Summary: {psirt_summary}

### Response:
Reasoning:"""
        return prompt

    def build_legacy_prompt(self, psirt_summary: str, platform: str, examples: List[Dict]) -> str:
        """Build legacy few-shot prompt (for non-CoT mode) WITH taxonomy definitions"""
        taxonomy_context = self._build_taxonomy_context(platform)

        prompt = f"""You are a Cisco security advisory labeling expert. Your task is to assign feature labels from a closed taxonomy to PSIRTs based on their summary text.

Platform: {platform}

TAXONOMY DEFINITIONS (use these to select the correct label):
{taxonomy_context}

CRITICAL: Pay attention to "Do NOT use" constraints in definitions.

Here are some examples of correctly labeled PSIRTs:

"""
        for i, ex in enumerate(examples, 1):
            prompt += f"""Example {i}:
Summary: {ex['summary']}
Platform: {ex['platform']}
Labels: {json.dumps(ex['labels'])}

"""

        prompt += f"""Now label this new PSIRT.

CRITICAL: Return a valid JSON object with two fields:
1. "reasoning": A single sentence explaining why the labels match the summary.
2. "labels": A list of up to 3 valid labels from the taxonomy above.

Summary: {psirt_summary}
Platform: {platform}

JSON:"""

        return prompt

    def _parse_cot_response(self, response: str) -> Dict[str, Any]:
        """Parse Chain-of-Thought response format with multiple fallbacks"""
        reasoning = ""
        labels = []

        # Extract reasoning (handle various formats)
        reasoning_match = re.search(r'Reasoning:\s*\n?(.*?)(?=Labels?:|Label:|$)', response, re.DOTALL | re.IGNORECASE)
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()

        # Try multiple label extraction patterns
        # Pattern 1: "Labels: ['label1', 'label2']" or "Label: ['label1']"
        labels_match = re.search(r'Labels?:\s*\n?\[([^\]]*)\]', response, re.DOTALL | re.IGNORECASE)
        if labels_match:
            try:
                labels_str = '[' + labels_match.group(1) + ']'
                labels = json.loads(labels_str)
            except json.JSONDecodeError:
                # Fallback: extract quoted strings
                labels = re.findall(r"'([^']+)'", labels_match.group(1))
                if not labels:
                    labels = re.findall(r'"([^"]+)"', labels_match.group(1))

        # Pattern 2: JSON format {"labels": [...]}
        if not labels:
            json_match = re.search(r'\{[^{}]*"labels"\s*:\s*\[([^\]]*)\][^{}]*\}', response, re.DOTALL)
            if json_match:
                try:
                    labels = json.loads('[' + json_match.group(1) + ']')
                except:
                    labels = re.findall(r'"([^"]+)"', json_match.group(1))

        # Pattern 3: Look for label-like patterns (UPPER_CASE with underscores)
        if not labels:
            # Find all potential labels in the response
            potential = re.findall(r'\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b', response)
            # Filter to valid taxonomy labels (will be done in predict_labels)
            labels = list(dict.fromkeys(potential))[:3]  # Dedupe, max 3

        return {'reasoning': reasoning, 'labels': labels}

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response format"""
        reasoning = ""
        labels = []

        # Try to find JSON object
        json_match = re.search(r'\{[^{}]*"reasoning"[^{}]*"labels"[^{}]*\}', response, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{[^{}]*"labels"[^{}]*\}', response, re.DOTALL)

        if json_match:
            try:
                result = json.loads(json_match.group(0))
                labels = result.get('labels', [])
                reasoning = result.get('reasoning', '')
            except json.JSONDecodeError:
                pass

        # Fallback: extract labels array
        if not labels:
            labels_match = re.search(r'"labels"\s*:\s*\[([^\]]*)', response)
            if labels_match:
                labels = re.findall(r'"([^"]+)"', labels_match.group(1))[:3]

        return {'reasoning': reasoning, 'labels': labels}

    def predict_labels(
        self,
        psirt_summary: str,
        platform: str,
        advisory_id: Optional[str] = None,
        k: int = 5,
        max_tokens: int = 600,
        mode: str = 'auto'
    ) -> Dict[str, Any]:
        """
        Predict labels for a PSIRT/bug summary.

        Args:
            psirt_summary: The security advisory or bug summary text
            platform: Target platform (IOS-XE, IOS-XR, ASA, FTD, NX-OS)
            advisory_id: Optional advisory ID for exact match lookup
            k: Number of similar examples for few-shot mode
            max_tokens: Maximum tokens to generate
            mode: Inference mode:
                  - 'cot': Chain-of-Thought with taxonomy definitions (best for PSIRTs)
                  - 'fewshot': Few-shot with FAISS examples (best for bugs, 71% accuracy)
                  - 'auto': Auto-detect based on text length (>300 chars = cot)

        Returns:
            dict with keys: predicted_labels, reasoning, confidence, mode, etc.
        """
        # Try exact match first
        if advisory_id:
            exact_match = self.exact_match_lookup(advisory_id, platform=platform)
            if exact_match:
                print(f"✅ EXACT MATCH: Found {advisory_id} in training data")
                return {
                    'predicted_labels': exact_match['labels'],
                    'reasoning': exact_match.get('reasoning', 'Exact match from training data'),
                    'confidence': 1.0,
                    'mode': 'exact_match',
                    'source': 'exact_match',
                    'raw_response': f"Exact match from {exact_match['source']}",
                    'similarity_scores': [1.0]
                }

        # Auto-detect mode based on text length
        # PSIRTs are typically verbose (500+ chars), bugs are terse (20-200 chars)
        if mode == 'auto':
            mode = 'cot' if len(psirt_summary) > 300 else 'fewshot'
            print(f"📊 Auto-detected mode: {mode} (text length: {len(psirt_summary)} chars)")

        # Retrieve similar examples (used for fewshot mode and confidence)
        examples, similarity_scores = self.retrieve_similar_examples(psirt_summary, platform=platform, k=k)
        faiss_confidence = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0

        # Route to appropriate prediction method
        if mode == 'cot':
            return self._predict_cot_mode(psirt_summary, platform, examples, similarity_scores,
                                          faiss_confidence, max_tokens)
        else:  # fewshot
            return self._predict_fewshot_mode(psirt_summary, platform, examples, similarity_scores,
                                              faiss_confidence, max_tokens)

    def _predict_cot_mode(
        self,
        psirt_summary: str,
        platform: str,
        examples: List[Dict],
        similarity_scores: List[float],
        faiss_confidence: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """
        CoT mode: Best for PSIRTs (verbose text with explicit keywords).
        Uses Chain-of-Thought reasoning + keyword filtering to remove hallucinations.
        """
        # Build CoT prompt with taxonomy definitions
        prompt = self.build_cot_prompt(psirt_summary, platform)

        # Generate response
        print(f"🔍 Generating with CoT adapter...")
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            verbose=False
        )

        # Parse CoT response
        parsed = self._parse_cot_response(response)

        # Validate labels against taxonomy
        valid_labels = self.taxonomy.get(platform, [])
        validated_labels = [l for l in parsed['labels'] if l in valid_labels]

        # Apply inference-time filter for known over-predictions
        filtered_labels = filter_overpredictions(validated_labels, psirt_summary)

        # Apply keyword filtering to remove hallucinated labels (PSIRTs are verbose)
        final_labels = filter_labels_hybrid(filtered_labels, psirt_summary, source_type='psirt')

        # Fallback: if CoT parsing failed but we have keyword evidence, suggest labels
        if not final_labels:
            keyword_suggested = self._suggest_labels_from_keywords(psirt_summary, platform)
            if keyword_suggested:
                print(f"⚠️  CoT returned empty labels, using keyword fallback: {keyword_suggested}")
                final_labels = keyword_suggested

        # Calculate per-label confidence based on keyword evidence
        label_confidence = {
            label: calculate_label_confidence(label, psirt_summary)
            for label in final_labels
        }

        # Get detailed evidence for debugging
        label_evidence = {
            label: get_label_evidence(label, psirt_summary)
            for label in final_labels
        }

        # Confidence based on keyword evidence (more meaningful for PSIRTs)
        overall_confidence = max(label_confidence.values()) if label_confidence else faiss_confidence

        return {
            'predicted_labels': final_labels,
            'reasoning': parsed['reasoning'],
            'confidence': overall_confidence,
            'mode': 'cot',
            'label_confidence': label_confidence,
            'retrieval_similarity': faiss_confidence,
            'source': 'cot_adapter',
            'raw_response': response,
            'retrieved_examples': examples,
            'similarity_scores': similarity_scores,
            'label_evidence': label_evidence
        }

    def _predict_fewshot_mode(
        self,
        psirt_summary: str,
        platform: str,
        examples: List[Dict],
        similarity_scores: List[float],
        faiss_confidence: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """
        Few-shot mode: Best for bugs (terse text, Cisco jargon).
        Uses FAISS-retrieved examples + label extraction (71% accuracy on bug test set).
        """
        # Build few-shot prompt with examples (matching scripts/evaluate_v2_adapter.py approach)
        valid_labels = self.taxonomy.get(platform, [])

        prompt = f"""You are a Cisco security advisory labeling expert. Your task is to assign feature labels from a closed taxonomy to PSIRTs based on their summary text.

Platform: {platform}

CRITICAL: You must ONLY use labels from this exact list. Do not invent new labels.
Available labels for {platform}:
{', '.join(sorted(valid_labels))}

Here are some examples of correctly labeled PSIRTs:

"""
        for i, ex in enumerate(examples, 1):
            prompt += f"""Example {i}:
Summary: {ex['summary']}
Labels: {json.dumps(ex['labels'])}

"""

        prompt += f"""Now label this new PSIRT.

Summary: {psirt_summary}
Platform: {platform}

Think step by step about which features are affected, then provide your answer.
Label:"""

        # Generate response
        print(f"🔍 Generating with few-shot mode...")
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            verbose=False
        )

        # Extract labels using the same logic as scripts/evaluate_v2_adapter.py
        labels = self._extract_labels_from_text(response)

        # Validate against taxonomy
        validated_labels = [l for l in labels if l in valid_labels]

        # Apply inference-time filter for known over-predictions (71% accuracy boost)
        final_labels = filter_overpredictions(validated_labels, psirt_summary)

        # Ensure at least one label
        if not final_labels and validated_labels:
            final_labels = [validated_labels[0]]

        return {
            'predicted_labels': final_labels,
            'reasoning': f"Few-shot inference from {len(examples)} similar examples",
            'confidence': faiss_confidence,  # FAISS similarity is the confidence metric
            'mode': 'fewshot',
            'label_confidence': {label: faiss_confidence for label in final_labels},
            'retrieval_similarity': faiss_confidence,
            'source': 'few_shot',
            'raw_response': response,
            'retrieved_examples': examples,
            'similarity_scores': similarity_scores
        }

    def _extract_labels_from_text(self, text: str) -> List[str]:
        """
        Extract labels from model output text.
        Matches the logic from scripts/evaluate_v2_adapter.py for consistency.
        """
        labels = []

        # Format 0: Raw list format ['X', 'Y'] at start (common from our adapter)
        match = re.search(r"^\s*\[([^\]]+)\]", text.strip())
        if match:
            labels = re.findall(r"'([^']+)'", match.group(1))
            if not labels:
                labels = re.findall(r'"([^"]+)"', match.group(1))
            if labels:
                return labels

        # Format 1: Label: ['X', 'Y'] or Labels: ['X', 'Y']
        match = re.search(r"Label[s]?:\s*\[([^\]]+)\]", text, re.IGNORECASE)
        if match:
            labels = re.findall(r"'([^']+)'", match.group(1))
            if not labels:
                labels = re.findall(r'"([^"]+)"', match.group(1))
            if labels:
                return labels

        # Format 2: {"labels": ["X", "Y"]}
        match = re.search(r'"labels"\s*:\s*\[([^\]]+)\]', text)
        if match:
            labels = re.findall(r'"([^"]+)"', match.group(1))
            if labels:
                return labels

        # Format 3: Label-like patterns (UPPERCASE_WITH_UNDERSCORES)
        potential = re.findall(r'\b([A-Z][A-Z0-9_]+(?:_[A-Z0-9]+)+)\b', text)
        labels = [l for l in potential if len(l) > 5 and '_' in l][:3]

        return labels


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='MLX PSIRT Labeler')
    parser.add_argument('--adapter', default=MLX_ADAPTER_PATH, help='LoRA adapter path')
    parser.add_argument('--no-adapter', action='store_true', help='Run without adapter')
    parser.add_argument('--summary', default='SSH connection causes high CPU and device crash', help='PSIRT summary')
    parser.add_argument('--platform', default='IOS-XE', help='Platform')
    args = parser.parse_args()

    adapter = None if args.no_adapter else args.adapter
    labeler = MLXPSIRTLabeler(adapter_path=adapter)

    print("\n" + "="*60)
    print("Testing prediction...")
    print("="*60)
    print(f"Summary: {args.summary}")
    print(f"Platform: {args.platform}")

    result = labeler.predict_labels(args.summary, args.platform)

    print(f"\n✅ Predicted Labels: {result['predicted_labels']}")
    print(f"📝 Reasoning: {result['reasoning']}")
    print(f"📊 Confidence: {result['confidence']:.3f}")
    print(f"🔧 Source: {result['source']}")
