"""
exchanges/binance.py — Binance Spot adapter.

Implements the Exchange Protocol against the Binance Spot REST API
(https://binance-docs.github.io/apidocs/spot/en/). API keys live in env
vars on the user's own machine; this module never holds or transmits
them anywhere except to api.binance.com.

SAFETY:
- `dry_run=True` is the default. Set `dry_run=False` (or `EXCHANGE_LIVE=1`
  in env) only after validating on testnet.
- For testnet, set `BINANCE_REST=https://testnet.binance.vision` in env
  and use a testnet API key.
- We default to MARKET orders. Use limit_* if you want quote control.

Required env vars:
- BINANCE_API_KEY     (or pass api_key kwarg)
- BINANCE_API_SECRET  (or pass api_secret kwarg)
- BINANCE_REST        (optional; defaults to live api.binance.com)

Asset symbol convention: this module accepts "ETH-USD" and converts to
"ETHUSDT" (Binance's convention; USD pairs are typically USDT). Override
with `quote_asset="USDC"` etc. if needed.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import uuid
from urllib.parse import urlencode

import requests

from .base import OrderResult, PriceQuote


def _to_binance_symbol(asset: str, quote_asset: str = "USDT") -> str:
    if "-" in asset:
        base = asset.split("-")[0]
    else:
        base = asset
    return f"{base}{quote_asset}".upper()


class BinanceExchange:
    name = "binance"

    def __init__(self,
                  api_key: str | None = None,
                  api_secret: str | None = None,
                  dry_run: bool | None = None,
                  rest_url: str | None = None,
                  quote_asset: str = "USDT",
                  recv_window_ms: int = 5000,
                  timeout_s: float = 10.0):
        self.api_key = api_key or os.environ.get("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("BINANCE_API_SECRET", "")
        self.rest_url = (rest_url
                         or os.environ.get("BINANCE_REST", "https://api.binance.com")
                         ).rstrip("/")
        if dry_run is None:
            env = os.environ.get("EXCHANGE_LIVE", "0").lower()
            dry_run = env not in ("1", "true", "yes")
        self.dry_run = dry_run
        self.quote_asset = quote_asset
        self.recv_window_ms = recv_window_ms
        self.timeout_s = timeout_s
        self._positions_cache: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def _sign(self, query: str) -> str:
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _signed_request(self, method: str, path: str, params: dict) -> dict:
        if not self.api_key or not self.api_secret:
            raise RuntimeError("BINANCE_API_KEY / BINANCE_API_SECRET not set")
        params = dict(params)
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.recv_window_ms
        query = urlencode(params)
        sig = self._sign(query)
        url = f"{self.rest_url}{path}?{query}&signature={sig}"
        headers = {"X-MBX-APIKEY": self.api_key}
        r = requests.request(method, url, headers=headers, timeout=self.timeout_s)
        return r.json()

    # ------------------------------------------------------------------
    # Quote
    # ------------------------------------------------------------------

    def get_quote(self, asset: str) -> PriceQuote:
        symbol = _to_binance_symbol(asset, self.quote_asset)
        url = f"{self.rest_url}/api/v3/ticker/bookTicker"
        try:
            r = requests.get(url, params={"symbol": symbol}, timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json()
            bid = float(data["bidPrice"])
            ask = float(data["askPrice"])
        except Exception as e:
            raise RuntimeError(f"binance quote failed for {asset}: {e}")
        return PriceQuote(asset=asset, bid=bid, ask=ask, mid=(bid + ask) / 2,
                           timestamp_utc=time.time())

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def _post_order(self, params: dict) -> OrderResult:
        path = "/api/v3/order"
        if self.dry_run:
            return OrderResult(
                success=True,
                exchange_order_id=f"DRYRUN-{str(uuid.uuid4())[:8]}",
                raw={"dry_run": True, "would_post": params},
            )
        try:
            data = self._signed_request("POST", path, params)
        except Exception as e:
            return OrderResult(success=False, error=str(e))
        if data.get("orderId"):
            fills = data.get("fills") or []
            avg_price = (sum(float(f["price"]) * float(f["qty"]) for f in fills)
                          / max(sum(float(f["qty"]) for f in fills), 1e-12)
                          ) if fills else 0.0
            total_qty = sum(float(f["qty"]) for f in fills) if fills else 0.0
            total_fee = sum(float(f["commission"]) for f in fills) if fills else 0.0
            return OrderResult(
                success=True,
                exchange_order_id=str(data["orderId"]),
                fill_price=avg_price,
                fill_size=total_qty,
                fees_usd=total_fee,
                raw=data,
            )
        return OrderResult(success=False, error=str(data), raw=data)

    def market_buy(self, asset: str, notional_usd: float) -> OrderResult:
        params = {
            "symbol": _to_binance_symbol(asset, self.quote_asset),
            "side": "BUY",
            "type": "MARKET",
            "quoteOrderQty": round(notional_usd, 2),
            "newClientOrderId": str(uuid.uuid4())[:32],
        }
        return self._post_order(params)

    def market_sell(self, asset: str, size: float) -> OrderResult:
        params = {
            "symbol": _to_binance_symbol(asset, self.quote_asset),
            "side": "SELL",
            "type": "MARKET",
            "quantity": round(size, 8),
            "newClientOrderId": str(uuid.uuid4())[:32],
        }
        return self._post_order(params)

    def limit_buy(self, asset: str, price: float, size: float) -> OrderResult:
        params = {
            "symbol": _to_binance_symbol(asset, self.quote_asset),
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": round(size, 8),
            "price": round(price, 2),
            "newClientOrderId": str(uuid.uuid4())[:32],
        }
        return self._post_order(params)

    def limit_sell(self, asset: str, price: float, size: float) -> OrderResult:
        params = {
            "symbol": _to_binance_symbol(asset, self.quote_asset),
            "side": "SELL",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": round(size, 8),
            "price": round(price, 2),
            "newClientOrderId": str(uuid.uuid4())[:32],
        }
        return self._post_order(params)

    # ------------------------------------------------------------------
    # Account / positions
    # ------------------------------------------------------------------

    def get_position(self, asset: str) -> float:
        if self.dry_run:
            return self._positions_cache.get(asset, 0.0)
        base = asset.split("-")[0] if "-" in asset else asset
        try:
            data = self._signed_request("GET", "/api/v3/account", {})
        except Exception as e:
            print(f"[binance] get_position {asset}: {e}", flush=True)
            return 0.0
        for bal in data.get("balances", []):
            if bal.get("asset") == base.upper():
                try:
                    return float(bal.get("free", 0))
                except Exception:
                    return 0.0
        return 0.0
