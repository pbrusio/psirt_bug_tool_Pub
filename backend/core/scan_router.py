"""
Scan Router - Decision Logic and Orchestration

Routes requests to the appropriate scanning path:
- Path A (DatabaseScanner): Fast database queries for known vulnerabilities
- Path B (AIAnalyzer): LLM inference for new/unknown PSIRTs

Responsibilities:
- Determine which path to use based on request type
- Coordinate between scanners
- Handle unified scanning (future: /scan-all)
- Apply rate limiting and circuit breakers (future)

This module is the "traffic cop" that decides how to handle each request.
"""
from typing import Dict, List, Optional
from datetime import datetime
import logging

from .db_scanner import DatabaseScanner, get_db_scanner
from .ai_analyzer import AIAnalyzer, get_ai_analyzer

logger = logging.getLogger(__name__)


class ScanRouter:
    """
    Routes scanning requests to appropriate backend.

    Decision Logic:
    - scan_device() -> Always use DatabaseScanner (Path A)
    - analyze_psirt() -> Use AIAnalyzer (Path B) with cache check
    - scan_all() -> Orchestrate both paths (future)

    The router maintains references to both scanners and coordinates
    requests between them.
    """

    def __init__(self, db_path: str, sec8b_analyzer=None):
        """
        Initialize router with both scanning backends.

        Args:
            db_path: Path to SQLite vulnerability database
            sec8b_analyzer: Optional SEC8BAnalyzer instance for AI path
        """
        self.db_path = db_path

        # Initialize both scanners
        self._db_scanner = DatabaseScanner(db_path)
        self._ai_analyzer = AIAnalyzer(db_path, sec8b_analyzer)

        logger.info(f"ScanRouter initialized with database: {db_path}")

    @property
    def db_scanner(self) -> DatabaseScanner:
        """Get the database scanner instance."""
        return self._db_scanner

    @property
    def ai_analyzer(self) -> AIAnalyzer:
        """Get the AI analyzer instance."""
        return self._ai_analyzer

    # =========================================================================
    # PATH A: DATABASE SCANNING (delegated)
    # =========================================================================

    def scan_device(
        self,
        platform: str,
        version: str,
        labels: Optional[List[str]] = None,
        hardware_model: Optional[str] = None,
        severity_filter: Optional[List[int]] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> Dict:
        """
        Route to DatabaseScanner for fast vulnerability lookup.

        This is Path A - the fast path using pre-indexed database queries.

        Args:
            platform: Device platform (e.g., "IOS-XE")
            version: Device software version (e.g., "17.3.5")
            labels: Optional list of configured feature labels
            hardware_model: Optional hardware model (e.g., "Cat9300")
            severity_filter: Optional list of severity levels to include
            limit: Optional max results to return
            offset: Pagination offset

        Returns:
            Scan result dict from DatabaseScanner

        Performance: <10ms typical
        """
        logger.debug(f"Routing scan_device to DatabaseScanner: platform={platform}")

        return self._db_scanner.scan_device(
            platform=platform,
            version=version,
            labels=labels,
            hardware_model=hardware_model,
            severity_filter=severity_filter,
            limit=limit,
            offset=offset
        )

    # =========================================================================
    # PATH B: AI ANALYSIS (delegated)
    # =========================================================================

    def analyze_psirt(
        self,
        summary: str,
        platform: str,
        advisory_id: Optional[str] = None
    ) -> Dict:
        """
        Route to AIAnalyzer for PSIRT analysis.

        This is Path B - uses LLM inference for new/unknown advisories.
        AIAnalyzer handles:
        - Database cache check (fast if cached)
        - SEC-8B inference (slow for new PSIRTs)
        - Auto-caching of high-confidence results

        Args:
            summary: PSIRT summary text
            platform: Platform (e.g., "IOS-XE")
            advisory_id: Optional advisory ID for cache lookup

        Returns:
            Analysis result dict from AIAnalyzer

        Performance:
        - Cache hit: <10ms
        - LLM inference: ~3400ms
        """
        logger.debug(f"Routing analyze_psirt to AIAnalyzer: platform={platform}")

        return self._ai_analyzer.analyze_psirt(
            summary=summary,
            platform=platform,
            advisory_id=advisory_id
        )

    # =========================================================================
    # UNIFIED OPERATIONS (future)
    # =========================================================================

    def scan_all(
        self,
        platform: str,
        version: str,
        labels: Optional[List[str]] = None,
        hardware_model: Optional[str] = None,
        include_psirt_analysis: bool = False,
        psirt_summaries: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Unified scanning: Combine database scan with optional PSIRT analysis.

        Future enhancement for /scan-all endpoint.

        Process:
        1. Run database scan (Path A) - always
        2. If include_psirt_analysis:
           - Run AI analysis on any provided PSIRT summaries (Path B)
           - Merge results

        Args:
            platform: Device platform
            version: Device software version
            labels: Optional feature labels
            hardware_model: Optional hardware model
            include_psirt_analysis: Whether to include PSIRT analysis
            psirt_summaries: List of PSIRT summaries to analyze

        Returns:
            Combined scan result with both paths' outputs
        """
        start_time = datetime.now()

        # Path A: Database scan (always)
        db_result = self.scan_device(
            platform=platform,
            version=version,
            labels=labels,
            hardware_model=hardware_model
        )

        result = {
            'scan_id': db_result['scan_id'],
            'platform': platform,
            'version': version,
            'hardware_model': hardware_model,
            'features': labels,
            'database_scan': db_result,
            'psirt_analyses': [],
            'timestamp': datetime.now()
        }

        # Path B: PSIRT analysis (optional)
        if include_psirt_analysis and psirt_summaries:
            for psirt in psirt_summaries:
                try:
                    analysis = self.analyze_psirt(
                        summary=psirt.get('summary', ''),
                        platform=platform,
                        advisory_id=psirt.get('advisory_id')
                    )
                    result['psirt_analyses'].append(analysis)
                except Exception as e:
                    logger.error(f"PSIRT analysis failed: {e}")
                    result['psirt_analyses'].append({
                        'advisory_id': psirt.get('advisory_id'),
                        'error': str(e),
                        'source': 'error'
                    })

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        result['total_time_ms'] = round(elapsed_ms, 2)

        logger.info(
            f"Unified scan complete: scan_id={result['scan_id']}, "
            f"db_bugs={len(db_result['bugs'])}, "
            f"psirt_analyses={len(result['psirt_analyses'])}, "
            f"time={elapsed_ms:.1f}ms"
        )

        return result

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_bug_details(self, bug_id: str) -> Optional[Dict]:
        """
        Get full details for a specific bug.

        Delegates to DatabaseScanner.

        Args:
            bug_id: Bug ID (CSCxxxx)

        Returns:
            Full bug dict or None if not found
        """
        return self._db_scanner.get_bug_details(bug_id)

    def health_check(self) -> Dict:
        """
        Check health of scanning backends.

        Returns:
            Health status dict for monitoring/observability
        """
        return {
            'router': 'healthy',
            'db_scanner': 'healthy' if self._db_scanner else 'unavailable',
            'ai_analyzer': 'healthy' if self._ai_analyzer else 'unavailable',
            'db_path': self.db_path,
            'timestamp': datetime.now().isoformat()
        }


# Module-level singleton
_router_instance = None


def get_router(db_path: str = None, sec8b_analyzer=None) -> ScanRouter:
    """
    Get or create ScanRouter singleton.

    Args:
        db_path: Path to SQLite database (required on first call)
        sec8b_analyzer: Optional SEC8BAnalyzer instance

    Returns:
        ScanRouter instance
    """
    global _router_instance

    if _router_instance is None:
        if db_path is None:
            raise ValueError("db_path required on first call to get_router()")
        _router_instance = ScanRouter(db_path, sec8b_analyzer)

    return _router_instance
