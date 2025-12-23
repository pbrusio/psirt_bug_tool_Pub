"""
Reasoning Engine for AI-powered vulnerability analysis.

This module provides the core logic for the AI Reasoning Layer, enabling:
- Explanation of why labels apply to PSIRTs
- Remediation guidance generation
- Natural language query processing
- Executive summary generation

The engine leverages the fine-tuned Foundation-Sec-8B model with taxonomy
knowledge to provide contextual understanding that batch processing cannot deliver.
"""

import json
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from enum import Enum
from datetime import datetime, timedelta

import yaml

from backend.db.utils import get_db_connection
from backend.core.sec8b import get_analyzer

logger = logging.getLogger(__name__)


# =============================================================================
# Intent Classification for /ask endpoint
# =============================================================================

class QueryIntent(Enum):
    """Supported query intents for /ask endpoint"""
    LIST_VULNERABILITIES = "list_vulnerabilities"
    LIST_DEVICES = "list_devices"
    DEVICE_VULNERABILITIES = "device_vulnerabilities"  # bugs/PSIRTs for specific device
    DEVICES_BY_RISK = "devices_by_risk"  # which devices have critical/high bugs
    PRIORITIZE = "prioritize"  # recommendations on what to focus on
    EXPLAIN_VULNERABILITY = "explain_vulnerability"
    EXPLAIN_LABEL = "explain_label"
    REMEDIATION = "remediation"
    COMPARE_VERSIONS = "compare_versions"
    SUMMARY = "summary"
    COUNT = "count"
    UNKNOWN = "unknown"


# Rule-based patterns for fast intent classification
INTENT_PATTERNS = {
    # Order matters - more specific patterns first
    QueryIntent.REMEDIATION: [
        r'\b(how|what).*(fix|remediat|mitigat|patch|workaround)',
        r'\b(fix|remediat|mitigat)\b',
        r'\bworkaround\b',
    ],
    QueryIntent.COUNT: [
        r'\bhow\s+many\b',
        r'\b(count|total|number)\s+(of)?\b',
    ],
    QueryIntent.SUMMARY: [
        r'\b(summar|overview|report|status)\b',
        r'\b(weekly|monthly|daily)\b.*\b(report|summary)',
        r'\bposture\b',
    ],
    # PRIORITIZE: "what should I focus on", "recommendations" - must come FIRST
    QueryIntent.PRIORITIZE: [
        r'\b(recommend|suggestion|prioriti|focus)\b',
        r'\b(where|what)\b.*\b(should|do)\b.*\b(i|we)\b.*\b(start|focus|look|prioriti)',
        r'\bwhat\s+(to|should)\b.*\b(fix|address|remediate)\s+first\b',
        r'\bmost\s+(important|urgent|critical)\b',
        r'\btop\s+priorit',
    ],
    # DEVICES_BY_RISK: "which devices have critical bugs"
    QueryIntent.DEVICES_BY_RISK: [
        r'\b(which|what|show)\b.*\bdevices?\b.*\b(have|with)\b.*\b(critical|high|severe)',
        r'\bdevices?\b.*\b(most|highest)\b.*\b(risk|vulnerable|exposed)',
        r'\b(critical|high)\b.*\b(bug|vuln|issue)s?\b.*\bdevices?\b',
        r'\bdevices?\b.*\bat\s+risk\b',
        r'\bworst\b.*\bdevices?\b',
        r'\briskiest\b.*\bdevices?\b',
    ],
    # DEVICE_VULNERABILITIES: bugs for a SPECIFIC device (e.g., "bugs for C9200L")
    QueryIntent.DEVICE_VULNERABILITIES: [
        r'\b(bug|vuln|psirt|cve|advisory|issue)s?\b.*(impact|affect|for|on)\b.*\b(device|switch|router|this|that|\w+-?\d+)',
        r'\b(which|what|list|show|tell)\b.*\b(bug|vuln|psirt|cve)s?\b.*(device|switch|router|this|that)',
        r'\b(device|switch|router)\b.*\b(susceptible|vulnerable)\b.*\bto\b',
        r'\bimpacting\b.*\b(device|this)',
        r'\bfor\s+(this\s+)?device\b',
    ],
    QueryIntent.LIST_DEVICES: [
        r'\b(which|what|list|show)\b.*\b(device|switch|router)s?\b(?!.*\b(bug|vuln|psirt|cve|critical|high))',
        r'\baffected\s+device',
    ],
    QueryIntent.EXPLAIN_LABEL: [
        r'\bwhat\s+(does|is)\s+[a-z]{2,}_',  # "what does SEC_CoPP mean"
        r'\bexplain\s+(what\s+)?[a-z]{2,}_',  # "explain SEC_CoPP"
        r'\b[a-z]{2,}_[a-z]+\b.*\bmean',  # "what does MGMT_SSH_HTTP mean"
    ],
    QueryIntent.EXPLAIN_VULNERABILITY: [
        r'\b(explain|why|what does)\b.*\b(vuln|cve|advisory|psirt|cisco-sa)',
        r'\bwhy\s+(is|does)\b.*\b(label|tag)',
    ],
    QueryIntent.LIST_VULNERABILITIES: [
        r'\b(which|what|list|show)\b.*\b(vuln|cve|bug|advisory|psirt)',
        r'\bvulnerabilit(y|ies)\b.*(affect|impact|for)',
        r'\bcritical\b.*\b(vuln|bug|issue)',
    ],
    QueryIntent.COMPARE_VERSIONS: [
        r'\b(compar|diff|between)\b.*\b(version|upgrade)',
        r'\bupgrad(e|ing)\b.*(from|to)\b',
        r'\bif\s+i\s+upgrade\b',
    ],
}


# =============================================================================
# Keyword Scoring Configuration
# =============================================================================

INTENT_KEYWORDS = {
    QueryIntent.PRIORITIZE: {
        'keywords': ['recommend', 'priorit', 'focus', 'should i', 'start with', 'important', 'urgent'],
        'weight': 3,
    },
    QueryIntent.DEVICES_BY_RISK: {
        'keywords': ['device', 'switch', 'router'],
        'requires_all': ['device', 'switch', 'router'],  # Must have device-related word
        'requires_any': ['critical', 'high', 'severe', 'risk', 'worst', 'dangerous'],  # And severity word
        'weight': 5,
    },
    QueryIntent.DEVICE_VULNERABILITIES: {
        'keywords': ['bug', 'vuln', 'psirt', 'cve', 'affect', 'impact', 'susceptible'],
        'requires_any': ['device', 'switch', 'router'],
        'has_device_pattern': True,  # Look for specific device names like C9200L
        'weight': 4,
    },
    QueryIntent.LIST_DEVICES: {
        'keywords': ['device', 'switch', 'router', 'list', 'show', 'inventory'],
        'excludes': ['bug', 'vuln', 'critical', 'high', 'affect'],  # Avoid overlap
        'weight': 2,
    },
    QueryIntent.LIST_VULNERABILITIES: {
        'keywords': ['bug', 'vuln', 'psirt', 'cve', 'advisory', 'critical', 'high'],
        'excludes': ['device', 'switch', 'router'],  # If device mentioned, not this intent
        'weight': 3,
    },
    QueryIntent.EXPLAIN_LABEL: {
        'keywords': ['what is', 'what does', 'explain', 'mean'],
        'has_label_pattern': True,  # Look for UPPER_CASE labels
        'weight': 4,
    },
    QueryIntent.EXPLAIN_VULNERABILITY: {
        'keywords': ['explain', 'why', 'what does'],
        'has_advisory_pattern': True,  # Look for cisco-sa-xxx
        'weight': 4,
    },
    QueryIntent.REMEDIATION: {
        'keywords': ['fix', 'remediat', 'mitigat', 'patch', 'workaround', 'how to'],
        'weight': 3,
    },
    QueryIntent.SUMMARY: {
        'keywords': ['summary', 'overview', 'report', 'status', 'posture'],
        'weight': 3,
    },
    QueryIntent.COUNT: {
        'keywords': ['how many', 'count', 'total', 'number of'],
        'weight': 3,
    },
    QueryIntent.COMPARE_VERSIONS: {
        'keywords': ['compare', 'diff', 'upgrade', 'between', 'version'],
        'weight': 3,
    },
}


def _quick_intent_override(question: str) -> Optional[QueryIntent]:
    """
    Fast-path overrides for obvious patterns.

    These catch common cases where keyword combinations clearly indicate intent,
    regardless of exact phrasing or grammar.
    """
    q = question.lower()

    # Device + severity words → DEVICES_BY_RISK (regardless of "has" vs "have")
    if 'device' in q and any(s in q for s in ['critical', 'high', 'severe', 'risk', 'worst']):
        return QueryIntent.DEVICES_BY_RISK

    # Recommendation/priority words → PRIORITIZE
    if any(w in q for w in ['recommend', 'prioriti', 'should i focus', 'where should i start']):
        return QueryIntent.PRIORITIZE

    # Specific device name + bugs/vulns → DEVICE_VULNERABILITIES
    device_pattern = re.search(r'\b([A-Za-z]+-?\d+[A-Za-z]*(?:-\d+)?)\b', q)
    if device_pattern and any(w in q for w in ['bug', 'vuln', 'affect', 'impact', 'psirt']):
        return QueryIntent.DEVICE_VULNERABILITIES

    return None


def _score_intent(question: str, intent: QueryIntent) -> float:
    """
    Score how well a question matches an intent using keyword analysis.

    Returns a score from 0 (no match) to higher values (better match).
    """
    q = question.lower()
    config = INTENT_KEYWORDS.get(intent, {})

    if not config:
        return 0.0

    score = 0.0

    # Check requires_all - must have at least one of these keywords
    requires_all = config.get('requires_all', [])
    if requires_all and not any(kw in q for kw in requires_all):
        return 0.0  # Disqualify - no device-related keyword

    # Check requires_any - must have at least one of these keywords
    requires_any = config.get('requires_any', [])
    if requires_any and not any(kw in q for kw in requires_any):
        return 0.0  # Disqualify if required keywords missing

    # Check exclusions
    excludes = config.get('excludes', [])
    if excludes and any(kw in q for kw in excludes):
        score -= 2  # Penalize but don't disqualify

    # Score keyword matches
    for kw in config.get('keywords', []):
        if kw in q:
            score += 1

    # Bonus for requires_any match
    if requires_any and any(kw in q for kw in requires_any):
        score += 2

    # Check for special patterns
    if config.get('has_device_pattern'):
        if re.search(r'\b([A-Za-z]+-?\d+[A-Za-z]*)\b', q):
            score += 2

    if config.get('has_label_pattern'):
        if re.search(r'\b[A-Z]{2,}_[A-Za-z]+', question):  # Original case
            score += 3

    if config.get('has_advisory_pattern'):
        if 'cisco-sa' in q:
            score += 3

    # Apply weight multiplier
    weight = config.get('weight', 1)
    score *= weight

    # Also check regex patterns for bonus
    patterns = INTENT_PATTERNS.get(intent, [])
    for pattern in patterns:
        if re.search(pattern, q):
            score += 5  # Significant bonus for regex match
            break

    return score


def classify_intent(question: str, use_llm_fallback: bool = False, llm_classifier=None) -> Tuple[QueryIntent, float, Optional[Dict]]:
    """
    Classify query intent using hybrid 3-tier approach:

    1. Quick override - instant, catches obvious patterns
    2. Keyword scoring - instant, scores all intents and picks best
    3. LLM fallback - ~1-2s, used when scoring is ambiguous

    Args:
        question: The user's question
        use_llm_fallback: Whether to use LLM for ambiguous cases
        llm_classifier: Callable that takes question and returns QueryIntent

    Returns:
        Tuple of (intent, confidence, extracted_entities)
    """
    question_lower = question.lower()

    # Tier 1: Quick override for obvious patterns
    override = _quick_intent_override(question)
    if override:
        entities = extract_entities(question, override)
        logger.debug(f"Intent override: {override.value} for '{question[:50]}'")
        return (override, 0.95, entities)

    # Tier 2: Keyword scoring - score ALL intents
    scores = {}
    for intent in QueryIntent:
        if intent != QueryIntent.UNKNOWN:
            scores[intent] = _score_intent(question, intent)

    # Sort by score
    sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Log top 3 for debugging
    top_3 = sorted_intents[:3]
    logger.debug(f"Intent scores for '{question[:40]}': {[(i.value, s) for i, s in top_3]}")

    if sorted_intents:
        best_intent, best_score = sorted_intents[0]
        second_score = sorted_intents[1][1] if len(sorted_intents) > 1 else 0

        # Calculate confidence based on score margin
        if best_score > 0:
            margin = best_score - second_score

            # High confidence if clear winner
            if margin >= 5 or best_score >= 15:
                entities = extract_entities(question, best_intent)
                confidence = min(0.95, 0.7 + (margin * 0.05))
                return (best_intent, confidence, entities)

            # Medium confidence - still use best match
            if best_score >= 5:
                entities = extract_entities(question, best_intent)
                confidence = 0.6 + (margin * 0.03)
                return (best_intent, confidence, entities)

            # Low confidence - check for LLM fallback
            if use_llm_fallback and llm_classifier and margin < 3:
                logger.info(f"Using LLM fallback for ambiguous query: '{question[:50]}'")
                try:
                    llm_intent = llm_classifier(question)
                    if llm_intent and llm_intent != QueryIntent.UNKNOWN:
                        entities = extract_entities(question, llm_intent)
                        return (llm_intent, 0.85, entities)
                except Exception as e:
                    logger.warning(f"LLM classification failed: {e}")

            # Use best scoring intent even with low confidence
            if best_score > 0:
                entities = extract_entities(question, best_intent)
                return (best_intent, 0.5, entities)

    # No good match - return UNKNOWN
    return (QueryIntent.UNKNOWN, 0.3, extract_entities(question, QueryIntent.UNKNOWN))


def extract_entities(question: str, intent: QueryIntent) -> Dict:
    """Extract relevant entities from the question"""
    entities = {}
    question_lower = question.lower()

    # Extract platform mentions
    platforms = []
    if 'ios-xe' in question_lower or 'iosxe' in question_lower:
        platforms.append('IOS-XE')
    if 'ios-xr' in question_lower or 'iosxr' in question_lower:
        platforms.append('IOS-XR')
    if 'asa' in question_lower:
        platforms.append('ASA')
    if 'ftd' in question_lower:
        platforms.append('FTD')
    if 'nxos' in question_lower or 'nx-os' in question_lower:
        platforms.append('NX-OS')
    if platforms:
        entities['platforms'] = platforms

    # Extract severity
    if 'critical' in question_lower:
        entities['severity'] = 'critical'
    elif 'high' in question_lower:
        entities['severity'] = 'high'
    elif 'medium' in question_lower:
        entities['severity'] = 'medium'
    elif 'low' in question_lower:
        entities['severity'] = 'low'

    # Extract timeframe
    if 'last week' in question_lower or 'past week' in question_lower:
        entities['timeframe'] = 'week'
    elif 'last month' in question_lower or 'past month' in question_lower:
        entities['timeframe'] = 'month'
    elif 'today' in question_lower:
        entities['timeframe'] = 'day'

    # Extract advisory ID patterns
    advisory_match = re.search(r'cisco-sa-[\w-]+', question_lower)
    if advisory_match:
        entities['advisory_id'] = advisory_match.group(0)

    # Extract label patterns (UPPER_CASE_WITH_UNDERSCORES, mixed case allowed)
    # Match patterns like SEC_CoPP, MGMT_SSH_HTTP, RTE_BGP, etc.
    label_matches = re.findall(r'\b([A-Z]{2,}(?:_[A-Za-z0-9]+)+)\b', question)
    if label_matches:
        entities['labels'] = label_matches

    # Extract version patterns
    version_match = re.search(r'\b(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?[a-z]?)\b', question)
    if version_match:
        entities['version'] = version_match.group(1)

    return entities


# =============================================================================
# Reasoning Engine
# =============================================================================

class ReasoningEngine:
    """
    AI Reasoning Engine for vulnerability analysis.

    Responsibilities:
    - Load and utilize taxonomy definitions for context
    - Construct prompts that leverage fine-tuned model knowledge
    - Interface with MLX analyzer for inference
    - Fetch device/PSIRT context from database
    """

    def __init__(self, db_path: str = "vulnerability_db.sqlite"):
        """
        Initialize the Reasoning Engine.

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self._project_root = Path(__file__).parent.parent.parent

        # Get existing SEC8B analyzer (shares model instance)
        self._sec8b = None
        self._labeler = None
        self._backend_type = None  # 'mlx' or 'transformers'

        # Load taxonomies
        self._taxonomies = self._load_all_taxonomies()
        self._anti_defs = self._load_anti_definitions()

        logger.info(f"ReasoningEngine initialized with DB: {db_path}")

    def _get_labeler(self):
        """Lazy-load the labeler from SEC8B (avoids loading model until needed)"""
        if self._labeler is None:
            try:
                self._sec8b = get_analyzer()
                self._labeler = self._sec8b.pipeline.labeler
                # Detect backend type from the labeler class
                labeler_class = type(self._labeler).__name__
                if 'MLX' in labeler_class:
                    self._backend_type = 'mlx'
                else:
                    self._backend_type = 'transformers'
                logger.info(f"Labeler acquired from SEC8B analyzer (backend: {self._backend_type})")
            except Exception as e:
                logger.warning(f"Failed to get labeler: {e}")
                self._backend_type = None
        return self._labeler

    def _load_all_taxonomies(self) -> Dict[str, Dict]:
        """Load all platform taxonomies into memory"""
        taxonomy_files = {
            'IOS-XE': 'taxonomies/features.yml',
            'IOS-XR': 'taxonomies/features_iosxr.yml',
            'ASA': 'taxonomies/features_asa.yml',
            'FTD': 'taxonomies/features_asa.yml',
            'NX-OS': 'taxonomies/features_nxos.yml'
        }

        taxonomies = {}
        for platform, filepath in taxonomy_files.items():
            full_path = self._project_root / filepath
            if full_path.exists():
                try:
                    with open(full_path, 'r') as f:
                        features = yaml.safe_load(f)
                        # Convert list to dict keyed by label
                        taxonomies[platform] = {
                            f['label']: f for f in features if 'label' in f
                        }
                except Exception as e:
                    logger.error(f"Failed to load taxonomy {filepath}: {e}")
                    taxonomies[platform] = {}
            else:
                taxonomies[platform] = {}

        total_labels = sum(len(p) for p in taxonomies.values())
        logger.info(f"Loaded {len(taxonomies)} platform taxonomies ({total_labels} labels)")
        return taxonomies

    def _load_anti_definitions(self) -> Dict[str, str]:
        """Load anti-definition rules from taxonomy_anti_definitions.yml"""
        anti_defs = {}
        anti_def_path = self._project_root / 'transfer_package/taxonomy_anti_definitions.yml'

        if anti_def_path.exists():
            try:
                with open(anti_def_path, 'r') as f:
                    data = yaml.safe_load(f)
                    if data and 'anti_definitions' in data:
                        anti_defs = data['anti_definitions']
                        logger.info(f"Loaded {len(anti_defs)} anti-definitions")
            except Exception as e:
                logger.warning(f"Failed to load anti-definitions: {e}")

        return anti_defs

    def get_taxonomy_definitions(
        self,
        labels: List[str],
        platform: str,
        include_anti_defs: bool = True
    ) -> str:
        """
        Get formatted taxonomy definitions for labels.

        Args:
            labels: List of feature labels
            platform: Target platform
            include_anti_defs: If True, include anti-definitions (for model prompts).
                             If False, exclude them (for user-facing output).

        Includes:
        - Full description (what it IS)
        - Anti-definition (what it is NOT) - only if include_anti_defs=True
        - Config regex patterns
        - Show commands
        """
        taxonomy = self._taxonomies.get(platform, {})
        definitions = []

        for label in labels:
            if label in taxonomy:
                feature = taxonomy[label]
                desc = feature.get('description', 'No description available')

                # Extract anti-definition from "Do NOT use" in description
                anti_def = ""
                if "Do NOT use" in desc:
                    anti_def = desc[desc.index("Do NOT use"):]
                    desc = desc[:desc.index("Do NOT use")].strip()

                # Check for separate anti-definition file
                if label in self._anti_defs:
                    anti_def = self._anti_defs[label]

                config_regex = feature.get('presence', {}).get('config_regex', [])
                show_cmds = feature.get('presence', {}).get('show_cmds', [])

                # Build definition - only include anti-def if requested (model prompts)
                definition = f"""**{label}** ({feature.get('domain', 'Unknown Domain')})
Description: {desc}
{"Anti-definition: " + anti_def if anti_def and include_anti_defs else ""}
Config patterns: {', '.join(config_regex[:3]) if config_regex else 'None'}
Verification commands: {', '.join(show_cmds[:2]) if show_cmds else 'None'}"""
                definitions.append(definition.strip())
            else:
                definitions.append(f"**{label}**: Definition not found in {platform} taxonomy")

        return "\n\n".join(definitions)

    def _generate_text(self, prompt: str, max_tokens: int = 1024) -> str:
        """Generate free-form text using the available model backend"""
        labeler = self._get_labeler()

        if self._backend_type is None:
            raise RuntimeError("No model backend available for text generation")

        try:
            if self._backend_type == 'mlx':
                # MLX backend (Mac only)
                from mlx_lm import generate
                response = generate(
                    labeler.model,
                    labeler.tokenizer,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    verbose=False,
                )
                return response
            else:
                # Transformers backend (Linux/CUDA/CPU)
                import torch
                inputs = labeler.tokenizer(prompt, return_tensors="pt").to(labeler.device)
                with torch.no_grad():
                    outputs = labeler.model.generate(
                        **inputs,
                        max_new_tokens=max_tokens,
                        do_sample=True,
                        temperature=0.7,
                        top_p=0.9,
                        pad_token_id=labeler.tokenizer.eos_token_id
                    )
                response = labeler.tokenizer.decode(outputs[0], skip_special_tokens=True)
                # Strip the prompt from the response
                if response.startswith(prompt):
                    response = response[len(prompt):].strip()
                return response
        except Exception as e:
            logger.error(f"Text generation failed ({self._backend_type}): {e}")
            raise

    def _run_inference(self, prompt: str, max_tokens: int = 1024) -> Dict[str, Any]:
        """
        Run inference using the available backend for free-form generation.

        Returns:
            Dict with 'response' and 'confidence'
        """
        try:
            response = self._generate_text(prompt, max_tokens=max_tokens)

            # Post-process to truncate repetitive content
            response = self._truncate_repetition(response)

            return {
                'response': response,
                'confidence': 0.85  # Heuristic for explanation confidence
            }
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return {
                'response': f"Unable to generate response: {str(e)}",
                'confidence': 0.0
            }

    def _truncate_repetition(self, text: str, min_length: int = 100) -> str:
        """
        Detect and truncate repetitive text.

        Strategy: Split into sentences, find first sentence that repeats, stop there.
        """
        if len(text) < min_length * 2:
            return text

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)

        if len(sentences) < 3:
            return text

        # Method 1: Find sentences that start with the same pattern
        result_sentences = []
        seen_starts = {}

        for i, sent in enumerate(sentences):
            # Use first 40 characters as signature
            sent_clean = sent.strip()
            if len(sent_clean) < 20:
                result_sentences.append(sent_clean)
                continue

            sig = sent_clean[:40].lower()

            if sig in seen_starts:
                # Found repetition - stop before this sentence
                break

            seen_starts[sig] = i
            result_sentences.append(sent_clean)

        result = ' '.join(result_sentences).strip()

        # If result is still long, try method 2: detect repeated phrases
        if len(result) > 500:
            # Look for any 25-char phrase that appears more than once
            for i in range(0, min(len(result), 400)):
                phrase = result[i:i + 25]
                if len(phrase) < 25:
                    break
                # Count occurrences
                count = result.count(phrase)
                if count > 1:
                    # Find end of sentence containing first occurrence
                    first_end = result.find('.', i + 25)
                    if first_end > 0:
                        return result[:first_end + 1].strip()

        return result

    # =========================================================================
    # Database Queries
    # =========================================================================

    def _fetch_psirt(self, advisory_id: str, platform: str) -> Optional[Dict]:
        """Fetch PSIRT from database"""
        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()
                cursor.execute("""
                    SELECT bug_id, summary, labels, platform, severity,
                           affected_versions_raw, fixed_version
                    FROM vulnerabilities
                    WHERE bug_id LIKE ? AND platform = ?
                    LIMIT 1
                """, (f"%{advisory_id}%", platform))
                row = cursor.fetchone()

                if row:
                    return {
                        'advisory_id': row['bug_id'],
                        'summary': row['summary'],
                        'labels': json.loads(row['labels']) if row['labels'] else [],
                        'platform': row['platform'],
                        'severity': row['severity'],
                        'affected_versions': row['affected_versions_raw'],
                        'fixed_versions': row['fixed_version']
                    }
        except Exception as e:
            logger.error(f"Failed to fetch PSIRT: {e}")
        return None

    def _fetch_device(self, device_id: int) -> Optional[Dict]:
        """Fetch device from inventory"""
        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()
                cursor.execute("""
                    SELECT id, hostname, ip_address, platform, version,
                           hardware_model, features, discovery_status
                    FROM device_inventory
                    WHERE id = ?
                    LIMIT 1
                """, (device_id,))
                row = cursor.fetchone()

                if row:
                    device = dict(row)
                    # Parse features JSON
                    if device.get('features'):
                        try:
                            device['features'] = json.loads(device['features'])
                        except json.JSONDecodeError:
                            device['features'] = []
                    else:
                        device['features'] = []
                    return device
        except Exception as e:
            logger.error(f"Failed to fetch device: {e}")
        return None

    def _format_device_context(self, device: Dict) -> str:
        """Format device data for prompt context"""
        return f"""Device: {device.get('hostname', 'Unknown')}
IP: {device.get('ip_address', 'Unknown')}
Platform: {device.get('platform', 'Unknown')}
Version: {device.get('version', 'Unknown')}
Hardware: {device.get('hardware_model', 'Unknown')}
Features: {len(device.get('features', []))} configured"""

    # =========================================================================
    # Phase 1: Explain
    # =========================================================================

    async def explain(
        self,
        psirt_id: Optional[str] = None,
        psirt_summary: Optional[str] = None,
        labels: Optional[List[str]] = None,
        platform: str = "IOS-XE",
        device_id: Optional[int] = None,
        device_features: Optional[List[str]] = None,
        question_type: str = "why"
    ) -> Dict[str, Any]:
        """
        Generate explanation for vulnerability assessment.

        Args:
            psirt_id: Advisory ID to look up
            psirt_summary: Direct summary text (if no psirt_id)
            labels: Labels to explain (fetched if not provided)
            platform: Target platform
            device_id: Optional device for context
            device_features: Optional device features
            question_type: Type of explanation (why/impact/technical)

        Returns:
            Dict with explanation, labels, confidence, etc.
        """
        # Fetch PSIRT if ID provided
        if psirt_id and not psirt_summary:
            psirt_data = self._fetch_psirt(psirt_id, platform)
            if psirt_data:
                psirt_summary = psirt_data.get('summary', '')
                if not labels:
                    labels = psirt_data.get('labels', [])

        if not psirt_summary:
            raise ValueError("Either psirt_id or psirt_summary required")

        if not labels:
            labels = []

        # Fetch device context if ID provided
        device_context = None
        device_data = None
        if device_id:
            device_data = self._fetch_device(device_id)
            if device_data:
                device_context = self._format_device_context(device_data)
                if not device_features:
                    device_features = device_data.get('features', [])

        # Get taxonomy definitions
        definitions = self.get_taxonomy_definitions(labels, platform)

        # Build prompt based on question type
        prompt = self._build_explain_prompt(
            psirt_summary=psirt_summary,
            labels=labels,
            definitions=definitions,
            platform=platform,
            device_context=device_context,
            device_features=device_features,
            question_type=question_type
        )

        # Run inference (512 tokens is enough for explanations)
        result = self._run_inference(prompt, max_tokens=512)

        # Determine if device is affected
        affected = None
        if device_features and labels:
            affected = bool(set(labels) & set(device_features))

        return {
            'explanation': result['response'],
            'labels': labels,
            'confidence': result['confidence'],
            'device_context': device_context,
            'affected': affected
        }

    def _build_explain_prompt(
        self,
        psirt_summary: str,
        labels: List[str],
        definitions: str,
        platform: str,
        device_context: Optional[str],
        device_features: Optional[List[str]],
        question_type: str
    ) -> str:
        """Build prompt for explanation generation"""

        # Task-specific instructions
        task_instructions = {
            "why": "For each assigned label, explain WHY it applies by citing specific evidence from the advisory text.",
            "impact": "Describe the business and operational impact: what could an attacker do and what services would be affected.",
            "technical": "Provide technical analysis: attack vectors, prerequisites, and exploitation complexity."
        }

        task = task_instructions.get(question_type, task_instructions['why'])

        # Build prompt with clear structure and output format
        prompt = f"""### Instruction:
You are a Cisco security expert explaining why specific feature labels were assigned to a vulnerability advisory.

### Advisory Summary ({platform}):
{psirt_summary[:1500]}

### Assigned Labels:
{', '.join(labels) if labels else 'None'}

### Label Definitions:
{definitions}

"""

        if device_context:
            prompt += f"""### Device Context:
{device_context}
Configured features: {', '.join(device_features) if device_features else 'Unknown'}

"""

        prompt += f"""### Task:
{task}

### Output Format:
Provide a concise explanation (2-4 sentences) covering:
1. What feature/protocol is affected
2. Why each label applies (cite specific evidence)
{"3. Whether this device is affected" if device_context else ""}

### Explanation:"""

        return prompt

    # =========================================================================
    # Phase 2: Remediate
    # =========================================================================

    async def remediate(
        self,
        psirt_id: str,
        platform: str,
        device_id: Optional[int] = None,
        device_version: Optional[str] = None,
        device_features: Optional[List[str]] = None,
        include_commands: bool = True,
        include_upgrade_path: bool = True
    ) -> Dict[str, Any]:
        """
        Generate remediation guidance for vulnerability.

        Returns multiple options with commands, impact assessment,
        and effectiveness rating.
        """
        # Fetch PSIRT data
        psirt_data = self._fetch_psirt(psirt_id, platform)
        if not psirt_data:
            raise ValueError(f"PSIRT not found: {psirt_id}")

        labels = psirt_data.get('labels', [])
        summary = psirt_data.get('summary', '')

        # Get device context
        device_context = None
        if device_id:
            device_data = self._fetch_device(device_id)
            if device_data:
                device_context = self._format_device_context(device_data)
                device_version = device_version or device_data.get('version')
                device_features = device_features or device_data.get('features', [])

        # Get taxonomy info for config patterns
        definitions = self.get_taxonomy_definitions(labels, platform)

        # Build remediation prompt
        prompt = self._build_remediate_prompt(
            summary=summary,
            labels=labels,
            definitions=definitions,
            platform=platform,
            device_version=device_version,
            device_features=device_features,
            include_commands=include_commands
        )

        # Run inference
        result = self._run_inference(prompt, max_tokens=1500)

        # Parse structured output or generate defaults
        options = self._parse_remediation_options(result['response'], labels, platform)

        # Get upgrade path if requested
        upgrade_path = None
        if include_upgrade_path and device_version:
            upgrade_path = self._get_upgrade_path(device_version, psirt_id, platform)

        return {
            'options': options,
            'recommended_option': 0,
            'device_context': device_context,
            'severity': self._get_psirt_severity(psirt_id, platform),
            'upgrade_path': upgrade_path,
            'confidence': result['confidence']
        }

    def _build_remediate_prompt(
        self,
        summary: str,
        labels: List[str],
        definitions: str,
        platform: str,
        device_version: Optional[str],
        device_features: Optional[List[str]],
        include_commands: bool
    ) -> str:
        """Build prompt for remediation generation"""

        prompt = f"""### Instruction:
You are a Cisco security engineer providing remediation guidance for a vulnerability.

### Vulnerability Summary:
{summary[:1200]}

### Affected Features:
Labels: {', '.join(labels)}

### Feature Definitions:
{definitions}

### Device Context:
Platform: {platform}
Version: {device_version or 'Unknown'}
Configured Features: {', '.join(device_features) if device_features else 'Unknown'}

### Task:
Provide 2-3 remediation options ordered from most to least disruptive.

### Output Format:
For each option, provide:
- Action: (disable_feature, apply_acl, upgrade, or workaround)
- Title: Brief name
- Description: What to do
{"- Commands: Specific CLI commands" if include_commands else ""}
- Impact: Operational impact
- Effectiveness: full/partial/temporary

### Remediation Options:"""

        return prompt

    def _parse_remediation_options(
        self,
        response: str,
        labels: List[str],
        platform: str
    ) -> List[Dict]:
        """
        Parse LLM response into structured remediation options.

        Falls back to generating default options based on taxonomy
        if parsing fails.
        """
        options = []
        taxonomy = self._taxonomies.get(platform, {})

        # Generate options based on labels
        for label in labels[:2]:  # First 2 labels
            if label in taxonomy:
                feature = taxonomy[label]
                config_patterns = feature.get('presence', {}).get('config_regex', [])

                # Generate disable option
                if config_patterns:
                    disable_cmds = self._infer_disable_commands(config_patterns)
                    options.append({
                        'action': 'disable_feature',
                        'title': f'Disable {label}',
                        'description': f'Disable the {label} feature to eliminate the attack surface.',
                        'commands': disable_cmds,
                        'impact': f'Loss of {label} functionality',
                        'effectiveness': 'full'
                    })

        # Always include upgrade option
        options.append({
            'action': 'upgrade',
            'title': 'Upgrade to Fixed Version',
            'description': 'Upgrade to a software version where the vulnerability is patched.',
            'commands': None,
            'impact': 'Requires maintenance window',
            'effectiveness': 'full'
        })

        return options

    def _infer_disable_commands(self, config_patterns: List[str]) -> List[str]:
        """Infer disable commands from config regex patterns"""
        commands = []
        for pattern in config_patterns[:2]:
            # Clean regex pattern to get base command
            clean = pattern.replace('^', '').replace('\\b', '').replace('\\s+', ' ')
            clean = re.sub(r'\([^)]*\)', '', clean)  # Remove groups
            clean = clean.strip()
            if clean and not clean.startswith('no '):
                commands.append(f"no {clean}")
        return commands if commands else ["! Consult documentation for disable commands"]

    def _get_upgrade_path(
        self,
        current_version: str,
        psirt_id: str,
        platform: str
    ) -> Optional[Dict]:
        """Get upgrade path to fixed version"""
        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()
                cursor.execute("""
                    SELECT fixed_version
                    FROM vulnerabilities
                    WHERE bug_id LIKE ? AND platform = ?
                    LIMIT 1
                """, (f"%{psirt_id}%", platform))
                row = cursor.fetchone()

                if row and row['fixed_version']:
                    return {
                        'current': current_version,
                        'target': row['fixed_version'],
                        'direct_upgrade': True,
                        'intermediate_versions': None
                    }
        except Exception as e:
            logger.error(f"Failed to get upgrade path: {e}")

        return None

    def _get_psirt_severity(self, psirt_id: str, platform: str) -> str:
        """Get PSIRT severity from database"""
        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()
                cursor.execute("""
                    SELECT severity FROM vulnerabilities
                    WHERE bug_id LIKE ? AND platform = ?
                    LIMIT 1
                """, (f"%{psirt_id}%", platform))
                row = cursor.fetchone()

                if row and row['severity']:
                    severity_map = {1: 'critical', 2: 'high', 3: 'medium', 4: 'low'}
                    return severity_map.get(row['severity'], 'unknown')
        except Exception as e:
            logger.error(f"Failed to get severity: {e}")
        return 'unknown'

    # =========================================================================
    # Phase 3: Ask (Natural Language Query)
    # =========================================================================

    def _classify_with_llm(self, question: str) -> Optional[QueryIntent]:
        """
        Use LLM to classify intent for ambiguous queries.

        This is the fallback when keyword scoring produces low confidence.
        Takes ~1-2 seconds but is more robust for edge cases.
        """
        prompt = f"""Classify this question into exactly ONE category.

Question: "{question}"

Categories:
- DEVICES_BY_RISK: Questions about which devices have critical/high/severe bugs
- DEVICE_VULNERABILITIES: Questions about bugs affecting a specific named device
- LIST_DEVICES: Questions about listing or showing devices in inventory
- LIST_VULNERABILITIES: Questions about listing bugs from the database
- PRIORITIZE: Questions asking for recommendations or what to focus on
- SUMMARY: Questions asking for a summary or overview
- COUNT: Questions asking "how many" of something
- EXPLAIN_LABEL: Questions asking what a feature label (like SEC_CoPP) means
- REMEDIATION: Questions about how to fix or remediate something
- UNKNOWN: If none of the above fit

Reply with ONLY the category name, nothing else."""

        try:
            result = self._run_inference(prompt, max_tokens=20)
            response = result.get('response', '').strip().upper()

            # Map response to QueryIntent
            intent_map = {
                'DEVICES_BY_RISK': QueryIntent.DEVICES_BY_RISK,
                'DEVICE_VULNERABILITIES': QueryIntent.DEVICE_VULNERABILITIES,
                'LIST_DEVICES': QueryIntent.LIST_DEVICES,
                'LIST_VULNERABILITIES': QueryIntent.LIST_VULNERABILITIES,
                'PRIORITIZE': QueryIntent.PRIORITIZE,
                'SUMMARY': QueryIntent.SUMMARY,
                'COUNT': QueryIntent.COUNT,
                'EXPLAIN_LABEL': QueryIntent.EXPLAIN_LABEL,
                'REMEDIATION': QueryIntent.REMEDIATION,
            }

            for key, intent in intent_map.items():
                if key in response:
                    logger.info(f"LLM classified '{question[:40]}' as {intent.value}")
                    return intent

            return QueryIntent.UNKNOWN

        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            return None

    async def ask(
        self,
        question: str,
        context: Optional[Dict] = None,
        use_llm_fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Answer natural language questions about vulnerabilities.

        Uses hybrid 3-tier intent classification:
        1. Quick override - instant, catches obvious patterns
        2. Keyword scoring - instant, scores all intents and picks best
        3. LLM fallback - ~1-2s, used when scoring is ambiguous

        Args:
            question: The user's question
            context: Optional additional context
            use_llm_fallback: Whether to use LLM for ambiguous queries (default: True)
        """
        # Classify intent with optional LLM fallback
        intent, intent_confidence, entities = classify_intent(
            question,
            use_llm_fallback=use_llm_fallback,
            llm_classifier=self._classify_with_llm if use_llm_fallback else None
        )

        logger.info(f"Intent: {intent.value} (confidence: {intent_confidence:.2f}) for: '{question[:50]}'")

        # Route to appropriate handler
        if intent == QueryIntent.PRIORITIZE:
            return await self._handle_prioritize(question, entities)
        elif intent == QueryIntent.DEVICES_BY_RISK:
            return await self._handle_devices_by_risk(question, entities)
        elif intent == QueryIntent.DEVICE_VULNERABILITIES:
            return await self._handle_device_vulnerabilities(question, entities)
        elif intent == QueryIntent.LIST_DEVICES:
            return await self._handle_list_devices(question, entities)
        elif intent == QueryIntent.LIST_VULNERABILITIES:
            return await self._handle_list_vulnerabilities(question, entities)
        elif intent == QueryIntent.EXPLAIN_VULNERABILITY:
            return await self._handle_explain_query(question, entities)
        elif intent == QueryIntent.EXPLAIN_LABEL:
            return await self._handle_label_query(question, entities)
        elif intent == QueryIntent.REMEDIATION:
            return await self._handle_remediation_query(question, entities)
        elif intent == QueryIntent.SUMMARY:
            return await self._handle_summary_query(question, entities)
        elif intent == QueryIntent.COUNT:
            return await self._handle_count_query(question, entities)
        else:
            # UNKNOWN: Use LLM for free-form response
            return await self._handle_freeform_query(question, entities)

    async def _handle_devices_by_risk(self, question: str, entities: Dict) -> Dict[str, Any]:
        """
        Handle queries about which devices have critical/high bugs.

        Queries actual scan results from device_inventory, not the vulnerabilities table.
        """
        sources = []

        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()

                # Get all scanned devices with their scan results
                cursor.execute("""
                    SELECT id, hostname, platform, version, hardware_model,
                           ip_address, last_scan_result, last_scan_id
                    FROM device_inventory
                    WHERE discovery_status = 'success'
                    AND last_scan_result IS NOT NULL
                """)

                devices = [dict(row) for row in cursor.fetchall()]
                sources.append({'type': 'inventory', 'scanned_devices': len(devices)})

                if not devices:
                    return {
                        'answer': "No devices have been scanned yet. Please scan your devices first to see which have critical or high severity bugs.",
                        'sources': sources,
                        'confidence': 0.9,
                        'suggested_actions': ['Scan devices', 'View inventory']
                    }

                # Parse scan results and calculate risk for each device
                device_risk = []
                for device in devices:
                    try:
                        scan_result = json.loads(device.get('last_scan_result', '{}'))

                        # Get bug counts
                        total_bugs = scan_result.get('total_bugs', 0) or 0
                        critical_high = scan_result.get('critical_high', 0) or scan_result.get('bug_critical_high', 0) or 0
                        total_psirts = scan_result.get('total_psirts', 0) or 0
                        psirt_critical_high = scan_result.get('psirt_critical_high', 0) or 0

                        device_risk.append({
                            'hostname': device['hostname'],
                            'platform': device['platform'],
                            'version': device.get('version', 'N/A'),
                            'ip_address': device.get('ip_address', 'N/A'),
                            'total_bugs': int(total_bugs),
                            'critical_high': int(critical_high),
                            'total_psirts': int(total_psirts),
                            'psirt_critical_high': int(psirt_critical_high),
                            'total_critical_high': int(critical_high) + int(psirt_critical_high)
                        })
                    except (json.JSONDecodeError, TypeError):
                        continue

                if not device_risk:
                    return {
                        'answer': "Could not parse scan results for any devices. Please re-scan your devices.",
                        'sources': sources,
                        'confidence': 0.5
                    }

                # Sort by total critical+high (worst first)
                device_risk.sort(key=lambda x: (-x['total_critical_high'], -x['total_bugs']))

                # Build response
                has_critical = any(d['total_critical_high'] > 0 for d in device_risk)

                if has_critical:
                    # Show devices with critical/high bugs
                    at_risk = [d for d in device_risk if d['total_critical_high'] > 0]
                    device_list = "\n".join([
                        f"- **{d['hostname']}** ({d['platform']} {d['version']}) - 🔴 {d['total_critical_high']} critical/high ({d['total_bugs']} bugs, {d['total_psirts']} PSIRTs)"
                        for d in at_risk[:10]
                    ])

                    answer = f"**{len(at_risk)} device(s) with Critical/High severity issues:**\n\n{device_list}"

                    if len(at_risk) > 10:
                        answer += f"\n\n...and {len(at_risk) - 10} more devices with critical/high issues."

                    # Add safe devices count
                    safe_count = len(device_risk) - len(at_risk)
                    if safe_count > 0:
                        answer += f"\n\n✅ {safe_count} device(s) have no critical/high bugs."
                else:
                    # No critical/high - show summary
                    answer = f"✅ **Good news!** None of your {len(device_risk)} scanned devices have critical or high severity bugs.\n\n"

                    # Show devices with most bugs anyway
                    if device_risk[0]['total_bugs'] > 0:
                        answer += "**Devices with the most bugs (Medium/Low):**\n"
                        top_devices = [d for d in device_risk if d['total_bugs'] > 0][:5]
                        answer += "\n".join([
                            f"- **{d['hostname']}** ({d['platform']}) - {d['total_bugs']} bugs"
                            for d in top_devices
                        ])
                    else:
                        answer += "All devices are clean with no known bugs affecting them."

                return {
                    'answer': answer,
                    'sources': sources,
                    'confidence': 0.95,
                    'suggested_actions': ['View device details', 'Get remediation for specific bug']
                }

        except Exception as e:
            logger.error(f"Failed to get devices by risk: {e}")
            return {
                'answer': f"Error querying device risk: {str(e)}",
                'sources': [],
                'confidence': 0.0
            }

    async def _handle_prioritize(self, question: str, entities: Dict) -> Dict[str, Any]:
        """
        Handle prioritization/recommendation queries.

        Provides actionable recommendations on what to focus on based on:
        - Severity of bugs (critical > high > medium > low)
        - Device importance (could be enhanced with device criticality metadata)
        - Ease of remediation
        """
        sources = []

        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()

                # Get all scanned devices with their scan results
                cursor.execute("""
                    SELECT id, hostname, platform, version, hardware_model,
                           ip_address, last_scan_result, last_scan_id
                    FROM device_inventory
                    WHERE discovery_status = 'success'
                    AND last_scan_result IS NOT NULL
                """)

                devices = [dict(row) for row in cursor.fetchall()]
                sources.append({'type': 'inventory', 'scanned_devices': len(devices)})

                if not devices:
                    return {
                        'answer': "**No scanned devices found.**\n\nTo get prioritization recommendations:\n1. Go to the **Device Inventory** tab\n2. Click **Discover** on pending devices\n3. Click **Scan** to check for vulnerabilities\n\nOnce you have scan data, I can recommend which devices need immediate attention.",
                        'sources': sources,
                        'confidence': 0.9,
                        'suggested_actions': ['Discover devices', 'Scan devices']
                    }

                # Parse scan results and calculate risk for each device
                device_risk = []
                for device in devices:
                    try:
                        scan_result = json.loads(device.get('last_scan_result', '{}'))

                        total_bugs = scan_result.get('total_bugs', 0) or 0
                        critical_high = scan_result.get('critical_high', 0) or scan_result.get('bug_critical_high', 0) or 0
                        total_psirts = scan_result.get('total_psirts', 0) or 0
                        psirt_critical_high = scan_result.get('psirt_critical_high', 0) or 0

                        device_risk.append({
                            'id': device['id'],
                            'hostname': device['hostname'],
                            'platform': device['platform'],
                            'version': device.get('version', 'N/A'),
                            'ip_address': device.get('ip_address', 'N/A'),
                            'hardware_model': device.get('hardware_model', 'Unknown'),
                            'total_bugs': int(total_bugs),
                            'critical_high': int(critical_high),
                            'total_psirts': int(total_psirts),
                            'psirt_critical_high': int(psirt_critical_high),
                            'total_critical_high': int(critical_high) + int(psirt_critical_high),
                            'scan_id': device.get('last_scan_id')
                        })
                    except (json.JSONDecodeError, TypeError):
                        continue

                if not device_risk:
                    return {
                        'answer': "Could not parse scan results. Please re-scan your devices.",
                        'sources': sources,
                        'confidence': 0.5
                    }

                # Sort by risk: most critical/high first, then total bugs
                device_risk.sort(key=lambda x: (-x['total_critical_high'], -x['total_bugs']))

                # Build prioritized recommendations
                answer = "**🎯 Prioritization Recommendations**\n\n"

                # Check if any devices have critical/high issues
                critical_devices = [d for d in device_risk if d['total_critical_high'] > 0]

                if critical_devices:
                    # Priority 1: Device with most critical/high bugs
                    top_device = critical_devices[0]
                    answer += f"**🔴 Priority 1: {top_device['hostname']}**\n"
                    answer += f"   Platform: {top_device['platform']} {top_device['version']}\n"
                    answer += f"   Hardware: {top_device['hardware_model']}\n"
                    answer += f"   Issues: **{top_device['total_critical_high']} critical/high** ({top_device['total_bugs']} bugs, {top_device['total_psirts']} PSIRTs)\n\n"
                    answer += f"   **Why:** This device has the highest number of critical/high severity issues that need immediate attention.\n\n"

                    # If more critical devices, list them
                    if len(critical_devices) > 1:
                        answer += f"**🟠 Other devices needing attention ({len(critical_devices) - 1} more):**\n"
                        for d in critical_devices[1:5]:
                            answer += f"   - **{d['hostname']}** - {d['total_critical_high']} critical/high\n"
                        if len(critical_devices) > 5:
                            answer += f"   - ...and {len(critical_devices) - 5} more\n"
                        answer += "\n"

                    # Recommended actions
                    answer += "**📋 Recommended Actions:**\n"
                    answer += f"1. Ask: \"What bugs affect {top_device['hostname']}?\" to see the full list\n"
                    answer += f"2. Check if software upgrades are available for {top_device['platform']} {top_device['version']}\n"
                    answer += f"3. Review workarounds for any critical bugs that can't be patched immediately\n"

                else:
                    # No critical/high - good news!
                    answer += "✅ **Good news!** No devices have critical or high severity bugs.\n\n"

                    # Still show devices with medium/low bugs
                    devices_with_bugs = [d for d in device_risk if d['total_bugs'] > 0]
                    if devices_with_bugs:
                        top_device = devices_with_bugs[0]
                        answer += f"**🟡 Lowest Priority Focus: {top_device['hostname']}**\n"
                        answer += f"   Has {top_device['total_bugs']} medium/low bugs - address during scheduled maintenance.\n\n"

                        answer += "**📋 Recommended Actions:**\n"
                        answer += "1. Plan software upgrades during next maintenance window\n"
                        answer += "2. Review any devices not yet scanned\n"
                        answer += "3. Set up regular scan schedule to catch new vulnerabilities\n"
                    else:
                        answer += "🎉 All devices are clean with no known bugs!\n\n"
                        answer += "**📋 Recommended Actions:**\n"
                        answer += "1. Ensure all devices are being scanned regularly\n"
                        answer += "2. Check for any pending device discoveries\n"
                        answer += "3. Keep monitoring for new vulnerability disclosures\n"

                # Summary stats
                total_critical_high = sum(d['total_critical_high'] for d in device_risk)
                total_bugs = sum(d['total_bugs'] for d in device_risk)
                answer += f"\n---\n**Summary:** {len(device_risk)} devices scanned, {total_critical_high} critical/high issues, {total_bugs} total bugs"

                return {
                    'answer': answer,
                    'sources': sources,
                    'confidence': 0.95,
                    'suggested_actions': [
                        f"View {critical_devices[0]['hostname']} details" if critical_devices else "View inventory",
                        'Get remediation guidance',
                        'Compare before/after scans'
                    ]
                }

        except Exception as e:
            logger.error(f"Failed to generate prioritization: {e}")
            return {
                'answer': f"Error generating recommendations: {str(e)}",
                'sources': [],
                'confidence': 0.0
            }

    async def _handle_list_devices(self, question: str, entities: Dict) -> Dict[str, Any]:
        """Handle queries about affected devices"""
        sources = []

        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()

                # Query devices with optional filters
                query = "SELECT * FROM device_inventory WHERE discovery_status = 'success'"
                params = []

                if entities.get('platforms'):
                    placeholders = ','.join(['?' for _ in entities['platforms']])
                    query += f" AND platform IN ({placeholders})"
                    params.extend(entities['platforms'])

                cursor.execute(query, params)
                devices = [dict(row) for row in cursor.fetchall()]
                sources.append({'type': 'inventory', 'count': len(devices)})

                if not devices:
                    return {
                        'answer': "No devices found matching your criteria.",
                        'sources': sources,
                        'confidence': 0.9
                    }

                # Format response
                device_list = "\n".join([
                    f"- **{d['hostname']}** ({d['platform']} {d.get('version', 'N/A')}) - {d.get('ip_address', 'N/A')}"
                    for d in devices[:10]
                ])

                answer = f"Found {len(devices)} device(s):\n\n{device_list}"
                if len(devices) > 10:
                    answer += f"\n\n...and {len(devices) - 10} more."

                return {
                    'answer': answer,
                    'sources': sources,
                    'confidence': 0.9,
                    'suggested_actions': ['View all devices', 'Filter by platform']
                }

        except Exception as e:
            logger.error(f"Failed to list devices: {e}")
            return {
                'answer': f"Error querying devices: {str(e)}",
                'sources': [],
                'confidence': 0.0
            }

    async def _handle_device_vulnerabilities(self, question: str, entities: Dict) -> Dict[str, Any]:
        """
        Handle queries about bugs/PSIRTs affecting a specific device.

        This fetches actual scan results for a device, not just generic DB queries.
        """
        sources = []

        try:
            # Extract device identifier from question
            import re
            question_lower = question.lower()

            # Try to find device hostname/identifier in question
            # Patterns: C9200L, Cat9300, device-name, IP address
            hostname_match = re.search(r'\b([A-Za-z]+-?\d+[A-Za-z]*(?:-\d+)?)\b', question)
            ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', question)

            device_identifier = None
            if hostname_match:
                device_identifier = hostname_match.group(1)
            elif ip_match:
                device_identifier = ip_match.group(1)

            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()

                # Find the device
                if device_identifier:
                    cursor.execute("""
                        SELECT id, hostname, platform, version, hardware_model,
                               last_scan_id, last_scan_result, features
                        FROM device_inventory
                        WHERE hostname LIKE ? OR ip_address LIKE ?
                        LIMIT 1
                    """, (f'%{device_identifier}%', f'%{device_identifier}%'))
                else:
                    # No specific device - try to get most recently scanned
                    cursor.execute("""
                        SELECT id, hostname, platform, version, hardware_model,
                               last_scan_id, last_scan_result, features
                        FROM device_inventory
                        WHERE last_scan_id IS NOT NULL
                        ORDER BY id DESC LIMIT 1
                    """)

                device = cursor.fetchone()

                if not device:
                    return {
                        'answer': f"No device found matching '{device_identifier or 'your criteria'}'. Please specify a device hostname or IP address.",
                        'sources': [],
                        'confidence': 0.5,
                        'suggested_actions': ['List all devices', 'Scan a device first']
                    }

                device = dict(device)
                sources.append({'type': 'inventory', 'device': device['hostname']})

                # Check if device has been scanned
                if not device.get('last_scan_id'):
                    return {
                        'answer': f"**{device['hostname']}** ({device['platform']} {device.get('version', 'N/A')}) has not been scanned yet.\n\nPlease run a vulnerability scan on this device first.",
                        'sources': sources,
                        'confidence': 0.8,
                        'suggested_actions': ['Scan this device', 'View device details']
                    }

                # Get scan results
                cursor.execute("""
                    SELECT scan_id, timestamp, full_result
                    FROM scan_results
                    WHERE scan_id = ?
                """, (device['last_scan_id'],))

                scan_row = cursor.fetchone()

                if not scan_row:
                    # Fall back to summary in device_inventory
                    scan_summary = json.loads(device.get('last_scan_result', '{}'))
                    bug_count = scan_summary.get('total_bugs', 0)
                    psirt_count = scan_summary.get('total_psirts', 0)

                    answer = f"""**{device['hostname']}** ({device['platform']} {device.get('version', 'N/A')})

**Scan Summary:**
- Bugs: {bug_count}
- PSIRTs: {psirt_count}
- Critical/High: {scan_summary.get('critical_high', 0)}

*Detailed bug list not available. Run a new scan to get full details.*"""

                    return {
                        'answer': answer,
                        'sources': sources,
                        'confidence': 0.7,
                        'suggested_actions': ['Re-scan device', 'View in Inventory']
                    }

                # Parse full scan results
                scan_data = dict(scan_row)
                results = json.loads(scan_data.get('full_result', '{}'))
                bugs = results.get('bugs', [])
                psirts = results.get('psirts', [])

                sources.append({'type': 'scan_results', 'scan_id': device['last_scan_id']})

                # Format bug list
                severity_labels = {1: '🔴 Critical', 2: '🟠 High', 3: '🟡 Medium', 4: '🟢 Low'}

                # Helper to strip HTML tags
                def strip_html(text: str) -> str:
                    import re
                    return re.sub(r'<[^>]+>', '', text).strip()

                bug_list = ""
                if bugs:
                    # Sort by severity
                    sorted_bugs = sorted(bugs, key=lambda x: x.get('severity', 5))[:10]
                    bug_list = "\n".join([
                        f"- **{b.get('bug_id', 'Unknown')}** ({severity_labels.get(b.get('severity'), 'Unknown')})\n  {strip_html(b.get('headline', b.get('summary', 'No description')))[:100]}..."
                        for b in sorted_bugs
                    ])
                    if len(bugs) > 10:
                        bug_list += f"\n\n...and {len(bugs) - 10} more bugs."

                psirt_list = ""
                if psirts:
                    sorted_psirts = sorted(psirts, key=lambda x: x.get('severity', 5))[:5]
                    psirt_list = "\n".join([
                        f"- **{p.get('bug_id', 'Unknown')}** ({severity_labels.get(p.get('severity'), 'Unknown')})\n  {strip_html(p.get('headline', p.get('summary', 'No description')))[:100]}..."
                        for p in sorted_psirts
                    ])
                    if len(psirts) > 5:
                        psirt_list += f"\n\n...and {len(psirts) - 5} more PSIRTs."

                # Build response
                answer = f"""**{device['hostname']}** ({device['platform']} {device.get('version', 'N/A')})
Hardware: {device.get('hardware_model', 'Unknown')}

**Summary:** {len(bugs)} bugs, {len(psirts)} PSIRTs affecting this device

"""
                if bugs:
                    answer += f"**Bugs ({len(bugs)}):**\n{bug_list}\n\n"
                else:
                    answer += "**Bugs:** None found matching device version and features.\n\n"

                if psirts:
                    answer += f"**PSIRTs ({len(psirts)}):**\n{psirt_list}"
                else:
                    answer += "**PSIRTs:** None found matching device version and features."

                return {
                    'answer': answer,
                    'sources': sources,
                    'confidence': 0.95,
                    'suggested_actions': ['Explain a specific bug', 'Get remediation', 'Compare with previous scan']
                }

        except Exception as e:
            logger.error(f"Failed to get device vulnerabilities: {e}")
            return {
                'answer': f"Error querying device vulnerabilities: {str(e)}",
                'sources': [],
                'confidence': 0.0
            }

    async def _handle_list_vulnerabilities(self, question: str, entities: Dict) -> Dict[str, Any]:
        """Handle queries about vulnerabilities"""
        sources = []

        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()

                # Build query with filters
                query = "SELECT bug_id, summary, platform, severity, labels FROM vulnerabilities WHERE 1=1"
                params = []

                if entities.get('platforms'):
                    placeholders = ','.join(['?' for _ in entities['platforms']])
                    query += f" AND platform IN ({placeholders})"
                    params.extend(entities['platforms'])

                if entities.get('severity'):
                    severity_map = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4}
                    sev_val = severity_map.get(entities['severity'])
                    if sev_val:
                        query += " AND severity = ?"
                        params.append(sev_val)

                if entities.get('labels'):
                    for label in entities['labels']:
                        query += " AND labels LIKE ?"
                        params.append(f'%{label}%')

                query += " ORDER BY severity ASC LIMIT 20"

                cursor.execute(query, params)
                vulns = [dict(row) for row in cursor.fetchall()]
                sources.append({'type': 'vulnerabilities', 'count': len(vulns)})

                if not vulns:
                    return {
                        'answer': "No vulnerabilities found matching your criteria.",
                        'sources': sources,
                        'confidence': 0.9
                    }

                # Format response
                severity_labels = {1: '🔴 Critical', 2: '🟠 High', 3: '🟡 Medium', 4: '🟢 Low'}
                vuln_list = "\n".join([
                    f"- **{v['bug_id']}** ({severity_labels.get(v['severity'], 'Unknown')}) - {v['platform']}\n  {(v['summary'] or 'No description')[:100]}..."
                    for v in vulns[:5]
                ])

                answer = f"Found {len(vulns)} vulnerability(ies):\n\n{vuln_list}"
                if len(vulns) > 5:
                    answer += f"\n\n...and {len(vulns) - 5} more."

                return {
                    'answer': answer,
                    'sources': sources,
                    'confidence': 0.9,
                    'suggested_actions': ['Explain vulnerability', 'Get remediation']
                }

        except Exception as e:
            logger.error(f"Failed to list vulnerabilities: {e}")
            return {
                'answer': f"Error querying vulnerabilities: {str(e)}",
                'sources': [],
                'confidence': 0.0
            }

    async def _handle_explain_query(self, question: str, entities: Dict) -> Dict[str, Any]:
        """Handle explain queries"""
        if entities.get('advisory_id'):
            platform = entities.get('platforms', ['IOS-XE'])[0]
            try:
                result = await self.explain(
                    psirt_id=entities['advisory_id'],
                    platform=platform,
                    question_type='why'
                )
                return {
                    'answer': result['explanation'],
                    'sources': [{'type': 'psirt', 'id': entities['advisory_id']}],
                    'confidence': result['confidence']
                }
            except Exception as e:
                return {
                    'answer': f"Could not explain {entities['advisory_id']}: {str(e)}",
                    'sources': [],
                    'confidence': 0.0
                }

        return await self._handle_freeform_query(question, entities)

    async def _handle_label_query(self, question: str, entities: Dict) -> Dict[str, Any]:
        """Handle label explanation queries"""
        if entities.get('labels'):
            label = entities['labels'][0]
            platform = entities.get('platforms', ['IOS-XE'])[0]

            # User-facing output: exclude anti-definitions (internal labeling guidance)
            definition = self.get_taxonomy_definitions([label], platform, include_anti_defs=False)
            return {
                'answer': definition,
                'sources': [{'type': 'taxonomy', 'platform': platform}],
                'confidence': 0.95
            }

        return await self._handle_freeform_query(question, entities)

    async def _handle_remediation_query(self, question: str, entities: Dict) -> Dict[str, Any]:
        """Handle remediation queries"""
        if entities.get('advisory_id'):
            platform = entities.get('platforms', ['IOS-XE'])[0]
            try:
                result = await self.remediate(
                    psirt_id=entities['advisory_id'],
                    platform=platform
                )

                # Format options
                options_text = "\n\n".join([
                    f"**Option {i+1}: {opt['title']}**\n{opt['description']}\nEffectiveness: {opt['effectiveness']}"
                    for i, opt in enumerate(result['options'])
                ])

                return {
                    'answer': f"Remediation options for {entities['advisory_id']}:\n\n{options_text}",
                    'sources': [{'type': 'remediation', 'id': entities['advisory_id']}],
                    'confidence': result['confidence']
                }
            except Exception as e:
                return {
                    'answer': f"Could not generate remediation: {str(e)}",
                    'sources': [],
                    'confidence': 0.0
                }

        return await self._handle_freeform_query(question, entities)

    async def _handle_summary_query(self, question: str, entities: Dict) -> Dict[str, Any]:
        """Handle summary queries"""
        timeframe = entities.get('timeframe', 'week')
        return await self.summary(period=timeframe, scope='all', format='brief')

    async def _handle_count_query(self, question: str, entities: Dict) -> Dict[str, Any]:
        """Handle count queries"""
        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()

                # Count vulnerabilities
                query = "SELECT COUNT(*) as cnt, platform FROM vulnerabilities"
                params = []

                if entities.get('platforms'):
                    placeholders = ','.join(['?' for _ in entities['platforms']])
                    query += f" WHERE platform IN ({placeholders})"
                    params.extend(entities['platforms'])

                query += " GROUP BY platform"

                cursor.execute(query, params)
                counts = {row['platform']: row['cnt'] for row in cursor.fetchall()}

                total = sum(counts.values())
                breakdown = ", ".join([f"{p}: {c}" for p, c in counts.items()])

                return {
                    'answer': f"Total: **{total}** vulnerabilities\n\nBy platform: {breakdown}",
                    'sources': [{'type': 'count', 'total': total}],
                    'confidence': 0.95
                }

        except Exception as e:
            return {
                'answer': f"Error counting: {str(e)}",
                'sources': [],
                'confidence': 0.0
            }

    async def _handle_freeform_query(self, question: str, entities: Dict) -> Dict[str, Any]:
        """
        Handle unknown queries - provide helpful guidance instead of LLM freeform.

        For questions that don't match our structured intents, guide users to
        questions we CAN answer well rather than relying on LLM which may
        hallucinate or produce low-quality responses.
        """
        # Instead of asking the LLM for freeform answers (which can leak prompts
        # or produce poor results), provide structured guidance
        question_lower = question.lower()

        # Check if this is a "why" follow-up (e.g., "why that device?")
        if 'why' in question_lower and len(question_lower) < 50:
            return {
                'answer': """I can explain "why" for specific items. Try asking:

- "What bugs affect [device name]?" - See the full bug list
- "Which devices have critical bugs?" - Risk-ranked device list
- "What should I focus on?" - Get prioritized recommendations

What would you like to know more about?""",
                'sources': [],
                'confidence': 0.8,
                'suggested_actions': ['View device details', 'Get recommendations', 'List critical bugs']
            }

        # Check if asking about capabilities
        if any(word in question_lower for word in ['can you', 'what can', 'how do i', 'help']):
            return {
                'answer': """**I can help you with:**

**Device Questions:**
- "What bugs affect C9200L?" - List bugs for a specific device
- "Which devices have critical bugs?" - See at-risk devices
- "What should I focus on?" - Get prioritized recommendations

**Bug/PSIRT Questions:**
- "List critical IOS-XE bugs" - Filter by severity and platform
- "Explain SEC_CoPP" - Get label definitions
- "How do I fix cisco-sa-xxx?" - Get remediation guidance

**Summary:**
- "Give me a summary" - Executive posture overview

What would you like to know?""",
                'sources': [],
                'confidence': 0.9,
                'suggested_actions': ['View recommendations', 'List devices', 'Get summary']
            }

        # Default: suggest structured queries
        return {
            'answer': f"""I'm not sure how to answer "{question[:50]}{'...' if len(question) > 50 else ''}"

**Try one of these instead:**

- "What bugs affect [device name]?" - See bugs for a device
- "Which devices have critical bugs?" - Risk-ranked list
- "What should I prioritize?" - Recommendations
- "Give me a summary" - Security posture overview
- "Explain [label name]" - Label definitions

What would you like to know?""",
            'sources': [],
            'confidence': 0.6,
            'suggested_actions': ['Get recommendations', 'List critical bugs', 'View summary']
        }

    # =========================================================================
    # Phase 4: Summary
    # =========================================================================

    async def summary(
        self,
        period: str = "week",
        scope: str = "all",
        format: str = "brief"
    ) -> Dict[str, Any]:
        """
        Generate executive summary of security posture.

        Shows bugs that affect YOUR inventory, not the entire database.
        This provides actionable, relevant counts for security posture.

        Args:
            period: Time period (week, month, or custom YYYY-MM-DD:YYYY-MM-DD)
            scope: What to summarize (all, critical, device:{id})
            format: Output format (brief, detailed, executive)
        """
        # Parse period
        if period == "week":
            start_date = datetime.now() - timedelta(days=7)
            period_str = f"Past 7 days"
        elif period == "month":
            start_date = datetime.now() - timedelta(days=30)
            period_str = f"Past 30 days"
        else:
            # Custom period
            period_str = period
            start_date = None

        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()

                # Get device inventory statistics
                device_query = """
                    SELECT discovery_status, COUNT(*) as cnt
                    FROM device_inventory
                    GROUP BY discovery_status
                """
                cursor.execute(device_query)
                device_counts = {row['discovery_status']: row['cnt'] for row in cursor.fetchall()}

                total_devices = sum(device_counts.values())
                discovered_devices = device_counts.get('success', 0)

                # Try to use real scan results first (most accurate)
                cursor.execute("""
                    SELECT last_scan_result
                    FROM device_inventory
                    WHERE discovery_status = 'success' AND last_scan_result IS NOT NULL
                """)
                last_scans = cursor.fetchall()
                inventory_devices_scanned = len(last_scans)
                scan_based_totals = {
                    # Bug totals (vuln_type='bug')
                    'total_bugs': 0,
                    'bug_critical_high': 0,
                    # PSIRT totals (vuln_type='psirt') - version+feature filtered
                    'total_psirts': 0,
                    'psirt_critical_high': 0,
                    # Combined totals (backward compat)
                    'critical_high': 0,
                    'medium_low': 0
                }

                for row in last_scans:
                    try:
                        scan_summary = json.loads(row['last_scan_result'])
                        # Bug counts (handle old field names for backward compat)
                        bugs = scan_summary.get('total_bugs') or scan_summary.get('total_vulnerabilities') or 0
                        scan_based_totals['total_bugs'] += int(bugs)
                        scan_based_totals['bug_critical_high'] += int(scan_summary.get('bug_critical_high', 0) or 0)
                        # PSIRT counts (properly filtered by version + features)
                        scan_based_totals['total_psirts'] += int(scan_summary.get('total_psirts', 0) or 0)
                        scan_based_totals['psirt_critical_high'] += int(scan_summary.get('psirt_critical_high', 0) or 0)
                        # Combined totals
                        scan_based_totals['critical_high'] += int(scan_summary.get('critical_high', 0) or 0)
                        scan_based_totals['medium_low'] += int(scan_summary.get('medium_low', 0) or 0)
                    except Exception as e:
                        logger.debug(f"Failed to parse last_scan_result: {e}")

                # Get unique platforms and versions from discovered devices
                cursor.execute("""
                    SELECT DISTINCT platform, version
                    FROM device_inventory
                    WHERE discovery_status IN ('success', 'manual') AND platform IS NOT NULL
                """)
                device_platforms = [(row['platform'], row['version']) for row in cursor.fetchall()]
                inventory_platforms = list(set([p for p, _ in device_platforms]))

                # Count bugs that affect YOUR inventory (not entire DB)
                # This provides actionable, relevant counts
                affecting_severity_counts = {1: 0, 2: 0, 3: 0, 4: 0}
                affecting_platform_counts = {}
                total_affecting_bugs = 0

                # Initialize PSIRT counts
                psirts_affecting_inventory = 0
                psirts_critical_high = 0

                if inventory_devices_scanned > 0:
                    # Use scan results when available (best accuracy - version+feature filtered)
                    total_affecting_bugs = scan_based_totals['total_bugs']
                    affecting_severity_counts[1] = scan_based_totals['bug_critical_high']
                    affecting_severity_counts[2] = 0  # Combined critical/high count stored together
                    affecting_severity_counts[3] = scan_based_totals['medium_low']
                    affecting_severity_counts[4] = 0
                    # PSIRTs are now properly filtered by version + features (not just platform)
                    psirts_affecting_inventory = scan_based_totals['total_psirts']
                    psirts_critical_high = scan_based_totals['psirt_critical_high']
                elif device_platforms:
                    # No scans yet: do not claim every DB bug applies. Require a scan to populate counts.
                    total_affecting_bugs = 0
                    affecting_platform_counts = {p: 0 for p, _ in device_platforms}
                    # PSIRTs also require a scan for accurate counts
                    psirts_affecting_inventory = 0
                    psirts_critical_high = 0

                critical_count = affecting_severity_counts.get(1, 0)
                high_count = affecting_severity_counts.get(2, 0)
                medium_low_count = affecting_severity_counts.get(3, 0) + affecting_severity_counts.get(4, 0)

                # Get total bugs in database for reference
                cursor.execute("SELECT COUNT(*) as cnt FROM vulnerabilities")
                total_db_bugs = cursor.fetchone()['cnt']

                # Query bugs by severity and type (separate bugs from PSIRTs)
                cursor.execute("""
                    SELECT severity, COUNT(*) as cnt
                    FROM vulnerabilities
                    WHERE vuln_type = 'bug'
                    GROUP BY severity
                """)
                bug_severity = {row['severity']: row['cnt'] for row in cursor.fetchall()}

                cursor.execute("""
                    SELECT severity, COUNT(*) as cnt
                    FROM vulnerabilities
                    WHERE vuln_type = 'psirt'
                    GROUP BY severity
                """)
                psirt_severity = {row['severity']: row['cnt'] for row in cursor.fetchall()}

                # Query bugs by platform (for separated metrics)
                cursor.execute("""
                    SELECT platform, COUNT(*) as cnt
                    FROM vulnerabilities
                    WHERE vuln_type = 'bug'
                    GROUP BY platform
                """)
                bug_by_platform = {row['platform'] or 'Unknown': row['cnt'] for row in cursor.fetchall()}

                cursor.execute("""
                    SELECT platform, COUNT(*) as cnt
                    FROM vulnerabilities
                    WHERE vuln_type = 'psirt'
                    GROUP BY platform
                """)
                psirt_by_platform = {row['platform'] or 'Unknown': row['cnt'] for row in cursor.fetchall()}

                # Determine risk assessment based on bugs affecting YOUR environment
                if critical_count > 10:
                    risk_level = "critical"
                elif critical_count > 0 or high_count > 20:
                    risk_level = "elevated"
                elif high_count > 0:
                    risk_level = "moderate"
                else:
                    risk_level = "low"

                # Build summary text based on format
                if format == "brief":
                    summary_text = f"""**Security Posture Summary ({period_str})**

📊 **Your Environment:**
- {total_affecting_bugs:,} bugs affect your inventory
- {critical_count} critical, {high_count} high severity
- {total_devices} devices ({discovered_devices} discovered)
{("- No device scans yet; run a scan to compute impact.") if inventory_devices_scanned == 0 else ""}

🔴 **Risk Level:** {risk_level.upper()}

_Database contains {total_db_bugs:,} total bugs across all platforms._"""

                elif format == "executive":
                    platform_breakdown = chr(10).join([
                        f"- {p}: {c:,} bugs" for p, c in affecting_platform_counts.items()
                    ]) if affecting_platform_counts else "- No discovered devices yet"

                    summary_text = f"""**Executive Summary: Security Posture ({period_str})**

**Environment Overview:**
{total_devices} network devices are inventoried, with {discovered_devices} fully discovered. Based on your inventory's platforms and versions, **{total_affecting_bugs:,} bugs** may affect your environment.
{("No device scans found; counts will remain zero until a scan is completed.") if inventory_devices_scanned == 0 else ""}

**Risk Assessment: {risk_level.upper()}**
- Critical bugs: {critical_count}
- High severity: {high_count}
- Medium/Low: {medium_low_count}

**Bugs by Platform (Your Inventory):**
{platform_breakdown}

**Recommended Actions:**
1. {"Address " + str(critical_count) + " critical bugs immediately" if critical_count > 0 else "No critical bugs - focus on high severity"}
2. {"Schedule remediation for " + str(high_count) + " high-severity bugs" if high_count > 0 else "Review medium/low priority items"}
3. {"Discover remaining " + str(total_devices - discovered_devices) + " pending devices" if discovered_devices < total_devices else "All devices discovered - maintain scanning schedule"}

_Note: Database tracks {total_db_bugs:,} total bugs. Posture shows only bugs affecting your inventory._"""

                else:  # detailed
                    summary_text = f"Detailed report with {total_affecting_bugs} bugs affecting your environment..."

                # Build critical actions
                critical_actions = []
                if critical_count > 0:
                    critical_actions.append({
                        'priority': 1,
                        'action': f'Address {critical_count} critical bugs',
                        'affected_devices': discovered_devices
                    })
                if high_count > 0:
                    critical_actions.append({
                        'priority': 2,
                        'action': f'Remediate {high_count} high-severity bugs',
                        'affected_devices': discovered_devices
                    })
                if discovered_devices < total_devices:
                    critical_actions.append({
                        'priority': 3,
                        'action': f'Complete discovery for {total_devices - discovered_devices} devices',
                        'affected_devices': total_devices - discovered_devices
                    })

                return {
                    'answer': summary_text,
                    'period': period_str,
                    'total_advisories': total_affecting_bugs,  # Bugs affecting YOUR inventory
                    'total_bugs_in_db': total_db_bugs,  # Total in database (for reference)
                    'inventory_devices_scanned': inventory_devices_scanned,
                    'inventory_critical_high': scan_based_totals.get('critical_high', 0),
                    'inventory_medium_low': scan_based_totals.get('medium_low', 0),
                    'affecting_environment': critical_count + high_count,
                    'summary_text': summary_text,
                    'risk_assessment': risk_level,
                    'critical_actions': critical_actions,
                    'trends': {
                        'by_severity': affecting_severity_counts,
                        'by_platform': affecting_platform_counts
                    },
                    'bugs': {
                        'total': sum(bug_severity.values()),
                        'critical_high': bug_severity.get(1, 0) + bug_severity.get(2, 0),
                        'by_platform': bug_by_platform
                    },
                    'psirts': {
                        'total': sum(psirt_severity.values()),
                        'critical_high': psirt_severity.get(1, 0) + psirt_severity.get(2, 0),
                        'by_platform': psirt_by_platform,
                        'affecting_inventory': psirts_affecting_inventory,
                        'inventory_critical_high': psirts_critical_high
                    },
                    'inventory_platforms': inventory_platforms,
                    'sources': [{'type': 'database', 'tables': ['vulnerabilities', 'device_inventory']}],
                    'confidence': 0.95
                }

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return {
                'answer': f"Error generating summary: {str(e)}",
                'period': period_str,
                'total_advisories': 0,
                'total_bugs_in_db': 0,
                'inventory_devices_scanned': 0,
                'inventory_critical_high': 0,
                'affecting_environment': 0,
                'summary_text': '',
                'risk_assessment': 'unknown',
                'critical_actions': [],
                'sources': [],
                'confidence': 0.0
            }


# =============================================================================
# Module-level singleton
# =============================================================================

_reasoning_engine_instance = None


def get_reasoning_engine(db_path: str = None) -> ReasoningEngine:
    """Get or create ReasoningEngine singleton"""
    global _reasoning_engine_instance

    if _reasoning_engine_instance is None:
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent / "vulnerability_db.sqlite")
        _reasoning_engine_instance = ReasoningEngine(db_path)

    return _reasoning_engine_instance
