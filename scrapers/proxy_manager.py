"""Proxy rotation manager with health checks."""

import random
import time
import threading
from typing import Optional

import httpx
from loguru import logger
from fake_useragent import UserAgent

from config import settings


class ProxyManager:
    """Manages proxy rotation, health checking, and user-agent spoofing."""

    def __init__(self):
        self._proxies: list[str] = []
        self._healthy_proxies: list[str] = []
        self._current_index: int = 0
        self._lock = threading.Lock()
        self._last_health_check: float = 0
        self._health_check_interval: float = 300  # 5 min
        self._ua = UserAgent(browsers=["chrome", "firefox", "edge"], os=["windows", "macos", "linux"])

        self._load_proxies()

    def _load_proxies(self):
        """Load proxies from config."""
        if settings.PROXY_LIST:
            self._proxies = [p.strip() for p in settings.PROXY_LIST.split(",") if p.strip()]
            self._healthy_proxies = list(self._proxies)
            logger.info(f"Loaded {len(self._proxies)} proxies")
        else:
            logger.warning("No proxies configured. Running without proxy.")

    def get_proxy(self) -> Optional[str]:
        """Get next healthy proxy via round-robin."""
        if not self._healthy_proxies:
            return None

        with self._lock:
            if time.time() - self._last_health_check > self._health_check_interval:
                self._run_health_check_async()

            proxy = self._healthy_proxies[self._current_index % len(self._healthy_proxies)]
            self._current_index += 1
            return proxy

    def get_random_proxy(self) -> Optional[str]:
        """Get a random healthy proxy."""
        if not self._healthy_proxies:
            return None
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

    def get_selenium_proxy(self) -> Optional[str]:
        """Get proxy string for Selenium."""
        return self.get_proxy()

    def mark_bad(self, proxy: str):
        """Mark a proxy as non-functional."""
        with self._lock:
            if proxy in self._healthy_proxies:
                self._healthy_proxies.remove(proxy)
                logger.warning(f"Proxy marked bad: {proxy}. Healthy: {len(self._healthy_proxies)}")

    def mark_good(self, proxy: str):
        """Mark a proxy as working (re-add if was removed)."""
        with self._lock:
            if proxy not in self._healthy_proxies and proxy in self._proxies:
                self._healthy_proxies.append(proxy)
                logger.info(f"Proxy restored: {proxy}")

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

    def _run_health_check_async(self):
        """Quick health check of all proxies."""
        self._last_health_check = time.time()
        alive = []
        for proxy in self._proxies:
            try:
                with httpx.Client(timeout=10, proxies={"http://": proxy, "https://": proxy}) as client:
                    resp = client.get("https://httpbin.org/ip")
                    if resp.status_code == 200:
                        alive.append(proxy)
            except Exception:
                pass

        if alive:
            self._healthy_proxies = alive
            logger.info(f"Health check: {len(alive)}/{len(self._proxies)} proxies alive")
        else:
            logger.error("All proxies failed health check!")

    @property
    def proxy_count(self) -> int:
        return len(self._healthy_proxies)

    def add_proxies(self, proxies: list[str]):
        """Add new proxies at runtime."""
        with self._lock:
            for p in proxies:
                if p not in self._proxies:
                    self._proxies.append(p)
                    self._healthy_proxies.append(p)
            logger.info(f"Added {len(proxies)} proxies. Total: {len(self._proxies)}")


# Singleton
proxy_manager = ProxyManager()
