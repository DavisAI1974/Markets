"""Exact identities and primitive validation shared by forecast contracts."""
from dataclasses import asdict
import math
import re

try:
    from .c15_journal import evidence_hash
except ImportError:
    from c15_journal import evidence_hash


def finite_number(value, name):
    if type(value) not in (int, float):
        raise ValueError(f'{name} must be a finite number')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f'{name} must be a finite number')


def sha256_digest(value, name):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError(f'{name} must be a lowercase SHA-256 digest')


def unique_names(values, name):
    if (type(values) is not tuple or not values or
            any(type(v) is not str or not v.strip() for v in values) or
            len(set(values)) != len(values)):
        raise ValueError(f'{name} must be a nonempty tuple of unique identifiers')


class HashedContract:
    __slots__ = ()

    @property
    def digest(self):
        return evidence_hash(dict(schema='BOSS_FORECAST_CONTRACT_V1',
                                  kind=type(self).__name__, fields=asdict(self)))
