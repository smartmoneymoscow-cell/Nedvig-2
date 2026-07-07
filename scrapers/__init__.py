"""Scrapers package — lazy imports to avoid hard dependency on playwright."""

__all__ = [
    "TorgiGovScraper",
    "CianScraper",
    "FedresursScraper",
    "EtpScraper",
    "proxy_manager",
]


def __getattr__(name: str):
    if name == "TorgiGovScraper":
        from .torgi_scraper import TorgiGovScraper
        return TorgiGovScraper
    if name == "CianScraper":
        from .cian_scraper import CianScraper
        return CianScraper
    if name == "FedresursScraper":
        from .fedresurs_scraper import FedresursScraper
        return FedresursScraper
    if name == "EtpScraper":
        from .etp_scraper import EtpScraper
        return EtpScraper
    if name == "proxy_manager":
        from .proxy_manager import proxy_manager
        return proxy_manager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
