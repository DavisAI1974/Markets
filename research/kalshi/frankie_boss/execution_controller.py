"""Deterministic execution composition; no network client or account truth.

Expected hashes and issuer/convention identities are independently caller-trusted.
Retained witnesses establish byte identity, not authenticated provider semantics.
"""
from dataclasses import asdict, dataclass, fields, is_dataclass
import hashlib
import json
import os
from pathlib import Path

from .c15_journal import pack, unpack
from .execution_contracts import (Contract, AccountKey, AccountSnapshot, Intent,
    Policy, Registry, SourceReference, Valuation, MarketSnapshot)
from .execution_adapters import (KalshiPin, TastytradePin, TransportReceipt,
    translate, parse_order_response, preflight_request, parse_tastytrade_preflight, observation)
from .execution_ledger import WireRequest
from .forecast_contract import sha256_digest


def _validate(value):
    if is_dataclass(value):
        value.__post_init__()
        for field in fields(value):
            _validate(getattr(value, field.name))
    elif type(value) is tuple:
        for item in value:
            _validate(item)


def _pin(value, expected):
    _validate(value)
    sha256_digest(expected, 'independent expected pin')
    if value.digest != expected:
        raise ValueError('evidence differs from independent expected pin')


class ReceiptStore:
    """Immutable exact envelopes; orphan/partial files fail closed on readback.

    This store is not order authority. Its locators and ledger checkpoints must
    be retained by the caller. A crash losing a receipt never authorizes resend.
    """
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.mkdir(parents=True, exist_ok=True)

    def put(self, payload):
        data = json.dumps(pack(payload), ensure_ascii=True, separators=(',', ':')).encode('ascii')
        key = hashlib.sha256(data).hexdigest()
        target = self.path / key
        try:
            with target.open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if os.name != 'nt':
                directory = os.open(self.path, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        except FileExistsError:
            pass
        if target.is_symlink() or target.read_bytes() != data:
            raise ValueError('immutable receipt bytes differ')
        return key

    def get(self, key):
        sha256_digest(key, 'receipt locator')
        target = self.path / key
        if target.is_symlink():
            raise ValueError('receipt symlink refused')
        data = target.read_bytes()
        if hashlib.sha256(data).hexdigest() != key:
            raise ValueError('receipt bytes differ from trusted locator')
        return unpack(json.loads(data))


@dataclass(frozen=True)
class AccountEvidence(Contract):
    snapshot: AccountSnapshot
    issuer_hash: str
    convention_hash: str
    witnesses: tuple[bytes, ...]

    def __post_init__(self):
        super().__post_init__()
        if not self.witnesses or any(not item for item in self.witnesses):
            raise ValueError('nonempty account witness bytes required')
        if not self.snapshot.complete:
            raise ValueError('complete caller-attested account evidence required')


@dataclass(frozen=True)
class ExecutionAuthority(Contract):
    account: AccountKey
    policy_hash: str
    registry_hash: str
    adapter_hash: str
    source_hash: str
    valuation_hash: str
    account_issuer_hash: str
    account_convention_hash: str
    transport_hash: str

@dataclass(frozen=True)
class ExecutionInputs(Contract):
    intent: Intent
    policy: Policy
    registry: Registry
    source: SourceReference
    valuation: Valuation
    market: MarketSnapshot
    loss_day: str


@dataclass(frozen=True)
class PreparedExecution(Contract):
    inputs: ExecutionInputs
    account_evidence: AccountEvidence
    expected_account_evidence_hash: str
    authority_hash: str
    wire: WireRequest


@dataclass(frozen=True)
class DispatchResult(Contract):
    prepared_hash: str
    transport_receipt_hash: str
    receipt_locator: str
    fact_hash: str
    # This receipt is transport evidence only: ledger remains SENT_UNKNOWN.


@dataclass(frozen=True)
class ReflectionEvidence(Contract):
    fact_hash: str
    account_evidence_hash: str
    issuer_hash: str
    convention_hash: str
    positions_match: bool
    witnesses: tuple[bytes, ...]

    def __post_init__(self):
        super().__post_init__()
        if not self.witnesses or any(not item for item in self.witnesses):
            raise ValueError('independent reflection witness bytes required')


@dataclass(frozen=True)
class ReconciliationResult(Contract):
    observation_hash: str
    evidence_locator: str
    accepted: bool
    status: str
    checkpoint_count: int
    checkpoint_head_hash: str


class ExecutionController:
    def __init__(self, *, ledger, store, authority, expected_authority_hash, pin):
        if type(authority) is not ExecutionAuthority or type(pin) not in (KalshiPin, TastytradePin):
            raise ValueError('exact authority and adapter pin required')
        _pin(authority, expected_authority_hash)
        _pin(pin, authority.adapter_hash)
        if pin.account != authority.account:
            raise ValueError('adapter account differs from authority')
        self.ledger, self.store = ledger, store
        self.authority, self.expected_authority_hash, self.pin = authority, expected_authority_hash, pin

    def _account(self, account, expected_hash):
        if type(account) is not AccountEvidence:
            raise ValueError('typed account evidence required')
        _pin(account, expected_hash)
        if (account.snapshot.account != self.authority.account
                or account.issuer_hash != self.authority.account_issuer_hash
                or account.convention_hash != self.authority.account_convention_hash):
            raise ValueError('account evidence authority differs')

    def prepare(self, inputs, account_evidence, *, expected_account_evidence_hash):
        _pin(self.authority, self.expected_authority_hash)
        _pin(self.pin, self.authority.adapter_hash)
        if type(inputs) is not ExecutionInputs:
            raise ValueError('exact execution inputs required')
        _validate(inputs)
        self._account(account_evidence, expected_account_evidence_hash)
        for value, expected in ((inputs.policy, self.authority.policy_hash),
                (inputs.registry, self.authority.registry_hash), (inputs.source, self.authority.source_hash),
                (inputs.valuation, self.authority.valuation_hash)):
            _pin(value, expected)
        if inputs.intent.account != self.authority.account:
            raise ValueError('intent account differs from authority')
        matches = [i for i in inputs.registry.instruments if i.instrument_id == inputs.intent.instrument_id]
        if len(matches) != 1:
            raise ValueError('one exact registered instrument required')
        wire = translate(inputs.intent, matches[0], self.pin)
        prepared = PreparedExecution(inputs, account_evidence, expected_account_evidence_hash,
            self.authority.digest, wire)
        self.store.put(dict(kind='prepared', value=asdict(prepared)))
        return prepared

    def _prepared(self, prepared, expected_hash):
        if type(prepared) is not PreparedExecution:
            raise ValueError('typed prepared execution required')
        _pin(prepared, expected_hash)
        current = self.prepare(prepared.inputs, prepared.account_evidence,
            expected_account_evidence_hash=prepared.expected_account_evidence_hash)
        if prepared != current:
            raise ValueError('prepared authority or exact wire changed')

    def dispatch_once(self, prepared, *, expected_prepared_hash, transport, transport_hash, now,
                      preflight_receipt=None, expected_preflight_hash=None):
        self._prepared(prepared, expected_prepared_hash)
        if transport_hash != self.authority.transport_hash or not callable(transport) or not callable(now):
            raise ValueError('explicit pinned transport capability and clock required')
        if type(self.pin) is TastytradePin:
            if type(preflight_receipt) is not TransportReceipt:
                raise ValueError('exact successful tastytrade preflight required')
            self.store.put(dict(kind='preflight', value=asdict(preflight_receipt)))
            _pin(preflight_receipt, expected_preflight_hash)
            parse_tastytrade_preflight(preflight_receipt, preflight=preflight_request(prepared.wire, self.pin))
        elif preflight_receipt is not None or expected_preflight_hash is not None:
            raise ValueError('unexpected preflight for this adapter')
        clock = now()
        if type(clock) is not int or clock < 0:
            raise ValueError('explicit nonnegative integer clock required')
        if preflight_receipt is not None and not prepared.inputs.intent.created_ns <= preflight_receipt.received_ns <= clock:
            raise ValueError('preflight clock outside intent/send interval')
        inputs = prepared.inputs
        evaluation = dict(intent=inputs.intent, policy=inputs.policy, registry=inputs.registry,
            source=inputs.source, expected_source_hash=self.authority.source_hash,
            expected_valuation_hash=self.authority.valuation_hash, valuation=inputs.valuation,
            market=inputs.market, account=prepared.account_evidence.snapshot, reservations=(),
            now=clock, loss_day=inputs.loss_day, kill_switch=False)
        self.ledger.create(inputs.intent)
        if self.ledger.state(inputs.intent.intent_id)['wire'] is not None:
            raise ValueError('submission outcome exists; reconcile, never resend')
        retained = []

        def sender(wire):
            response = transport(wire)
            if type(response) is not TransportReceipt:
                raise ValueError('complete typed transport receipt required')
            # Retain before interpreting HTTP/JSON or validating claimed identity.
            locator = self.store.put(dict(kind='transport', value=asdict(response)))
            retained.append((response, locator))
            _validate(response)
            if response.received_ns < clock:
                raise ValueError('transport receipt precedes dispatch')
            return response.body

        try:
            self.ledger.dispatch_once(wire=prepared.wire, sender=sender, **evaluation)
            response, locator = retained[0]
            source = 'kalshi.create_order' if type(self.pin) is KalshiPin else 'tastytrade.submit_order'
            fact = parse_order_response(response, intent=inputs.intent, wire=prepared.wire,
                pin=self.pin, expected_source=source)
            result = DispatchResult(prepared.digest, response.digest, locator, fact.digest)
            self.store.put(dict(kind='dispatch_result', value=asdict(result), checkpoint=self.ledger.checkpoint()))
            return result
        except BaseException as original:
            # Only an attempted send makes this an exposure uncertainty. Policy
            # refusal before SENT_UNKNOWN does not turn into provider rejection.
            try:
                uncertain = self.ledger.state(inputs.intent.intent_id)['wire'] is not None
            except BaseException:
                uncertain = True  # A poisoned journal cannot certify no transmission.
            if uncertain:
                self._stop('controller dispatch unresolved', original)
            raise

    def _stop(self, reason, original):
        try:
            self.ledger.latch_kill(reason)
        except BaseException as latch_error:
            # Preserve process-control exceptions and surface durability failure.
            raise original from latch_error

    def ingest_order_observation(self, prepared, *, expected_prepared_hash, receipt,
            expected_receipt_hash, expected_source, account_evidence,
            expected_account_evidence_hash, reflection, expected_reflection_hash):
        self._prepared(prepared, expected_prepared_hash)
        intent, wire = prepared.inputs.intent, prepared.wire
        try:
            if (type(receipt) is not TransportReceipt or type(reflection) is not ReflectionEvidence
                    or type(account_evidence) is not AccountEvidence):
                raise ValueError('typed transport and independent reflection evidence required')
            # Retain the full rejected envelope, too; never reduce it to a bool.
            locator = self.store.put(dict(kind='reconciliation', receipt=asdict(receipt),
                account=asdict(account_evidence), reflection=asdict(reflection)))
            state = self.ledger.state(intent.intent_id)
            if state['intent'] != asdict(intent) or state['wire'] != asdict(wire):
                raise ValueError('observation requires the exact durably attempted intent and wire')
            _pin(receipt, expected_receipt_hash)
            self._account(account_evidence, expected_account_evidence_hash)
            _pin(reflection, expected_reflection_hash)
            fact = parse_order_response(receipt, intent=intent, wire=wire,
                pin=self.pin, expected_source=expected_source)
            snapshot = account_evidence.snapshot
            if (reflection.fact_hash != fact.digest or reflection.account_evidence_hash != account_evidence.digest
                    or reflection.issuer_hash != self.authority.account_issuer_hash
                    or reflection.convention_hash != self.authority.account_convention_hash
                    or not reflection.positions_match):
                raise ValueError('independent reflection evidence does not match fact and account')
            if (snapshot.units != prepared.inputs.policy.units
                    or {e.scope for e in snapshot.exposures} != {s.scope for s in prepared.inputs.policy.scope_limits}
                    or snapshot.observed_ns < snapshot.pnl_observed_ns
                    or snapshot.pnl_observed_ns < fact.received_ns):
                raise ValueError('reflected account coverage or causal clock differs')
            obs = observation(fact, intent=intent, wire=wire, receipt=receipt,
                observation_id=reflection.digest, account_snapshot_hash=snapshot.digest,
                positions_match=reflection.positions_match)
            accepted = self.ledger.reconcile(obs, account_snapshot=snapshot, expected_account_hash=snapshot.digest)
            checkpoint = self.ledger.checkpoint()
            result = ReconciliationResult(obs.digest, locator, accepted, self.ledger.state(intent.intent_id)['status'],
                checkpoint['count'], checkpoint['head_hash'])
            self.store.put(dict(kind='reconciliation_result', value=asdict(result)))
            return result
        except BaseException as original:
            self._stop('controller reconciliation unresolved', original)
            raise

    def admit_account_successor(self, account_evidence, *, expected_account_evidence_hash):
        _pin(self.authority, self.expected_authority_hash)
        self._account(account_evidence, expected_account_evidence_hash)
        self.store.put(dict(kind='account_successor', value=asdict(account_evidence)))
        # The independent envelope pin above binds this exact snapshot digest.
        self.ledger.reflect_account(account_evidence.snapshot, expected_hash=account_evidence.snapshot.digest)
        return self.ledger.checkpoint()
