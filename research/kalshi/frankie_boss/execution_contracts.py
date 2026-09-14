"""Immutable execution evidence in explicit integer units; no broker authority."""
from dataclasses import asdict, dataclass, fields
from math import gcd
from fractions import Fraction
from typing import get_args, get_origin

from .c15_journal import evidence_hash
from .forecast_contract import sha256_digest

SCHEMA = 'BOSS_EXECUTION_CONTRACT_V1'


def _typed(value, annotation, name):
    if get_origin(annotation) is tuple:
        if type(value) is not tuple:
            raise ValueError(f'{name} requires an immutable tuple')
        item_type, _ = get_args(annotation)
        for item in value:
            _typed(item, item_type, name)
    elif type(value) is not annotation:
        raise ValueError(f'{name} has the wrong exact type')
    if annotation is str and not value.strip():
        raise ValueError(f'{name} must be nonempty')


def _unique(values, name):
    if len(values) != len(set(values)):
        raise ValueError(f'duplicate {name}')


class Contract:
    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            _typed(value, field.type, field.name)
            if field.name.endswith('_hash'):
                sha256_digest(value, field.name)
            if field.type is int and field.name.endswith('_ns') and value < 0:
                raise ValueError('timestamps/durations cannot be negative')

    @property
    def digest(self):
        return evidence_hash(dict(schema=SCHEMA,kind=type(self).__name__,fields=asdict(self)))


@dataclass(frozen=True)
class AccountKey(Contract):
    venue: str
    environment: str
    account_id: str


@dataclass(frozen=True)
class Units(Contract):
    quantity: str
    price: str
    money: str
    exposure: str


@dataclass(frozen=True)
class Ratio(Contract):
    numerator: int
    denominator: int

    def __post_init__(self):
        super().__post_init__()
        if self.numerator < 0 or self.denominator <= 0 or gcd(self.numerator,self.denominator) != 1:
            raise ValueError('nonnegative reduced ratio required')


@dataclass(frozen=True)
class SignedRatio(Contract):
    numerator: int
    denominator: int

    def __post_init__(self):
        super().__post_init__()
        if self.denominator <= 0 or gcd(self.numerator,self.denominator) != 1:
            raise ValueError('reduced signed ratio required')


@dataclass(frozen=True)
class Instrument(Contract):
    instrument_id: str
    product: str
    underlying: str
    maturity: str
    units: Units
    quantity_step: int
    price_step: int
    min_price: int
    max_price: int
    scopes: tuple[str, ...]
    valuation_convention_hash: str

    def __post_init__(self):
        super().__post_init__()
        if self.quantity_step <= 0 or self.price_step <= 0 or self.min_price > self.max_price:
            raise ValueError('invalid instrument grid')
        if not self.scopes:
            raise ValueError('explicit risk scopes required')
        _unique(self.scopes,'risk scopes')


@dataclass(frozen=True)
class Registry(Contract):
    instruments: tuple[Instrument, ...]

    def __post_init__(self):
        super().__post_init__()
        _unique(tuple(i.instrument_id for i in self.instruments),'instrument IDs')


@dataclass(frozen=True)
class SourceReference(Contract):
    publication_hash: str
    artifact_hash: str
    record_hash: str
    source_hash: str
    model_hash: str
    data_hash: str


@dataclass(frozen=True)
class Intent(Contract):
    intent_id: str
    account: AccountKey
    instrument_id: str
    side: str
    effect: str
    order_type: str
    tif: str
    quantity: int
    price: int
    created_ns: int
    expires_ns: int
    source_hash: str
    registry_hash: str
    policy_hash: str
    valuation_hash: str
    strategy_hash: str
    adapter_hash: str

    def __post_init__(self):
        super().__post_init__()
        if self.quantity <= 0 or self.expires_ns <= self.created_ns:
            raise ValueError('positive quantity and intent lifetime required')


@dataclass(frozen=True)
class ScopeLimit(Contract):
    scope: str
    gross: int
    net_min: int
    net_max: int

    def __post_init__(self):
        super().__post_init__()
        if self.gross < 0 or self.net_min > 0 or self.net_max < 0:
            raise ValueError('invalid exposure limits')


@dataclass(frozen=True)
class Policy(Contract):
    allowed_accounts: tuple[AccountKey, ...]
    allowed_instruments: tuple[str, ...]
    allowed_products: tuple[str, ...]
    allowed_maturities: tuple[str, ...]
    allowed_sides: tuple[str, ...]
    allowed_effects: tuple[str, ...]
    allowed_order_types: tuple[str, ...]
    allowed_tifs: tuple[str, ...]
    units: Units
    max_order_quantity: int
    max_order_notional: int
    scope_limits: tuple[ScopeLimit, ...]
    max_realized_loss: int
    max_mtm_loss: int
    max_market_age_ns: int
    max_account_age_ns: int
    max_valuation_age_ns: int
    max_intent_age_ns: int
    session_start_ns: int
    session_end_ns: int
    max_slippage: int
    trusted_models: tuple[str, ...]
    trusted_data: tuple[str, ...]
    trusted_strategies: tuple[str, ...]
    trusted_adapters: tuple[str, ...]

    def __post_init__(self):
        super().__post_init__()
        for field in fields(self):
            value = getattr(self,field.name)
            if field.name.startswith('max_') and value < 0:
                raise ValueError('negative limit')
            if field.name.startswith(('allowed_','trusted_')):
                _unique(value,field.name)
            if field.name.startswith('trusted_'):
                for digest in value:
                    sha256_digest(digest,field.name)
        _unique(tuple(s.scope for s in self.scope_limits),'scope limits')
        if self.session_start_ns >= self.session_end_ns:
            raise ValueError('explicit nonempty trading window required')


@dataclass(frozen=True)
class Exposure(Contract):
    scope: str
    gross: int
    net_min: int
    net_max: int

    def __post_init__(self):
        super().__post_init__()
        if self.gross < 0 or self.net_min > self.net_max or self.gross < max(abs(self.net_min),abs(self.net_max)):
            raise ValueError('inconsistent gross/net exposure interval')


@dataclass(frozen=True)
class AccountSnapshot(Contract):
    account: AccountKey
    units: Units
    observed_ns: int
    complete: bool
    loss_day: str
    pnl_observed_ns: int
    realized_loss: int
    mtm_loss: int
    exposures: tuple[Exposure, ...]
    reflected_intents: tuple[str, ...]

    def __post_init__(self):
        super().__post_init__()
        if self.realized_loss < 0 or self.mtm_loss < 0:
            raise ValueError('explicit nonnegative loss metrics required')
        _unique(tuple(e.scope for e in self.exposures),'account scopes')
        _unique(self.reflected_intents,'reflected intents')


@dataclass(frozen=True)
class MarketSnapshot(Contract):
    instrument_id: str
    registry_hash: str
    source_hash: str
    data_hash: str
    event_ns: int
    received_ns: int
    observed_ns: int
    bid: int
    ask: int
    healthy: bool


@dataclass(frozen=True)
class Valuation(Contract):
    """Caller-attested conservative coefficients over the stated price interval.

    This does not derive option risk, broker margin or fees. The caller must trust
    its convention and exact digest independently before binding an intent to it.
    """
    instrument_id: str
    registry_hash: str
    convention_hash: str
    source_hash: str
    observed_ns: int
    min_price: int
    max_price: int
    notional_per_quantity: Ratio
    exposure_per_quantity: Ratio
    fee_per_quantity: Ratio
    side: str
    net_min_per_quantity: SignedRatio
    net_max_per_quantity: SignedRatio

    def __post_init__(self):
        super().__post_init__()
        if self.min_price > self.max_price or self.notional_per_quantity.numerator <= 0 or self.exposure_per_quantity.numerator <= 0:
            raise ValueError('positive risk valuation with explicit price interval required')
        gross=Fraction(self.exposure_per_quantity.numerator,self.exposure_per_quantity.denominator)
        low=Fraction(self.net_min_per_quantity.numerator,self.net_min_per_quantity.denominator)
        high=Fraction(self.net_max_per_quantity.numerator,self.net_max_per_quantity.denominator)
        if self.side not in ('buy','sell') or not -gross <= low <= 0 <= high <= gross:
            raise ValueError('side-bound net interval must contain zero and fit gross bound')


@dataclass(frozen=True)
class Reservation(Contract):
    intent_id: str
    account: AccountKey
    units: Units
    exposures: tuple[Exposure, ...]

    def __post_init__(self):
        super().__post_init__()
        _unique(tuple(e.scope for e in self.exposures),'reservation scopes')
