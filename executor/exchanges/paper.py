"""
exchanges/paper.py — paper-trading exchange adapter.

Simulates orders against the backend's quote endpoint. No real money. No
external API calls beyond fetching the current price from our own API.
Logs all simulated trades to a JSONL file for audit.

Use this to validate the executor end-to-end before integrating a real
exchange.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import requests

from .base import OrderResult, PriceQuote


class PaperExchange:
    name = "paper"

    def __init__(self, api_base: str = "http://localhost:8000",
                 trade_log_path: str = "executor/paper_trades.jsonl",
                 simulated_fee_bps: float = 25.0):
        self.api_base = api_base.rstrip("/")
        self.trade_log_path = trade_log_path
        self.simulated_fee_bps = simulated_fee_bps
        self.positions: dict[str, float] = {}
        os.makedirs(os.path.dirname(trade_log_path) or ".", exist_ok=True)

    def get_quote(self, asset: str) -> PriceQuote:
        """Fetch most recent close price from the markets-watch API.

        We don't have real bid/ask in our bins; simulate a 1 bp spread around close.
        """
        # Try Coinbase first, fall back to Kraken; either is fine for paper sim
        for venue in ("Coinbase", "Kraken"):
            try:
                r = requests.get(f"{self.api_base}/api/chart/{asset}/{venue}?n_minutes=1",
                                  timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    pts = data.get("data") or []
                    if pts:
                        mid = float(pts[-1]["price"])
                        spread_bps = 1.0
                        return PriceQuote(
                            asset=asset,
                            bid=mid * (1 - spread_bps / 20000),
                            ask=mid * (1 + spread_bps / 20000),
                            mid=mid,
                            timestamp_utc=time.time(),
                        )
            except Exception:
                continue
        raise RuntimeError(f"could not get quote for {asset} from paper backend")

    def market_buy(self, asset: str, notional_usd: float) -> OrderResult:
        q = self.get_quote(asset)
        # Pay the ask + fee
        size = notional_usd / q.ask
        fee = notional_usd * (self.simulated_fee_bps / 10000.0)
        oid = str(uuid.uuid4())[:12]
        self.positions[asset] = self.positions.get(asset, 0.0) + size
        self._log({
            "ts": time.time(),
            "side": "buy",
            "asset": asset,
            "notional_usd": notional_usd,
            "fill_price": q.ask,
            "fill_size": size,
            "fees_usd": fee,
            "order_id": oid,
            "post_position": self.positions[asset],
        })
        return OrderResult(
            success=True, exchange_order_id=oid,
            fill_price=q.ask, fill_size=size, fees_usd=fee,
        )

    def market_sell(self, asset: str, size: float) -> OrderResult:
        q = self.get_quote(asset)
        proceeds = size * q.bid
        fee = proceeds * (self.simulated_fee_bps / 10000.0)
        oid = str(uuid.uuid4())[:12]
        self.positions[asset] = self.positions.get(asset, 0.0) - size
        self._log({
            "ts": time.time(),
            "side": "sell",
            "asset": asset,
            "size": size,
            "fill_price": q.bid,
            "proceeds_usd": proceeds,
            "fees_usd": fee,
            "order_id": oid,
            "post_position": self.positions[asset],
        })
        return OrderResult(
            success=True, exchange_order_id=oid,
            fill_price=q.bid, fill_size=size, fees_usd=fee,
        )

    def get_position(self, asset: str) -> float:
        return self.positions.get(asset, 0.0)

    def _log(self, entry: dict) -> None:
        with open(self.trade_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
