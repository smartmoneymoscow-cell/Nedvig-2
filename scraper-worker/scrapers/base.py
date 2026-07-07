"""Base scraper with anti-detection, retries, and proxy rotation."""

import time
import random
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Optional

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import settings

# Optional: curl_cffi for TLS fingerprint impersonation
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    logger.warning("curl_cffi not installed — using httpx only")


class BaseScraper(ABC):
    def __init__(self, source_name: str):
        self.source_name = source_name
        self._session = None
        self._request_count: int = 0
        self._last_request_time: float = 0

    def _get_delay(self, min_delay: float = None, max_delay: float = None) -> float:
        min_d = min_delay or settings.REQUEST_DELAY_MIN
        max_d = max_delay or settings.REQUEST_DELAY_MAX
        return random.uniform(min_d, max_d)

    def _throttle(self, min_delay: float = None, max_delay: float = None):
        elapsed = time.time() - self._last_request_time
        delay = self._get_delay(min_delay, max_delay)
        if elapsed < delay:
            wait = delay - elapsed
            logger.debug(f"[{self.source_name}] Throttling {wait:.1f}s")
            time.sleep(wait)
        self._last_request_time = time.time()
        self._request_count += 1

    def _create_session(self):
        if HAS_CURL_CFFI:
            session = curl_requests.Session(impersonate="chrome120", verify=True)  # SSL verification ON
            session.headers.update(self._get_headers())
            proxy = self._get_proxy()
            if proxy:
                session.proxies = {"http": proxy, "https": proxy}
            return session
        else:
            return httpx.Client(
                timeout=30,
                headers=self._get_headers(),
                follow_redirects=True,
            )

    def _get_proxy(self) -> Optional[str]:
        if settings.PROXY_LIST:
            proxies = [p.strip() for p in settings.PROXY_LIST.split(",") if p.strip()]
            if proxies:
                return random.choice(proxies)
        if settings.USE_TOR:
            return "socks5h://127.0.0.1:9050"
        return None

    def _get_headers(self) -> dict:
        return {
            "User-Agent": self._random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": "1",
        }

    def _random_ua(self) -> str:
        uas = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]
        return random.choice(uas)

    def _get(self, url: str, params: dict = None, **kwargs):
        if not self._session:
            self._session = self._create_session()
        self._throttle()

        try:
            if HAS_CURL_CFFI:
                response = self._session.get(url, params=params, timeout=30, **kwargs)
            else:
                response = self._session.get(url, params=params, **kwargs)

            if response.status_code == 403:
                logger.warning(f"[{self.source_name}] 403 Forbidden, rotating session")
                self._rotate_session()
                raise Exception("403 Forbidden")

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

    def _rotate_session(self):
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
        self._session = self._create_session()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    def fetch_with_retry(self, url: str, params: dict = None, **kwargs):
        return self._get(url, params=params, **kwargs)

    def _parse_price(self, price_str: str) -> Optional[float]:
        if not price_str:
            return None
        cleaned = price_str.replace(" ", "").replace("\xa0", "").replace("руб.", "").replace("₽", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        if not date_str:
            return None
        formats = ["%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%d.%m.%Y %H:%M"]
        date_str = date_str.strip()
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        if not dt_str:
            return None
        formats = ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ"]
        dt_str = dt_str.strip()
        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        return None

    @abstractmethod
    def scrape_listings(self, **kwargs) -> list[dict]:
        pass

    def close(self):
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
