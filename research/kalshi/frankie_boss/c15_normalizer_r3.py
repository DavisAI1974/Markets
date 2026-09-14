"""C15R3 normalization with all 19 windows; immutable R2 math stays shared."""
from collections import deque
import hashlib
import math
from pathlib import Path
import struct

try:
    from . import c15_normalizer as control
    from .c15_journal import evidence_hash
except ImportError:
    import c15_normalizer as control
    from c15_journal import evidence_hash

SCHEMA = 'C15_NORM_ONLINE_R3_V1'
CANDIDATE = 'BOSS_TEACHER_CANDIDATE_C15R3'


class NormalizerR3(control.Normalizer):
    """Same exclusive-prefix robust transform, separately identified state.

    Reuses transform/update/freeze and the strict checkpoint field validator;
    the internal restore translation changes schema labels only, never windows.
    Public R2 exports are rejected rather than silently migrated.
    """
    def __init__(self, config):
        super().__init__(config)
        self._windows = {(i, c): deque(maxlen=config.n_norm)
                         for i in config.instrument_ids for c in control.COLUMNS}
        self._counts = dict.fromkeys(self._windows, 0)

    def _validate(self, instrument_id, column, value, state):
        if type(instrument_id) is not int or instrument_id not in self.config.instrument_ids:
            raise ValueError('instrument outside declared universe')
        if column not in control.COLUMNS:
            raise ValueError('unknown column')
        if type(state) not in (int, control.State):
            raise ValueError('unknown state')
        state = control.State(state)
        if type(value) not in (int, float):
            raise ValueError('value must be finite real number')
        try:
            value = float(value)
        except OverflowError as exc:
            raise ValueError('value outside float64') from exc
        if not math.isfinite(value) or (state != control.State.PRESENT and value != 0.):
            raise ValueError('finite PRESENT or zero non-PRESENT value required')
        return value, state

    def export(self):
        return dict(super().export(), schema=SCHEMA, candidate=CANDIDATE)

    @property
    def state_hash(self):
        return evidence_hash(self.export())

    @property
    def normalizer_id(self):
        return f'{SCHEMA}:FROZEN:{self.state_hash}' if self.config.mode == 'FROZEN' else f'{SCHEMA}:UPDATING'

    @classmethod
    def restore(cls, config, payload, expected_hash):
        if (type(payload) is not dict or payload.get('schema') != SCHEMA
                or payload.get('candidate') != CANDIDATE):
            raise ValueError('R3 checkpoint schema required')
        translated = dict(payload, schema=control.SCHEMA, candidate=control.CANDIDATE)
        return super().restore(config, translated, expected_hash)

    def receipt(self):
        return dict(schema=SCHEMA, candidate=CANDIDATE,
            normalizer_code_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            control_code_sha=hashlib.sha256(Path(control.__file__).read_bytes()).hexdigest(),
            config_hash=self.config.config_hash, state_hash=self.state_hash,
            normalizer_id=self.normalizer_id)


class IdentityNormalizerR3:
    """Mechanics only: finite float32 shares, explicitly distinct from R2."""
    normalizer_id = 'C15_NORM_IDENTITY_R3'
    _validate = NormalizerR3._validate

    def __init__(self, instrument_ids):
        self.config = control.NormalizerConfig(instrument_ids)

    def observe(self, instrument_id, column, value, state=control.State.PRESENT):
        value, state = self._validate(instrument_id, column, value, state)
        try:
            value = struct.unpack('<f', struct.pack('<f', value))[0]
        except OverflowError as exc:
            raise ValueError('identity value outside float32') from exc
        return control.NormalizedValue(value if state == control.State.PRESENT else 0., state)

    def export(self):
        return dict(schema=self.normalizer_id, candidate=CANDIDATE,
                    config=self.config.payload(), windows=[])
