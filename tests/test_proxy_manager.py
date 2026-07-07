"""Tests for proxy manager."""

import pytest
from unittest.mock import patch

from scrapers.proxy_manager import ProxyManager


class TestProxyManager:
    """Test ProxyManager functionality."""

    def test_no_proxies(self):
        """Should work without proxies configured."""
        with patch("scrapers.proxy_manager.settings") as mock_settings:
            mock_settings.PROXY_LIST = ""
            with patch.object(ProxyManager, '_bootstrap_proxies'):
                pm = ProxyManager()
                assert pm.proxy_count == 0
            assert pm.get_proxy() is None
            assert pm.get_httpx_proxy() is None
            assert pm.get_requests_proxy() is None
            assert pm.get_random_proxy() is None

    def test_load_proxies(self):
        """Should load proxies from config."""
        with patch("scrapers.proxy_manager.settings") as mock_settings:
            mock_settings.PROXY_LIST = "http://p1:8080,http://p2:8080,socks5://p3:1080"
            pm = ProxyManager()
            assert pm.proxy_count == 3

    def test_round_robin(self):
        """Should rotate proxies in round-robin fashion."""
        with patch("scrapers.proxy_manager.settings") as mock_settings:
            mock_settings.PROXY_LIST = "http://p1:8080,http://p2:8080"
            pm = ProxyManager()
            first = pm.get_proxy()
            second = pm.get_proxy()
            third = pm.get_proxy()
            assert first == "http://p1:8080"
            assert second == "http://p2:8080"
            assert third == "http://p1:8080"  # Wraps around

    def test_mark_bad(self):
        """Should remove bad proxy from rotation."""
        with patch("scrapers.proxy_manager.settings") as mock_settings:
            mock_settings.PROXY_LIST = "http://p1:8080,http://p2:8080"
            pm = ProxyManager()
            pm.mark_bad("http://p1:8080")
            assert pm.proxy_count == 1
            assert pm.get_proxy() == "http://p2:8080"

    def test_mark_good_restore(self):
        """Should restore a previously bad proxy."""
        with patch("scrapers.proxy_manager.settings") as mock_settings:
            mock_settings.PROXY_LIST = "http://p1:8080,http://p2:8080"
            pm = ProxyManager()
            pm.mark_bad("http://p1:8080")
            assert pm.proxy_count == 1
            pm.mark_good("http://p1:8080")
            assert pm.proxy_count == 2

    def test_add_proxies(self):
        """Should add new proxies at runtime."""
        with patch("scrapers.proxy_manager.settings") as mock_settings:
            mock_settings.PROXY_LIST = "http://p1:8080"
            pm = ProxyManager()
            assert pm.proxy_count == 1
            pm.add_proxies(["http://p2:8080", "http://p3:8080"])
            assert pm.proxy_count == 3

    def test_user_agent(self):
        """Should return a non-empty user agent."""
        with patch("scrapers.proxy_manager.settings") as mock_settings:
            mock_settings.PROXY_LIST = ""
            pm = ProxyManager()
            ua = pm.get_user_agent()
            assert isinstance(ua, str)
            assert len(ua) > 10

    def test_headers(self):
        """Should return realistic browser headers."""
        with patch("scrapers.proxy_manager.settings") as mock_settings:
            mock_settings.PROXY_LIST = ""
            pm = ProxyManager()
            headers = pm.get_headers()
            assert "User-Agent" in headers
            assert "Accept" in headers
            assert "Accept-Language" in headers
            assert "ru-RU" in headers["Accept-Language"]

    def test_httpx_proxy_format(self):
        """Should return correctly formatted httpx proxy dict."""
        with patch("scrapers.proxy_manager.settings") as mock_settings:
            mock_settings.PROXY_LIST = "http://proxy:8080"
            pm = ProxyManager()
            proxy = pm.get_httpx_proxy()
            assert proxy == {"http://": "http://proxy:8080", "https://": "http://proxy:8080"}

    def test_requests_proxy_format(self):
        """Should return correctly formatted requests proxy dict."""
        with patch("scrapers.proxy_manager.settings") as mock_settings:
            mock_settings.PROXY_LIST = "http://proxy:8080"
            pm = ProxyManager()
            proxy = pm.get_requests_proxy()
            assert proxy == {"http": "http://proxy:8080", "https": "http://proxy:8080"}
