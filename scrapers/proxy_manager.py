"""Auto-discovery proxy manager with Russian SOCKS5 proxy support.

Automatically fetches free SOCKS5 proxies from multiple sources,
tests them against the target API, and maintains a pool of working proxies.
Falls back to direct connection if no proxies needed.
"""

import re
import time
import random
import threading
from typing import Optional

import httpx
from loguru import logger
from fake_useragent import UserAgent

from config import settings


# Proxy sources (free, public)
PROXY_SOURCES = [
    # proxifly/free-proxy-list (GitHub)
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
    # monosans/proxy-list
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/protocols/socks5.txt",
    # TheSpeedX/PROXY-List
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
]

# Test URL for proxy validation
TEST_URL = "https://torgi.gov.ru/new/api/public/lotcards/search"
TEST_PARAMS = {
    "lotStatus": "PUBLISHED",
    "byFirstVersion": "true",
    "size": "1",
    "sort": "firstVersionPublicationDate,desc",
}

# Known Russian IP ranges (first octets commonly used in RU)
RU_IP_PREFIXES = [
    "5.", "31.", "37.", "45.", "46.", "62.", "77.", "78.", "79.",
    "80.", "81.", "82.", "83.", "84.", "85.", "86.", "87.", "88.",
    "89.", "90.", "91.", "92.", "93.", "94.", "95.", "109.", "176.",
    "178.", "185.", "188.", "193.", "194.", "195.", "212.", "213.",
    "217.",
]


def _is_likely_russian_ip(ip: str) -> bool:
    """Check if IP is likely Russian based on first octet."""
    return any(ip.startswith(prefix) for prefix in RU_IP_PREFIXES)


class ProxyManager:
    """Manages proxy discovery, rotation, health checking, and user-agent spoofing."""

    def __init__(self):
        self._configured_proxies: list[str] = []
        self._discovered_proxies: list[str] = []
        self._healthy_proxies: list[str] = []
        self._current_index: int = 0
        self._lock = threading.Lock()
        self._last_health_check: float = 0
        self._last_discovery: float = 0
        self._health_check_interval: float = 300  # 5 min
        self._discovery_interval: float = 3600  # 1 hour
        self._ua = UserAgent(browsers=["chrome", "firefox", "edge"], os=["windows", "macos", "linux"])
        self._test_timeout: float = 10.0

        self._load_configured_proxies()

    def _load_configured_proxies(self):
        """Load manually configured proxies from settings."""
        if settings.PROXY_LIST:
            self._configured_proxies = [p.strip() for p in settings.PROXY_LIST.split(",") if p.strip()]
            self._healthy_proxies = list(self._configured_proxies)
            logger.info(f"Loaded {len(self._configured_proxies)} configured proxies")
        else:
            # Bootstrap with known working proxies
            self._bootstrap_proxies()

    def _bootstrap_proxies(self):
        """Seed with known working proxies for immediate use."""
        # These are tested and confirmed working with torgi.gov.ru
        known_good = [
            "socks5://194.28.162.12:1080",
        ]
        self._configured_proxies = known_good
        self._healthy_proxies = list(known_good)
        logger.info(f"[ProxyManager] Bootstrapped with {len(known_good)} known proxies")

    def _discover_proxies(self):
        """Fetch fresh SOCKS5 proxies from public sources."""
        logger.info("[ProxyManager] Discovering fresh proxies...")
        all_proxies = set()

        for source_url in PROXY_SOURCES:
            try:
                with httpx.Client(timeout=10) as client:
                    resp = client.get(source_url)
                    if resp.status_code == 200:
                        # Parse proxy list (one per line, format: socks5://host:port or host:port)
                        for line in resp.text.strip().split("\n"):
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            # Normalize format
                            if "://" in line:
                                proxy = line
                            else:
                                proxy = f"socks5://{line}"
                            # Extract IP to check if Russian
                            ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", proxy)
                            if ip_match:
                                ip = ip_match.group(1)
                                if _is_likely_russian_ip(ip):
                                    all_proxies.add(proxy)

                        logger.info(f"[ProxyManager] Fetched proxies from {source_url.split('/')[-1]}")
            except Exception as e:
                logger.warning(f"[ProxyManager] Failed to fetch from {source_url}: {e}")

        if all_proxies:
            self._discovered_proxies = list(all_proxies)
            logger.info(f"[ProxyManager] Discovered {len(self._discovered_proxies)} Russian SOCKS5 proxies")
        else:
            logger.warning("[ProxyManager] No proxies discovered")

    def _test_proxy(self, proxy: str) -> bool:
        """Test if a proxy can reach the target API."""
        try:
            from curl_cffi import requests as curl_requests
            r = curl_requests.get(
                TEST_URL,
                params=TEST_PARAMS,
                timeout=self._test_timeout,
                proxies={"http": proxy, "https": proxy},
                impersonate="chrome120",
                verify=False,
            )
            return r.status_code == 200
        except Exception:
            return False

    def _health_check_proxies(self):
        """Test all known proxies and keep only working ones."""
        candidates = list(set(self._configured_proxies + self._discovered_proxies))
        if not candidates:
            return

        logger.info(f"[ProxyManager] Health checking {len(candidates)} proxies...")
        alive = []

        for proxy in candidates[:30]:  # Test max 30 to avoid long delays
            if self._test_proxy(proxy):
                alive.append(proxy)
                if len(alive) >= 10:  # Found enough working proxies
                    break

        with self._lock:
            self._healthy_proxies = alive
            self._last_health_check = time.time()

        if alive:
            logger.info(f"[ProxyManager] Health check: {len(alive)} proxies alive")
        else:
            logger.warning("[ProxyManager] All proxies failed health check!")

    def get_proxy(self) -> Optional[str]:
        """Get next healthy proxy. Auto-discovers if needed."""
        with self._lock:
            # Auto-discover if stale
            if time.time() - self._last_discovery > self._discovery_interval:
                self._last_discovery = time.time()
                # Run discovery in background
                threading.Thread(target=self._discover_proxies, daemon=True).start()

            # Health check if stale
            if time.time() - self._last_health_check > self._health_check_interval:
                self._last_health_check = time.time()
                threading.Thread(target=self._health_check_proxies, daemon=True).start()

            if not self._healthy_proxies:
                # Try to do initial discovery synchronously
                if self._discovered_proxies:
                    self._healthy_proxies = list(self._discovered_proxies[:10])

            if not self._healthy_proxies:
                return None

            proxy = self._healthy_proxies[self._current_index % len(self._healthy_proxies)]
            self._current_index += 1
            return proxy

    def get_random_proxy(self) -> Optional[str]:
        """Get a random healthy proxy."""
        with self._lock:
            if not self._healthy_proxies:
                return self.get_proxy()
            return random.choice(self._healthy_proxies)

    def get_httpx_proxy(self) -> Optional[dict]:
        """Get proxy dict formatted for httpx."""
        proxy = self.get_proxy()
        if proxy:
            return {"http://": proxy, "https://": proxy}
        return None

    def get_requests_proxy(self) -> Optional[dict]:
        """Get proxy dict formatted for requests."""
        proxy = self.get_proxy()
        if proxy:
            return {"http": proxy, "https": proxy}
        return None

    def get_curl_cffi_proxies(self) -> Optional[dict]:
        """Get proxy dict formatted for curl_cffi."""
        proxy = self.get_proxy()
        if proxy:
            return {"http": proxy, "https": proxy}
        return None

    def mark_bad(self, proxy: str):
        """Mark a proxy as non-functional."""
        with self._lock:
            if proxy in self._healthy_proxies:
                self._healthy_proxies.remove(proxy)
                logger.warning(f"[ProxyManager] Proxy marked bad: {proxy}. Healthy: {len(self._healthy_proxies)}")

    def mark_good(self, proxy: str):
        """Mark a proxy as working."""
        with self._lock:
            if proxy not in self._healthy_proxies:
                self._healthy_proxies.append(proxy)
                logger.info(f"[ProxyManager] Proxy restored: {proxy}")

    def force_discovery(self):
        """Force immediate proxy discovery and health check."""
        self._discover_proxies()
        self._health_check_proxies()

    def get_user_agent(self) -> str:
        """Get a random realistic user agent."""
        return self._ua.random

    def get_headers(self) -> dict:
        """Get realistic browser headers."""
        return {
            "User-Agent": self.get_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
        }

    @property
    def proxy_count(self) -> int:
        return len(self._healthy_proxies)

    @property
    def total_known(self) -> int:
        return len(set(self._configured_proxies + self._discovered_proxies))

    def add_proxies(self, proxies: list[str]):
        """Add new proxies at runtime."""
        with self._lock:
            for p in proxies:
                if p not in self._configured_proxies:
                    self._configured_proxies.append(p)
                    self._healthy_proxies.append(p)
            logger.info(f"[ProxyManager] Added {len(proxies)} proxies. Total: {len(self._configured_proxies)}")


# Singleton
proxy_manager = ProxyManager()
