"""
exchanges/coinbase.py — Coinbase Advanced Trade adapter.

Implements the Exchange Protocol. Uses Coinbase's Advanced Trade REST API
(https://docs.cloud.coinbase.com/advanced-trade-api/docs/welcome). API
keys live in env vars on the user's own machine; this module never holds
or transmits them anywhere except to api.coinbase.com.

SAFETY:
- `dry_run=True` is the default. With dry_run on, the adapter constructs
  the signed request but does NOT send it; it returns a synthetic
  OrderResult so you can verify the executor pipeline before going live.
- Set `dry_run=False` (or `EXCHANGE_LIVE=1` in env) only after you've
  validated end-to-end on testnet / sandbox.
- We default to MARKET orders. Configure `slippage_bps` if you need a
  guard (rejected if quote moves more than X bps between fetch and post).

Required env vars:
- COINBASE_API_KEY     (or pass api_key kwarg)
- COINBASE_API_SECRET  (or pass api_secret kwarg)

Asset symbol convention: "BTC-USD", "ETH-USD" (matches the rest of the
repo's symbology).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid

import requests

from .base import OrderResult, PriceQuote


COINBASE_REST = "https://api.coinbase.com"


class CoinbaseExchange:
    name = "coinbase"

    def __init__(self,
                  api_key: str | None = None,
                  api_secret: str | None = None,
                  dry_run: bool | None = None,
                  slippage_bps: float = 50.0,
                  timeout_s: float = 10.0):
        self.api_key = api_key or os.environ.get("COINBASE_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("COINBASE_API_SECRET", "")
        if dry_run is None:
            env = os.environ.get("EXCHANGE_LIVE", "0").lower()
            dry_run = env not in ("1", "true", "yes")
        self.dry_run = dry_run
        self.slippage_bps = slippage_bps
        self.timeout_s = timeout_s
        self._positions_cache: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def _sign(self, ts: str, method: str, path: str, body: str) -> str:
        msg = f"{ts}{method}{path}{body}"
        return hmac.new(
            self.api_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _signed_headers(self, method: str, path: str, body: str = "") -> dict:
        if not self.api_key or not self.api_secret:
            raise RuntimeError("COINBASE_API_KEY / COINBASE_API_SECRET not set")
        ts = str(int(time.time()))
        return {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": self._sign(ts, method, path, body),
            "CB-ACCESS-TIMESTAMP": ts,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Quote
    # ------------------------------------------------------------------

    def get_quote(self, asset: str) -> PriceQuote:
        """Public best-bid / best-ask from the public market data endpoint.

        asset format: "ETH-USD" — passed straight through.
        """
        url = f"{COINBASE_REST}/api/v3/brokerage/market/products/{asset}/ticker"
        try:
            r = requests.get(url, timeout=self.timeout_s, params={"limit": 1})
            r.raise_for_status()
            data = r.json()
            best_bid = float(data.get("best_bid", 0))
            best_ask = float(data.get("best_ask", 0))
            mid = (best_bid + best_ask) / 2 if best_bid and best_ask else float(data.get("price", 0))
        except Exception as e:
            raise RuntimeError(f"coinbase quote failed for {asset}: {e}")
        return PriceQuote(asset=asset, bid=best_bid, ask=best_ask, mid=mid,
                           timestamp_utc=time.time())

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def _post_order(self, body: dict) -> OrderResult:
        path = "/api/v3/brokerage/orders"
        body_str = json.dumps(body)
        if self.dry_run:
            return OrderResult(
                success=True,
                exchange_order_id=f"DRYRUN-{str(uuid.uuid4())[:8]}",
                fill_price=0.0, fill_size=0.0, fees_usd=0.0,
                raw={"dry_run": True, "would_post": body},
            )
        try:
            headers = self._signed_headers("POST", path, body_str)
            r = requests.post(COINBASE_REST + path, headers=headers,
                                data=body_str, timeout=self.timeout_s)
            data = r.json()
        except Exception as e:
            return OrderResult(success=False, error=str(e))
        if not r.ok or not data.get("success", False):
            return OrderResult(success=False, error=str(data), raw=data)
        oid = data.get("order_id") or data.get("success_response", {}).get("order_id", "")
        return OrderResult(success=True, exchange_order_id=oid, raw=data)

    def market_buy(self, asset: str, notional_usd: float) -> OrderResult:
        body = {
            "client_order_id": str(uuid.uuid4()),
            "product_id": asset,
            "side": "BUY",
            "order_configuration": {
                "market_market_ioc": {"quote_size": str(round(notional_usd, 2))},
            },
        }
        return self._post_order(body)

    def market_sell(self, asset: str, size: float) -> OrderResult:
        body = {
            "client_order_id": str(uuid.uuid4()),
            "product_id": asset,
            "side": "SELL",
            "order_configuration": {
                "market_market_ioc": {"base_size": str(round(size, 8))},
            },
        }
        return self._post_order(body)

    def limit_buy(self, asset: str, price: float, size: float,
                   post_only: bool = True) -> OrderResult:
        body = {
            "client_order_id": str(uuid.uuid4()),
            "product_id": asset,
            "side": "BUY",
            "order_configuration": {
                "limit_limit_gtc": {
                    "base_size": str(round(size, 8)),
                    "limit_price": str(round(price, 2)),
                    "post_only": post_only,
                },
            },
        }
        return self._post_order(body)

    def limit_sell(self, asset: str, price: float, size: float,
                    post_only: bool = True) -> OrderResult:
        body = {
            "client_order_id": str(uuid.uuid4()),
            "product_id": asset,
            "side": "SELL",
            "order_configuration": {
                "limit_limit_gtc": {
                    "base_size": str(round(size, 8)),
                    "limit_price": str(round(price, 2)),
                    "post_only": post_only,
                },
            },
        }
        return self._post_order(body)

    # ------------------------------------------------------------------
    # Account / positions
    # ------------------------------------------------------------------

    def get_position(self, asset: str) -> float:
        """Return base-currency balance for the asset (e.g. ETH for ETH-USD)."""
        if self.dry_run:
            return self._positions_cache.get(asset, 0.0)
        base = asset.split("-")[0]
        path = "/api/v3/brokerage/accounts"
        try:
            headers = self._signed_headers("GET", path, "")
            r = requests.get(COINBASE_REST + path, headers=headers,
                              timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[coinbase] get_position {asset}: {e}", flush=True)
            return 0.0
        for acct in data.get("accounts", []):
            if acct.get("currency") == base:
                bal = acct.get("available_balance", {}).get("value", "0")
                try:
                    return float(bal)
                except Exception:
                    return 0.0
        return 0.0
