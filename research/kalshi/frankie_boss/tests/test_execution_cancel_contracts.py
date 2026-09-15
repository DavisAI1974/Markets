"""Synthetic immutable cancellation wire contracts; no venue access."""
from dataclasses import replace
import pytest
from research.kalshi.frankie_boss.execution_contracts import AccountKey
from research.kalshi.frankie_boss.execution_cancel_contracts import CancelWire, cancel_path
H='a'*64


def wire():
    return CancelWire(H,H,AccountKey('kalshi','replay','synthetic'),'provider-1','client-1',
        'SYN:TICKER',0,'DELETE',cancel_path('provider-1',0,'SYN:TICKER'),b'',20)


def test_delete_route_is_explicit_and_hash_bound():
    value=wire()
    assert value.path == '/trade-api/v2/portfolio/events/orders/provider-1?subaccount=0&exchange_index=-1&market_ticker=SYN%3ATICKER'
    assert value.digest != replace(value,expires_ns=21).digest


@pytest.mark.parametrize('changes',[dict(method='POST'),dict(body=b'{}'),dict(path='/other'),
    dict(provider_order_id='../other'),dict(subaccount=64),dict(expires_ns=0),dict(expires_ns=True),
    dict(account=AccountKey('tastytrade','replay','synthetic'))])
def test_cancel_wire_cannot_be_coerced_or_redirected(changes):
    with pytest.raises(ValueError):replace(wire(),**changes)
