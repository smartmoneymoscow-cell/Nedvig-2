"""Base scraper with anti-detection, retries, and proxy rotation."""

import time
import random
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Optional

import httpx
from curl_cffi import requests as curl_requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .proxy_manager import proxy_manager
from config import settings


class BaseScraper(ABC):
    """Base class for all scrapers with anti-detection measures."""

    def __init__(self, source_name: str):
        self.source_name = source_name
        self._session: Optional[curl_requests.Session] = None
        self._request_count: int = 0
        self._last_request_time: float = 0

    def _get_delay(self, min_delay: float = None, max_delay: float = None) -> float:
        """Random delay between requests."""
        min_d = min_delay or settings.REQUEST_DELAY_MIN
        max_d = max_delay or settings.REQUEST_DELAY_MAX
        return random.uniform(min_d, max_d)

    def _throttle(self, min_delay: float = None, max_delay: float = None):
        """Wait between requests to avoid detection."""
        elapsed = time.time() - self._last_request_time
        delay = self._get_delay(min_delay, max_delay)
        if elapsed < delay:
            wait = delay - elapsed
            logger.debug(f"[{self.source_name}] Throttling {wait:.1f}s")
            time.sleep(wait)
        self._last_request_time = time.time()
        self._request_count += 1

    def _create_session(self) -> curl_requests.Session:
        """Create a curl_cffi session with TLS fingerprint impersonation."""
        session = curl_requests.Session(impersonate="chrome120")
        headers = proxy_manager.get_headers()
        session.headers.update(headers)

        proxy = proxy_manager.get_proxy()
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
            logger.debug(f"[{self.source_name}] Using proxy: {proxy}")

        return session

    def _rotate_session(self):
        """Rotate proxy and create new session."""
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
        self._session = self._create_session()
        logger.debug(f"[{self.source_name}] Session rotated")

    def _get(self, url: str, params: dict = None, **kwargs) -> httpx.Response:
        """Make GET request with anti-detection and retry logic."""
        if not self._session:
            self._session = self._create_session()

        self._throttle()

        try:
            response = self._session.get(url, params=params, timeout=30, **kwargs)

            if response.status_code == 403:
                logger.warning(f"[{self.source_name}] 403 Forbidden, rotating proxy")
                proxy = self._session.proxies.get("http") if hasattr(self._session, 'proxies') else None
                if proxy:
                    proxy_manager.mark_bad(proxy)
                self._rotate_session()
                raise Exception("403 Forbidden - rotated")

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"[{self.source_name}] Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
                raise Exception("429 Rate Limited")

            response.raise_for_status()
            return response

        except Exception as e:
            logger.error(f"[{self.source_name}] Request failed: {url} - {e}")
            self._rotate_session()
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    def fetch_with_retry(self, url: str, params: dict = None, **kwargs):
        """Fetch URL with automatic retries."""
        return self._get(url, params=params, **kwargs)

    def _parse_price(self, price_str: str) -> Optional[float]:
        """Parse price string to float."""
        if not price_str:
            return None
        cleaned = (
            price_str.replace(" ", "")
            .replace("\xa0", "")
            .replace("руб.", "")
            .replace("₽", "")
            .replace(",", ".")
        )
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse Russian date string."""
        if not date_str:
            return None
        formats = [
            "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d",
            "%d %B %Y", "%d %b %Y",
            "%d.%m.%Y %H:%M", "%d/%m/%Y %H:%M",
        ]
        date_str = date_str.strip()
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parse Russian datetime string."""
        if not dt_str:
            return None
        formats = [
            "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M",
            "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ",
        ]
        dt_str = dt_str.strip()
        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        return None

    @abstractmethod
    def scrape_listings(self, **kwargs) -> list[dict]:
        """Scrape property listings. Must be implemented by subclasses."""
        pass

    def close(self):
        """Clean up resources."""
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
