"""Explicit Kalshi cancellation controls; distinct from exposure-increasing wires."""
from dataclasses import dataclass
import re
from urllib.parse import quote
from .execution_contracts import AccountKey, Contract


def cancel_path(provider_order_id, subaccount, market_ticker):
    if type(provider_order_id) is not str or re.fullmatch(r'[A-Za-z0-9_-]+',provider_order_id) is None:
        raise ValueError('plain provider order path identifier required')
    if type(subaccount) is not int or not 0 <= subaccount <= 63:
        raise ValueError('explicit Kalshi subaccount 0..63 required')
    if type(market_ticker) is not str or re.fullmatch(r'[A-Za-z0-9_.:/-]+',market_ticker) is None:
        raise ValueError('explicit market ticker required for cancellation routing')
    return ('/trade-api/v2/portfolio/events/orders/' + provider_order_id +
            f'?subaccount={subaccount}&exchange_index=-1&market_ticker=' + quote(market_ticker,safe=''))


@dataclass(frozen=True)
class CancelAuthorization(Contract):
    account: AccountKey
    authority_hash: str
    adapter_hash: str
    transport_hash: str
    issuer_hash: str
    schema_hash: str
    created_ns: int
    expires_ns: int
    max_target_age_ns: int

    def __post_init__(self):
        super().__post_init__()
        if self.account.venue != 'kalshi' or self.expires_ns <= self.created_ns or self.max_target_age_ns <= 0:
            raise ValueError('explicit Kalshi cancellation authority and positive time bounds required')


@dataclass(frozen=True)
class CancelIntent(Contract):
    control_id: str
    original_intent_id: str
    original_intent_hash: str
    submitted_wire_hash: str
    account: AccountKey
    provider_order_id: str
    client_id: str
    target_receipt_hash: str
    authorization_hash: str
    created_ns: int
    expires_ns: int

    def __post_init__(self):
        super().__post_init__()
        if self.account.venue != 'kalshi' or self.expires_ns <= self.created_ns:
            raise ValueError('bounded Kalshi cancellation intent required')


@dataclass(frozen=True)
class CancelWire(Contract):
    control_hash: str
    adapter_hash: str
    account: AccountKey
    provider_order_id: str
    client_id: str
    market_ticker: str
    subaccount: int
    method: str
    path: str
    body: bytes
    expires_ns: int

    def __post_init__(self):
        super().__post_init__()
        if self.account.venue != 'kalshi' or self.method != 'DELETE' or self.body != b'' or self.expires_ns <= 0:
            raise ValueError('explicit bounded Kalshi DELETE wire with empty body required')
        if self.path != cancel_path(self.provider_order_id,self.subaccount,self.market_ticker):
            raise ValueError('cancellation route differs from exact target/subaccount/ticker')
