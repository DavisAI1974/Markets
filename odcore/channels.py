"""
odcore/channels.py — the channel factory: turn BinSeries into normalized scalar
channels and enumerate channel pairs for the coupling scanner.

The process is supposed to FIND which channels carry the strongest signal, so the
factory exposes many channel kinds and a pair enumerator across them.

Normalization (INFO-051 l.1051): marginal-entropy scale is a units choice and MI is the
invariant, so we globally condition each channel to a comparable scale before the
windowed entropies are computed -- otherwise a channel whose raw values span many orders
of magnitude (taker volume) dominates the un-z-scored SVD and the MI axis collapses into
the null trivially. Conditioning is a global (not per-window) transform, so it shifts
every H by a constant and preserves the cross-window H variation the null extraction uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .io import BinSeries


def _zscore(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    s = x.std()
    return (x - x.mean()) / s if s > 1e-12 else x - x.mean()


def _log_z(x: np.ndarray) -> np.ndarray:
    """log1p then z-score — for heavy-tailed non-negative channels (volume)."""
    return _zscore(np.log1p(np.maximum(x, 0.0)))


# channel kind -> (extractor from BinSeries, conditioning transform)
_EXTRACTORS: dict[str, tuple[Callable[[BinSeries], np.ndarray], Callable]] = {
    "taker_buy":  (lambda s: s.buy,         _log_z),
    "taker_sell": (lambda s: s.sell,        _log_z),
    "volume":     (lambda s: s.volume,      _log_z),
    "log_return": (lambda s: s.log_return(), _zscore),
    "abs_return": (lambda s: s.abs_return(), _log_z),
    "spread":     (lambda s: s.spread,      _log_z),
    "mid":        (lambda s: s.mid,          _zscore),
}

CHANNEL_KINDS = tuple(_EXTRACTORS)


@dataclass
class Channel:
    source: str   # e.g. "btc_coinbase"
    kind: str     # e.g. "taker_buy"

    @property
    def name(self) -> str:
        return f"{self.source}.{self.kind}"


def materialize(source: str, kind: str, series: BinSeries) -> np.ndarray:
    """Extract + globally condition a channel from a BinSeries."""
    extract, transform = _EXTRACTORS[kind]
    return transform(extract(series))


@dataclass
class PairSpec:
    a: Channel
    b: Channel
    pair_kind: str   # orderflow | internal | cross_venue | cross_asset

    @property
    def name(self) -> str:
        return f"{self.a.name} <> {self.b.name}"


def enumerate_pairs(sources: dict[str, BinSeries]) -> list[PairSpec]:
    """Enumerate the channel pairs the scanner should rank across all sources.

    - orderflow: taker_buy vs taker_sell within each source.
    - internal:  abs_return vs volume within each source.
    - cross_venue: same-asset log_return across venues.
    - cross_asset: log_return across assets (different base symbol).
    """
    pairs: list[PairSpec] = []
    for src in sources:
        pairs.append(PairSpec(Channel(src, "taker_buy"), Channel(src, "taker_sell"), "orderflow"))
        pairs.append(PairSpec(Channel(src, "abs_return"), Channel(src, "volume"), "internal"))

    def base(src: str) -> str:
        return src.split("_", 1)[0]

    names = list(sources)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            s1, s2 = names[i], names[j]
            kind = "cross_venue" if base(s1) == base(s2) else "cross_asset"
            pairs.append(PairSpec(Channel(s1, "log_return"), Channel(s2, "log_return"), kind))
    return pairs
