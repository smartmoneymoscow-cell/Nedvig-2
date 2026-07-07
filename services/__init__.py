"""Services package — lazy imports."""

__all__ = ["geocoder", "enrichment_service"]


def __getattr__(name: str):
    if name == "geocoder":
        from .geocoder import geocoder
        return geocoder
    if name == "enrichment_service":
        from .enrichment import enrichment_service
        return enrichment_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
