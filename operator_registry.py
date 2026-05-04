"""
operator_registry.py — per-(asset, venue) preferred operator tracking.

The adaptive backtester accumulates rolling performance per generator across
each (asset, venue) source independently. The registry persists those findings
to a JSON file and exposes "what's the preferred operator for source X" so
the executor and backend can surface the right operator's signal.

Schema:
{
  "BTC.Coinbase": {
    "preferred": "dipole_x_volz",
    "rolling_sharpe": 1.23,
    "n_trades": 47,
    "last_updated_utc": 1234567890,
    "all_generators": {
      "pure_dipole_fade": {"sharpe": 0.5, "n": 47, "pnl_bps": 120},
      "dipole_x_volz":     {"sharpe": 1.23, "n": 47, "pnl_bps": 287},
      ...
    }
  },
  ...
}

The preferred operator is whichever has the highest rolling sharpe at last
update. If sharpe is non-positive across all generators, preferred is None
(meaning "sit out for this source").

Updated by adaptive_backtester.py when --persist-registry is passed.
Read by signal generators to attach a "this signal came from operator X"
note to each emitted signal.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class GeneratorStats:
    sharpe: float = 0.0
    n_trades: int = 0
    pnl_bps: float = 0.0
    last_updated_utc: float = 0.0


@dataclass
class SourceEntry:
    preferred: str | None = None
    rolling_sharpe: float = 0.0
    n_trades: int = 0
    last_updated_utc: float = 0.0
    all_generators: dict[str, GeneratorStats] = field(default_factory=dict)


class OperatorRegistry:
    """Persistent JSON-backed registry of per-source operator preferences."""

    def __init__(self, path: str = "operator_registry.json"):
        self.path = path
        self.entries: dict[str, SourceEntry] = {}   # key: "ASSET.VENUE"
        self._load()

    @staticmethod
    def _key(asset: str, venue: str) -> str:
        return f"{asset}.{venue}"

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path) as f:
                raw = json.load(f)
            for k, v in raw.items():
                self.entries[k] = SourceEntry(
                    preferred=v.get("preferred"),
                    rolling_sharpe=float(v.get("rolling_sharpe", 0.0)),
                    n_trades=int(v.get("n_trades", 0)),
                    last_updated_utc=float(v.get("last_updated_utc", 0.0)),
                    all_generators={
                        gn: GeneratorStats(**gs) for gn, gs in v.get("all_generators", {}).items()
                    },
                )
        except Exception as e:
            print(f"[registry] could not load {self.path}: {e}")

    def save(self):
        out = {
            k: {
                "preferred": v.preferred,
                "rolling_sharpe": v.rolling_sharpe,
                "n_trades": v.n_trades,
                "last_updated_utc": v.last_updated_utc,
                "all_generators": {gn: asdict(gs) for gn, gs in v.all_generators.items()},
            }
            for k, v in self.entries.items()
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(out, f, indent=2)
        os.replace(tmp, self.path)

    def update_source(self, asset: str, venue: str,
                       generator_stats: dict[str, GeneratorStats]):
        """Update one source's stats. Picks the highest-sharpe generator with n>=5
        as preferred; sets preferred=None if no generator has positive sharpe."""
        key = self._key(asset, venue)
        # Pick preferred
        eligible = {n: s for n, s in generator_stats.items() if s.n_trades >= 5}
        preferred = None
        rolling_sharpe = 0.0
        if eligible:
            best_name, best_stats = max(eligible.items(), key=lambda x: x[1].sharpe)
            if best_stats.sharpe > 0:
                preferred = best_name
                rolling_sharpe = best_stats.sharpe
        total_n = sum(s.n_trades for s in generator_stats.values())
        self.entries[key] = SourceEntry(
            preferred=preferred,
            rolling_sharpe=rolling_sharpe,
            n_trades=total_n,
            last_updated_utc=time.time(),
            all_generators=generator_stats,
        )

    def preferred_for(self, asset: str, venue: str) -> str | None:
        e = self.entries.get(self._key(asset, venue))
        return e.preferred if e else None

    def stats_for(self, asset: str, venue: str) -> SourceEntry | None:
        return self.entries.get(self._key(asset, venue))

    def summary(self) -> str:
        lines = []
        for key in sorted(self.entries):
            e = self.entries[key]
            pref = e.preferred or "(none — sit out)"
            lines.append(f"  {key:<18} preferred={pref:<24} sharpe={e.rolling_sharpe:+.3f} n={e.n_trades}")
        return "\n".join(lines) if lines else "(empty registry)"


if __name__ == "__main__":
    reg = OperatorRegistry()
    print(f"Loaded {len(reg.entries)} entries from {reg.path}")
    print(reg.summary())
