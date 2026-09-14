"""Pure typed Kalshi / tastytrade wire translation and provider-observation parsing.

No network, credentials, retries or authority live here. ``translate`` turns an
already typed ``Intent`` into exact wire bytes (a ledger ``WireRequest``) under a
caller-pinned adapter mapping; ``parse_order_response`` / ``parse_kalshi_fills``
turn retained provider bytes into typed facts; ``observation`` binds a fact to the
ledger's ``Observation`` contract only with the caller's independent account and
clock evidence. Serialization never authorizes sending: the ledger's single
dispatch and its SENT_UNKNOWN rule remain the only path to transport.

Supported subset (everything else is rejected, never coerced):

* Kalshi: single-leg limit order on an ``event`` instrument via
  POST /trade-api/v2/portfolio/events/orders (create-order v2). ``side`` is the
  YES book (``bid`` buys YES, ``ask`` sells YES); NO economics are expressed only
  through the explicit complement mapping pinned by the caller (``outcome='no'``:
  buy NO at p == ask YES at 1-p). ``count``/``price`` are fixed-point strings.
  ``effect='close'`` is unsupported (no reduce_only claim). TIF ``day`` is
  unsupported on this schema.
* tastytrade: single-leg ``Limit`` order, ``instrument-type`` ``Future`` or
  ``Future Option`` via POST /accounts/{account-number}/orders. Debit/Credit is
  pinned per side by the caller, never derived. TIF ``fill_or_kill`` is unsupported
  on this schema (no FOK enum). The dry-run route is a distinct ``PreflightRequest``
  so it cannot be dispatched as the order.

Every economic mapping (ticker/symbol, outcome, unit scales, price effect,
self-trade prevention, subaccount, source) comes from an adapter pin whose digest
is the intent's ``adapter_hash``; the pin also binds the exact account key so a
mismatched venue/environment/account refuses before any bytes exist.

Provenance: a ``TransportReceipt`` is the CALLER's attestation of which wire the
response answered, which account/environment/source it came from and when it was
received. Identifiers inside the JSON (order ids, client ids, engine clocks) are
self-asserted by the provider and are only cross-checked, never trusted alone.
Official documentation used is cited in SPEC-execution-adapters.md.
"""
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import re

try:
    from .execution_contracts import AccountKey, Contract, Instrument, Intent, _typed
    from .execution_ledger import Observation, WireRequest
    from .forecast_contract import sha256_digest
except ImportError:  # standalone package-directory import
    from execution_contracts import AccountKey, Contract, Instrument, Intent, _typed
    from execution_ledger import Observation, WireRequest
    from forecast_contract import sha256_digest

SCHEMA = 'BOSS_EXECUTION_ADAPTER_V1'

KALSHI_CREATE_PATH = '/trade-api/v2/portfolio/events/orders'
KALSHI_ORDER_PATH = '/trade-api/v2/portfolio/orders/{order_id}'
KALSHI_FILLS_PATH = '/trade-api/v2/portfolio/fills'
TASTYTRADE_ORDERS_PATH = '/accounts/{account}/orders'
TASTYTRADE_DRY_RUN_PATH = '/accounts/{account}/orders/dry-run'

KALSHI_TIF = {'good_till_canceled': 'good_till_canceled', 'fill_or_kill': 'fill_or_kill',
              'immediate_or_cancel': 'immediate_or_cancel'}
KALSHI_STP = ('taker_at_cross', 'maker')
KALSHI_SOURCES = ('kalshi.create_order', 'kalshi.get_order', 'kalshi.historical_order')
KALSHI_STATUS = {'resting': None, 'executed': 'FILLED', 'canceled': 'CANCELED'}
TASTYTRADE_TIF = {'day': 'Day', 'good_till_canceled': 'GTC', 'immediate_or_cancel': 'IOC'}
TASTYTRADE_ACTION = {'Future': {('buy', 'open'): 'Buy', ('buy', 'close'): 'Buy',
                                ('sell', 'open'): 'Sell', ('sell', 'close'): 'Sell'},
                     'Future Option': {('buy', 'open'): 'Buy to Open', ('buy', 'close'): 'Buy to Close',
                                       ('sell', 'open'): 'Sell to Open', ('sell', 'close'): 'Sell to Close'}}
TASTYTRADE_SOURCES = ('tastytrade.submit_order', 'tastytrade.get_order')
TASTYTRADE_NONTERMINAL = ('Received', 'Routed', 'In Flight', 'Live', 'Cancel Requested')
TASTYTRADE_TERMINAL = {'Filled': 'FILLED', 'Cancelled': 'CANCELED', 'Rejected': 'REJECTED'}
# Documented terminal status with no ledger vocabulary; refused, see SPEC (contract gap 1).
TASTYTRADE_UNREPRESENTABLE = ('Expired',)
_IDENTIFIER = re.compile(r'[A-Za-z0-9_.:/-]+')  # JSON string identifiers; never interpolated into a path here
_DECIMAL = re.compile(r'(0|[1-9][0-9]*)(?:\.([0-9]+))?')
_ISO = re.compile(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?(Z|\+00:00)')


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fraction(units: int, per_one: int) -> Fraction:
    return Fraction(units, per_one)


def _decimal_text(value: Fraction, *, min_decimals: int, max_decimals: int) -> str:
    """Exact terminating decimal or refusal; never rounds."""
    if value < 0:
        raise ValueError('negative wire value is not representable')
    for places in range(min_decimals, max_decimals + 1):
        scaled = value * 10 ** places
        if scaled.denominator == 1:
            digits = str(scaled.numerator).rjust(places + 1, '0')
            return digits if places == 0 else digits[:-places] + '.' + digits[-places:]
    raise ValueError(f'value {value} needs more than {max_decimals} decimals; refusing to round')


def _parse_decimal(text, name) -> Fraction:
    if type(text) is not str or _DECIMAL.fullmatch(text) is None:
        raise ValueError(f'{name} must be a canonical nonnegative decimal string')
    return Fraction(text)


def _parse_iso_ns(text, name) -> int:
    match = _ISO.fullmatch(text) if type(text) is str else None
    if match is None:
        raise ValueError(f'{name} must be an ISO-8601 UTC timestamp')
    import datetime
    year, month, day, hour, minute, second = (int(match.group(i)) for i in range(1, 7))
    base = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
    frac = (match.group(7) or '').ljust(9, '0')
    return int(base.timestamp()) * 1_000_000_000 + int(frac)


def _identifier(value, name) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f'{name} must be a plain identifier string')
    return value


def _json_object(body: bytes, name: str) -> dict:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'{name}: duplicate JSON key {key!r}')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f'{name}: nonfinite JSON constant {value}')

    try:
        value = json.loads(body.decode('utf-8'), object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f'{name}: response is not a JSON document') from exc
    if type(value) is not dict:
        raise ValueError(f'{name}: response is not a JSON object')
    return value


def _require(obj: dict, key: str, kind, name: str):
    if key not in obj:
        raise ValueError(f'{name}: missing required field {key!r}')
    value = obj[key]
    if type(value) is not kind:
        raise ValueError(f'{name}: field {key!r} has the wrong JSON type')
    return value


# --------------------------------------------------------------------------------
# Caller-pinned adapter mappings
# --------------------------------------------------------------------------------

@dataclass(frozen=True)
class KalshiPin(Contract):
    """Explicit Kalshi mapping for exactly one instrument on one account."""
    account: AccountKey
    instrument_id: str
    ticker: str
    outcome: str                       # 'yes' | 'no': which contract the instrument IS
    self_trade_prevention_type: str    # required by create-order v2
    subaccount: int                    # 0 = primary; always sent explicitly
    price_units_per_dollar: int        # intent price units in one dollar
    quantity_units_per_contract: int   # intent quantity units in one contract

    def __post_init__(self):
        super().__post_init__()
        if self.account.venue != 'kalshi':
            raise ValueError('Kalshi pin requires a kalshi account key')
        _identifier(self.ticker, 'ticker')
        if self.outcome not in ('yes', 'no') or self.self_trade_prevention_type not in KALSHI_STP:
            raise ValueError('explicit yes/no outcome and documented self-trade prevention required')
        if not 0 <= self.subaccount <= 63 or self.price_units_per_dollar <= 0 or self.quantity_units_per_contract <= 0:
            raise ValueError('explicit positive unit scales and subaccount 0..63 required')


@dataclass(frozen=True)
class TastytradePin(Contract):
    """Explicit tastytrade mapping for exactly one instrument on one account."""
    account: AccountKey
    instrument_id: str
    symbol: str
    instrument_type: str               # 'Future' | 'Future Option'
    price_effect_buy: str              # 'Debit' | 'Credit', pinned, never derived
    price_effect_sell: str
    automated_source: bool
    source: str
    price_units_per_currency: int
    quantity_units_per_contract: int

    def __post_init__(self):
        super().__post_init__()
        if self.account.venue != 'tastytrade':
            raise ValueError('tastytrade pin requires a tastytrade account key')
        if re.fullmatch(r'[A-Za-z0-9_-]+', self.account.account_id) is None:
            raise ValueError('tastytrade account number must be a plain identifier')
        if self.instrument_type not in TASTYTRADE_ACTION:
            raise ValueError('instrument-type must be Future or Future Option')
        if {self.price_effect_buy, self.price_effect_sell} - {'Debit', 'Credit'}:
            raise ValueError('price-effect must be pinned as Debit or Credit per side')
        if self.price_units_per_currency <= 0 or self.quantity_units_per_contract <= 0:
            raise ValueError('explicit positive unit scales required')


# --------------------------------------------------------------------------------
# Intent -> wire
# --------------------------------------------------------------------------------

def _bind(intent, instrument, pin, product):
    _typed(intent, Intent, 'intent'); _typed(instrument, Instrument, 'instrument')
    intent.__post_init__(); instrument.__post_init__(); pin.__post_init__()
    if intent.adapter_hash != pin.digest:
        raise ValueError('intent adapter_hash does not pin this adapter mapping')
    if intent.account != pin.account:
        raise ValueError('intent account/environment differs from the pinned account')
    if intent.instrument_id != instrument.instrument_id != pin.instrument_id or intent.instrument_id != pin.instrument_id:
        raise ValueError('intent, instrument and pin name different instruments')
    if instrument.product != product:
        raise ValueError(f'{pin.account.venue} adapter supports only {product!r} instruments')
    if intent.order_type != 'limit' or intent.side not in ('buy', 'sell') or intent.effect not in ('open', 'close'):
        raise ValueError('only single-leg limit buy/sell open/close intents are representable')
    if intent.quantity % instrument.quantity_step or intent.price % instrument.price_step \
            or not instrument.min_price <= intent.price <= instrument.max_price:
        raise ValueError('intent is off the instrument grid; no rounding to valid')
    return _identifier(intent.intent_id, 'intent_id')


def _kalshi_side_and_price(intent, pin):
    price = _fraction(intent.price, pin.price_units_per_dollar)
    if not 0 < price < 1:
        raise ValueError('Kalshi limit price must lie strictly inside (0, 1) dollars')
    if pin.outcome == 'yes':
        return ('bid' if intent.side == 'buy' else 'ask'), price
    # Explicit complement mapping: buying NO at p is an ask on the YES book at 1-p.
    return ('ask' if intent.side == 'buy' else 'bid'), 1 - price


def translate(intent: Intent, instrument: Instrument, pin) -> WireRequest:
    """Deterministic exact wire bytes; identity, account, adapter hash and units preserved."""
    if type(pin) is KalshiPin:
        client_id = _bind(intent, instrument, pin, 'event')
        if intent.effect != 'close' and intent.tif in KALSHI_TIF:
            side, price = _kalshi_side_and_price(intent, pin)
            body = {'ticker': pin.ticker, 'side': side,
                    'count': _decimal_text(_fraction(intent.quantity, pin.quantity_units_per_contract),
                                           min_decimals=2, max_decimals=2),
                    'price': _decimal_text(price, min_decimals=2, max_decimals=4),
                    'time_in_force': KALSHI_TIF[intent.tif],
                    'self_trade_prevention_type': pin.self_trade_prevention_type,
                    'client_order_id': client_id, 'subaccount': pin.subaccount}
            return WireRequest(intent.digest, pin.digest, 'POST', KALSHI_CREATE_PATH, _canonical(body), client_id)
        raise ValueError('Kalshi v2 subset: effect=open and TIF in good_till_canceled/fill_or_kill/immediate_or_cancel only')
    if type(pin) is TastytradePin:
        client_id = _bind(intent, instrument, pin, 'future' if pin.instrument_type == 'Future' else 'future_option')
        if intent.tif not in TASTYTRADE_TIF:
            raise ValueError('tastytrade subset: TIF day/good_till_canceled/immediate_or_cancel only')
        if intent.price < 0:
            raise ValueError('negative limit price cannot be expressed; price-effect is pinned, not inferred')
        body = {'order-type': 'Limit', 'time-in-force': TASTYTRADE_TIF[intent.tif],
                'price': _decimal_text(_fraction(intent.price, pin.price_units_per_currency), min_decimals=1, max_decimals=8),
                'price-effect': pin.price_effect_buy if intent.side == 'buy' else pin.price_effect_sell,
                'legs': [{'instrument-type': pin.instrument_type, 'symbol': pin.symbol,
                          'action': TASTYTRADE_ACTION[pin.instrument_type][(intent.side, intent.effect)],
                          'quantity': _decimal_text(_fraction(intent.quantity, pin.quantity_units_per_contract),
                                                    min_decimals=0, max_decimals=8)}],
                'external-identifier': client_id, 'automated-source': pin.automated_source, 'source': pin.source}
        return WireRequest(intent.digest, pin.digest, 'POST',
                           TASTYTRADE_ORDERS_PATH.format(account=pin.account.account_id), _canonical(body), client_id)
    raise ValueError('unsupported adapter pin type')


@dataclass(frozen=True)
class PreflightRequest(Contract):
    """tastytrade dry-run of the exact order bytes; a distinct type so it cannot be dispatched."""
    wire_hash: str
    adapter_hash: str
    method: str
    path: str
    body: bytes
    account: AccountKey


def preflight_request(wire: WireRequest, pin: TastytradePin) -> PreflightRequest:
    _typed(wire, WireRequest, 'wire'); _typed(pin, TastytradePin, 'pin')
    if wire.method != 'POST' or wire.adapter_hash != pin.digest or wire.path != TASTYTRADE_ORDERS_PATH.format(account=pin.account.account_id):
        raise ValueError('preflight must mirror a wire produced under this pin')
    return PreflightRequest(wire.digest, pin.digest, 'POST',
                            TASTYTRADE_DRY_RUN_PATH.format(account=pin.account.account_id), wire.body, pin.account)


# --------------------------------------------------------------------------------
# Provider bytes -> typed facts
# --------------------------------------------------------------------------------

@dataclass(frozen=True)
class TransportReceipt(Contract):
    """Caller-attested transport provenance: which wire, which account, which source, when."""
    wire_hash: str
    account: AccountKey
    source: str
    http_status: int
    body: bytes
    received_ns: int

    def __post_init__(self):
        super().__post_init__()
        if not 100 <= self.http_status <= 599:
            raise ValueError('explicit HTTP status required')

    @property
    def body_hash(self):
        return _sha(self.body)


@dataclass(frozen=True)
class OrderFact(Contract):
    """One provider statement about one order, in intent units, with both clocks."""
    venue: str
    source: str
    request_hash: str
    response_hash: str
    provider_id: str
    client_id: str
    provider_status: str
    status: str                  # ledger vocabulary
    filled_quantity: int
    remaining_quantity: int      # still working; 0 once terminal
    initial_quantity: int
    event_ns: int                # self-asserted provider clock
    received_ns: int             # caller transport clock

    def __post_init__(self):
        super().__post_init__()
        if self.event_ns > self.received_ns:
            raise ValueError('provider clock is later than the trusted receive clock')
        if min(self.filled_quantity, self.remaining_quantity, self.initial_quantity) < 0:
            raise ValueError('negative quantities')


def _units(value: Fraction, per_one: int, name: str) -> int:
    scaled = value * per_one
    if scaled.denominator != 1:
        raise ValueError(f'{name} is finer than the declared quantity unit; refusing to round')
    return int(scaled)


def _status_from_counts(filled, initial, *, nonterminal_names, name):
    if filled == 0:
        return 'ACKNOWLEDGED'
    if filled < initial:
        return 'PARTIAL'
    raise ValueError(f'{name}: {nonterminal_names} status reports the whole order filled; conflicting counts')


def _receipt_ok(receipt, wire, intent, pin, sources):
    _typed(receipt, TransportReceipt, 'receipt'); _typed(wire, WireRequest, 'wire'); _typed(intent, Intent, 'intent')
    receipt.__post_init__(); wire.__post_init__(); intent.__post_init__(); pin.__post_init__()
    if receipt.source not in sources:
        raise ValueError(f'receipt source {receipt.source!r} is not one of {sources}')
    if receipt.wire_hash != wire.digest or wire.intent_hash != intent.digest or wire.adapter_hash != pin.digest:
        raise ValueError('receipt, wire, intent and pin do not form one bound chain')
    if receipt.account != intent.account or receipt.account != pin.account:
        raise ValueError('receipt account/environment differs from the intent and pin')


def _kalshi_order(receipt, *, intent, wire, pin):
    name = receipt.source
    body = _json_object(receipt.body, name)
    sent = json.loads(wire.body.decode())
    if name == 'kalshi.create_order':
        if receipt.http_status != 201:
            raise ValueError(f'{name}: only a 201 body is an acknowledgement; status {receipt.http_status} is not a provider fact')
        order = body
        provider_status, event_ns = 'created', _require(order, 'ts_ms', int, name) * 1_000_000
        filled_text, remaining_text = _require(order, 'fill_count', str, name), _require(order, 'remaining_count', str, name)
        initial = Fraction(sent['count'])
    else:
        if receipt.http_status != 200:
            raise ValueError(f'{name}: only a 200 body is an order fact')
        order = _require(body, 'order', dict, name)
        provider_status = _require(order, 'status', str, name)
        if provider_status not in KALSHI_STATUS:
            raise ValueError(f'{name}: unknown Kalshi order status {provider_status!r}')
        event_ns = _parse_iso_ns(_require(order, 'last_update_time', str, name), name + '.last_update_time')
        filled_text, remaining_text = _require(order, 'fill_count_fp', str, name), _require(order, 'remaining_count_fp', str, name)
        initial = _parse_decimal(_require(order, 'initial_count_fp', str, name), name + '.initial_count_fp')
        if _require(order, 'ticker', str, name) != sent['ticker'] or _require(order, 'book_side', str, name) != sent['side']:
            raise ValueError(f'{name}: order ticker/book side differ from the sent wire')
        if _parse_decimal(_require(order, 'yes_price_dollars', str, name), name + '.yes_price_dollars') != Fraction(sent['price']):
            raise ValueError(f'{name}: yes price differs from the sent wire')
    provider_id = _identifier(_require(order, 'order_id', str, name), name + '.order_id')
    if _require(order, 'client_order_id', str, name) != wire.client_id:
        raise ValueError(f'{name}: client_order_id does not echo the sent client identity')
    filled = _parse_decimal(filled_text, name + '.fill_count')
    remaining = _parse_decimal(remaining_text, name + '.remaining_count')
    if initial != Fraction(sent['count']) or filled > initial or remaining > initial:
        raise ValueError(f'{name}: counts conflict with the sent order size')
    status = KALSHI_STATUS.get(provider_status)
    if name == 'kalshi.create_order':
        tif = sent['time_in_force']
        if tif in ('immediate_or_cancel', 'fill_or_kill'):
            if remaining != 0 or (tif == 'fill_or_kill' and filled not in (0, initial)):
                raise ValueError(f'{name}: immediate order outcome conflicts with time in force')
            status = 'FILLED' if filled == initial else 'CANCELED'
        elif filled == initial and remaining == 0:
            status = 'FILLED'
    if status is None:
        if filled + remaining != initial:
            raise ValueError(f'{name}: resting counts do not sum to the order size')
        status = _status_from_counts(filled, initial, nonterminal_names='resting/created', name=name)
    elif status == 'FILLED' and (filled != initial or remaining != 0):
        raise ValueError(f'{name}: executed status conflicts with counts')
    elif status == 'CANCELED' and filled + remaining > initial:
        raise ValueError(f'{name}: canceled counts exceed the sent order size')
    working = remaining if status in ('ACKNOWLEDGED', 'PARTIAL') else Fraction(0)
    per = pin.quantity_units_per_contract
    return OrderFact('kalshi', name, wire.digest, receipt.body_hash, provider_id, wire.client_id, provider_status, status,
                     _units(filled, per, 'fill_count'), _units(working, per, 'remaining_count'),
                     _units(initial, per, 'initial count'), event_ns, receipt.received_ns)


def _tastytrade_shape(order, sent, account, name):
    if _require(order, 'account-number', str, name) != account.account_id:
        raise ValueError(f'{name}: account-number differs from the pinned account')
    for key in ('order-type', 'time-in-force', 'price-effect'):
        if _require(order, key, str, name) != sent[key]:
            raise ValueError(f'{name}: {key} differs from the sent wire')
    if _parse_decimal(_require(order, 'price', str, name), name + '.price') != Fraction(sent['price']):
        raise ValueError(f'{name}: price differs from the sent wire')
    legs = _require(order, 'legs', list, name)
    if len(legs) != 1 or type(legs[0]) is not dict:
        raise ValueError(f'{name}: exactly one leg is representable')
    leg, sent_leg = legs[0], sent['legs'][0]
    for key in ('instrument-type', 'symbol', 'action'):
        if _require(leg, key, str, name) != sent_leg[key]:
            raise ValueError(f'{name}: leg {key} differs from the sent wire')
    initial = _parse_decimal(_require(order, 'size', str, name), name + '.size')
    if initial != Fraction(sent_leg['quantity']) or _parse_decimal(_require(leg, 'quantity', str, name), name + '.leg.quantity') != initial:
        raise ValueError(f'{name}: order size differs from the sent quantity')
    return initial, leg


def _tastytrade_order(receipt, *, intent, wire, pin):
    name = receipt.source
    body = _json_object(receipt.body, name)
    sent = json.loads(wire.body.decode())
    data = _require(body, 'data', dict, name)
    if name == 'tastytrade.submit_order':
        if receipt.http_status != 201:
            raise ValueError(f'{name}: only a 201 body is an acknowledgement; status {receipt.http_status} is not a provider fact')
        if _require(data, 'errors', list, name):
            raise ValueError(f'{name}: submission reported errors')
        order = _require(data, 'order', dict, name)
    else:
        if receipt.http_status != 200:
            raise ValueError(f'{name}: only a 200 body is an order fact')
        order = data
    provider_status = _require(order, 'status', str, name)
    if provider_status in TASTYTRADE_UNREPRESENTABLE:
        raise ValueError(f'{name}: provider status {provider_status!r} has no ledger vocabulary (see SPEC contract gap 1)')
    if provider_status not in TASTYTRADE_NONTERMINAL and provider_status not in TASTYTRADE_TERMINAL:
        raise ValueError(f'{name}: unknown tastytrade order status {provider_status!r}')
    provider_id = _identifier(_require(order, 'id', str, name), name + '.id')
    if _require(order, 'external-identifier', str, name) != wire.client_id:
        raise ValueError(f'{name}: external-identifier does not echo the sent client identity')
    initial, leg = _tastytrade_shape(order, sent, pin.account, name)
    remaining = _parse_decimal(_require(leg, 'remaining-quantity', str, name), name + '.leg.remaining-quantity')
    if 'remaining-quantity' in order and _parse_decimal(order['remaining-quantity'], name + '.remaining-quantity') != remaining:
        raise ValueError(f'{name}: order and leg remaining quantities conflict')
    seen, filled = set(), Fraction(0)
    for fill in _require(leg, 'fills', list, name):
        if type(fill) is not dict:
            raise ValueError(f'{name}: malformed fill')
        fill_id = _identifier(_require(fill, 'fill-id', str, name), name + '.fill-id')
        if fill_id in seen:
            raise ValueError(f'{name}: duplicate fill-id inside one response')
        seen.add(fill_id)
        filled += _parse_decimal(_require(fill, 'quantity', str, name), name + '.fill.quantity')
    if filled > initial or remaining > initial:
        raise ValueError(f'{name}: fills or remaining exceed the order size')
    if provider_status in TASTYTRADE_NONTERMINAL:
        if filled + remaining != initial:
            raise ValueError(f'{name}: enumerated fills do not reconcile with size minus remaining-quantity')
        status = _status_from_counts(filled, initial, nonterminal_names='/'.join(TASTYTRADE_NONTERMINAL), name=name)
    else:
        status = TASTYTRADE_TERMINAL[provider_status]
        if status == 'FILLED' and (filled != initial or remaining != 0):
            raise ValueError(f'{name}: Filled status without enumerated fills for the whole size')
        if status == 'REJECTED' and filled != 0:
            raise ValueError(f'{name}: Rejected status with enumerated fills')
    event_ns = _parse_iso_ns(_require(order, 'updated-at', str, name), name + '.updated-at')
    working = remaining if status in ('ACKNOWLEDGED', 'PARTIAL') else Fraction(0)
    per = pin.quantity_units_per_contract
    return OrderFact('tastytrade', name, wire.digest, receipt.body_hash, provider_id, wire.client_id, provider_status,
                     status, _units(filled, per, 'fill quantity'), _units(working, per, 'remaining-quantity'),
                     _units(initial, per, 'size'), event_ns, receipt.received_ns)


def parse_order_response(receipt: TransportReceipt, *, intent: Intent, wire: WireRequest, pin,
                         expected_source: str) -> OrderFact:
    """Typed fact from retained bytes; the caller's receipt pins account, source and clock."""
    if type(pin) is KalshiPin:
        sources, parser = KALSHI_SOURCES, _kalshi_order
    elif type(pin) is TastytradePin:
        sources, parser = TASTYTRADE_SOURCES, _tastytrade_order
    else:
        raise ValueError('unsupported adapter pin type')
    _receipt_ok(receipt, wire, intent, pin, sources)
    if expected_source != receipt.source:
        raise ValueError('receipt source differs from the independently expected source')
    return parser(receipt, intent=intent, wire=wire, pin=pin)


@dataclass(frozen=True)
class FillsFact(Contract):
    """Complete, deduplicated Kalshi fills for one order across a pinned page chain."""
    venue: str
    request_hash: str
    pages_hash: str
    provider_id: str
    fill_ids: tuple[str, ...]
    filled_quantity: int
    last_fill_ns: int
    received_ns: int


def parse_kalshi_fills(pages, *, intent: Intent, wire: WireRequest, pin: KalshiPin, provider_id: str,
                       received_ns: int) -> FillsFact:
    """Pages are ((request_cursor, response_bytes), ...) in fetch order.

    The chain must start at an empty cursor, every response cursor must be the next
    request cursor, and the last response cursor must be empty; otherwise there is no
    completeness claim and this raises. Absent fills are absent, not zero: an empty
    complete chain yields filled_quantity 0 only because every page was seen.
    """
    _typed(wire, WireRequest, 'wire'); _typed(intent, Intent, 'intent'); _typed(pin, KalshiPin, 'pin')
    if wire.intent_hash != intent.digest or wire.adapter_hash != pin.digest or intent.account != pin.account:
        raise ValueError('fills must bind to one wire, intent and pin')
    _identifier(provider_id, 'provider_id')
    if type(received_ns) is not int or received_ns < 0:
        raise ValueError('explicit receive clock required')
    _typed(pages, tuple[tuple, ...], 'pages')
    if not pages:
        raise ValueError('no pages: absence of evidence is not an empty fill set')
    sent = json.loads(wire.body.decode())
    expected_cursor, fills, seen, last_ns = '', Fraction(0), [], 0
    requested_cursors = set()
    for index, page in enumerate(pages):
        if len(page) != 2 or type(page[0]) is not str or type(page[1]) is not bytes:
            raise ValueError('each page is (request_cursor, response_bytes)')
        cursor, body = page
        if index and not expected_cursor:
            raise ValueError('page supplied after the terminal page')
        if cursor in requested_cursors:
            raise ValueError('page cursor cycle')
        requested_cursors.add(cursor)
        if cursor != expected_cursor:
            raise ValueError(f'page {index} was requested with cursor {cursor!r}, chain expected {expected_cursor!r}')
        obj = _json_object(body, 'kalshi.get_fills')
        for fill in _require(obj, 'fills', list, 'kalshi.get_fills'):
            if type(fill) is not dict or _require(fill, 'order_id', str, 'fill') != provider_id:
                raise ValueError('fill belongs to another order; page filter/completeness untrusted')
            fill_id = _identifier(_require(fill, 'fill_id', str, 'fill'), 'fill_id')
            if fill_id in seen:
                raise ValueError(f'duplicate fill_id {fill_id!r} across pages')
            if _require(fill, 'ticker', str, 'fill') != sent['ticker'] or _require(fill, 'book_side', str, 'fill') != sent['side']:
                raise ValueError('fill ticker/book side differ from the sent wire')
            seen.append(fill_id)
            fills += _parse_decimal(_require(fill, 'count_fp', str, 'fill'), 'count_fp')
            last_ns = max(last_ns, _parse_iso_ns(_require(fill, 'created_time', str, 'fill'), 'created_time'))
        expected_cursor = obj.get('cursor', '')
        if type(expected_cursor) is not str:
            raise ValueError('cursor must be a string')
    if expected_cursor != '':
        raise ValueError('page chain is open (last cursor nonempty): no completeness claim')
    if fills * pin.quantity_units_per_contract > intent.quantity:
        raise ValueError('fills exceed the intent quantity')
    if last_ns > received_ns:
        raise ValueError('fill clock is later than the trusted receive clock')
    pages_hash = _sha(b''.join(_canonical([c, _sha(b)]) for c, b in pages))
    return FillsFact('kalshi', wire.digest, pages_hash, provider_id, tuple(seen),
                     _units(fills, pin.quantity_units_per_contract, 'count_fp'), last_ns, received_ns)


# --------------------------------------------------------------------------------
# Fact -> ledger observation (caller evidence required)
# --------------------------------------------------------------------------------

def observation(fact: OrderFact, *, intent: Intent, wire: WireRequest, receipt: TransportReceipt, observation_id: str,
                account_snapshot_hash: str, positions_match: bool) -> Observation:
    """Bind a fact to the ledger contract with the CALLER's account evidence.

    ``account_snapshot_hash`` and ``positions_match`` are the caller's independent
    attestations about a reflected account snapshot; an order response never
    certifies them. The ledger separately requires the typed snapshot for release.
    """
    _typed(fact, OrderFact, 'fact'); _typed(intent, Intent, 'intent'); _typed(wire, WireRequest, 'wire')
    _typed(receipt, TransportReceipt, 'receipt')
    if type(positions_match) is not bool:
        raise ValueError('explicit boolean positions_match attestation required')
    sha256_digest(account_snapshot_hash, 'account_snapshot_hash')
    if (fact.request_hash != wire.digest or wire.intent_hash != intent.digest or receipt.wire_hash != wire.digest
            or fact.response_hash != receipt.body_hash or fact.received_ns != receipt.received_ns
            or fact.client_id != wire.client_id or fact.source != receipt.source
            or receipt.account != intent.account or fact.venue != intent.account.venue):
        raise ValueError('fact, receipt, wire and intent are not one bound chain')
    return Observation(_identifier(observation_id, 'observation_id'), intent.intent_id, intent.digest, intent.account,
                       fact.provider_id, fact.client_id, fact.status, fact.filled_quantity, fact.remaining_quantity,
                       account_snapshot_hash, fact.received_ns, True, positions_match, receipt.body)


# --------------------------------------------------------------------------------
# tastytrade dry-run parsing (validation evidence only)
# --------------------------------------------------------------------------------

@dataclass(frozen=True)
class PreflightReceipt(Contract):
    wire_hash: str
    response_hash: str
    warnings: int
    errors: int
    received_ns: int


def parse_tastytrade_preflight(receipt: TransportReceipt, *, preflight: PreflightRequest) -> PreflightReceipt:
    """Dry-run evidence bound to the exact order bytes; any error or warning refuses."""
    _typed(receipt, TransportReceipt, 'receipt'); _typed(preflight, PreflightRequest, 'preflight')
    if (receipt.source != 'tastytrade.dry_run' or receipt.wire_hash != preflight.wire_hash
            or receipt.account != preflight.account):
        raise ValueError('preflight receipt must bind the dry-run of this exact wire')
    if receipt.http_status != 201:
        raise ValueError('dry-run did not return a 201 preflight body')
    data = _require(_json_object(receipt.body, 'dry_run'), 'data', dict, 'dry_run')
    warnings, errors = _require(data, 'warnings', list, 'dry_run'), _require(data, 'errors', list, 'dry_run')
    if warnings or errors:
        raise ValueError(f'dry-run reported {len(errors)} errors and {len(warnings)} unhandled warnings')
    order = _require(data, 'order', dict, 'dry_run')
    sent = _json_object(preflight.body, 'preflight request')
    if _require(order, 'external-identifier', str, 'dry_run') != sent['external-identifier']:
        raise ValueError('dry-run external-identifier differs from the sent wire')
    _tastytrade_shape(order, sent, preflight.account, 'dry_run')
    return PreflightReceipt(preflight.wire_hash, receipt.body_hash, 0, 0, receipt.received_ns)
