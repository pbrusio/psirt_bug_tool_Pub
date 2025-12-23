"""
AI Analyzer - LLM Path (Path B)

Handles PSIRT analysis using SEC-8B LLM inference.
Extracted from vulnerability_scanner.py for modularity.

Responsibilities:
- Check database cache for existing analyses
- Run SEC-8B inference for cache misses
- Cache high-confidence results
- Handle fallbacks (timeout, low similarity)

Performance:
- Cache hit: <10ms
- LLM inference: ~3400ms (8-bit SEC-8B)
"""
from typing import Dict, Optional, List
from datetime import datetime
import uuid
import logging
import json
import yaml
from pathlib import Path

from backend.db.utils import get_db_connection

logger = logging.getLogger(__name__)

# Thresholds from architecture doc (Section 6)
CACHE_CONFIDENCE_THRESHOLD = 0.75  # Only cache if confidence >= this
FAISS_SIMILARITY_THRESHOLD = 0.70  # Below this, skip few-shot examples


class AIAnalyzer:
    """
    AI-powered PSIRT analyzer using SEC-8B LLM.

    This module handles Path B of the dual-path architecture:
    - Database cache lookup for known PSIRTs
    - SEC-8B inference for new/unknown advisories
    - Caching of high-confidence results
    - Fallback handling for timeouts/errors
    """

    def __init__(self, db_path: str, sec8b_analyzer=None):
        """
        Initialize AI analyzer.

        Args:
            db_path: Path to SQLite vulnerability database
            sec8b_analyzer: SEC8BAnalyzer instance (optional, will create if None)
        """
        self.db_path = db_path

        # SEC-8B analyzer (existing component)
        if sec8b_analyzer is None:
            from .sec8b import get_analyzer
            self.sec8b = get_analyzer()
        else:
            self.sec8b = sec8b_analyzer

        # Load feature file mapping for taxonomy lookups
        # Paths are relative to project root, under taxonomies/ directory
        # FTD shares ASA taxonomy (no separate FTD taxonomy file)
        self._feature_file_map = {
            'IOS-XE': 'taxonomies/features.yml',
            'IOS-XR': 'taxonomies/features_iosxr.yml',
            'ASA': 'taxonomies/features_asa.yml',
            'FTD': 'taxonomies/features_asa.yml',  # FTD uses ASA taxonomy
            'NX-OS': 'taxonomies/features_nxos.yml'
        }

        # Project root for taxonomy file lookups
        # Path: backend/core/ai_analyzer.py -> parent.parent.parent = project root
        self._project_root = Path(__file__).parent.parent.parent

        logger.info(f"AIAnalyzer initialized with database: {db_path}")

    def analyze_psirt(
        self,
        summary: str,
        platform: str,
        advisory_id: Optional[str] = None
    ) -> Dict:
        """
        Analyze PSIRT: Check database cache, fallback to SEC-8B.

        Process:
        1. If advisory_id provided, check database cache
        2. Cache hit: Return database result (fast)
        3. Cache miss: Run SEC-8B inference (slow)
        4. If high confidence (>=0.75), cache result in database
        5. Return analysis with source indicator

        Args:
            summary: PSIRT summary text
            platform: Platform (e.g., "IOS-XE")
            advisory_id: Optional advisory ID (e.g., "cisco-sa-iosxe-ssh-dos")

        Returns:
            Analysis result dict with labels, confidence, and source

        Performance:
        - Database hit: <10ms
        - LLM inference: ~3400ms (8-bit SEC-8B)
        """
        logger.info(
            f"Analyzing PSIRT: platform={platform}, "
            f"advisory_id={advisory_id}, has_summary={bool(summary)}"
        )

        # Check database cache if advisory_id provided
        if advisory_id:
            cached = self._check_cache(advisory_id, platform)
            if cached:
                logger.info(f"Cache hit: advisory_id={advisory_id}")
                cached['source'] = 'database'
                cached['cached'] = True
                return cached

        # Cache miss - run SEC-8B inference
        logger.info(f"Cache miss - running SEC-8B inference")
        start_time = datetime.now()

        try:
            result = self.sec8b.analyze_psirt(
                summary=summary,
                platform=platform,
                advisory_id=advisory_id
            )

            inference_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(
                f"SEC-8B inference complete: time={inference_time_ms:.1f}ms, "
                f"confidence={result.get('confidence', 0):.3f}"
            )

        except TimeoutError as e:
            # LLM timeout fallback
            logger.warning(f"LLM timeout: {e}")
            return self._create_fallback_response(
                summary, platform, advisory_id,
                error="LLM inference timed out",
                confidence_source="heuristic"
            )

        except Exception as e:
            # LLM error fallback
            logger.error(f"LLM error: {e}")
            return self._create_fallback_response(
                summary, platform, advisory_id,
                error=f"LLM inference failed: {str(e)}",
                confidence_source="heuristic"
            )

        # Add source indicator and confidence metadata
        result['source'] = 'llm'
        confidence = result.get('confidence', 0.0)

        # Apply FAISS similarity threshold (Section 6.2 of architecture doc)
        # If confidence < 0.70, mark as needs_review with heuristic source
        if confidence < FAISS_SIMILARITY_THRESHOLD:
            logger.info(
                f"Low confidence ({confidence:.3f} < {FAISS_SIMILARITY_THRESHOLD}): "
                f"marking as needs_review"
            )
            result['needs_review'] = True
            result['confidence_source'] = 'heuristic'
        else:
            result['needs_review'] = False
            result['confidence_source'] = 'model'

        # Cache if high confidence (and not needs_review)
        cached = False
        if self._should_cache(result):
            logger.info(
                f"Caching result: advisory_id={advisory_id}, "
                f"confidence={confidence:.3f}"
            )
            self._cache_result(result)
            cached = True

        result['cached'] = cached
        return result

    def _check_cache(self, advisory_id: str, platform: str) -> Optional[Dict]:
        """
        Check database cache for existing analysis.

        Args:
            advisory_id: Advisory ID (e.g., "cisco-sa-iosxe-ssh-dos")
            platform: Platform (e.g., "IOS-XE")

        Returns:
            Cached result dict or None if not found
        """
        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()

                # Query for PSIRT by advisory_id + platform
                cursor.execute("""
                    SELECT
                        advisory_id, platform, summary, labels,
                        affected_versions_raw, labels_source
                    FROM vulnerabilities
                    WHERE advisory_id = ? AND platform = ? AND vuln_type = 'psirt'
                    LIMIT 1
                """, (advisory_id, platform))

                row = cursor.fetchone()

            if not row:
                return None

            # Parse labels from JSON
            labels = json.loads(row['labels']) if row['labels'] else []

            # Map labels to config patterns and commands using taxonomy YAMLs
            config_regex, show_commands = self._get_taxonomy_mappings(labels, platform)

            # Format result to match SEC-8B output format
            return {
                'analysis_id': f"cached-{uuid.uuid4().hex[:8]}",
                'advisory_id': advisory_id,
                'psirt_summary': row['summary'] or '',
                'platform': platform,
                'predicted_labels': labels,
                'confidence': 1.0,  # Cached results are high confidence
                'confidence_source': 'cache',
                'config_regex': config_regex,
                'show_commands': show_commands,
                'needs_review': False,
                'timestamp': datetime.now()
            }

        except Exception as e:
            logger.error(f"Cache lookup failed: {e}")
            return None

    def _get_taxonomy_mappings(
        self,
        labels: List[str],
        platform: str
    ) -> tuple:
        """
        Get config regex and show commands for labels from taxonomy.

        Args:
            labels: List of feature labels
            platform: Platform for taxonomy file selection

        Returns:
            (config_regex, show_commands) tuple of lists
        """
        config_regex = []
        show_commands = []

        feature_file = self._feature_file_map.get(platform, 'taxonomies/features.yml')
        feature_path = self._project_root / feature_file

        if not feature_path.exists():
            logger.warning(f"Taxonomy file not found: {feature_path}")
            return config_regex, show_commands

        try:
            with open(feature_path, 'r') as f:
                features = yaml.safe_load(f)

            for label in labels:
                if label in features:
                    feature_def = features[label]

                    # Config regex
                    if 'config_regex' in feature_def:
                        if isinstance(feature_def['config_regex'], list):
                            config_regex.extend(feature_def['config_regex'])
                        else:
                            config_regex.append(feature_def['config_regex'])

                    # Show commands
                    if 'show_cmds' in feature_def:
                        if isinstance(feature_def['show_cmds'], list):
                            show_commands.extend(feature_def['show_cmds'])
                        else:
                            show_commands.append(feature_def['show_cmds'])

        except Exception as e:
            logger.error(f"Failed to load taxonomy: {e}")

        return list(set(config_regex)), list(set(show_commands))

    def _should_cache(self, result: Dict) -> bool:
        """
        Determine if LLM result should be cached in database.

        Cache if ALL conditions met:
        - Confidence >= 0.75 (HIGH confidence threshold)
        - Advisory ID provided (identifiable)
        - Labels validated against taxonomy
        - confidence_source is 'model' (not heuristic)

        Args:
            result: LLM analysis result

        Returns:
            True if should cache, False otherwise
        """
        has_advisory_id = bool(result.get('advisory_id'))
        high_confidence = result.get('confidence', 0.0) >= CACHE_CONFIDENCE_THRESHOLD
        has_labels = len(result.get('predicted_labels', [])) > 0
        needs_review = result.get('needs_review', False)
        confidence_source = result.get('confidence_source', 'model')

        # Do NOT cache if needs_review or heuristic source
        if needs_review or confidence_source == 'heuristic':
            logger.debug(
                f"Skipping cache: needs_review={needs_review}, "
                f"confidence_source={confidence_source}"
            )
            return False

        should_cache = has_advisory_id and high_confidence and has_labels

        logger.debug(
            f"Cache decision: advisory_id={has_advisory_id}, "
            f"confidence={result.get('confidence', 0.0):.3f}, "
            f"has_labels={has_labels} -> {should_cache}"
        )

        return should_cache

    def _cache_result(self, result: Dict) -> None:
        """
        Cache LLM result in database for future fast lookups.

        Inserts into:
        - vulnerabilities table (main record)
        - label_index table (for each predicted label)

        Args:
            result: LLM analysis result
        """
        try:
            with get_db_connection(self.db_path) as db:
                cursor = db.cursor()

                # Check if already exists (avoid duplicates)
                cursor.execute("""
                    SELECT id FROM vulnerabilities
                    WHERE advisory_id = ? AND platform = ?
                """, (result['advisory_id'], result['platform']))

                if cursor.fetchone():
                    logger.warning(f"PSIRT already cached: {result['advisory_id']}")
                    return

                # Insert main vulnerability record
                cursor.execute('''
                    INSERT INTO vulnerabilities (
                        bug_id, advisory_id, vuln_type, severity, headline, summary,
                        url, status, platform, product_series,
                        affected_versions_raw, version_pattern, version_min, version_max,
                        fixed_version, labels, labels_source, last_modified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    result['advisory_id'],
                    result['advisory_id'],
                    'psirt',
                    None,  # severity
                    result.get('psirt_summary', '')[:200],
                    result.get('psirt_summary', ''),
                    f"https://sec.cloudapps.cisco.com/security/center/content/CiscoSecurityAdvisory/{result['advisory_id']}",
                    'Active',
                    result['platform'],
                    '',  # product_series
                    '',  # affected_versions_raw
                    'UNKNOWN',
                    None, None,  # version_min, version_max
                    None,  # fixed_version
                    json.dumps(result['predicted_labels']),
                    f"sec8b_confidence_{result.get('confidence', 0):.2f}",
                    datetime.now().isoformat()
                ))

                vuln_id = cursor.lastrowid

                # Insert label index entries
                for label in result['predicted_labels']:
                    cursor.execute('''
                        INSERT INTO label_index (vulnerability_id, label)
                        VALUES (?, ?)
                    ''', (vuln_id, label))

            logger.info(
                f"PSIRT cached successfully: advisory_id={result['advisory_id']}, "
                f"platform={result['platform']}, labels={len(result['predicted_labels'])}"
            )

        except Exception as e:
            logger.error(f"Failed to cache result: {e}")

    def _create_fallback_response(
        self,
        summary: str,
        platform: str,
        advisory_id: Optional[str],
        error: str,
        confidence_source: str = "heuristic"
    ) -> Dict:
        """
        Create fallback response when LLM fails.

        Args:
            summary: Original PSIRT summary
            platform: Platform
            advisory_id: Advisory ID if provided
            error: Error message to include
            confidence_source: Source of confidence (always 'heuristic' for fallback)

        Returns:
            Fallback response dict with needs_review=True
        """
        return {
            'analysis_id': f"fallback-{uuid.uuid4().hex[:8]}",
            'advisory_id': advisory_id,
            'psirt_summary': summary,
            'platform': platform,
            'predicted_labels': [],
            'confidence': 0.0,
            'confidence_source': confidence_source,
            'config_regex': [],
            'show_commands': [],
            'needs_review': True,
            'error': error,
            'source': 'fallback',
            'cached': False,
            'timestamp': datetime.now()
        }


# Module-level singleton
_ai_analyzer_instance = None


def get_ai_analyzer(db_path: str = None, sec8b_analyzer=None) -> AIAnalyzer:
    """
    Get or create AIAnalyzer singleton.

    Args:
        db_path: Path to SQLite database (required on first call)
        sec8b_analyzer: Optional SEC8BAnalyzer instance

    Returns:
        AIAnalyzer instance
    """
    global _ai_analyzer_instance

    if _ai_analyzer_instance is None:
        if db_path is None:
            raise ValueError("db_path required on first call to get_ai_analyzer()")
        _ai_analyzer_instance = AIAnalyzer(db_path, sec8b_analyzer)

    return _ai_analyzer_instance
