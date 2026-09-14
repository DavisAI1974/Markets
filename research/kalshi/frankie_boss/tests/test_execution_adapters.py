"""Pure adapter fixtures and fake transports; no venue, credential or network access."""
from dataclasses import replace
from fractions import Fraction
import json

import pytest

from test_execution_policy import fixture, H, codes
from research.kalshi.frankie_boss.execution_contracts import AccountKey, Instrument, Registry, Ratio, SignedRatio, Valuation, MarketSnapshot
from research.kalshi.frankie_boss.execution_ledger import ExecutionLedger, WireRequest, Observation
from research.kalshi.frankie_boss.execution_adapters import (
    KalshiPin, TastytradePin, TransportReceipt, PreflightRequest,
    translate, preflight_request, parse_order_response, parse_kalshi_fills, observation, parse_tastytrade_preflight,
    KALSHI_CREATE_PATH, TASTYTRADE_ORDERS_PATH, TASTYTRADE_DRY_RUN_PATH, _decimal_text, _parse_iso_ns)

SECOND = 1_000_000_000
RECEIVED = 12 * SECOND   # trusted receive clock; the ledger fixture's approval clock is the abstract integer 10


KALSHI_ACCOUNT = AccountKey('kalshi', 'replay', 'primary')
TASTY_ACCOUNT = AccountKey('tastytrade', 'replay', '5WT12345')


def kalshi_pin(**changes):
    base = dict(account=KALSHI_ACCOUNT, instrument_id='KX', ticker='KXNATGASD-26SEP15-T3.20', outcome='yes',
                self_trade_prevention_type='taker_at_cross', subaccount=0, price_units_per_dollar=100,
                quantity_units_per_contract=1)
    return KalshiPin(**{**base, **changes})


def tasty_pin(**changes):
    base = dict(account=TASTY_ACCOUNT, instrument_id='SYN', symbol='/NGZ6', instrument_type='Future',
                price_effect_buy='Debit', price_effect_sell='Credit', automated_source=True, source='boss',
                price_units_per_currency=1000, quantity_units_per_contract=1)
    return TastytradePin(**{**base, **changes})


def venue_fixture(venue, *, max_price=99, price=None, **pin_changes):
    """Re-anchor the shared policy fixture on a venue-specific account, instrument and pin."""
    args = fixture()
    if venue == 'kalshi':
        account = KALSHI_ACCOUNT
        units = args['policy'].units
        instrument = Instrument('KX', 'event', 'KXNATGASD', 'expiry-A', units, 1, 1, 1, max_price,
                                ('venue:kalshi', 'underlying:KXNATGASD'), H)
        pin = kalshi_pin(**pin_changes)
        price = 56 if price is None else price
        bid, ask = price - 1, price
    else:
        account = TASTY_ACCOUNT
        instrument = args['registry'].instruments[0]
        pin = tasty_pin(**pin_changes)
        price, bid, ask = 51, 50, 51
    registry = Registry((instrument,))
    policy = replace(args['policy'], allowed_accounts=(account,), allowed_instruments=(instrument.instrument_id,),
                     allowed_products=(instrument.product,), trusted_adapters=(pin.digest,),
                     allowed_tifs=('day', 'good_till_canceled', 'fill_or_kill', 'immediate_or_cancel'),
                     scope_limits=tuple(replace(s, scope=scope) for s, scope in zip(args['policy'].scope_limits, instrument.scopes)))
    valuation = Valuation(instrument.instrument_id, registry.digest, H, H, 9, instrument.min_price, instrument.max_price,
                          Ratio(100, 1), Ratio(2, 1), Ratio(0, 1), 'buy', SignedRatio(0, 1), SignedRatio(2, 1))
    intent = replace(args['intent'], account=account, instrument_id=instrument.instrument_id, price=price,
                     tif='good_till_canceled' if venue == 'kalshi' else 'day', registry_hash=registry.digest,
                     policy_hash=policy.digest, valuation_hash=valuation.digest, adapter_hash=pin.digest)
    market = MarketSnapshot(instrument.instrument_id, registry.digest, H, H, 8, 9, 9, bid, ask, True)
    account_snapshot = replace(args['account'], account=account,
                               exposures=tuple(replace(e, scope=scope) for e, scope in zip(args['account'].exposures, instrument.scopes)))
    args.update(intent=intent, policy=policy, registry=registry, valuation=valuation, expected_valuation_hash=valuation.digest,
                market=market, account=account_snapshot)
    return args, instrument, pin


def receipt(wire, account, source, body, *, status=None, received_ns=RECEIVED):
    default = 201 if source in ('kalshi.create_order', 'tastytrade.submit_order') else 200
    return TransportReceipt(wire.digest, account, source, default if status is None else status, body, received_ns)


def kalshi_create_body(wire, fill='0.00', remaining='2.00', **extra):
    return json.dumps(dict(order_id='ord-1', client_order_id=wire.client_id, fill_count=fill, remaining_count=remaining,
                           ts_ms=11_000, **extra)).encode()


def kalshi_order_body(wire, status='resting', fill='0.00', remaining='2.00', initial='2.00', **extra):
    sent = json.loads(wire.body)
    order = dict(order_id='ord-1', client_order_id=wire.client_id, ticker=sent['ticker'], book_side=sent['side'],
                 outcome_side='yes', status=status, yes_price_dollars=sent['price'], fill_count_fp=fill,
                 remaining_count_fp=remaining, initial_count_fp=initial, last_update_time='1970-01-01T00:00:11.000000Z',
                 created_time='1970-01-01T00:00:10Z')
    order.update(extra)
    return json.dumps(dict(order=order)).encode()


def tasty_order(wire, status='Routed', remaining='2', fills=(), **extra):
    sent = json.loads(wire.body)
    leg = dict(sent['legs'][0], fills=[dict(**{'fill-id': f'f{i}', 'quantity': q, 'fill-price': sent['price'],
                                              'filled-at': '1970-01-01T00:00:11Z', 'ext-exec-id': f'x{i}',
                                              'ext-group-fill-id': 'g', 'destination-venue': 'CME'}) for i, q in enumerate(fills)],
               **{'remaining-quantity': remaining})
    return {**{'id': '9001', 'account-number': '5WT12345', 'status': status, 'size': sent['legs'][0]['quantity'],
               'remaining-quantity': remaining, 'updated-at': '1970-01-01T00:00:11.000+00:00',
               'received-at': '1970-01-01T00:00:10Z', 'legs': [leg], 'external-identifier': wire.client_id},
            **{k: sent[k] for k in ('order-type', 'time-in-force', 'price', 'price-effect')}, **extra}


def tasty_submit_body(wire, status='Routed', **kw):
    return json.dumps({'data': {'order': tasty_order(wire, status, **kw), 'warnings': [], 'errors': []}, 'context': '/x'}).encode()


def tasty_get_body(wire, status='Routed', **kw):
    return json.dumps({'data': tasty_order(wire, status, **kw), 'context': '/x'}).encode()


# --- 1. exact wire bytes -----------------------------------------------------------

def test_kalshi_yes_buy_renders_documented_v2_shape_exactly():
    args, instrument, pin = venue_fixture('kalshi')
    wire = translate(args['intent'], instrument, pin)
    assert wire == translate(args['intent'], instrument, pin)
    assert (wire.method, wire.path, wire.client_id) == ('POST', KALSHI_CREATE_PATH, args['intent'].intent_id)
    assert (wire.intent_hash, wire.adapter_hash) == (args['intent'].digest, pin.digest)
    assert wire.body == (b'{"client_order_id":"intent/1","count":"2.00","price":"0.56","self_trade_prevention_type":'
                         b'"taker_at_cross","side":"bid","subaccount":0,"ticker":"KXNATGASD-26SEP15-T3.20",'
                         b'"time_in_force":"good_till_canceled"}')


@pytest.mark.parametrize('outcome,side,expected_side,expected_price', [
    ('yes', 'buy', 'bid', '0.56'), ('yes', 'sell', 'ask', '0.56'),
    ('no', 'buy', 'ask', '0.44'), ('no', 'sell', 'bid', '0.44')])
def test_kalshi_no_economics_use_only_the_explicit_complement_mapping(outcome, side, expected_side, expected_price):
    args, instrument, pin = venue_fixture('kalshi', outcome=outcome)
    intent = replace(args['intent'], side=side)
    body = json.loads(translate(intent, instrument, pin).body)
    assert (body['side'], body['price']) == (expected_side, expected_price)
    assert 'yes_price' not in body and 'no_price' not in body and 'action' not in body


def test_kalshi_price_precision_is_exact_up_to_four_decimals_never_rounded():
    args, instrument, pin = venue_fixture('kalshi', max_price=9_999, price=5_601, price_units_per_dollar=10_000)
    assert json.loads(translate(args['intent'], instrument, pin).body)['price'] == '0.5601'
    args, instrument, pin = venue_fixture('kalshi', max_price=99_999, price=56_001, price_units_per_dollar=100_000)
    with pytest.raises(ValueError, match='refusing to round'):
        translate(args['intent'], instrument, pin)


def test_tastytrade_future_renders_documented_shape_with_pinned_effect():
    args, instrument, pin = venue_fixture('tastytrade')
    wire = translate(args['intent'], instrument, pin)
    assert wire.path == TASTYTRADE_ORDERS_PATH.format(account='5WT12345')
    assert json.loads(wire.body) == {'order-type': 'Limit', 'time-in-force': 'Day', 'price': '0.051', 'price-effect': 'Debit',
                                     'legs': [{'instrument-type': 'Future', 'symbol': '/NGZ6', 'action': 'Buy', 'quantity': '2'}],
                                     'external-identifier': 'intent/1', 'automated-source': True, 'source': 'boss'}
    sell = json.loads(translate(replace(args['intent'], side='sell'), instrument, pin).body)
    assert (sell['price-effect'], sell['legs'][0]['action']) == ('Credit', 'Sell')


@pytest.mark.parametrize('side,effect,action', [('buy', 'open', 'Buy to Open'), ('buy', 'close', 'Buy to Close'),
                                                ('sell', 'open', 'Sell to Open'), ('sell', 'close', 'Sell to Close')])
def test_tastytrade_future_option_actions_carry_opening_closing_intent(side, effect, action):
    args, instrument, pin = venue_fixture('tastytrade')
    instrument = replace(instrument, product='future_option')
    registry = Registry((instrument,))
    pin = replace(pin, instrument_type='Future Option', price_effect_buy='Credit', price_effect_sell='Debit')
    intent = replace(args['intent'], side=side, effect=effect, registry_hash=registry.digest, adapter_hash=pin.digest)
    body = json.loads(translate(intent, instrument, pin).body)
    assert body['legs'][0]['action'] == action
    assert body['price-effect'] == ('Credit' if side == 'buy' else 'Debit')  # pinned, not derived from the action


@pytest.mark.parametrize('venue,changes,message', [
    ('kalshi', {'tif': 'day'}, 'Kalshi v2 subset'),
    ('kalshi', {'effect': 'close'}, 'Kalshi v2 subset'),
    ('kalshi', {'price': 100}, 'off the instrument grid'),
    ('kalshi', {'order_type': 'limit', 'quantity': 3}, None),
    ('tastytrade', {'tif': 'fill_or_kill'}, 'tastytrade subset'),
    ('tastytrade', {'price': -50}, 'price-effect is pinned'),
    ('tastytrade', {'adapter_hash': 'b' * 64}, 'adapter_hash'),
    ('tastytrade', {'account': AccountKey('tastytrade', 'live', '5WT12345')}, 'account/environment'),
    ('tastytrade', {'instrument_id': 'OTHER'}, 'different instruments'),
])
def test_unsupported_or_conflicting_intents_produce_no_bytes(venue, changes, message):
    args, instrument, pin = venue_fixture(venue)
    intent = replace(args['intent'], **changes)
    if changes == {'order_type': 'limit', 'quantity': 3}:
        instrument = replace(instrument, quantity_step=2)
    with pytest.raises(ValueError, match=message or '.'):
        translate(intent, instrument, pin)


def test_kalshi_price_outside_open_unit_interval_and_wrong_product_reject():
    args, instrument, pin = venue_fixture('kalshi', price=99, price_units_per_dollar=99)   # 99/99 == 1.00 dollar
    with pytest.raises(ValueError, match='strictly inside'):
        translate(args['intent'], instrument, pin)
    args, instrument, pin = venue_fixture('kalshi')
    with pytest.raises(ValueError, match="only 'event'"):
        translate(args['intent'], replace(instrument, product='future'), pin)


def test_kalshi_count_decimals_are_exactly_two_and_fractional_units_refuse():
    args, instrument, pin = venue_fixture('kalshi', quantity_units_per_contract=100)
    intent = replace(args['intent'], quantity=250)
    assert json.loads(translate(intent, instrument, pin).body)['count'] == '2.50'
    args, instrument, pin = venue_fixture('kalshi', quantity_units_per_contract=1000)
    with pytest.raises(ValueError, match='refusing to round'):
        translate(replace(args['intent'], quantity=251), instrument, pin)   # 0.251 contracts needs three places


@pytest.mark.parametrize('kwargs,message', [
    (dict(outcome='maybe'), 'yes/no outcome'), (dict(self_trade_prevention_type='none'), 'self-trade'),
    (dict(subaccount=64), 'subaccount'), (dict(price_units_per_dollar=0), 'unit scales'),
    (dict(account=AccountKey('tastytrade', 'replay', 'x')), 'kalshi account')])
def test_kalshi_pin_rejects_unsupported_enums_and_wrong_venue(kwargs, message):
    with pytest.raises(ValueError, match=message):
        kalshi_pin(**kwargs)


@pytest.mark.parametrize('kwargs,message', [
    (dict(instrument_type='Equity'), 'Future or Future Option'), (dict(price_effect_buy='Long'), 'Debit or Credit'),
    (dict(account=AccountKey('tastytrade', 'replay', 'bad account')), 'plain identifier'),
    (dict(quantity_units_per_contract=0), 'unit scales')])
def test_tastytrade_pin_rejects_unsupported_enums(kwargs, message):
    with pytest.raises(ValueError, match=message):
        tasty_pin(**kwargs)


def test_decimal_rendering_is_integer_exact():
    assert _decimal_text(Fraction(1, 8), min_decimals=1, max_decimals=8) == '0.125'
    assert _decimal_text(Fraction(1234, 100), min_decimals=2, max_decimals=2) == '12.34'
    with pytest.raises(ValueError):
        _decimal_text(Fraction(1, 3), min_decimals=1, max_decimals=8)
    assert _parse_iso_ns('1970-01-01T00:00:11.5Z', 'clock') == 11_500_000_000


def test_preflight_is_a_distinct_type_bound_to_the_wire():
    args, instrument, pin = venue_fixture('tastytrade')
    wire = translate(args['intent'], instrument, pin)
    pre = preflight_request(wire, pin)
    assert type(pre) is PreflightRequest and pre.path == TASTYTRADE_DRY_RUN_PATH.format(account='5WT12345')
    assert pre.body == wire.body and pre.wire_hash == wire.digest
    body = json.dumps({'data': {'order': tasty_order(wire), 'warnings': [], 'errors': []}}).encode()
    ok = parse_tastytrade_preflight(TransportReceipt(wire.digest, args['intent'].account, 'tastytrade.dry_run', 200, body, RECEIVED), preflight=pre)
    assert (ok.errors, ok.warnings) == (0, 0)
    warned = json.dumps({'data': {'order': tasty_order(wire), 'warnings': [{'code': 'x', 'message': 'y'}], 'errors': []}}).encode()
    with pytest.raises(ValueError, match='unhandled warnings'):
        parse_tastytrade_preflight(TransportReceipt(wire.digest, args['intent'].account, 'tastytrade.dry_run', 200, warned, RECEIVED), preflight=pre)


# --- 2. provider bytes -> typed facts ----------------------------------------------

def test_kalshi_create_ack_and_get_order_facts_bind_bytes_ids_and_clocks():
    args, instrument, pin = venue_fixture('kalshi')
    intent, wire = args['intent'], translate(args['intent'], instrument, pin)
    body = kalshi_create_body(wire, average_fill_price='0.5600')  # unknown extra fields retained, not promoted
    fact = parse_order_response(receipt(wire, intent.account, 'kalshi.create_order', body), intent=intent, wire=wire, pin=pin,
                                expected_source='kalshi.create_order')
    assert (fact.status, fact.provider_status, fact.provider_id, fact.client_id) == ('ACKNOWLEDGED', 'created', 'ord-1', 'intent/1')
    assert (fact.filled_quantity, fact.remaining_quantity, fact.initial_quantity) == (0, 2, 2)
    assert (fact.event_ns, fact.received_ns) == (11_000_000_000, RECEIVED)
    assert fact.request_hash == wire.digest and fact.response_hash == TransportReceipt(wire.digest, intent.account, 'kalshi.create_order', 201, body, RECEIVED).body_hash
    partial = parse_order_response(receipt(wire, intent.account, 'kalshi.get_order', kalshi_order_body(wire, fill='1.00', remaining='1.00')),
                                   intent=intent, wire=wire, pin=pin, expected_source='kalshi.get_order')
    assert (partial.status, partial.filled_quantity, partial.remaining_quantity) == ('PARTIAL', 1, 1)
    done = parse_order_response(receipt(wire, intent.account, 'kalshi.get_order', kalshi_order_body(wire, 'executed', '2.00', '0.00')),
                                intent=intent, wire=wire, pin=pin, expected_source='kalshi.get_order')
    assert (done.status, done.filled_quantity, done.remaining_quantity) == ('FILLED', 2, 0)
    canceled = parse_order_response(receipt(wire, intent.account, 'kalshi.get_order', kalshi_order_body(wire, 'canceled', '1.00', '1.00')),
                                    intent=intent, wire=wire, pin=pin, expected_source='kalshi.get_order')
    assert (canceled.status, canceled.filled_quantity, canceled.remaining_quantity) == ('CANCELED', 1, 0)


@pytest.mark.parametrize('body_changes,message', [
    ({'client_order_id': 'other'}, 'client_order_id'), ({'fill_count': '3.00'}, 'conflict'),
    ({'fill_count': '0.50', 'remaining_count': '1.50'}, 'finer than'), ({'fill_count': 0}, 'wrong JSON type'),
    ({'ts_ms': '11000'}, 'wrong JSON type'), ({'order_id': 'a b'}, 'plain identifier'),
    ({'fill_count': '2.00', 'remaining_count': '0.00'}, 'conflicting counts'),
    ({'fill_count': '1.00'}, 'do not sum'), ({'fill_count': '1e0'}, 'canonical'),
    ({'ts_ms': 13_000}, 'later than the trusted receive clock')])
def test_kalshi_create_malformed_or_conflicting_bodies_refuse(body_changes, message):
    args, instrument, pin = venue_fixture('kalshi')
    intent, wire = args['intent'], translate(args['intent'], instrument, pin)
    body = json.loads(kalshi_create_body(wire)); body.update(body_changes)
    with pytest.raises(ValueError, match=message):
        parse_order_response(receipt(wire, intent.account, 'kalshi.create_order', json.dumps(body).encode()),
                             intent=intent, wire=wire, pin=pin, expected_source='kalshi.create_order')


@pytest.mark.parametrize('kw,message', [
    (dict(status='pending'), 'unknown Kalshi order status'), (dict(status='executed', fill='1.00', remaining='1.00'), 'executed status conflicts'),
    (dict(fill='1.00', remaining='0.50'), 'do not sum'), (dict(initial='3.00', remaining='3.00'), 'sent order size'),
    (dict(book_side='ask'), 'differ from the sent wire'), (dict(yes_price_dollars='0.57'), 'yes price differs'),
    (dict(last_update_time='1970-01-01T00:00:11+05:00'), 'ISO-8601 UTC')])
def test_kalshi_get_order_conflicts_refuse(kw, message):
    args, instrument, pin = venue_fixture('kalshi')
    intent, wire = args['intent'], translate(args['intent'], instrument, pin)
    with pytest.raises(ValueError, match=message):
        parse_order_response(receipt(wire, intent.account, 'kalshi.get_order', kalshi_order_body(wire, **kw)),
                             intent=intent, wire=wire, pin=pin, expected_source='kalshi.get_order')


def test_non_success_status_is_never_a_provider_fact():
    """A timeout/5xx/unknown body is not rejected-and-safe; it is no fact at all."""
    args, instrument, pin = venue_fixture('kalshi')
    intent, wire = args['intent'], translate(args['intent'], instrument, pin)
    for status, body in ((500, b'{"error":"internal"}'), (429, b''), (201, b'not json'), (409, kalshi_create_body(wire))):
        with pytest.raises(ValueError):
            parse_order_response(receipt(wire, intent.account, 'kalshi.create_order', body, status=status),
                                 intent=intent, wire=wire, pin=pin, expected_source='kalshi.create_order')


def test_receipt_provenance_pins_are_independent_of_json_identity():
    args, instrument, pin = venue_fixture('kalshi')
    intent, wire = args['intent'], translate(args['intent'], instrument, pin)
    body = kalshi_create_body(wire)
    good = receipt(wire, intent.account, 'kalshi.create_order', body)
    with pytest.raises(ValueError, match='expected source'):
        parse_order_response(good, intent=intent, wire=wire, pin=pin, expected_source='kalshi.get_order')
    with pytest.raises(ValueError, match='one bound chain'):
        parse_order_response(replace(good, wire_hash='b' * 64), intent=intent, wire=wire, pin=pin, expected_source='kalshi.create_order')
    with pytest.raises(ValueError, match='account/environment'):
        parse_order_response(replace(good, account=AccountKey('kalshi', 'live', 'primary')), intent=intent, wire=wire, pin=pin,
                             expected_source='kalshi.create_order')
    with pytest.raises(ValueError, match='not one of'):
        parse_order_response(replace(good, source='tastytrade.submit_order'), intent=intent, wire=wire, pin=pin,
                             expected_source='tastytrade.submit_order')


def test_tastytrade_submit_and_get_facts_enumerate_fills_not_acknowledgement_size():
    args, instrument, pin = venue_fixture('tastytrade')
    intent, wire = args['intent'], translate(args['intent'], instrument, pin)
    ack = parse_order_response(receipt(wire, intent.account, 'tastytrade.submit_order', tasty_submit_body(wire)),
                               intent=intent, wire=wire, pin=pin, expected_source='tastytrade.submit_order')
    assert (ack.status, ack.provider_status, ack.provider_id, ack.filled_quantity, ack.remaining_quantity) == ('ACKNOWLEDGED', 'Routed', '9001', 0, 2)
    assert ack.event_ns == 11_000_000_000
    partial = parse_order_response(receipt(wire, intent.account, 'tastytrade.get_order', tasty_get_body(wire, 'Live', remaining='1', fills=('1',))),
                                   intent=intent, wire=wire, pin=pin, expected_source='tastytrade.get_order')
    assert (partial.status, partial.filled_quantity, partial.remaining_quantity) == ('PARTIAL', 1, 1)
    filled = parse_order_response(receipt(wire, intent.account, 'tastytrade.get_order', tasty_get_body(wire, 'Filled', remaining='0', fills=('1', '1'))),
                                  intent=intent, wire=wire, pin=pin, expected_source='tastytrade.get_order')
    assert (filled.status, filled.filled_quantity, filled.remaining_quantity) == ('FILLED', 2, 0)
    cancel_requested = parse_order_response(receipt(wire, intent.account, 'tastytrade.get_order', tasty_get_body(wire, 'Cancel Requested', remaining='1', fills=('1',))),
                                            intent=intent, wire=wire, pin=pin, expected_source='tastytrade.get_order')
    assert (cancel_requested.status, cancel_requested.provider_status) == ('PARTIAL', 'Cancel Requested')  # a cancel request undoes no fill


@pytest.mark.parametrize('kw,message', [
    (dict(status='Live', remaining='1'), 'do not reconcile'),                 # size-remaining implies a fill nobody enumerated
    (dict(status='Filled', remaining='0'), 'without enumerated fills'),
    (dict(status='Rejected', remaining='0', fills=('1',)), 'Rejected status with enumerated fills'),
    (dict(status='In Flight'), 'unknown tastytrade order status'),
    (dict(status='Expired', remaining='0'), 'no ledger vocabulary'),
    (dict(status='Live', remaining='0', fills=('1', '1', '1')), 'exceed the order size'),
])
def test_tastytrade_conflicting_or_unknown_statuses_refuse(kw, message):
    args, instrument, pin = venue_fixture('tastytrade')
    intent, wire = args['intent'], translate(args['intent'], instrument, pin)
    with pytest.raises(ValueError, match=message):
        parse_order_response(receipt(wire, intent.account, 'tastytrade.get_order', tasty_get_body(wire, **kw)),
                             intent=intent, wire=wire, pin=pin, expected_source='tastytrade.get_order')


def test_tastytrade_duplicate_fill_ids_two_legs_and_wrong_account_refuse():
    args, instrument, pin = venue_fixture('tastytrade')
    intent, wire = args['intent'], translate(args['intent'], instrument, pin)
    order = tasty_order(wire, 'Live', remaining='0', fills=('1', '1'))
    order['legs'][0]['fills'][1]['fill-id'] = 'f0'
    with pytest.raises(ValueError, match='duplicate fill-id'):
        parse_order_response(receipt(wire, intent.account, 'tastytrade.get_order', json.dumps({'data': order}).encode()),
                             intent=intent, wire=wire, pin=pin, expected_source='tastytrade.get_order')
    order = tasty_order(wire); order['legs'].append(dict(order['legs'][0]))
    with pytest.raises(ValueError, match='exactly one leg'):
        parse_order_response(receipt(wire, intent.account, 'tastytrade.get_order', json.dumps({'data': order}).encode()),
                             intent=intent, wire=wire, pin=pin, expected_source='tastytrade.get_order')
    order = tasty_order(wire, **{'account-number': '5WT99999'})
    with pytest.raises(ValueError, match='account-number'):
        parse_order_response(receipt(wire, intent.account, 'tastytrade.get_order', json.dumps({'data': order}).encode()),
                             intent=intent, wire=wire, pin=pin, expected_source='tastytrade.get_order')
    with pytest.raises(ValueError, match='reported errors'):
        parse_order_response(receipt(wire, intent.account, 'tastytrade.submit_order', json.dumps(
            {'data': {'order': tasty_order(wire), 'warnings': [], 'errors': [{'code': 'x'}]}}).encode()),
            intent=intent, wire=wire, pin=pin, expected_source='tastytrade.submit_order')


# --- 4. pagination completeness -------------------------------------------------------

def fills_page(wire, cursor, *fills):
    sent = json.loads(wire.body)
    return json.dumps(dict(cursor=cursor, fills=[dict(fill_id=f, order_id='ord-1', ticker=sent['ticker'], book_side=sent['side'],
                                                      outcome_side='yes', count_fp=c, yes_price_dollars=sent['price'],
                                                      no_price_dollars='0.44', is_taker=True, fee_cost='0.01',
                                                      created_time='1970-01-01T00:00:11Z') for f, c in fills])).encode()


def test_kalshi_fills_require_a_closed_pinned_page_chain():
    args, instrument, pin = venue_fixture('kalshi')
    intent, wire = args['intent'], translate(args['intent'], instrument, pin)
    pages = (('', fills_page(wire, 'c1', ('a', '1.00'))), ('c1', fills_page(wire, '', ('b', '1.00'))))
    fact = parse_kalshi_fills(pages, intent=intent, wire=wire, pin=pin, provider_id='ord-1', received_ns=RECEIVED)
    assert (fact.fill_ids, fact.filled_quantity, fact.last_fill_ns) == (('a', 'b'), 2, 11_000_000_000)
    assert fact == parse_kalshi_fills(pages, intent=intent, wire=wire, pin=pin, provider_id='ord-1', received_ns=RECEIVED)
    with pytest.raises(ValueError, match='chain is open'):
        parse_kalshi_fills(pages[:1], intent=intent, wire=wire, pin=pin, provider_id='ord-1', received_ns=RECEIVED)
    with pytest.raises(ValueError, match='chain expected'):
        parse_kalshi_fills((pages[0], ('c9', pages[1][1])), intent=intent, wire=wire, pin=pin, provider_id='ord-1', received_ns=RECEIVED)
    with pytest.raises(ValueError, match='no pages'):
        parse_kalshi_fills((), intent=intent, wire=wire, pin=pin, provider_id='ord-1', received_ns=RECEIVED)
    empty = parse_kalshi_fills((('', fills_page(wire, '')),), intent=intent, wire=wire, pin=pin, provider_id='ord-1', received_ns=RECEIVED)
    assert (empty.fill_ids, empty.filled_quantity) == ((), 0)


def test_kalshi_fills_duplicates_foreign_orders_and_overfill_refuse():
    args, instrument, pin = venue_fixture('kalshi')
    intent, wire = args['intent'], translate(args['intent'], instrument, pin)
    dup = (('', fills_page(wire, 'c1', ('a', '1.00'))), ('c1', fills_page(wire, '', ('a', '1.00'))))
    with pytest.raises(ValueError, match='duplicate fill_id'):
        parse_kalshi_fills(dup, intent=intent, wire=wire, pin=pin, provider_id='ord-1', received_ns=RECEIVED)
    with pytest.raises(ValueError, match='another order'):
        parse_kalshi_fills((('', fills_page(wire, '', ('a', '1.00'))),), intent=intent, wire=wire, pin=pin, provider_id='ord-2', received_ns=RECEIVED)
    with pytest.raises(ValueError, match='exceed the intent quantity'):
        parse_kalshi_fills((('', fills_page(wire, '', ('a', '3.00'))),), intent=intent, wire=wire, pin=pin, provider_id='ord-1', received_ns=RECEIVED)


# --- 3 + 5. through the ledger with fake transports ------------------------------------------

def build(tmp_path, venue='kalshi'):
    args, instrument, pin = venue_fixture(venue)
    ledger = ExecutionLedger(tmp_path / 'orders.sqlite', create=True)
    ledger.create(args['intent']); assert ledger.approve(**args).allowed
    return ledger, args, instrument, pin, translate(args['intent'], instrument, pin)


def bind(fact, args, wire, rcpt, observation_id, *, snapshot_hash=H, positions_match=True):
    return observation(fact, intent=args['intent'], wire=wire, receipt=rcpt, observation_id=observation_id,
                       account_snapshot_hash=snapshot_hash, positions_match=positions_match)


def reflected(args, obs, filled):
    return replace(args['account'], observed_ns=obs.observed_ns, pnl_observed_ns=obs.observed_ns,
                   exposures=tuple(replace(e, gross=filled * 2, net_min=filled * 2, net_max=filled * 2) for e in args['account'].exposures),
                   reflected_intents=(args['intent'].intent_id,))


@pytest.mark.parametrize('venue', ['kalshi', 'tastytrade'])
def test_exactly_one_send_of_exactly_the_translated_bytes(tmp_path, venue):
    ledger, args, instrument, pin, wire = build(tmp_path, venue)
    sent = []
    def transport(request):
        sent.append((request.method, request.path, request.body)); return b'{"synthetic":"ack"}'
    ledger.dispatch_once(wire=wire, sender=transport, **args)
    assert sent == [(wire.method, wire.path, wire.body)] and ledger.state(args['intent'].intent_id)['status'] == 'SENT_UNKNOWN'
    with pytest.raises(ValueError, match='never resend'):
        ledger.dispatch_once(wire=wire, sender=transport, **args)
    assert len(sent) == 1
    ledger.close()


def test_timeout_leaves_sent_unknown_and_restart_does_not_resend(tmp_path):
    ledger, args, instrument, pin, wire = build(tmp_path)
    def hung(_): raise TimeoutError('no response; outcome unknown')
    with pytest.raises(TimeoutError):
        ledger.dispatch_once(wire=wire, sender=hung, **args)
    assert ledger.state(args['intent'].intent_id)['status'] == 'SENT_UNKNOWN' and len(ledger.reservations()) == 1
    checkpoint = ledger.checkpoint(); ledger.close()
    restored = ExecutionLedger(tmp_path / 'orders.sqlite', checkpoint=checkpoint)
    with pytest.raises(ValueError, match='never resend'):
        restored.dispatch_once(wire=wire, sender=lambda _: pytest.fail('resent after timeout'), **args)
    assert restored.state(args['intent'].intent_id)['status'] == 'SENT_UNKNOWN'
    restored.close()


def test_wrong_binding_refuses_before_any_transport_call(tmp_path):
    ledger, args, instrument, pin, wire = build(tmp_path)
    other_pin = replace(pin, ticker='KXOTHER')
    foreign = WireRequest(wire.intent_hash, other_pin.digest, 'POST', KALSHI_CREATE_PATH, wire.body, wire.client_id)
    with pytest.raises(ValueError):
        ledger.dispatch_once(wire=foreign, sender=lambda _: pytest.fail('sent under a foreign adapter'), **args)
    with pytest.raises(ValueError):
        ledger.dispatch_once(wire=replace(wire, intent_hash='b' * 64), sender=lambda _: pytest.fail('sent'), **args)
    assert ledger.state(args['intent'].intent_id)['wire'] is None
    ledger.close()


def test_ack_then_terminal_needs_independently_pinned_reflected_account(tmp_path):
    ledger, args, instrument, pin, wire = build(tmp_path)
    intent = args['intent']
    ack_bytes = kalshi_create_body(wire)
    assert ledger.dispatch_once(wire=wire, sender=lambda _: ack_bytes, **args) == ack_bytes
    ack_rcpt = receipt(wire, intent.account, 'kalshi.create_order', ack_bytes)
    ack = bind(parse_order_response(ack_rcpt, intent=intent, wire=wire, pin=pin, expected_source='kalshi.create_order'), args, wire, ack_rcpt, 'obs/1')
    assert ledger.reconcile(ack) and ledger.state(intent.intent_id)['status'] == 'ACKNOWLEDGED'
    done_rcpt = receipt(wire, intent.account, 'kalshi.get_order', kalshi_order_body(wire, 'executed', '2.00', '0.00'), received_ns=13 * SECOND)
    fact = parse_order_response(done_rcpt, intent=intent, wire=wire, pin=pin, expected_source='kalshi.get_order')
    # An order response alone: the ledger refuses the terminal release, freezes and latches.
    unreflected = bind(fact, args, wire, done_rcpt, 'obs/2')
    assert not ledger.reconcile(unreflected) and len(ledger.reservations()) == 1 and ledger.killed
    ledger.close()


def test_terminal_release_with_reflected_snapshot_and_positions_attestation(tmp_path):
    ledger, args, instrument, pin, wire = build(tmp_path)
    intent = args['intent']
    ledger.dispatch_once(wire=wire, sender=lambda _: b'ack', **args)
    done_rcpt = receipt(wire, intent.account, 'kalshi.get_order', kalshi_order_body(wire, 'executed', '2.00', '0.00'))
    fact = parse_order_response(done_rcpt, intent=intent, wire=wire, pin=pin, expected_source='kalshi.get_order')
    draft = bind(fact, args, wire, done_rcpt, 'obs/1')
    snapshot = reflected(args, draft, 2)
    obs = bind(fact, args, wire, done_rcpt, 'obs/1', snapshot_hash=snapshot.digest)
    assert ledger.reconcile(obs, account_snapshot=snapshot, expected_account_hash=snapshot.digest)
    assert ledger.reservations() == () and ledger.state(intent.intent_id)['status'] == 'FILLED'
    ledger.close()


def test_out_of_order_duplicate_and_conflicting_observations_follow_ledger_rules(tmp_path):
    ledger, args, instrument, pin, wire = build(tmp_path)
    intent = args['intent']
    ledger.dispatch_once(wire=wire, sender=lambda _: b'ack', **args)
    later = receipt(wire, intent.account, 'kalshi.get_order', kalshi_order_body(wire, fill='1.00', remaining='1.00'), received_ns=14 * SECOND)
    partial = bind(parse_order_response(later, intent=intent, wire=wire, pin=pin, expected_source='kalshi.get_order'), args, wire, later, 'obs/1')
    assert ledger.reconcile(partial)
    earlier = receipt(wire, intent.account, 'kalshi.create_order', kalshi_create_body(wire), received_ns=12 * SECOND)
    stale = bind(parse_order_response(earlier, intent=intent, wire=wire, pin=pin, expected_source='kalshi.create_order'), args, wire, earlier, 'obs/2')
    assert not ledger.reconcile(stale) and ledger.killed          # out-of-order/regressing fill: frozen, not applied
    assert ledger.reconcile(partial)                                # exact duplicate: idempotent
    with pytest.raises(ValueError, match='observation ID changed'):
        ledger.reconcile(replace(partial, filled_quantity=2, remaining_quantity=0))   # same id, different content
    assert len(ledger.reservations()) == 1
    ledger.close()


def test_observation_binding_requires_one_chain_and_explicit_attestations():
    args, instrument, pin = venue_fixture('kalshi')
    intent, wire = args['intent'], translate(args['intent'], instrument, pin)
    rcpt = receipt(wire, intent.account, 'kalshi.create_order', kalshi_create_body(wire))
    fact = parse_order_response(rcpt, intent=intent, wire=wire, pin=pin, expected_source='kalshi.create_order')
    obs = bind(fact, args, wire, rcpt, 'obs/1')
    assert type(obs) is Observation and obs.raw_evidence == rcpt.body and obs.observed_ns == RECEIVED and obs.complete
    with pytest.raises(ValueError, match='one bound chain'):
        bind(fact, args, wire, replace(rcpt, body=b'{}'), 'obs/1')
    with pytest.raises(ValueError, match='one bound chain'):
        bind(replace(fact, received_ns=99 * SECOND), args, wire, rcpt, 'obs/1')
    with pytest.raises(ValueError, match='positions_match'):
        bind(fact, args, wire, rcpt, 'obs/1', positions_match=1)
    with pytest.raises(ValueError, match='account_snapshot_hash'):
        bind(fact, args, wire, rcpt, 'obs/1', snapshot_hash='not-a-digest')


def test_kill_latch_and_full_journal_verification_are_preserved(tmp_path):
    from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
    ledger, args, instrument, pin, wire = build(tmp_path)
    ledger.latch_kill('operator stop')
    with pytest.raises(ValueError):
        ledger.dispatch_once(wire=wire, sender=lambda _: pytest.fail('sent after kill'), **args)
    checkpoint = ledger.checkpoint(); ledger.close()
    other = EvidenceJournal(tmp_path / 'orders.sqlite'); other.append('foreign', {}); other.close()
    with pytest.raises(ValueError):
        ExecutionLedger(tmp_path / 'orders.sqlite', checkpoint=checkpoint)


def test_policy_still_gates_the_adapter_pin(tmp_path):
    args, instrument, pin = venue_fixture('kalshi')
    from research.kalshi.frankie_boss.execution_policy import evaluate
    untrusted = replace(args['policy'], trusted_adapters=('b' * 64,))
    args = {**args, 'policy': untrusted, 'intent': replace(args['intent'], policy_hash=untrusted.digest)}
    assert 'adapter_pin' in codes(evaluate(**args))

# Review regressions: bindings, provider schema, and contradictory retained evidence.

def test_review_tastytrade_remaining_quantity_comes_from_the_documented_leg():
    args, instrument, pin = venue_fixture('tastytrade')
    wire = translate(args['intent'], instrument, pin)
    order = tasty_order(wire)
    del order['remaining-quantity']
    rcpt = receipt(wire, args['intent'].account, 'tastytrade.get_order', json.dumps({'data': order}).encode())
    fact = parse_order_response(rcpt, intent=args['intent'], wire=wire, pin=pin, expected_source=rcpt.source)
    assert fact.remaining_quantity == 2


@pytest.mark.parametrize('kind', ['duplicate', 'nan'])
def test_review_ambiguous_json_refuses(kind):
    args, instrument, pin = venue_fixture('kalshi')
    wire = translate(args['intent'], instrument, pin)
    body = kalshi_create_body(wire)
    prefix = b'"fill_count":"2.00",' if kind == 'duplicate' else b'"extra":NaN,'
    rcpt = receipt(wire, args['intent'].account, 'kalshi.create_order', b'{' + prefix + body[1:])
    with pytest.raises(ValueError):
        parse_order_response(rcpt, intent=args['intent'], wire=wire, pin=pin, expected_source=rcpt.source)


@pytest.mark.parametrize('kind', ['terminal_restart', 'cycle'])
def test_review_pagination_cannot_restart_or_cycle(kind):
    args, instrument, pin = venue_fixture('kalshi')
    wire = translate(args['intent'], instrument, pin)
    pages = (('', fills_page(wire, '')), ('', fills_page(wire, '')))
    if kind == 'cycle':
        pages = (('', fills_page(wire, 'a')), ('a', fills_page(wire, 'a')), ('a', fills_page(wire, '')))
    with pytest.raises(ValueError):
        parse_kalshi_fills(pages, intent=args['intent'], wire=wire, pin=pin, provider_id='ord-1', received_ns=RECEIVED)


@pytest.mark.parametrize('account_id', ['../other', 'other/orders', '..'])
def test_review_account_must_be_one_path_segment(account_id):
    with pytest.raises(ValueError):
        tasty_pin(account=AccountKey('tastytrade', 'replay', account_id))


def test_review_preflight_refuses_foreign_account():
    args, instrument, pin = venue_fixture('tastytrade')
    wire = translate(args['intent'], instrument, pin)
    pre = preflight_request(wire, pin)
    rcpt = TransportReceipt(wire.digest, AccountKey('tastytrade', 'live', 'OTHER'), 'tastytrade.dry_run', 200,
                            tasty_submit_body(wire), RECEIVED)
    with pytest.raises(ValueError):
        parse_tastytrade_preflight(rcpt, preflight=pre)


def test_review_observation_refuses_changed_receipt_account():
    args, instrument, pin = venue_fixture('kalshi')
    wire = translate(args['intent'], instrument, pin)
    rcpt = receipt(wire, args['intent'].account, 'kalshi.create_order', kalshi_create_body(wire))
    fact = parse_order_response(rcpt, intent=args['intent'], wire=wire, pin=pin, expected_source=rcpt.source)
    with pytest.raises(ValueError):
        bind(fact, args, wire, replace(rcpt, account=AccountKey('kalshi', 'live', 'OTHER')), 'obs/1')


@pytest.mark.parametrize('venue', ['kalshi', 'tastytrade'])
def test_review_terminal_status_cannot_hide_impossible_remaining(venue):
    args, instrument, pin = venue_fixture(venue)
    wire = translate(args['intent'], instrument, pin)
    if venue == 'kalshi':
        source, body = 'kalshi.get_order', kalshi_order_body(wire, status='canceled', remaining='999.00')
    else:
        source, body = 'tastytrade.get_order', tasty_get_body(wire, status='Filled', remaining='1', fills=('2',))
    rcpt = receipt(wire, args['intent'].account, source, body)
    with pytest.raises(ValueError):
        parse_order_response(rcpt, intent=args['intent'], wire=wire, pin=pin, expected_source=source)


def test_review_tastytrade_equivalent_decimal_price_is_not_a_conflict():
    args, instrument, pin = venue_fixture('tastytrade')
    wire = translate(args['intent'], instrument, pin)
    body = tasty_get_body(wire, price='0.0510')
    rcpt = receipt(wire, args['intent'].account, 'tastytrade.get_order', body)
    assert parse_order_response(rcpt, intent=args['intent'], wire=wire, pin=pin, expected_source=rcpt.source).status == 'ACKNOWLEDGED'

@pytest.mark.parametrize('change', ['missing', 'wrong_account', 'wrong_body'])
def test_review_preflight_requires_the_matching_returned_order(change):
    args, instrument, pin = venue_fixture('tastytrade')
    wire = translate(args['intent'], instrument, pin)
    body = json.loads(tasty_submit_body(wire))
    if change == 'missing':
        del body['data']['order']
    elif change == 'wrong_account':
        body['data']['order']['account-number'] = 'OTHER'
    else:
        body['data']['order']['legs'][0]['symbol'] = '/OTHER'
    rcpt = receipt(wire, pin.account, 'tastytrade.dry_run', json.dumps(body).encode())
    with pytest.raises(ValueError):
        parse_tastytrade_preflight(rcpt, preflight=preflight_request(wire, pin))
