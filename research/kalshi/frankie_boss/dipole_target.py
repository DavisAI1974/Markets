"""
DIPOLE_TEACHER_SCHEMA_V1 -- the governed contract for a dipole teacher target.

Closes gate G11 (Gates sheet) and component C14 (Components sheet) of the
Frankie BOSS build plan. Until this object exists, two runs can put
different meanings behind the same (B, T, K) tensor shape and nobody can
tell. After it, a tensor that reaches the teacher without passing
through DipoleTarget is a bug by definition.

This module is a VALIDATOR, not a builder. It does not know how to derive
a dipole target from raw MBO; that is C15 and it belongs to Stage 7 after
the raw-MBO input builder (Stage 4) exists. What this module fixes now is
everything a builder must satisfy, so the builder is written against a
contract instead of against a synthetic tensor. That is the mistake the
first teacher.py made and it is not being made twice.

What the contract enforces
--------------------------
identity      schema_version, registry_id, ordered target_names/units,
              normalizer_id, builder_code_sha. Width is derived from the
              names, never declared as a bare integer.
provenance    source_manifest_hash (raw DBN roster) and source_prefix_hash
              (causal event-group prefix), both required, both opaque.
causality     as_of_ts_recv_ns is the sole availability cutoff. Every
              step's ts_recv_ns must be <= as_of and non-decreasing in T.
              Exchange time (ts_event) is not accepted here at all.
states        every (b, t, k) entry is PRESENT, MISSING, INVALID, or
              ABLATED. Values are finite where PRESENT and exactly 0.0
              elsewhere, so a zero can never be mistaken for a value:
              the state says which it is, not the number.
hash          target_hash is sha256 over canonical metadata plus the raw
              little-endian bytes of values, states, and timestamps. A
              supplied hash that does not match is rejected.

Loss coverage
-------------
masked_mse() scores only PRESENT entries. All arms in the D0-D5 matrix
must use the same mask so the auxiliary loss is computed over identical
positions; the one deliberate exception is the shuffled arm, which
derangs values and states together to preserve the joint marginal
including missingness. teacher.py reports aux_coverage per arm so that
divergence is visible rather than assumed away.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Mapping, Sequence

import torch

try:  # Package import in Markets.
    from .causal_packet import canonical_bytes
except ImportError:  # Direct execution with this directory on PYTHONPATH.
    from causal_packet import canonical_bytes

__all__ = [
    "SCHEMA_VERSION",
    "DipoleTargetSpec",
    "DipoleTarget",
    "TargetState",
    "SchemaError",
    "masked_mse",
]

SCHEMA_VERSION = "DIPOLE_TEACHER_SCHEMA_V1"
_HEX64 = 64


class SchemaError(ValueError):
    """Any violation of DIPOLE_TEACHER_SCHEMA_V1."""


class TargetState(IntEnum):
    PRESENT = 0
    MISSING = 1
    INVALID = 2
    ABLATED = 3


def _require_hex(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != _HEX64:
        raise SchemaError(f"{label} must be a 64-char hex sha256, got {value!r}")
    try:
        int(value, 16)
    except ValueError as e:
        raise SchemaError(f"{label} is not hex: {value!r}") from e
    return value


def _require_nonempty_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{label} must be a non-empty string")
    return value


@dataclass(frozen=True)
class DipoleTargetSpec:
    """The meaning of the K columns. Immutable; shared by every batch of a run."""

    registry_id: str
    target_names: tuple[str, ...]
    target_units: tuple[str, ...]
    normalizer_id: str
    builder_code_sha: str
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SchemaError(
                f"schema_version {self.schema_version!r} != {SCHEMA_VERSION!r}"
            )
        _require_nonempty_str(self.registry_id, "registry_id")
        _require_nonempty_str(self.normalizer_id, "normalizer_id")
        _require_nonempty_str(self.builder_code_sha, "builder_code_sha")
        names = tuple(self.target_names)
        units = tuple(self.target_units)
        if not names:
            raise SchemaError("target_names must not be empty; width is len(names)")
        if len(names) != len(units):
            raise SchemaError(
                f"target_names ({len(names)}) and target_units ({len(units)}) "
                f"must have equal length"
            )
        if len(set(names)) != len(names):
            raise SchemaError("target_names must be unique")
        for n in names:
            _require_nonempty_str(n, "target name")
        for u in units:
            _require_nonempty_str(u, "target unit")
        object.__setattr__(self, "target_names", names)
        object.__setattr__(self, "target_units", units)

    @property
    def width(self) -> int:
        return len(self.target_names)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "registry_id": self.registry_id,
            "target_names": list(self.target_names),
            "target_units": list(self.target_units),
            "normalizer_id": self.normalizer_id,
            "builder_code_sha": self.builder_code_sha,
        }

    @property
    def spec_hash(self) -> str:
        return hashlib.sha256(canonical_bytes(self.to_dict())).hexdigest()


@dataclass(frozen=True)
class DipoleTarget:
    """One batch of aligned dipole targets with provenance and causal receipt.

    values      (B, T, K) float32; finite where PRESENT, exactly 0.0 elsewhere
    states      (B, T, K) int8 in TargetState
    ts_recv_ns  (B, T)    int64; <= as_of_ts_recv_ns, non-decreasing in T
    """

    spec: DipoleTargetSpec
    source_manifest_hash: str
    source_prefix_hash: str
    as_of_ts_recv_ns: int
    values: torch.Tensor
    states: torch.Tensor
    ts_recv_ns: torch.Tensor
    target_hash: str = field(default="")

    def __post_init__(self) -> None:
        _require_hex(self.source_manifest_hash, "source_manifest_hash")
        _require_hex(self.source_prefix_hash, "source_prefix_hash")
        if isinstance(self.as_of_ts_recv_ns, bool) or not isinstance(
            self.as_of_ts_recv_ns, int
        ):
            raise SchemaError("as_of_ts_recv_ns must be an int (nanoseconds)")
        if self.as_of_ts_recv_ns <= 0:
            raise SchemaError("as_of_ts_recv_ns must be positive")

        v, s, ts = self.values, self.states, self.ts_recv_ns
        if not (torch.is_tensor(v) and torch.is_tensor(s) and torch.is_tensor(ts)):
            raise SchemaError("values, states and ts_recv_ns must be tensors")
        if v.dim() != 3:
            raise SchemaError(f"values must be (B, T, K), got {tuple(v.shape)}")
        if v.shape[-1] != self.spec.width:
            raise SchemaError(
                f"values width {v.shape[-1]} != len(target_names) {self.spec.width}"
            )
        if s.shape != v.shape:
            raise SchemaError(f"states {tuple(s.shape)} must match values {tuple(v.shape)}")
        if ts.shape != v.shape[:2]:
            raise SchemaError(
                f"ts_recv_ns {tuple(ts.shape)} must be (B, T) = {tuple(v.shape[:2])}"
            )
        if v.dtype != torch.float32:
            raise SchemaError(f"values must be float32, got {v.dtype}")
        if s.dtype != torch.int8:
            raise SchemaError(f"states must be int8, got {s.dtype}")
        if ts.dtype != torch.int64:
            raise SchemaError(f"ts_recv_ns must be int64, got {ts.dtype}")
        if v.device != s.device or v.device != ts.device:
            raise SchemaError("values, states and ts_recv_ns must share a device")

        valid = torch.tensor([int(x) for x in TargetState], device=s.device, dtype=torch.int8)
        if not torch.isin(s, valid).all():
            raise SchemaError("states contain a value outside TargetState")
        present = s == int(TargetState.PRESENT)
        if not torch.isfinite(v[present]).all():
            raise SchemaError("PRESENT values must be finite")
        if not (v[~present] == 0.0).all():
            raise SchemaError(
                "non-PRESENT values must be exactly 0.0; the state carries the "
                "meaning, not the number"
            )

        # Causal receipt: every step visible at or before the cutoff, in order.
        if (ts <= 0).any():
            raise SchemaError("ts_recv_ns must be positive")
        if (ts > self.as_of_ts_recv_ns).any():
            raise SchemaError(
                "ts_recv_ns exceeds as_of_ts_recv_ns: target uses data not yet "
                "available at the cutoff (answer-wall violation)"
            )
        if ts.shape[1] > 1 and (ts[:, 1:] < ts[:, :-1]).any():
            raise SchemaError("ts_recv_ns must be non-decreasing along T")

        computed = self._compute_hash()
        if self.target_hash == "":
            object.__setattr__(self, "target_hash", computed)
        elif self.target_hash != computed:
            raise SchemaError(
                f"target_hash mismatch: supplied {self.target_hash[:12]}..., "
                f"computed {computed[:12]}..."
            )

    # ---------------------------------------------------------------- hash

    def _compute_hash(self) -> str:
        h = hashlib.sha256()
        h.update(
            canonical_bytes(
                {
                    "spec": self.spec.to_dict(),
                    "source_manifest_hash": self.source_manifest_hash,
                    "source_prefix_hash": self.source_prefix_hash,
                    "as_of_ts_recv_ns": self.as_of_ts_recv_ns,
                    "shape": list(self.values.shape),
                }
            )
        )
        for t in (self.values, self.states, self.ts_recv_ns):
            h.update(t.detach().cpu().contiguous().numpy().tobytes())
        return h.hexdigest()

    # ------------------------------------------------------------- views

    @property
    def mask(self) -> torch.Tensor:
        """(B, T, K) float32, 1.0 where PRESENT."""
        return (self.states == int(TargetState.PRESENT)).to(self.values.dtype)

    @property
    def coverage(self) -> float:
        """Fraction of entries that are PRESENT."""
        return float(self.mask.mean())

    def state_counts(self) -> dict[str, int]:
        return {st.name: int((self.states == int(st)).sum()) for st in TargetState}

    def to_batch_fields(self) -> dict[str, torch.Tensor]:
        """The three tensors the training runner consumes, keyed the way
        teacher.run_experiment expects them."""
        return {
            "dipole": self.values,
            "dipole_mask": self.mask,
            "dipole_ts_recv_ns": self.ts_recv_ns,
        }

    def receipt(self) -> dict[str, Any]:
        """Everything a lock file needs to identify this target exactly."""
        return {
            "schema_version": self.spec.schema_version,
            "spec_hash": self.spec.spec_hash,
            "target_hash": self.target_hash,
            "source_manifest_hash": self.source_manifest_hash,
            "source_prefix_hash": self.source_prefix_hash,
            "as_of_ts_recv_ns": self.as_of_ts_recv_ns,
            "shape": list(self.values.shape),
            "state_counts": self.state_counts(),
            "coverage": self.coverage,
        }


# ------------------------------------------------------------------ loss


def masked_mse(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """MSE over PRESENT entries only. Refuses an empty mask rather than
    returning 0/0 as a silent zero loss."""
    if pred.shape != target.shape or mask.shape != target.shape:
        raise SchemaError(
            f"masked_mse shape mismatch: pred {tuple(pred.shape)} target "
            f"{tuple(target.shape)} mask {tuple(mask.shape)}"
        )
    n = mask.sum()
    if float(n) == 0.0:
        raise SchemaError("masked_mse: no PRESENT entries; refusing to report a zero loss")
    return ((pred - target) ** 2 * mask).sum() / n
