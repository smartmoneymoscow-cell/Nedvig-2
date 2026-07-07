"""Yandex Geocoder service."""

from typing import Optional
import httpx
from loguru import logger
from config import settings


YANDEX_GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x"


class Geocoder:
    def __init__(self):
        self._api_key = settings.YANDEX_MAPS_API_KEY
        self._cache: dict[str, tuple[float, float]] = {}

    def geocode(self, address: str, city: str = None) -> Optional[tuple[float, float]]:
        if not self._api_key:
            logger.warning("Yandex Maps API key not configured, skipping geocoding")
            return None

        full_address = f"{city}, {address}" if city else address
        if full_address in self._cache:
            return self._cache[full_address]

        try:
            params = {
                "apikey": self._api_key,
                "format": "json",
                "geocode": full_address,
                "lang": "ru_RU",
                "results": 1,
            }
            with httpx.Client(timeout=10) as client:
                response = client.get(YANDEX_GEOCODER_URL, params=params)
                response.raise_for_status()
                data = response.json()

            features = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
            if features:
                pos = features[0].get("GeoObject", {}).get("Point", {}).get("pos", "")
                if pos:
                    lon, lat = map(float, pos.split())
                    self._cache[full_address] = (lat, lon)
                    return (lat, lon)
            return None
        except Exception as e:
            logger.error(f"Geocoding error for '{full_address}': {e}")
            return None


geocoder = Geocoder()
