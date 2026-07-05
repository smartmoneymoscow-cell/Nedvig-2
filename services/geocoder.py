"""Yandex Geocoder service for resolving addresses to coordinates."""

import time
from typing import Optional

import httpx
from loguru import logger

from config import settings


YANDEX_GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x"


class Geocoder:
    """Geocode addresses using Yandex Geocoder API."""

    def __init__(self):
        self._api_key = settings.YANDEX_MAPS_API_KEY
        self._cache: dict[str, tuple[float, float]] = {}
        self._request_count = 0

    def geocode(self, address: str, city: str = None) -> Optional[tuple[float, float]]:
        """
        Geocode address to (latitude, longitude).

        Args:
            address: Street address
            city: City name for better accuracy

        Returns:
            Tuple of (lat, lon) or None
        """
        if not self._api_key:
            logger.warning("Yandex Maps API key not configured, skipping geocoding")
            return None

        full_address = f"{city}, {address}" if city else address

        # Check cache
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

            features = (
                data.get("response", {})
                .get("GeoObjectCollection", {})
                .get("featureMember", [])
            )

            if features:
                geo_obj = features[0].get("GeoObject", {})
                pos = geo_obj.get("Point", {}).get("pos", "")
                if pos:
                    lon, lat = map(float, pos.split())
                    self._cache[full_address] = (lat, lon)
                    self._request_count += 1
                    logger.debug(f"Geocoded: {full_address} → ({lat}, {lon})")
                    return (lat, lon)

            logger.warning(f"Geocoding failed for: {full_address}")
            return None

        except Exception as e:
            logger.error(f"Geocoding error for '{full_address}': {e}")
            return None

    def batch_geocode(self, addresses: list[dict], delay: float = 0.5) -> list[dict]:
        """
        Geocode multiple addresses.

        Args:
            addresses: List of dicts with 'address' and 'city' keys
            delay: Delay between requests

        Returns:
            List of dicts with 'latitude' and 'longitude' added
        """
        results = []
        for i, addr_data in enumerate(addresses):
            address = addr_data.get("address", "")
            city = addr_data.get("city", "")

            coords = self.geocode(address, city)

            result = dict(addr_data)
            if coords:
                result["latitude"] = coords[0]
                result["longitude"] = coords[1]
                result["is_geocoded"] = True
            else:
                result["is_geocoded"] = False

            results.append(result)

            if (i + 1) % 10 == 0:
                logger.info(f"Geocoded {i+1}/{len(addresses)}")

            time.sleep(delay)

        return results

    @property
    def total_requests(self) -> int:
        return self._request_count


geocoder = Geocoder()
