#!/usr/bin/env python3
"""
Cisco Vulnerability Data Fetcher
================================
Fetches PSIRTs, Bugs, and Security Advisories from Cisco APIs.
Designed to integrate with the Offline Update Packager.

Supports:
- PSIRT API (Security Advisories)
- Bug API (Bug Search)
- Automatic OAuth2 token management

Usage:
    python cisco_vuln_fetcher.py --mode psirt --days 30 --output psirts.json
    python cisco_vuln_fetcher.py --mode bugs --keyword "memory leak" --output bugs.json
    python cisco_vuln_fetcher.py --mode all --days 7 --output vuln_data.json

Author: Generated for PSIRT Identity Labeling Pipeline
"""

import os
import sys
import json
import logging
import argparse
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict, field
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class VulnerabilityItem:
    """Normalized vulnerability item for the labeling pipeline."""
    advisoryId: str
    summary: str
    platform: str
    type: str  # "PSIRT" or "BUG"
    severity: Optional[str] = None
    cves: Optional[List[str]] = None
    first_published: Optional[str] = None
    last_updated: Optional[str] = None
    products: Optional[List[str]] = None
    url: Optional[str] = None

    # Labeling fields (populated by Frontier or local model)
    labels: List[str] = field(default_factory=list)
    confidence: float = 0.0
    needs_label: bool = True  # Set to False after labeling

    # Extended metadata for DB compatibility
    hardware_models: Optional[List[str]] = None
    affected_versions: Optional[List[str]] = None
    fixed_versions: Optional[List[str]] = None


# Rate limiting configuration based on Cisco API docs
# Per Application: 5 calls/sec, 30 calls/min, 5000 calls/day
RATE_LIMIT_DELAY = 2.0  # seconds between requests (safe: 30 req/min = 1 req/2sec)


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, min_interval: float = RATE_LIMIT_DELAY):
        self.min_interval = min_interval
        self._last_call: Optional[float] = None

    def wait(self):
        """Wait if necessary to respect rate limits."""
        if self._last_call is not None:
            elapsed = time.time() - self._last_call
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                logger.debug(f"Rate limit: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
        self._last_call = time.time()


class CiscoAPIError(Exception):
    """Custom exception for Cisco API errors."""
    pass


class CiscoAuthManager:
    """Manages OAuth2 authentication for Cisco APIs."""
    
    OAUTH_URL = "https://id.cisco.com/oauth2/default/v1/token"
    TOKEN_REFRESH_MARGIN = 300  # 5 minutes before expiry
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self.session = requests.Session()
        
    def get_token(self) -> str:
        """Get a valid OAuth2 token, refreshing if necessary."""
        if self._is_token_valid():
            return self._token
            
        logger.info("🔐 Fetching new OAuth2 token...")
        
        try:
            response = self.session.post(
                self.OAUTH_URL,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            self._token = data['access_token']
            expires_in = data.get('expires_in', 3600)
            self._token_expiry = datetime.now() + timedelta(seconds=expires_in)
            
            logger.info(f"   Token acquired, expires in {expires_in}s")
            return self._token
            
        except requests.RequestException as e:
            raise CiscoAPIError(f"OAuth2 authentication failed: {e}")
            
    def _is_token_valid(self) -> bool:
        """Check if the current token is still valid."""
        if not self._token or not self._token_expiry:
            return False
        return datetime.now() < (self._token_expiry - timedelta(seconds=self.TOKEN_REFRESH_MARGIN))


class CiscoPSIRTClient:
    """Client for Cisco PSIRT (Security Advisory) API."""

    BASE_URL = "https://apix.cisco.com/security/advisories/v2"

    def __init__(self, auth_manager: CiscoAuthManager, rate_limiter: Optional[RateLimiter] = None):
        self.auth = auth_manager
        self.session = requests.Session()
        self.rate_limiter = rate_limiter or RateLimiter()

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make an authenticated API request with rate limiting."""
        self.rate_limiter.wait()  # Respect rate limits
        token = self.auth.get_token()

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise CiscoAPIError(f"PSIRT API request failed: {e}")
            
    def get_latest(self, count: int = 25) -> List[Dict]:
        """Get the latest N security advisories."""
        logger.info(f"📥 Fetching latest {count} PSIRTs...")
        data = self._make_request(f"/latest/{count}")
        return data.get('advisories', [])
        
    def get_by_severity(self, severity: str, page_size: int = 50) -> List[Dict]:
        """Get advisories by severity (critical, high, medium, low)."""
        logger.info(f"📥 Fetching {severity} severity PSIRTs...")
        data = self._make_request(f"/severity/{severity}", {'pageSize': page_size})
        return data.get('advisories', [])
        
    def get_by_date_range(self, start_date: str, end_date: str, page_size: int = 100) -> List[Dict]:
        """Get advisories published within a date range (YYYY-MM-DD format). Single page only."""
        logger.info(f"📥 Fetching PSIRTs from {start_date} to {end_date}...")
        data = self._make_request("/all/firstpublished", {
            'startDate': start_date,
            'endDate': end_date,
            'pageSize': page_size
        })
        return data.get('advisories', [])

    def get_by_date_range_paginated(
        self,
        start_date: str,
        end_date: str,
        page_size: int = 100,
        max_pages: int = 50
    ) -> List[Dict]:
        """
        Get ALL advisories in a date range with proper pagination.

        Uses pageIndex/pageSize pagination as documented in Cisco API docs.
        Rate limiting is applied automatically via _make_request().

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            page_size: Results per page (max 100)
            max_pages: Safety limit to prevent infinite loops

        Returns:
            List of all advisories in the date range
        """
        logger.info(f"📥 Fetching PSIRTs from {start_date} to {end_date} (paginated)...")
        all_advisories: List[Dict] = []
        page_index = 1

        while page_index <= max_pages:
            try:
                data = self._make_request("/all/firstpublished", {
                    'startDate': start_date,
                    'endDate': end_date,
                    'pageIndex': page_index,
                    'pageSize': page_size
                })
            except CiscoAPIError as e:
                # Handle 406 errors gracefully - endpoint can be flaky
                if "406" in str(e):
                    logger.warning(f"   ⚠️  Got 406 error on page {page_index}, stopping pagination")
                    break
                raise

            advisories = data.get('advisories', [])
            if not advisories:
                logger.info(f"   Page {page_index}: No more results")
                break

            all_advisories.extend(advisories)

            # Check pagination info
            paging = data.get('paging', {})
            total_count = paging.get('count', len(advisories))
            next_page = paging.get('next', 'NA')

            logger.info(f"   Page {page_index}: {len(advisories)} advisories (total: {total_count})")

            # Stop if no next page or we've fetched all
            if next_page == 'NA' or len(all_advisories) >= total_count:
                break

            page_index += 1

        logger.info(f"   ✅ Total fetched: {len(all_advisories)} PSIRTs")
        return all_advisories

    def get_by_year_paginated(self, year: int, page_size: int = 100, max_pages: int = 20) -> List[Dict]:
        """
        Get ALL advisories for a specific year with pagination.

        Fallback method when date-range endpoint is flaky.

        Args:
            year: Year to fetch (e.g., 2024)
            page_size: Results per page
            max_pages: Safety limit

        Returns:
            List of all advisories for the year
        """
        logger.info(f"📥 Fetching PSIRTs for year {year} (paginated)...")
        all_advisories: List[Dict] = []
        page_index = 1

        while page_index <= max_pages:
            try:
                data = self._make_request(f"/year/{year}", {
                    'pageIndex': page_index,
                    'pageSize': page_size
                })
            except CiscoAPIError as e:
                if "406" in str(e) or "404" in str(e):
                    logger.warning(f"   ⚠️  Got error on page {page_index}, stopping")
                    break
                raise

            advisories = data.get('advisories', [])
            if not advisories:
                break

            all_advisories.extend(advisories)

            paging = data.get('paging', {})
            total_count = paging.get('count', len(advisories))
            next_page = paging.get('next', 'NA')

            logger.info(f"   Page {page_index}: {len(advisories)} advisories")

            if next_page == 'NA' or len(all_advisories) >= total_count:
                break

            page_index += 1

        logger.info(f"   ✅ Total for {year}: {len(all_advisories)} PSIRTs")
        return all_advisories
        
    def get_by_year(self, year: int) -> List[Dict]:
        """Get all advisories for a specific year."""
        logger.info(f"📥 Fetching PSIRTs for year {year}...")
        data = self._make_request(f"/year/{year}")
        return data.get('advisories', [])
        
    def get_by_cve(self, cve_id: str) -> List[Dict]:
        """Get advisory by CVE ID."""
        logger.info(f"📥 Fetching PSIRT for {cve_id}...")
        data = self._make_request(f"/cve/{cve_id}")
        advisories = data.get('advisories', [])
        if not advisories and data.get('advisory'):
            advisories = [data['advisory']]
        return advisories
        
    def get_by_advisory_id(self, advisory_id: str) -> Optional[Dict]:
        """Get a specific advisory by ID."""
        logger.info(f"📥 Fetching PSIRT {advisory_id}...")
        data = self._make_request(f"/advisory/{advisory_id}")
        return data.get('advisory') or (data.get('advisories', [None])[0])


class CiscoBugClient:
    """Client for Cisco Bug Search API."""

    BASE_URL = "https://apix.cisco.com/bug/v2.0"

    def __init__(self, auth_manager: CiscoAuthManager, rate_limiter: Optional[RateLimiter] = None):
        self.auth = auth_manager
        self.session = requests.Session()
        self.rate_limiter = rate_limiter or RateLimiter()

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make an authenticated API request with rate limiting."""
        self.rate_limiter.wait()  # Respect rate limits
        token = self.auth.get_token()

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise CiscoAPIError(f"Bug API request failed: {e}")
            
    def search_by_keyword(self, keyword: str, severity: Optional[str] = None, 
                          status: Optional[str] = None, page_size: int = 100,
                          max_pages: int = 10) -> List[Dict]:
        """Search bugs by keyword with simple pagination."""
        logger.info(f"📥 Searching bugs for '{keyword}'...")
        
        all_bugs: List[Dict] = []
        page_index = 1
        
        status_map = {'open': 'O', 'fixed': 'F', 'terminated': 'T'}
        
        while page_index <= max_pages:
            params = {'page_index': page_index, 'page_size': page_size}
            if severity:
                params['severity'] = severity
            if status:
                params['status'] = status_map.get(status.lower(), status)
                
            endpoint = f"/bugs/keyword/{requests.utils.quote(keyword)}"
            data = self._make_request(endpoint, params)
            page_bugs = data.get('bugs', [])
            if not page_bugs:
                break
            
            all_bugs.extend(page_bugs)
            
            # Stop early if fewer results than the page size (no more pages)
            if len(page_bugs) < page_size:
                break
            page_index += 1
        
        return all_bugs
        
    def search_by_product(self, product_series: str, page_size: int = 50) -> List[Dict]:
        """Search bugs by product series."""
        logger.info(f"📥 Fetching bugs for product '{product_series}'...")
        
        endpoint = f"/bugs/products/product_series/{requests.utils.quote(product_series)}"
        data = self._make_request(endpoint, {'page_size': page_size})
        return data.get('bugs', [])
        
    def get_bug_details(self, bug_ids: List[str]) -> List[Dict]:
        """Get details for specific bug IDs."""
        logger.info(f"📥 Fetching details for {len(bug_ids)} bugs...")
        
        # API accepts comma-separated bug IDs
        endpoint = f"/bugs/bug_ids/{','.join(bug_ids)}"
        data = self._make_request(endpoint)
        return data.get('bugs', [])
        
    def search_by_modified_date(self, start_date: str, end_date: str, 
                                 page_size: int = 50) -> List[Dict]:
        """Search bugs modified within a date range."""
        logger.info(f"📥 Fetching bugs modified from {start_date} to {end_date}...")
        
        params = {
            'modified_date': f"{start_date}~{end_date}",
            'page_size': page_size
        }
        data = self._make_request("/bugs/keyword/security", params)  # Broad search
        return data.get('bugs', [])


class VulnerabilityFetcher:
    """
    Main class for fetching and normalizing vulnerability data.
    Outputs data compatible with the Offline Update Packager.
    """

    # Platform inference mapping based on keywords in product names
    PLATFORM_KEYWORDS = {
        'IOS-XE': ['ios xe', 'ios-xe', 'catalyst', 'c9', 'c3', 'isr', 'asr 1'],
        'IOS-XR': ['ios xr', 'ios-xr', 'asr 9', 'ncs', 'xr software'],
        'NX-OS': ['nx-os', 'nexus', 'nxos', 'aci', 'mds'],
        'ASA': ['asa', 'firepower', 'ftd', 'adaptive security'],
        'IOS': ['ios software', 'cisco ios']
    }

    def __init__(self, client_id: str, client_secret: str):
        self.auth = CiscoAuthManager(client_id, client_secret)
        # Share a single rate limiter across both clients to stay within API limits
        self.rate_limiter = RateLimiter()
        self.psirt_client = CiscoPSIRTClient(self.auth, self.rate_limiter)
        self.bug_client = CiscoBugClient(self.auth, self.rate_limiter)
        
    def infer_platform(self, advisory: Dict) -> str:
        """Infer the platform from advisory/bug metadata."""
        # Check product names
        products = advisory.get('productNames', []) or advisory.get('products', [])
        if isinstance(products, str):
            products = [products]
            
        # Also check title and summary
        text_to_check = ' '.join([
            advisory.get('advisoryTitle', ''),
            advisory.get('headline', ''),
            advisory.get('summary', ''),
            ' '.join(products)
        ]).lower()
        
        for platform, keywords in self.PLATFORM_KEYWORDS.items():
            if any(kw in text_to_check for kw in keywords):
                return platform
                
        return 'Unknown'
        
    def normalize_psirt(self, advisory: Dict) -> VulnerabilityItem:
        """Normalize a PSIRT advisory to our standard format."""
        advisory_id = advisory.get('advisoryId', 'Unknown')
        
        # Build summary from title + description if available
        summary = advisory.get('advisoryTitle', '')
        if advisory.get('summary'):
            summary = f"{summary}. {advisory['summary']}"
            
        return VulnerabilityItem(
            advisoryId=advisory_id,
            summary=summary,
            platform=self.infer_platform(advisory),
            type="PSIRT",
            severity=advisory.get('severity', advisory.get('sir')),
            cves=advisory.get('cves', []),
            first_published=advisory.get('firstPublished'),
            last_updated=advisory.get('lastUpdated'),
            products=advisory.get('productNames', []),
            url=f"https://tools.cisco.com/security/center/content/CiscoSecurityAdvisory/{advisory_id}"
        )
        
    def normalize_bug(self, bug: Dict) -> VulnerabilityItem:
        """Normalize a bug to our standard format."""
        bug_id = bug.get('bug_id', bug.get('id', 'Unknown'))
        
        return VulnerabilityItem(
            advisoryId=bug_id,
            summary=bug.get('headline', bug.get('description', '')),
            platform=self.infer_platform(bug),
            type="BUG",
            severity=str(bug.get('severity', '')),
            cves=bug.get('cves', []),
            first_published=bug.get('created_date'),
            last_updated=bug.get('last_modified_date'),
            products=bug.get('products', []),
            url=f"https://bst.cloudapps.cisco.com/bugsearch/bug/{bug_id}"
        )
        
    def fetch_recent_psirts(self, days: int = 30, use_pagination: bool = True) -> List[VulnerabilityItem]:
        """
        Fetch PSIRTs from the last N days.

        Args:
            days: Number of days to look back
            use_pagination: If True, uses paginated API (slower but complete).
                           If False, falls back to latest 100.

        Returns:
            List of normalized VulnerabilityItem objects
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        cutoff = datetime.now() - timedelta(days=days)

        advisories = []

        if use_pagination:
            # Strategy 1: Try paginated date-range endpoint
            try:
                advisories = self.psirt_client.get_by_date_range_paginated(start_date, end_date)
                logger.info(f"   📊 Paginated fetch returned {len(advisories)} PSIRTs")
            except CiscoAPIError as e:
                logger.warning(f"   ⚠️  Paginated date-range failed: {e}")
                # Strategy 2: Fallback to year-based pagination if spanning years
                current_year = datetime.now().year
                start_year = (datetime.now() - timedelta(days=days)).year

                try:
                    for year in range(start_year, current_year + 1):
                        year_advisories = self.psirt_client.get_by_year_paginated(year)
                        advisories.extend(year_advisories)
                    logger.info(f"   📊 Year-based fetch returned {len(advisories)} PSIRTs")
                except CiscoAPIError:
                    logger.warning("   ⚠️  Year-based fetch also failed, using latest fallback")
                    advisories = []

        # Strategy 3: Final fallback to latest N (quick but may miss older items)
        if not advisories:
            logger.info("   📊 Using /latest fallback...")
            advisories = self.psirt_client.get_latest(100)

        # Filter by date client-side (for fallback scenarios or to ensure date compliance)
        filtered = []
        for adv in advisories:
            try:
                pub_str = adv.get('firstPublished', '')
                if pub_str:
                    pub_date = datetime.strptime(pub_str.split('T')[0], '%Y-%m-%d')
                    if pub_date >= cutoff:
                        filtered.append(adv)
                else:
                    # Include if no date (be conservative)
                    filtered.append(adv)
            except (ValueError, TypeError):
                # Include if date parsing fails
                filtered.append(adv)

        # Use filtered list, fallback to all if filtering removed everything
        source = filtered if filtered else advisories
        logger.info(f"   ✅ After date filtering: {len(source)} PSIRTs")

        return [self.normalize_psirt(a) for a in source]
        
    def fetch_critical_psirts(self, count: int = 50) -> List[VulnerabilityItem]:
        """Fetch critical and high severity PSIRTs."""
        results = []
        
        for severity in ['critical', 'high']:
            advisories = self.psirt_client.get_by_severity(severity, page_size=count)
            results.extend([self.normalize_psirt(a) for a in advisories])
            
        return results
        
    def fetch_latest_psirts(self, count: int = 25) -> List[VulnerabilityItem]:
        """Fetch the latest N PSIRTs."""
        advisories = self.psirt_client.get_latest(count)
        return [self.normalize_psirt(a) for a in advisories]
        
    def fetch_bugs_by_keyword(self, keyword: str, severity: Optional[str] = None) -> List[VulnerabilityItem]:
        """Fetch bugs matching a keyword."""
        bugs = self.bug_client.search_by_keyword(keyword, severity=severity)
        return [self.normalize_bug(b) for b in bugs]
        
    def fetch_bugs_by_product(self, product: str) -> List[VulnerabilityItem]:
        """Fetch bugs for a specific product."""
        bugs = self.bug_client.search_by_product(product)
        return [self.normalize_bug(b) for b in bugs]
        
    def fetch_all(self, days: int = 30, bug_keywords: Optional[List[str]] = None) -> Dict[str, List[VulnerabilityItem]]:
        """
        Fetch all vulnerability data for the pipeline.
        
        Returns:
            Dictionary with 'psirts' and 'bugs' keys containing normalized items.
        """
        results = {
            'psirts': [],
            'bugs': [],
            'metadata': {
                'fetch_date': datetime.now().isoformat(),
                'days_lookback': days
            }
        }
        
        # Fetch PSIRTs
        logger.info("=" * 50)
        logger.info("📡 FETCHING PSIRT DATA")
        logger.info("=" * 50)
        
        try:
            results['psirts'] = self.fetch_recent_psirts(days)
            logger.info(f"   ✅ Fetched {len(results['psirts'])} PSIRTs")
        except CiscoAPIError as e:
            logger.error(f"   ❌ PSIRT fetch failed: {e}")
            
        # Fetch Bugs
        if bug_keywords:
            logger.info("=" * 50)
            logger.info("📡 FETCHING BUG DATA")
            logger.info("=" * 50)
            
            for keyword in bug_keywords:
                try:
                    bugs = self.fetch_bugs_by_keyword(keyword)
                    results['bugs'].extend(bugs)
                    logger.info(f"   ✅ Fetched {len(bugs)} bugs for '{keyword}'")
                except CiscoAPIError as e:
                    logger.error(f"   ❌ Bug fetch failed for '{keyword}': {e}")
                    
        # Deduplicate bugs
        seen_ids = set()
        unique_bugs = []
        for bug in results['bugs']:
            if bug.advisoryId not in seen_ids:
                seen_ids.add(bug.advisoryId)
                unique_bugs.append(bug)
        results['bugs'] = unique_bugs
        
        return results


def load_config() -> Dict[str, str]:
    """Load configuration from environment variables."""
    load_dotenv()
    
    # Try multiple possible env var names (compatible with SS_Pipeline and MCP server)
    client_id = (
        os.getenv('CISCO_CLIENT_ID') or 
        os.getenv('CISCO_CLIENT_ID_SN2INFO') or
        os.getenv('CISCO_CLIENT_ID_TARA')
    )
    
    client_secret = (
        os.getenv('CISCO_CLIENT_SECRET') or 
        os.getenv('CISCO_CLIENT_SECRET_SN2INFO') or
        os.getenv('CISCO_CLIENT_SECRET_TARA')
    )
    
    if not client_id or not client_secret:
        raise ValueError(
            "Missing Cisco API credentials. Set CISCO_CLIENT_ID and CISCO_CLIENT_SECRET "
            "environment variables or create a .env file."
        )
        
    return {
        'client_id': client_id,
        'client_secret': client_secret
    }


def export_for_packager(items: List[VulnerabilityItem], output_path: str):
    """Export items in the format expected by Offline Update Packager."""
    # Convert to packager-compatible format
    packager_format = []
    for item in items:
        packager_format.append({
            'advisoryId': item.advisoryId,
            'summary': item.summary,
            'platform': item.platform,
            'type': item.type,
            # Additional metadata preserved for enrichment
            '_meta': {
                'severity': item.severity,
                'cves': item.cves,
                'first_published': item.first_published,
                'products': item.products,
                'url': item.url
            }
        })

    with open(output_path, 'w') as f:
        json.dump(packager_format, f, indent=2)

    logger.info(f"📦 Exported {len(packager_format)} items to {output_path}")


def export_as_jsonl(items: List[VulnerabilityItem], output_path: str):
    """
    Export items as JSONL (one JSON object per line).
    This is the format used by the offline update pipeline.
    """
    with open(output_path, 'w') as f:
        for item in items:
            # Convert to dict with all fields
            item_dict = asdict(item)
            f.write(json.dumps(item_dict) + '\n')

    logger.info(f"📦 Exported {len(items)} items to {output_path} (JSONL)")


def filter_against_db(
    items: List[VulnerabilityItem],
    db_path: str
) -> List[VulnerabilityItem]:
    """
    Filter out items that already exist in the vulnerability database.

    This implements anti-affinity: only return NEW items not already in DB.

    Args:
        items: List of fetched vulnerability items
        db_path: Path to SQLite database

    Returns:
        List of items NOT already in the database
    """
    import sqlite3

    if not os.path.exists(db_path):
        logger.warning(f"   ⚠️  Database not found: {db_path}, skipping dedup")
        return items

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all existing advisory/bug IDs
        # Check both bug_id and advisory_id columns
        existing_ids = set()

        # Try to get from vulnerabilities table
        try:
            cursor.execute("SELECT bug_id FROM vulnerabilities WHERE bug_id IS NOT NULL")
            existing_ids.update(row[0] for row in cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("SELECT advisory_id FROM vulnerabilities WHERE advisory_id IS NOT NULL")
            existing_ids.update(row[0] for row in cursor.fetchall() if row[0])
        except sqlite3.OperationalError:
            pass

        # Also check advisoryId column if it exists (simplified schema)
        try:
            cursor.execute("SELECT advisoryId FROM vulnerabilities WHERE advisoryId IS NOT NULL")
            existing_ids.update(row[0] for row in cursor.fetchall())
        except sqlite3.OperationalError:
            pass

        conn.close()

        # Filter out existing items
        new_items = [item for item in items if item.advisoryId not in existing_ids]

        logger.info(f"   📊 Dedup: {len(items)} fetched → {len(new_items)} new (filtered {len(items) - len(new_items)} existing)")
        return new_items

    except Exception as e:
        logger.error(f"   ❌ Database dedup failed: {e}")
        return items


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Cisco vulnerability data for the labeling pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch PSIRTs from last 30 days (with pagination)
  python cisco_vuln_fetcher.py --mode psirt --days 30 --output psirts.json

  # Fetch bugs by keyword
  python cisco_vuln_fetcher.py --mode bugs --keywords "denial of service" "memory leak" --output bugs.json

  # Fetch everything for the offline update pipeline (JSONL format)
  python cisco_vuln_fetcher.py --mode all --days 7 --jsonl --output vuln_data.jsonl

  # Fetch only NEW items not in database
  python cisco_vuln_fetcher.py --mode all --days 7 --dedup --db vulnerability_db.sqlite -o new_items.jsonl --jsonl

  # Fetch latest critical PSIRTs only
  python cisco_vuln_fetcher.py --mode critical --count 50 --output critical.json

  # Quick fetch without pagination (for testing)
  python cisco_vuln_fetcher.py --mode psirt --days 7 --no-pagination --output quick.json
        """
    )

    parser.add_argument('--mode', choices=['psirt', 'bugs', 'critical', 'all', 'latest'],
                        default='all', help="Fetch mode")
    parser.add_argument('--days', type=int, default=30,
                        help="Number of days to look back (for psirt/all modes)")
    parser.add_argument('--count', type=int, default=25,
                        help="Number of items to fetch (for latest/critical modes)")
    parser.add_argument('--keywords', nargs='+',
                        default=['security', 'vulnerability', 'denial of service'],
                        help="Keywords for bug search")
    parser.add_argument('--output', '-o', type=str, default='vuln_data.json',
                        help="Output file path")
    parser.add_argument('--packager-format', action='store_true',
                        help="Export in Offline Update Packager format (JSON)")
    parser.add_argument('--jsonl', action='store_true',
                        help="Export as JSONL (one record per line, for offline pipeline)")
    parser.add_argument('--env', type=str, default='.env',
                        help="Path to .env file")

    # Pagination control
    parser.add_argument('--no-pagination', action='store_true',
                        help="Disable pagination (use /latest fallback only)")

    # Deduplication
    parser.add_argument('--dedup', action='store_true',
                        help="Filter out items already in database")
    parser.add_argument('--db', type=str, default='vulnerability_db.sqlite',
                        help="Path to SQLite database for dedup check")
                        
    args = parser.parse_args()

    # Load env file if specified
    if args.env and os.path.exists(args.env):
        load_dotenv(args.env)

    try:
        config = load_config()
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        sys.exit(1)

    fetcher = VulnerabilityFetcher(config['client_id'], config['client_secret'])

    # Determine pagination setting
    use_pagination = not args.no_pagination

    logger.info("🚀 Cisco Vulnerability Data Fetcher")
    logger.info(f"   Mode: {args.mode}")
    logger.info(f"   Pagination: {'enabled' if use_pagination else 'disabled'}")
    if args.dedup:
        logger.info(f"   Dedup against: {args.db}")

    all_items = []

    try:
        if args.mode == 'psirt':
            items = fetcher.fetch_recent_psirts(args.days, use_pagination=use_pagination)
            all_items.extend(items)

        elif args.mode == 'bugs':
            for keyword in args.keywords:
                items = fetcher.fetch_bugs_by_keyword(keyword)
                all_items.extend(items)

        elif args.mode == 'critical':
            items = fetcher.fetch_critical_psirts(args.count)
            all_items.extend(items)

        elif args.mode == 'latest':
            items = fetcher.fetch_latest_psirts(args.count)
            all_items.extend(items)

        elif args.mode == 'all':
            results = fetcher.fetch_all(days=args.days, bug_keywords=args.keywords)
            all_items.extend(results['psirts'])
            all_items.extend(results['bugs'])

    except CiscoAPIError as e:
        logger.error(f"❌ API Error: {e}")
        sys.exit(1)

    # Deduplicate by advisory ID (within fetched items)
    seen = set()
    unique_items = []
    for item in all_items:
        if item.advisoryId not in seen:
            seen.add(item.advisoryId)
            unique_items.append(item)

    logger.info(f"\n📊 FETCH SUMMARY")
    logger.info(f"   Total unique items: {len(unique_items)}")
    logger.info(f"   PSIRTs: {sum(1 for i in unique_items if i.type == 'PSIRT')}")
    logger.info(f"   Bugs: {sum(1 for i in unique_items if i.type == 'BUG')}")

    # Apply database deduplication if requested
    if args.dedup:
        logger.info("\n🔍 DEDUP AGAINST DATABASE")
        unique_items = filter_against_db(unique_items, args.db)

    # Final summary
    logger.info(f"\n📊 FINAL OUTPUT")
    logger.info(f"   Items to export: {len(unique_items)}")
    psirt_count = sum(1 for i in unique_items if i.type == 'PSIRT')
    bug_count = sum(1 for i in unique_items if i.type == 'BUG')
    logger.info(f"   PSIRTs: {psirt_count}")
    logger.info(f"   Bugs: {bug_count}")
    logger.info(f"   Needs labeling: {sum(1 for i in unique_items if i.needs_label)}")

    # Export
    if args.jsonl:
        export_as_jsonl(unique_items, args.output)
    elif args.packager_format:
        export_for_packager(unique_items, args.output)
    else:
        # Full export with all fields (JSON with metadata)
        output_data = {
            'metadata': {
                'fetch_date': datetime.now().isoformat(),
                'mode': args.mode,
                'days': args.days,
                'pagination': use_pagination,
                'dedup': args.dedup,
                'total_count': len(unique_items),
                'psirt_count': psirt_count,
                'bug_count': bug_count,
                'needs_labeling': sum(1 for i in unique_items if i.needs_label)
            },
            'items': [asdict(item) for item in unique_items]
        }
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        logger.info(f"📦 Exported to {args.output}")

    logger.info("✅ Done!")


if __name__ == "__main__":
    main()
