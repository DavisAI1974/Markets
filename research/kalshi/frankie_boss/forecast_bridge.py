"""Owner-approved category-free Frankie path, separate from protected BLD-1.

This module has no model imports at load time. The default route calls the exact
legacy callback. The enabled result has its own explicit contract identity.
"""
from dataclasses import dataclass
import json


class LegacyConfidenceCompatibilityError(ValueError):
    def __init__(self, draft):
        self.draft = draft
        super().__init__('Protected BLD-1 requires low|med|high; category-free confidence=null '
                         'requires an explicitly approved versioned interface. Draft forecast retained.')


@dataclass(frozen=True, slots=True)
class PreparedFrankieForecast:
    artifact_digest: str
    payload_json: str
    artifact_payload: bytes
    contract_id: str = 'BOSS_FRANKIE_CATEGORY_FREE_V1'

    @property
    def payload(self):
        return json.loads(self.payload_json)


def route_frankie_forecast(*, legacy, load_native, enabled=False,
                          expected_digest=None, publication_hash=None, metadata=None):
    """Enabled roots and metadata must come independently from the verified caller.

    The loader supplies only a proposal. This function cannot authenticate a ledger
    or a metadata origin; consume_forecast supplies the verified publication root.
    Caller metadata remains explicitly unverified in the returned transport stamp.
    """
    if type(enabled) is not bool:
        raise ValueError('explicit boolean enable flag required')
    if not enabled:
        return legacy()
    try:
        from .forecast_contract import sha256_digest
        from .frankie_contract import BLD1_FIELDS, BLD1_FIELD_NAMES
    except ImportError:
        from forecast_contract import sha256_digest
        from frankie_contract import BLD1_FIELDS, BLD1_FIELD_NAMES
    sha256_digest(expected_digest, 'trusted native artifact')
    sha256_digest(publication_hash, 'trusted publication')
    forecast_fields = {'guessed_net_usd', 'overnight_gap_usd', 'path_p50_curve', 'confidence'}
    if type(metadata) is not dict or set(metadata) != set(BLD1_FIELD_NAMES)-forecast_fields:
        raise ValueError('complete independent caller metadata required')
    metadata = json.loads(json.dumps(metadata, allow_nan=False))
    for spec in BLD1_FIELDS:
        if spec.name in metadata:
            spec.validate(metadata[spec.name])
    draft = load_native()
    if not isinstance(draft, PreparedFrankieForecast):
        raise ValueError('typed category-free draft required')
    try:
        from .frankie_category_free import CategoryFreeRecord, CONTRACT_ID
        from .forecast_artifact import NativeForecastArtifact
    except ImportError:
        from frankie_category_free import CategoryFreeRecord, CONTRACT_ID
        from forecast_artifact import NativeForecastArtifact
    if draft.contract_id != CONTRACT_ID:
        raise LegacyConfidenceCompatibilityError(draft)
    if draft.artifact_digest != expected_digest:
        raise ValueError('proposal differs from trusted native artifact')
    checked = CategoryFreeRecord(draft.payload_json, expected_digest, publication_hash)
    artifact = NativeForecastArtifact.from_payload(draft.artifact_payload, expected_digest=expected_digest)
    expected = prepare_frankie_forecast(artifact, expected_digest=expected_digest, metadata=metadata)
    if expected.payload != checked.payload:
        raise ValueError('projection differs from trusted native artifact or caller metadata')
    return checked


def prepare_frankie_forecast(artifact, *, expected_digest, metadata):
    """Prepare all twelve approved fields with explicit null confidence.

    No calibration diagnostic enters the fatal defect list. Metadata comes from
    the existing Frankie population path; this function does not invent plays,
    reasoning, disposition, or execution authority.
    """
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    try:
        from .forecast_artifact import NativeForecastArtifact
        from .frankie_contract import BLD1_FIELDS, BLD1_FIELD_NAMES, _curve_positions, _mechanically_linear
    except ImportError:
        from forecast_artifact import NativeForecastArtifact
        from frankie_contract import BLD1_FIELDS, BLD1_FIELD_NAMES, _curve_positions, _mechanically_linear
    if not isinstance(artifact, NativeForecastArtifact) or artifact.digest != expected_digest:
        raise ValueError('forecast differs from trusted native artifact')
    forecast_fields = {'guessed_net_usd', 'overnight_gap_usd', 'path_p50_curve', 'confidence'}
    if set(metadata) != set(BLD1_FIELD_NAMES)-forecast_fields:
        raise ValueError('all existing Frankie metadata fields must be supplied explicitly')
    if metadata['state_defects_and_gaps_reported']:
        raise ValueError('fatal source defects require the existing safety path')
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    et = ZoneInfo('America/New_York')
    opening = (epoch+timedelta(microseconds=artifact.session.open_ns//1000)).astimezone(et)
    closing = (epoch+timedelta(microseconds=artifact.session.close_ns//1000)).astimezone(et)
    if (opening.utcoffset() != closing.utcoffset()
            or artifact.session.duration_ns > 24*3600*10**9):
        raise ValueError('session cannot use the S121 clock across an offset change or multiple days')
    curve = []
    for index, point in enumerate(artifact.points):
        micros, remainder = divmod(point.time_ns, 1000)
        local = (epoch+timedelta(microseconds=micros)).astimezone(et)
        hour = local.hour+local.minute/60+local.second/3600+(local.microsecond*1000+remainder)/3_600_000_000_000
        terminal = index == len(artifact.points)-1
        # 24:00 means the terminal 20:00 under S121, never ordinary midnight.
        clock = '24:00' if terminal and hour == 20. else hour
        curve.append([clock, point.p50])
    positions = _curve_positions(curve)
    quantum = artifact.session.knot_policy.quantum_ns
    for point, (position, _) in zip(artifact.points, positions):
        encoded_ns = (position-positions[0][0])*3_600_000_000_000
        if abs(encoded_ns-(point.time_ns-artifact.session.open_ns)) > quantum/2:
            raise ValueError('session cannot be represented by the S121 clock at locked precision')
    if abs(positions[-1][1]) > 1e-9 and _mechanically_linear(positions):
        raise ValueError('S121 rejects decorative endpoint interpolation')
    payload = dict(metadata, guessed_net_usd=artifact.net_usd, overnight_gap_usd=artifact.gap_quantiles[1],
                   path_p50_curve=curve, confidence=None)
    for field in BLD1_FIELDS:
        if field.name != 'confidence':
            payload[field.name] = field.validate(payload[field.name])
    if payload['date'].replace('-', '') != closing.strftime('%Y%m%d'):
        raise ValueError('Frankie date must match the declared session close in ET')
    if not payload['reasoning'].strip():
        raise ValueError('existing Frankie reasoning must be nonempty')
    return PreparedFrankieForecast(artifact.digest,
        json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False), artifact.payload)
