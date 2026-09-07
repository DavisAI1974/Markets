"""Isolated C15R2 online normalization; no builder, replay, or phase authority.

The caller supplies already transformed raw values in authorized cutoff order.
``observe`` transforms against the exclusive window, then updates. ``transform``
and ``update`` are also separate for builder checkpoints. No timestamp sorting,
source-boundary reset, or automatic phase transition takes place here.
Result-bearing callers must enforce the approved candidate constants and phase
authorization; this module validates supplied configs but does not authorize them.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from enum import IntEnum
import hashlib
import math
from pathlib import Path
import struct
from statistics import median

try:
    from .causal_packet import canonical_bytes
except ImportError:
    from causal_packet import canonical_bytes

SCHEMA = "C15_NORM_ONLINE_V1"
CONFIG_DOMAIN = "C15_NORM_CONFIG_V1"
CANDIDATE = "BOSS_TEACHER_CANDIDATE_C15R2"
COLUMNS = (
    "far_front_age_log", "far_queue_age_p90_log", "far_size_hhi",
    "far_replenish_log1p_64", "far_replenish_log1p_1024",
    "far_priority_loss_rate_64", "far_priority_loss_rate_1024",
    "far_absorption_share_64", "far_absorption_share_1024",
    "far_identity_survival_64", "far_identity_survival_1024",
    "far_size_retention_64", "far_size_retention_1024",
    "unresolved_age_groups_log", "extension_count_log", "step_ratio_log",
    "pullback_ticks_last_log", "step_duration_groups_log", "pullback_ticks_prev_log",
)
ABLATED_COLUMNS = frozenset(COLUMNS[7:13])
SCALE_FLOORS = (.05, .05, .02, .05, .05, .02, .02, .02, .02,
                .02, .02, .02, .02, .10, .10, .05, .10, .10, .10)


class State(IntEnum):
    """Numeric wire values match C14, without importing its Torch dependency."""
    PRESENT = 0
    MISSING = 1
    INVALID = 2
    ABLATED = 3


def _finite(value):
    if type(value) not in (int, float):
        raise ValueError("value must be a finite real number, not bool")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError("value outside float64") from exc
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    return value


@dataclass(frozen=True)
class NormalizerConfig:
    instrument_ids: tuple[int, ...]
    mode: str = "UPDATING"
    n_norm: int = 4096
    n_warm: int = 256
    floors: tuple[float, ...] = SCALE_FLOORS
    clip: float = 8.0

    def __post_init__(self):
        if (type(self.instrument_ids) is not tuple or not self.instrument_ids
                or any(type(i) is not int or i < 0 for i in self.instrument_ids)
                or len(set(self.instrument_ids)) != len(self.instrument_ids)):
            raise ValueError("declare unique nonnegative integer instrument IDs")
        if self.mode not in ("UPDATING", "FROZEN"):
            raise ValueError("mode must be UPDATING or FROZEN")
        if (type(self.n_norm) is not int or type(self.n_warm) is not int
                or not 1 <= self.n_warm <= self.n_norm):
            raise ValueError("require 1 <= n_warm <= n_norm")
        if (type(self.floors) is not tuple or len(self.floors) != len(COLUMNS)
                or any(_finite(f) <= 0 for f in self.floors) or _finite(self.clip) <= 0):
            raise ValueError("require positive floors for every column and clip")
        if self.clip > 3.4028234663852886e38:
            raise ValueError("clip must fit finite float32 emission")

    def payload(self):
        # canonical_bytes quantizes numeric floats. Hex companions bind every
        # binary64 bit while retaining the required numeric export values and
        # using canonical_bytes as the sole serializer.
        return {"instrument_ids": list(self.instrument_ids), "mode": self.mode,
                "n_norm": self.n_norm, "n_warm": self.n_warm,
                "floors": list(self.floors), "clip": self.clip,
                "floors_hex": [float(v).hex() for v in self.floors],
                "clip_hex": float(self.clip).hex()}

    @property
    def config_hash(self):
        return hashlib.sha256(CONFIG_DOMAIN.encode() + b"\x00" + canonical_bytes(self.payload())).hexdigest()


@dataclass(frozen=True)
class NormalizedValue:
    value: float
    state: State
    reason: str = ""
    floor_bound: bool | None = None


class Normalizer:
    def __init__(self, config: NormalizerConfig):
        if not isinstance(config, NormalizerConfig):
            raise ValueError("NormalizerConfig required")
        self._config = config
        self._windows = {(i, c): deque(maxlen=config.n_norm)
                         for i in config.instrument_ids for c in COLUMNS
                         if c not in ABLATED_COLUMNS}
        self._counts = dict.fromkeys(self._windows, 0)

    @property
    def config(self):
        return self._config

    def _validate(self, instrument_id, column, value, state):
        if type(instrument_id) is not int or instrument_id not in self.config.instrument_ids:
            raise ValueError("instrument outside declared universe")
        if column not in COLUMNS:
            raise ValueError("unknown column")
        if type(state) not in (int, State):
            raise ValueError("unknown state")
        state = State(state)
        value = _finite(value)
        if column in ABLATED_COLUMNS and state != State.ABLATED:
            raise ValueError("blocked slot must be ABLATED")
        if state != State.PRESENT and value != 0.0:
            raise ValueError("non-PRESENT value must equal 0.0")
        return value, state

    def transform(self, instrument_id, column, value, state=State.PRESENT):
        value, state = self._validate(instrument_id, column, value, state)
        if state != State.PRESENT:
            return NormalizedValue(0.0, state)
        key = instrument_id, column
        if self._counts[key] < self.config.n_warm:
            return NormalizedValue(0.0, State.MISSING, "NORM_WARMUP")
        values = self._windows[key]
        location = median(values)
        mad_scale = 1.4826 * median([abs(v - location) for v in values])
        floor = self.config.floors[COLUMNS.index(column)]
        scale = max(mad_scale, floor)
        if not math.isfinite(location) or not math.isfinite(scale):
            raise ValueError("normalizer statistics outside float64")
        delta = value - location
        # Finite operands may overflow their subtraction even when the final
        # quotient is in range. Divide first only on that overflow path.
        z = delta / scale if math.isfinite(delta) else value / scale - location / scale
        z = max(-self.config.clip, min(self.config.clip, z))
        emitted = struct.unpack("<f", struct.pack("<f", z))[0]
        return NormalizedValue(emitted, State.PRESENT, floor_bound=mad_scale <= floor)

    def update(self, instrument_id, column, value, state=State.PRESENT):
        value, state = self._validate(instrument_id, column, value, state)
        if state == State.PRESENT and self.config.mode == "UPDATING":
            key = instrument_id, column
            self._windows[key].append(value)
            self._counts[key] += 1

    def observe(self, instrument_id, column, value, state=State.PRESENT):
        result = self.transform(instrument_id, column, value, state)
        self.update(instrument_id, column, value, state)
        return result

    def export(self):
        return {"schema": SCHEMA, "candidate": CANDIDATE,
                "config": self.config.payload(),
                "windows": [{"instrument_id": i, "column": c,
                             "values": list(v), "n_present": self._counts[i, c],
                             "values_hex": [x.hex() for x in v],
                             "mode": self.config.mode}
                            for (i, c), v in self._windows.items()]}

    @property
    def state_hash(self):
        return hashlib.sha256(SCHEMA.encode() + b"\x00" + canonical_bytes(self.export())).hexdigest()

    @property
    def normalizer_id(self):
        if self.config.mode == "FROZEN":
            return f"{SCHEMA}:FROZEN:{self.state_hash}"
        return f"{SCHEMA}:UPDATING"

    def freeze(self):
        """Explicit one-way transition; window values and counts do not change.

        Restore an UPDATING export under its original config before freezing.
        The resulting FROZEN export must subsequently restore as FROZEN.
        The caller is responsible for authorized phase/lock handling.
        """
        self._config = replace(self.config, mode="FROZEN")

    @classmethod
    def restore(cls, config, payload, expected_hash):
        """Validate a complete checkpoint against caller-supplied trusted identity.

        A self-consistent hash proves integrity, not authorization. The caller
        must obtain expected_hash from the authorized builder/phase receipt.
        """
        restored = cls(config)
        if (type(payload) is not dict or set(payload) != {"schema", "candidate", "config", "windows"}
                or payload["schema"] != SCHEMA or payload["candidate"] != CANDIDATE):
            raise ValueError("invalid checkpoint schema")
        raw_config = payload["config"]
        if type(raw_config) is not dict or raw_config != config.payload():
            raise ValueError("checkpoint config mismatch")
        # Revalidate types too: Python's True == 1 must not admit malformed config.
        if type(raw_config["instrument_ids"]) is not list or type(raw_config["floors"]) is not list:
            raise ValueError("invalid checkpoint config")
        config_fields = {k: v for k, v in raw_config.items() if k not in ("floors_hex", "clip_hex")}
        NormalizerConfig(**{**config_fields, "instrument_ids": tuple(raw_config["instrument_ids"]),
                            "floors": tuple(raw_config["floors"])})
        windows = payload["windows"]
        if type(windows) is not list or len(windows) != len(restored._windows):
            raise ValueError("checkpoint must contain each active window once")
        for row, key in zip(windows, restored._windows):
            if (type(row) is not dict or set(row) != {"instrument_id", "column", "values", "values_hex", "n_present", "mode"}
                    or type(row["instrument_id"]) is not int
                    or (row["instrument_id"], row["column"]) != key
                    or row["mode"] != config.mode):
                raise ValueError("invalid checkpoint window identity or mode")
            values, count = row["values"], row["n_present"]
            if (type(values) is not list or type(count) is not int or count < 0
                    or len(values) != min(count, config.n_norm)):
                raise ValueError("invalid checkpoint window count")
            parsed = [_finite(v) for v in values]
            if row["values_hex"] != [v.hex() for v in parsed]:
                raise ValueError("checkpoint float64 value/hex mismatch")
            restored._windows[key].extend(parsed)
            restored._counts[key] = count
        if (type(expected_hash) is not str or len(expected_hash) != 64
                or expected_hash != restored.state_hash):
            raise ValueError("checkpoint hash mismatch")
        return restored

    def receipt(self):
        content = Path(__file__).read_bytes()
        code_sha = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\x00" + content).hexdigest()
        return {"schema": SCHEMA, "candidate": CANDIDATE,
                "normalizer_code_sha": code_sha, "config_hash": self.config.config_hash,
                "state_hash": self.state_hash, "normalizer_id": self.normalizer_id}


class IdentityNormalizer:
    """Known-answer mechanics helper only; no fitting or phase authority."""
    normalizer_id = "C15_NORM_IDENTITY"
    _validate = Normalizer._validate

    def __init__(self, instrument_ids):
        self.config = NormalizerConfig(instrument_ids=instrument_ids)

    def observe(self, instrument_id, column, value, state=State.PRESENT):
        value, state = self._validate(instrument_id, column, value, state)
        try:
            value = struct.unpack("<f", struct.pack("<f", value))[0]
        except OverflowError as exc:
            raise ValueError("identity value outside float32") from exc
        return NormalizedValue(value if state == State.PRESENT else 0.0, state)

    def export(self):
        return {"schema": self.normalizer_id, "config": self.config.payload(), "windows": []}
