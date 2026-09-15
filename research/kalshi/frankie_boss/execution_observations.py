"""Authenticated read-only Kalshi primary balance/resting-order collection.

No order submission, valuation, P&L, positions or reflection authority. Returned
completeness describes a cursor chain, not an atomic account snapshot.
"""
from dataclasses import dataclass, field
import re
from urllib.parse import parse_qsl, urlencode
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from .execution_auth import CredentialReference, KalshiSecrets, kalshi_signature
from .execution_contracts import AccountKey, Contract
from .execution_transport import HTTPResponse, ORIGINS, TransportError, _clock, _failure, _object

BALANCE = 'kalshi.primary_balance'
ORDERS = 'kalshi.primary_resting_orders'
PATHS = {BALANCE: '/trade-api/v2/portfolio/balance', ORDERS: '/trade-api/v2/portfolio/orders'}


@dataclass(frozen=True)
class KalshiObservationCapability(Contract):
    account: AccountKey
    credential: CredentialReference
    origin: str
    http_hash: str
    user_agent: str
    timeout_ms: int
    collection_lifetime_ns: int
    page_size: int
    max_order_pages: int
    max_total_response_bytes: int

    def __post_init__(self):
        super().__post_init__()
        if (self.account.venue != 'kalshi' or self.credential.account != self.account
                or ORIGINS.get(('kalshi', self.account.environment)) != self.origin):
            raise ValueError('exact Kalshi account/credential/official origin required')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', self.user_agent):
            raise ValueError('product/version User-Agent required')
        if not 1 <= self.timeout_ms <= 60000 or not 1 <= self.collection_lifetime_ns <= 300_000_000_000:
            raise ValueError('bounded request/collection time required')
        if not 1 <= self.page_size <= 1000 or not 1 <= self.max_order_pages <= 1000:
            raise ValueError('bounded pagination required')
        if not 1 <= self.max_total_response_bytes <= 64*1024*1024:
            raise ValueError('bounded collection bytes required')


@dataclass(frozen=True)
class ObservationRequest(Contract):
    account: AccountKey
    capability_hash: str
    source: str
    method: str
    path: str
    query: str

    def __post_init__(self):
        super().__post_init__()
        if self.account.venue != 'kalshi' or self.method != 'GET' or PATHS.get(self.source) != self.path:
            raise ValueError('supported Kalshi GET observation required')
        pairs = parse_qsl(self.query, keep_blank_values=True, strict_parsing=True)
        if urlencode(pairs) != self.query or len(dict(pairs)) != len(pairs):
            raise ValueError('canonical unique query required')
        values = dict(pairs)
        if self.source == BALANCE:
            expected = [('subaccount', '0')]
        else:
            limit = values.get('limit', '')
            cursor = values.get('cursor', '')
            if not re.fullmatch(r'[1-9][0-9]{0,3}', limit) or not 1 <= int(limit) <= 1000:
                raise ValueError('bounded exact page size required')
            if len(cursor) > 4096 or any(ord(c) < 32 or ord(c) > 126 for c in cursor):
                raise ValueError('bounded printable cursor required')
            expected = [('subaccount', '0'), ('status', 'resting'), ('limit', limit)]
            if cursor:
                expected.append(('cursor', cursor))
        if pairs != expected:
            raise ValueError('exact primary-account observation query required')


@dataclass(frozen=True)
class ObservationAttempt(Contract):
    request: ObservationRequest
    started_ns: int
    last_clock_ns: int
    status: int
    body: bytes = field(repr=False)
    failure: str

    def __post_init__(self):
        super().__post_init__()
        if self.last_clock_ns < self.started_ns or (self.status != 0 and not 100 <= self.status <= 599):
            raise ValueError('invalid observation attempt clock/status')
        if self.failure == 'none' and self.status == 0:
            raise ValueError('successful exchange requires HTTP status')


@dataclass(frozen=True)
class ObservationCollection(Contract):
    capability: KalshiObservationCapability
    started_ns: int
    last_clock_ns: int
    attempts: tuple[ObservationAttempt, ...]
    outcome: str

    def __post_init__(self):
        super().__post_init__()
        if self.last_clock_ns < self.started_ns:
            raise ValueError('collection clock moved backwards')
        previous = self.started_ns
        for attempt in self.attempts:
            if attempt.request.account != self.capability.account or attempt.request.capability_hash != self.capability.digest:
                raise ValueError('attempt capability/account mismatch')
            if not previous <= attempt.started_ns <= attempt.last_clock_ns <= self.last_clock_ns:
                raise ValueError('attempt chronology mismatch')
            previous = attempt.last_clock_ns
        if self.complete:
            _validate_complete(self)

    @property
    def complete(self):
        return self.outcome == 'complete'


def _request(cap, source, cursor=''):
    pairs = [('subaccount', '0')]
    if source == ORDERS:
        pairs += [('status', 'resting'), ('limit', str(cap.page_size))]
        if cursor:
            pairs.append(('cursor', cursor))
    return ObservationRequest(cap.account, cap.digest, source, 'GET', PATHS[source], urlencode(pairs))


def _page(attempt, seen_orders, page_size):
    value = _object(attempt.body)
    if attempt.request.source == BALANCE:
        if any(type(value.get(k)) is not int for k in ('balance', 'portfolio_value', 'updated_ts')):
            raise ValueError('exact integer balance fields required')
        if value['updated_ts'] < 0 or type(value.get('balance_dollars')) is not str or not re.fullmatch(r'-?(0|[1-9][0-9]*)\.[0-9]{4}', value['balance_dollars']):
            raise ValueError('exact provider balance string and timestamp required')
        return ''
    rows, cursor = value.get('orders'), value.get('cursor')
    if type(rows) is not list or len(rows) > page_size or type(cursor) is not str:
        raise ValueError('orders array and explicit cursor required')
    if len(cursor) > 4096 or any(ord(c) < 32 or ord(c) > 126 for c in cursor):
        raise ValueError('bounded printable cursor required')
    for row in rows:
        if type(row) is not dict:
            raise ValueError('order object required')
        identity = row.get('order_id')
        if (type(identity) is not str or not identity or identity in seen_orders
                or row.get('user_id') != attempt.request.account.account_id
                or row.get('status') != 'resting'
                or type(row.get('subaccount_number')) is not int or row['subaccount_number'] != 0):
            raise ValueError('unique order and exact account/status/subaccount required')
        seen_orders.add(identity)
    return cursor


def _validate_complete(result):
    """Reject an inconsistent complete result, including dataclass replacement."""
    cap = result.capability
    if (not 2 <= len(result.attempts) <= 1 + cap.max_order_pages
            or result.last_clock_ns >= result.started_ns + cap.collection_lifetime_ns
            or sum(len(a.body) for a in result.attempts) > cap.max_total_response_bytes):
        raise ValueError('complete collection exceeds declared bounds')
    source, cursor, seen, cursors = BALANCE, '', set(), set()
    for index, attempt in enumerate(result.attempts):
        if attempt.request != _request(cap, source, cursor) or attempt.status != 200 or attempt.failure != 'none':
            raise ValueError('complete collection request/status mismatch')
        cursor = _page(attempt, seen, cap.page_size)
        if source == BALANCE:
            source = ORDERS
            continue
        if not cursor and index != len(result.attempts)-1:
            raise ValueError('requests after terminal cursor')
        if cursor and cursor in cursors:
            raise ValueError('cyclic complete collection')
        cursors.add(cursor)
    if cursor:
        raise ValueError('complete collection has open cursor')


def collect_kalshi_primary(*, capability, expected_capability_hash, expected_http_hash,
                          resolve_secret, http, now, retain_attempt):
    """Collect once; persist each immutable attempt before any later request.

The caller supplies trusted durable retention and independently pinned providers.
AccountKey.account_id must be the explicitly configured Kalshi user_id; this code
does not discover accounts or infer credential ownership from a balance response.
"""
    cap = capability
    if (type(cap) is not KalshiObservationCapability or cap.digest != expected_capability_hash
            or cap.http_hash != expected_http_hash or not all(callable(c) for c in (resolve_secret, http, now, retain_attempt))):
        raise TransportError('observation capability/provider pin mismatch')
    try:
        started = last = _clock(now)
        secrets = resolve_secret(cap.credential)
        if type(secrets) is not KalshiSecrets:
            raise ValueError('Kalshi secrets required')
        key = serialization.load_pem_private_key(secrets.private_key_pem, password=None)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise ValueError('RSA key of at least 2048 bits required')
    except BaseException as error:
        _failure('observation preparation failed', error)
    until, used_bytes = started + cap.collection_lifetime_ns, 0
    attempts, seen_orders, seen_cursors = [], set(), set()
    source, cursor, pages = BALANCE, '', 0
    outcome = 'time_budget'
    while True:
        request = _request(cap, source, cursor)
        try:
            request_start = _clock(now)
            if request_start < last:
                raise ValueError('clock moved backwards')
            last = request_start
        except BaseException as error:
            if not isinstance(error, Exception):
                _failure('observation canceled', error)
            outcome = 'clock_error'
            break
        if last >= until:
            break
        try:
            signature = kalshi_signature(key, last//1_000_000, 'GET', request.path)
            signed = _clock(now)
            if signed < last:
                raise ValueError('clock moved backwards')
            last = signed
        except BaseException as error:
            if not isinstance(error, Exception):
                _failure('observation canceled', error)
            outcome = 'signing_or_clock_error'
            break
        timeout_ms = min(cap.timeout_ms, (until-last)//1_000_000)
        if timeout_ms < 1:
            break
        status, body, failure = 0, b'', 'none'
        canceled = None
        url = cap.origin + request.path + '?' + request.query
        try:
            response = http(method='GET', url=url, body=b'', timeout_ms=timeout_ms,
                headers={'User-Agent': cap.user_agent, 'Accept': 'application/json',
                    'KALSHI-ACCESS-KEY': secrets.key_id, 'KALSHI-ACCESS-TIMESTAMP': str(request_start//1_000_000),
                    'KALSHI-ACCESS-SIGNATURE': signature}, follow_redirects=False, retries=0)
            if type(response) is not HTTPResponse or response.url != url:
                failure = 'response_binding'
            else:
                status = response.status
                if any(secret in response.body for secret in (secrets.key_id.encode(), secrets.private_key_pem, signature.encode())):
                    failure = 'secret_echo'
                elif used_bytes + len(response.body) > cap.max_total_response_bytes:
                    failure = 'byte_budget'
                else:
                    body = response.body
                    used_bytes += len(body)
        except Exception:
            failure = 'transport_error'
        except BaseException as error:
            failure, canceled = 'canceled', error
        try:
            received = _clock(now)
            if received < last:
                raise ValueError('clock moved backwards')
            last = received
        except BaseException as error:
            if not isinstance(error, Exception):
                canceled = error
            failure = 'clock_error'
        attempt = ObservationAttempt(request, request_start, last, status, body, failure)
        try:
            retain_attempt(attempt)
        except BaseException as error:
            _failure('observation retention failed', error)
        attempts.append(attempt)
        if canceled is not None:
            _failure('observation canceled', canceled)
        if failure != 'none':
            outcome = failure
            break
        if last >= until:
            outcome = 'time_budget'
            break
        if status != 200:
            outcome = 'http_status'
            break
        try:
            cursor = _page(attempt, seen_orders, cap.page_size)
        except Exception:
            outcome = 'invalid_page'
            break
        if source == BALANCE:
            source = ORDERS
            continue
        pages += 1
        if not cursor:
            outcome = 'complete'
            break
        if cursor in seen_cursors:
            outcome = 'cursor_cycle'
            break
        seen_cursors.add(cursor)
        if pages >= cap.max_order_pages:
            outcome = 'page_budget'
            break
    return ObservationCollection(cap, started, last, tuple(attempts), outcome)
