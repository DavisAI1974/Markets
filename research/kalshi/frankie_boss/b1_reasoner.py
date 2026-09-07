"""Additive C19/C20 recurrence; no production wiring or cross-packet state.

Implements BOSS_CONTRACT_ADDENDUM_R3_20260907 rev 1 plus the H2 ruling. Tensor arguments
match Trunk, leaving packet-to-tensor conversion to the existing boundary.
``represent`` is the teacher surface. ``forward`` returns the same head
mapping as B0 with provenance attached as attributes, outside the heads.
The caller supplies the upstream causal packet hash; this module does not
invent a tensor serializer or claim to validate the upstream packet.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import nn

try:
    from .causal_packet import canonical_bytes
    from .trunk import GatedDeltaCell, SlidingWindowAttention, Trunk
except ImportError:
    from causal_packet import canonical_bytes
    from trunk import GatedDeltaCell, SlidingWindowAttention, Trunk


RECURRENCE_SCHEMA = "BOSS_B1_RECURRENCE_V1"
HALT_SCHEMA = "BOSS_B1_HALT_V1"
K_MIN = 1


@dataclass(frozen=True)
class B1Config:
    """Declared architecture/ablation values, never adapted during a forward.

    The blind-day registry must lock the default constants externally;
    overrides exist for the explicitly required depth/threshold tests.
    """

    k_max: int = 8
    k_fixed: int = 8
    halt_policy: str = "FIXED"
    conv_tau: float = 1e-3
    inject_input: bool = True
    step_embedding: bool = True

    def __post_init__(self):
        if type(self.k_max) is not int or self.k_max < 1:
            raise ValueError("k_max must be a positive integer")
        if type(self.k_fixed) is not int or not 0 <= self.k_fixed <= self.k_max:
            raise ValueError("k_fixed must be an integer in [0, k_max]")
        if self.halt_policy not in ("FIXED", "CONVERGENCE"):
            raise ValueError("halt_policy must be FIXED or CONVERGENCE")
        if (type(self.conv_tau) not in (int, float)
                or not math.isfinite(self.conv_tau) or self.conv_tau < 0):
            raise ValueError("conv_tau must be finite and nonnegative")
        if type(self.inject_input) is not bool or type(self.step_embedding) is not bool:
            raise ValueError("ablation flags must be boolean")

    @property
    def config_hash(self) -> str:
        return hashlib.sha256(RECURRENCE_SCHEMA.encode() + b"\0"
                              + canonical_bytes(asdict(self))).hexdigest()


@dataclass(frozen=True)
class RecurrenceReceipt:
    schema: str
    b1_code_sha: str
    config_hash: str
    n_params_core: int
    n_params_step_embedding: int
    packet_hash: str
    halt_schema: str
    policy: str
    k_min: int
    k_max: int
    conv_tau: float
    depth_used: tuple[int, ...]
    stop_reason: tuple[str, ...]
    r_trace: tuple[tuple[float, ...], ...]


class B1Output(dict):
    """Only TypedHeads keys participate in the mapping/decision surface."""

    def __init__(self, heads, representation, receipt):
        super().__init__(heads)
        self.representation = representation
        self.receipt = receipt


def convergence_halt(z_prev, z_next, valid_mask, k, constants):
    """Outcome-independent relative change; k is the completed step count."""
    mask = valid_mask.unsqueeze(-1)
    delta = torch.where(mask, z_next - z_prev, torch.zeros_like(z_prev))
    prior = torch.where(mask, z_prev, torch.zeros_like(z_prev))
    ratio = torch.linalg.vector_norm(delta, dim=(1, 2)) / torch.clamp(
        torch.linalg.vector_norm(prior, dim=(1, 2)), min=1e-6)
    halt = (ratio < constants.conv_tau) & (k >= K_MIN)
    return ratio, halt


def _code_blob_sha():
    content = Path(__file__).read_bytes()
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


class B1Reasoner(nn.Module):
    """One B0 representation, one shared reasoning cell, then B0 typed heads.

    Every parameter except e_step belongs to n_params_core, including the
    jointly trained trunk, exactly as the corrected acceptance A2 states.
    GatedDeltaCell initializes S locally on each invocation; no S is stored
    here. Ablations disable contributions while keeping parameter shapes.
    """

    def __init__(self, trunk: Trunk, config: B1Config | None = None):
        super().__init__()
        self.trunk = trunk
        self.config = config if config is not None else B1Config()
        self.cfg = trunk.cfg
        d = self.cfg.d_model
        self.w_in = nn.Linear(d, d, bias=False)
        self.e_step = nn.Parameter(torch.empty(self.config.k_max, d))
        nn.init.normal_(self.e_step, std=0.02)
        self.ln_in = nn.LayerNorm(d)
        self.swa_r = SlidingWindowAttention(self.cfg)
        self.gdc_r = GatedDeltaCell(self.cfg)
        self.ff_r = nn.Sequential(nn.LayerNorm(d),
                                  nn.Linear(d, self.cfg.d_ff_mult * d), nn.GELU(),
                                  nn.Linear(self.cfg.d_ff_mult * d, d))
        self.ln_out = nn.LayerNorm(d)
        self.b1_code_sha = _code_blob_sha()

    def reasoning_step(self, z, h0, k):
        return self._cell(z, h0, k)

    def _cell(self, z, h0, k):
        u = z
        if self.config.inject_input:
            u = u + self.w_in(h0)
        if self.config.step_embedding:
            u = u + self.e_step[k]
        u = self.swa_r(self.ln_in(u))
        u = self.gdc_r(u)
        return self.ln_out(u + self.ff_r(u))

    def represent_b0(self, *args, **kwargs):
        """Diagnostic B0 surface, not the B1 teacher attachment."""
        return self.trunk.represent(*args, **kwargs)

    def _run(self, args, kwargs, valid_mask):
        h0 = self.trunk.represent(*args, **kwargs)
        b, t, _ = h0.shape
        if b == 0 or t == 0:
            raise ValueError("B1 requires a nonempty batch and sequence")
        if valid_mask is None:
            valid_mask = torch.ones((b, t), dtype=torch.bool, device=h0.device)
        if (valid_mask.shape != (b, t) or valid_mask.dtype != torch.bool
                or valid_mask.device != h0.device or not valid_mask.any(dim=1).all()):
            raise ValueError("valid_mask must be boolean (B,T), same device, with valid tokens per row")
        z = h0
        active = torch.ones(b, dtype=torch.bool, device=h0.device)
        depths = [0] * b
        reasons = ["FIXED_DEPTH"] * b
        traces = [[] for _ in range(b)]
        fixed = self.config.halt_policy == "FIXED"
        limit = self.config.k_fixed if fixed else self.config.k_max
        for k in range(limit):
            proposed = self.reasoning_step(z, h0, k)
            next_z = torch.where(active[:, None, None], proposed, z)
            ratio, halt = convergence_halt(z, next_z, valid_mask, k + 1, self.config)
            if not torch.isfinite(ratio).all():
                raise ValueError("nonfinite recurrence change")
            # Host diagnostics do not replace or detach the model's state.
            for i, (is_active, value) in enumerate(zip(active.tolist(), ratio.tolist())):
                if is_active:
                    depths[i] = k + 1
                    traces[i].append(value)
            z = next_z
            if not fixed:
                stopped = active & halt
                for i in range(b):
                    if stopped[i]:
                        reasons[i] = "CONVERGED"
                    elif active[i]:
                        reasons[i] = "MAX_DEPTH"
                active = active & ~halt
                if not active.any():
                    break
        return z, tuple(depths), tuple(reasons), tuple(tuple(v) for v in traces)

    def represent(self, *args, valid_mask=None, **kwargs):
        """Return only the final (possibly per-example frozen) teacher state."""
        return self._run(args, kwargs, valid_mask)[0]

    def forward(self, *args, packet_hash: str, valid_mask=None, **kwargs):
        if not isinstance(packet_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", packet_hash):
            raise ValueError("packet_hash must be the upstream 64-hex causal packet hash")
        z, depths, reasons, traces = self._run(args, kwargs, valid_mask)
        embedding_count = self.e_step.numel()
        receipt = RecurrenceReceipt(
            schema=RECURRENCE_SCHEMA, b1_code_sha=self.b1_code_sha,
            config_hash=self.config.config_hash,
            n_params_core=sum(p.numel() for p in self.parameters()) - embedding_count,
            n_params_step_embedding=embedding_count, packet_hash=packet_hash,
            halt_schema=HALT_SCHEMA, policy=self.config.halt_policy, k_min=K_MIN,
            k_max=self.config.k_max, conv_tau=self.config.conv_tau,
            depth_used=depths, stop_reason=reasons, r_trace=traces)
        return B1Output(self.trunk.heads(z), z, receipt)

    def forward_decision(self, *args, packet_hash: str, valid_mask=None, **kwargs):
        """Audited serving entry: exactly one packet per forward (H2 ruling).

        ``forward`` permits batches for training and shadow evaluation. Packet
        hash determinism in A3/H5 is guaranteed for this batch-one path.
        """
        if self.training:
            raise ValueError("audited decision requires eval mode")
        numeric = args[0] if args else kwargs.get("numeric")
        if not isinstance(numeric, torch.Tensor) or numeric.ndim != 3 or numeric.shape[0] != 1:
            raise ValueError("audited decision requires exactly one packet")
        for value in (*args, *kwargs.values(), valid_mask):
            if isinstance(value, torch.Tensor) and (value.ndim == 0 or value.shape[0] != 1):
                raise ValueError("audited decision requires exactly one packet in every tensor")
        return self.forward(*args, packet_hash=packet_hash, valid_mask=valid_mask, **kwargs)
