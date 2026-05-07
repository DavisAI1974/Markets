"""
exchanges/kraken.py — Kraken Spot adapter.

Implements the Exchange Protocol against Kraken's REST API
(https://docs.kraken.com/rest/). API keys live in env vars on the user's
own machine; this module never holds or transmits them anywhere except
to api.kraken.com.

SAFETY:
- `dry_run=True` is the default. Set `dry_run=False` (or `EXCHANGE_LIVE=1`
  in env) only after validating manually first.
- Kraken does not provide a public testnet for spot, so dry-run mode is
  particularly important here.
- We default to MARKET orders. Use limit_* if you want quote control.

Required env vars:
- KRAKEN_API_KEY     (or pass api_key kwarg)
- KRAKEN_API_SECRET  (or pass api_secret kwarg; this is the base64-
                       encoded API secret you copy from Kraken)

Asset symbol convention: this module accepts "ETH-USD" / "BTC-USD" and
maps to Kraken's pair format ("XETHZUSD", "XXBTZUSD"). For pairs not in
the static mapping below, it tries the "<base>USD" form. Override
`pair_overrides` for any custom mapping you need.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
import urllib.parse
import uuid

import requests

from .base import OrderResult, PriceQuote


KRAKEN_REST = "https://api.kraken.com"

# Kraken's "XBT" naming for Bitcoin and the Z-prefix for fiat are quirky;
# this static mapping covers the common pairs. Add to pair_overrides on
# the constructor for anything else.
_DEFAULT_PAIR_MAP = {
    "BTC-USD": "XXBTZUSD",
    "ETH-USD": "XETHZUSD",
    "SOL-USD": "SOLUSD",
    "ADA-USD": "ADAUSD",
    "XRP-USD": "XXRPZUSD",
    "DOGE-USD": "XDGUSD",
}


class KrakenExchange:
    name = "kraken"

    def __init__(self,
                  api_key: str | None = None,
                  api_secret: str | None = None,
                  dry_run: bool | None = None,
                  pair_overrides: dict | None = None,
                  timeout_s: float = 10.0):
        self.api_key = api_key or os.environ.get("KRAKEN_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("KRAKEN_API_SECRET", "")
        if dry_run is None:
            env = os.environ.get("EXCHANGE_LIVE", "0").lower()
            dry_run = env not in ("1", "true", "yes")
        self.dry_run = dry_run
        self.pair_map = dict(_DEFAULT_PAIR_MAP)
        if pair_overrides:
            self.pair_map.update(pair_overrides)
        self.timeout_s = timeout_s
        self._positions_cache: dict[str, float] = {}

    def _pair(self, asset: str) -> str:
        if asset in self.pair_map:
            return self.pair_map[asset]
        if "-" in asset:
            base = asset.split("-")[0]
            return f"{base}USD"
        return asset

    # ------------------------------------------------------------------
    # Signing — Kraken uses HMAC-SHA512 of (path + sha256(nonce + post_data))
    # signed with the base64-decoded api_secret.
    # ------------------------------------------------------------------

    def _sign(self, path: str, post_data: str, nonce: str) -> str:
        if not self.api_secret:
            raise RuntimeError("KRAKEN_API_SECRET not set")
        sha256 = hashlib.sha256((nonce + post_data).encode()).digest()
        msg = path.encode() + sha256
        secret = base64.b64decode(self.api_secret)
        sig = hmac.new(secret, msg, hashlib.sha512).digest()
        return base64.b64encode(sig).decode()

    def _private_post(self, path: str, params: dict) -> dict:
        if not self.api_key or not self.api_secret:
            raise RuntimeError("KRAKEN_API_KEY / KRAKEN_API_SECRET not set")
        nonce = str(int(time.time() * 1000))
        params = dict(params)
        params["nonce"] = nonce
        post_data = urllib.parse.urlencode(params)
        headers = {
            "API-Key": self.api_key,
            "API-Sign": self._sign(path, post_data, nonce),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        r = requests.post(KRAKEN_REST + path, data=post_data, headers=headers,
                            timeout=self.timeout_s)
        return r.json()

    # ------------------------------------------------------------------
    # Quote
    # ------------------------------------------------------------------

    def get_quote(self, asset: str) -> PriceQuote:
        pair = self._pair(asset)
        url = f"{KRAKEN_REST}/0/public/Ticker"
        try:
            r = requests.get(url, params={"pair": pair}, timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json()
            if data.get("error"):
                raise RuntimeError(str(data["error"]))
            result = data.get("result", {})
            tk = next(iter(result.values()), None)
            if not tk:
                raise RuntimeError("empty result")
            bid = float(tk["b"][0])
            ask = float(tk["a"][0])
        except Exception as e:
            raise RuntimeError(f"kraken quote failed for {asset}: {e}")
        return PriceQuote(asset=asset, bid=bid, ask=ask, mid=(bid + ask) / 2,
                           timestamp_utc=time.time())

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def _add_order(self, params: dict) -> OrderResult:
        path = "/0/private/AddOrder"
        if self.dry_run:
            return OrderResult(
                success=True,
                exchange_order_id=f"DRYRUN-{str(uuid.uuid4())[:8]}",
                raw={"dry_run": True, "would_post": params},
            )
        try:
            data = self._private_post(path, params)
        except Exception as e:
            return OrderResult(success=False, error=str(e))
        if data.get("error"):
            return OrderResult(success=False, error=str(data["error"]), raw=data)
        result = data.get("result") or {}
        txid = (result.get("txid") or [""])[0]
        return OrderResult(success=True, exchange_order_id=str(txid), raw=data)

    def market_buy(self, asset: str, notional_usd: float) -> OrderResult:
        # Kraken doesn't accept quote-currency size for market orders;
        # we estimate volume from the current ask.
        q = self.get_quote(asset)
        if q.ask <= 0:
            return OrderResult(success=False, error="no live ask")
        volume = round(notional_usd / q.ask, 8)
        params = {
            "ordertype": "market",
            "type": "buy",
            "volume": str(volume),
            "pair": self._pair(asset),
            "userref": int(uuid.uuid4().int >> 100) & 0x7fffffff,
        }
        return self._add_order(params)

    def market_sell(self, asset: str, size: float) -> OrderResult:
        params = {
            "ordertype": "market",
            "type": "sell",
            "volume": str(round(size, 8)),
            "pair": self._pair(asset),
            "userref": int(uuid.uuid4().int >> 100) & 0x7fffffff,
        }
        return self._add_order(params)

    def limit_buy(self, asset: str, price: float, size: float) -> OrderResult:
        params = {
            "ordertype": "limit",
            "type": "buy",
            "volume": str(round(size, 8)),
            "price": str(round(price, 2)),
            "pair": self._pair(asset),
            "userref": int(uuid.uuid4().int >> 100) & 0x7fffffff,
        }
        return self._add_order(params)

    def limit_sell(self, asset: str, price: float, size: float) -> OrderResult:
        params = {
            "ordertype": "limit",
            "type": "sell",
            "volume": str(round(size, 8)),
            "price": str(round(price, 2)),
            "pair": self._pair(asset),
            "userref": int(uuid.uuid4().int >> 100) & 0x7fffffff,
        }
        return self._add_order(params)

    # ------------------------------------------------------------------
    # Account / positions
    # ------------------------------------------------------------------

    def get_position(self, asset: str) -> float:
        if self.dry_run:
            return self._positions_cache.get(asset, 0.0)
        base = asset.split("-")[0] if "-" in asset else asset
        try:
            data = self._private_post("/0/private/Balance", {})
        except Exception as e:
            print(f"[kraken] get_position {asset}: {e}", flush=True)
            return 0.0
        if data.get("error"):
            return 0.0
        # Kraken returns balances keyed by their asset codes (e.g. "XETH")
        result = data.get("result") or {}
        for k, v in result.items():
            if k.upper().endswith(base.upper()) or k.upper() == base.upper():
                try:
                    return float(v)
                except Exception:
                    return 0.0
        return 0.0
