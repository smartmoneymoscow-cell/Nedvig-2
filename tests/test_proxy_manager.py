"""Tests for proxy manager."""

from unittest.mock import patch, MagicMock
import types

# Create a mock module to avoid real imports
mock_settings = types.SimpleNamespace(
    PROXY_LIST="",
    USE_TOR=False,
)

# Patch before import
with patch.dict('sys.modules', {
    'config': types.SimpleNamespace(settings=mock_settings),
}):
    from scrapers.proxy_manager import ProxyManager


class TestProxyManager:
    """Test ProxyManager functionality."""

    def _make_pm(self, proxy_list=""):
        """Create a ProxyManager with mocked config."""
        mock_settings.PROXY_LIST = proxy_list
        pm = ProxyManager.__new__(ProxyManager)
        pm._configured_proxies = []
        pm._discovered_proxies = []
        pm._healthy_proxies = []
        pm._current_index = 0
        import threading
        pm._lock = threading.Lock()
        pm._last_health_check = 9999999999
        pm._last_discovery = 9999999999
        pm._health_check_interval = 300
        pm._discovery_interval = 3600
        pm._ua = MagicMock()
        pm._ua.random = "Mozilla/5.0 Test"
        pm._test_timeout = 10.0
        if proxy_list:
            pm._configured_proxies = [p.strip() for p in proxy_list.split(",") if p.strip()]
            pm._healthy_proxies = list(pm._configured_proxies)
        return pm

    def test_no_proxies(self):
        pm = self._make_pm()
        assert pm.proxy_count == 0
        assert pm.get_proxy() is None

    def test_load_proxies(self):
        pm = self._make_pm("http://p1:8080,http://p2:8080,socks5://p3:1080")
        assert pm.proxy_count == 3

    def test_round_robin(self):
        pm = self._make_pm("http://p1:8080,http://p2:8080")
        assert pm.get_proxy() == "http://p1:8080"
        assert pm.get_proxy() == "http://p2:8080"
        assert pm.get_proxy() == "http://p1:8080"

    def test_mark_bad(self):
        pm = self._make_pm("http://p1:8080,http://p2:8080")
        pm.mark_bad("http://p1:8080")
        assert pm.proxy_count == 1
        assert pm.get_proxy() == "http://p2:8080"

    def test_mark_good_restore(self):
        pm = self._make_pm("http://p1:8080,http://p2:8080")
        pm.mark_bad("http://p1:8080")
        assert pm.proxy_count == 1
        pm.mark_good("http://p1:8080")
        assert pm.proxy_count == 2

    def test_add_proxies(self):
        pm = self._make_pm("http://p1:8080")
        assert pm.proxy_count == 1
        pm.add_proxies(["http://p2:8080", "http://p3:8080"])
        assert pm.proxy_count == 3

    def test_user_agent(self):
        pm = self._make_pm()
        ua = pm.get_user_agent()
        assert isinstance(ua, str)

    def test_headers(self):
        pm = self._make_pm()
        headers = pm.get_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers

    def test_httpx_proxy_format(self):
        pm = self._make_pm("http://proxy:8080")
        proxy = pm.get_httpx_proxy()
        assert proxy == {"http://": "http://proxy:8080", "https://": "http://proxy:8080"}

    def test_requests_proxy_format(self):
        pm = self._make_pm("http://proxy:8080")
        proxy = pm.get_requests_proxy()
        assert proxy == {"http": "http://proxy:8080", "https": "http://proxy:8080"}
