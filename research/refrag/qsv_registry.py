"""Governed QSV feature registry derived from Markets' executable encoder."""

from markets_adapter import MarketChunkEncoder


QSV_FEATURE_REGISTRY: tuple[str, ...] = MarketChunkEncoder().feature_registry


__all__ = ["QSV_FEATURE_REGISTRY"]
