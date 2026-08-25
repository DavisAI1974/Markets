"""Additive from-scratch boss-model components around Frankie's frozen seam."""

from .frankie_contract import (
    BLD1_FIELD_NAMES,
    INTERNAL_HEAD_TO_BLD1,
    FrankieProjector,
    InternalBLD1Heads,
)
from .trunk import Trunk, TrunkConfig

__all__ = [
    "BLD1_FIELD_NAMES",
    "INTERNAL_HEAD_TO_BLD1",
    "FrankieProjector",
    "InternalBLD1Heads",
    "Trunk",
    "TrunkConfig",
]
