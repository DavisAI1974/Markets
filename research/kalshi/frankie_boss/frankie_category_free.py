"""Owner-approved opt-in twelve-field interface, separate from protected BLD-1."""
from dataclasses import dataclass, field
import hashlib
import json

try:
    from .frankie_contract import BLD1_FIELDS, BLD1_FIELD_NAMES, ContractError, _curve_positions, _mechanically_linear
    from .forecast_contract import sha256_digest
except ImportError:
    from frankie_contract import BLD1_FIELDS, BLD1_FIELD_NAMES, ContractError, _curve_positions, _mechanically_linear
    from forecast_contract import sha256_digest

CONTRACT_ID = 'BOSS_FRANKIE_CATEGORY_FREE_V1'
ADAPTER_ID = 'BOSS_FRANKIE_CATEGORY_FREE_ADAPTER_V1'


def validate_category_free(payload):
    """The defects list is fatal-only; report non-fatal gaps in reasoning."""
    if not isinstance(payload, dict) or set(payload) != set(BLD1_FIELD_NAMES):
        raise ValueError('exactly the twelve Frankie fields are required')
    if payload['confidence'] is not None:
        raise ValueError('category-free confidence must be null')
    try:
        checked = {f.name: (None if f.name == 'confidence' else f.validate(payload[f.name])) for f in BLD1_FIELDS}
        points = _curve_positions(checked['path_p50_curve'])
    except ContractError as exc:
        raise ValueError(str(exc)) from exc
    if not checked['reasoning'].strip():
        raise ValueError('reasoning must be nonempty')
    if abs(points[0][1]) > 1e-9:
        raise ValueError('first cumulative value must be zero')
    if checked['guessed_net_usd'] != checked['overnight_gap_usd'] + points[-1][1]:
        raise ValueError('terminal must equal net minus gap')
    if abs(points[-1][1]) > 1e-9 and _mechanically_linear(points):
        raise ValueError('decorative endpoint interpolation rejected')
    if checked['state_defects_and_gaps_reported']:
        if (checked['disposition'] != 'ABSTAIN' or checked['guessed_net_usd'] != 0
                or checked['overnight_gap_usd'] != 0 or checked['plays_fired'] or checked['plays_stood_down']
                or checked['path_p50_curve'] != [[20., 0.], [24., 0.]]):
            raise ValueError('fatal defects require complete safety abstention')
    return checked


@dataclass(frozen=True, slots=True)
class CategoryFreeRecord:
    payload_json: str
    artifact_digest: str | None
    publication_hash: str | None = None
    reproduction_status: str = 'unknown'
    contract_id: str = field(default=CONTRACT_ID, init=False)
    adapter_id: str = field(default=ADAPTER_ID, init=False)

    def __post_init__(self):
        if type(self.payload_json) is not str:
            raise ValueError('immutable JSON record required')
        payload = validate_category_free(json.loads(self.payload_json))
        if self.artifact_digest is None:
            if not payload['state_defects_and_gaps_reported']:
                raise ValueError('forecast record requires its trusted artifact identity')
        else:
            sha256_digest(self.artifact_digest, 'artifact')
        if self.publication_hash is not None:
            sha256_digest(self.publication_hash, 'publication')
        if self.reproduction_status not in ('unknown', 'publisher_verified'):
            raise ValueError('unknown publisher reproduction status')
        object.__setattr__(self, 'payload_json', json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False))

    @property
    def payload(self):
        return json.loads(self.payload_json)

    def to_json(self):
        forecast_fields = {'guessed_net_usd', 'overnight_gap_usd', 'path_p50_curve', 'confidence'}
        metadata = {k: v for k, v in self.payload.items() if k not in forecast_fields}
        metadata_hash = hashlib.sha256(json.dumps(metadata, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        return json.dumps(dict(payload=self.payload, stamp=dict(contract_id=self.contract_id,
            adapter_id=self.adapter_id, artifact_digest=self.artifact_digest,
            publication_hash=self.publication_hash, reproduction_status=self.reproduction_status,
            metadata_hash=metadata_hash,
            metadata_verification='caller_supplied_unverified')), sort_keys=True, separators=(',', ':'), allow_nan=False)

    @property
    def digest(self):
        return hashlib.sha256(self.to_json().encode()).hexdigest()


def category_free_abstain(metadata, reasons):
    """Same complete safety fields as Frankie, with the approved null confidence."""
    if not isinstance(reasons, (list, tuple)) or not reasons or any(type(r) is not str or not r.strip() for r in reasons):
        raise ValueError('explicit nonempty defect reasons required')
    expected = set(BLD1_FIELD_NAMES)-{'guessed_net_usd', 'overnight_gap_usd', 'path_p50_curve', 'confidence'}
    if not isinstance(metadata, dict) or set(metadata) != expected:
        raise ValueError('complete existing Frankie metadata required')
    for f in BLD1_FIELDS:
        if f.name in metadata:
            f.validate(metadata[f.name])
    payload = dict(metadata)
    for f in BLD1_FIELDS:
        if f.name not in ('specialist', 'group', 'date', 'reasoning'):
            value = None if f.name == 'confidence' else f.zero_on_abstain
            payload[f.name] = value
    payload.update(disposition='ABSTAIN', state_defects_and_gaps_reported=list(reasons),
                   reasoning=metadata['reasoning'].strip() or '; '.join(reasons))
    if metadata['plays_fired'] or metadata['plays_stood_down']:
        history = {k: metadata[k] for k in ('plays_fired', 'plays_stood_down')}
        payload['reasoning'] += '\nPre-abstention play metadata: ' + json.dumps(history, sort_keys=True)
    return CategoryFreeRecord(json.dumps(payload), None)


def report_nonfatal_gaps(metadata, gaps):
    """Preserve twelve fields: non-fatal missingness is visible in reasoning.

    This helper does not decide severity. Callers must not downgrade causal or
    integrity failures; those remain in state_defects_and_gaps_reported.
    """
    if (not isinstance(gaps, (list, tuple)) or not gaps
            or any(type(g) is not str or not g.strip() for g in gaps)):
        raise ValueError('explicit nonempty non-fatal gap descriptions required')
    expected = set(BLD1_FIELD_NAMES)-{'guessed_net_usd', 'overnight_gap_usd', 'path_p50_curve', 'confidence'}
    if type(metadata) is not dict or set(metadata) != expected:
        raise ValueError('complete existing Frankie metadata required')
    result = json.loads(json.dumps(metadata, allow_nan=False))
    for f in BLD1_FIELDS:
        if f.name in result:
            f.validate(result[f.name])
    result['reasoning'] = result['reasoning'].rstrip() + '\nNon-fatal gaps: ' + json.dumps(list(gaps))
    return result
