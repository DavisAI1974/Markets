from .base import Exchange, OrderResult, PriceQuote
from .paper import PaperExchange
from .coinbase import CoinbaseExchange
from .binance import BinanceExchange
from .kraken import KrakenExchange


def make_exchange(name: str, **kwargs):
    """Factory for selecting an exchange adapter by config name.

    name: "paper" | "coinbase" | "binance" | "kraken"
    kwargs: forwarded to the adapter constructor (api_key, api_secret,
            dry_run, etc.). Adapter defaults read from env vars when
            not passed.
    """
    name = (name or "paper").lower()
    if name == "paper":
        return PaperExchange(**kwargs)
    if name == "coinbase":
        return CoinbaseExchange(**kwargs)
    if name == "binance":
        return BinanceExchange(**kwargs)
    if name == "kraken":
        return KrakenExchange(**kwargs)
    raise ValueError(f"unknown exchange '{name}'; use one of: "
                       f"paper, coinbase, binance, kraken")


__all__ = [
    "Exchange", "OrderResult", "PriceQuote",
    "PaperExchange", "CoinbaseExchange", "BinanceExchange", "KrakenExchange",
    "make_exchange",
]
