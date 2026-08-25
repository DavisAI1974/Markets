"""
Fixed-depth trunk. The baseline the diagram says must prove itself first.

Scope discipline
----------------
Recurrent-depth reasoning, Mamba-3 complex-state, and the reservoir
ensemble are NOT here. The spec is explicit that shared-weight recurrent
reasoning comes only after the fixed-depth core proves itself, and a
baseline that already contains the experiment cannot serve as a baseline.

Licensing
---------
The GatedDeltaNet reference implementation is NVIDIA Source Code
License-NC (non-commercial), and the GDN-2 repository declares
NOASSERTION. Neither is usable here. The cell below is written from the
published description of the mechanism -- a channel-wise erase gate and
a channel-wise write gate replacing the single scalar gate -- on plain
torch primitives. Mechanisms are not copyrightable; implementations are.
No NVlabs code is read, vendored, or adapted. If you later swap in
fla (MIT) kernels for speed, that is a clean substitution.

Determinism
-----------
eval() mode is deterministic by construction: no dropout, no sampling,
no data-dependent control flow. This matters because the frozen boss
model sits behind a packet hash, and a trunk that produced different
logits for the same packet would make the whole audit chain a fiction.
test_trunk.py asserts it rather than trusting it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import torch
import torch.nn as nn
import torch.nn.functional as F

__all__ = [
    "TrunkConfig",
    "FieldEncoder",
    "GatedDeltaCell",
    "SlidingWindowAttention",
    "TemporalGraphBranch",
    "TypedHeads",
    "Trunk",
]


@dataclass
class TrunkConfig:
    """Every dimension is a parameter. Nothing here assumes a schema.

    n_numeric / categorical_cardinalities describe the event fields.
    qsv_dim is the OD/QSV state vector width -- set it when you know it;
    zero disables the branch cleanly rather than erroring.
    """

    d_model: int = 256
    n_heads: int = 4
    n_layers: int = 4
    window: int = 128
    n_numeric: int = 16
    categorical_cardinalities: tuple[int, ...] = (8, 32)
    qsv_dim: int = 0
    n_venues: int = 8
    n_instruments: int = 16
    n_regimes: int = 3
    d_ff_mult: int = 4
    use_delta_memory: bool = True

    def __post_init__(self) -> None:
        if self.d_model % self.n_heads:
            raise ValueError("d_model must divide by n_heads")


# --------------------------------------------------------------------------
# Typed event and field encoders
# --------------------------------------------------------------------------


class FieldEncoder(nn.Module):
    """Typed encoder: numerics get their own projection, categoricals
    get embeddings, and the QSV/OD state vector enters as its own
    stream rather than being concatenated into the numerics.

    Keeping QSV separate is deliberate. If it is folded into the generic
    numeric block you cannot ablate it, and the whole dipole-teacher
    question turns on being able to ablate it.
    """

    def __init__(self, cfg: TrunkConfig):
        super().__init__()
        self.cfg = cfg
        self.numeric = nn.Linear(cfg.n_numeric, cfg.d_model)
        self.cats = nn.ModuleList(
            [nn.Embedding(c, cfg.d_model) for c in cfg.categorical_cardinalities]
        )
        self.qsv = (
            nn.Linear(cfg.qsv_dim, cfg.d_model) if cfg.qsv_dim > 0 else None
        )
        self.norm = nn.LayerNorm(cfg.d_model)

    def forward(
        self,
        numeric: torch.Tensor,        # (B, T, n_numeric)
        categorical: torch.Tensor,    # (B, T, n_cat) long
        qsv: torch.Tensor | None = None,  # (B, T, qsv_dim)
    ) -> torch.Tensor:
        h = self.numeric(numeric)
        for i, emb in enumerate(self.cats):
            h = h + emb(categorical[..., i])
        if self.qsv is not None:
            if qsv is None:
                raise ValueError("qsv_dim > 0 but no qsv tensor supplied")
            h = h + self.qsv(qsv)
        return self.norm(h)


# --------------------------------------------------------------------------
# Gated delta memory (clean-room)
# --------------------------------------------------------------------------


class GatedDeltaCell(nn.Module):
    """Delta-rule linear attention with decoupled erase and write gates.

    State S is (B, H, Dk, Dv). Per step:

        read_t  = S_{t-1} k_t
        S_t     = S_{t-1} * diag(1 - b_t k_t-side)  +  w_t (v_t - read_t) k_t^T

    b_t is the channel-wise erase gate on the key side; w_t is the
    channel-wise write gate on the value side. Collapsing both to one
    scalar recovers the earlier single-gate formulation, which is the
    limitation the decoupling exists to remove.

    Written as an explicit recurrence: correct, slow, and easy to check
    against. Swap in a chunked kernel once it is validated -- not before.
    """

    def __init__(self, cfg: TrunkConfig):
        super().__init__()
        self.h = cfg.n_heads
        self.dk = cfg.d_model // cfg.n_heads
        self.dv = self.dk
        d = cfg.d_model
        self.q = nn.Linear(d, d, bias=False)
        self.k = nn.Linear(d, d, bias=False)
        self.v = nn.Linear(d, d, bias=False)
        self.erase = nn.Linear(d, d)   # channel-wise, key side
        self.write = nn.Linear(d, d)   # channel-wise, value side
        self.out = nn.Linear(d, d, bias=False)
        self.norm = nn.LayerNorm(d)

    def _split(self, x: torch.Tensor) -> torch.Tensor:
        b, t, _ = x.shape
        return x.view(b, t, self.h, self.dk).transpose(1, 2)  # (B,H,T,D)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, _ = x.shape
        q = F.normalize(self._split(self.q(x)), dim=-1)
        k = F.normalize(self._split(self.k(x)), dim=-1)
        v = self._split(self.v(x))
        # Gates in (0,1), channel-wise, not scalar.
        be = torch.sigmoid(self._split(self.erase(x)))
        wr = torch.sigmoid(self._split(self.write(x)))

        S = x.new_zeros(b, self.h, self.dk, self.dv)
        outs = []
        for i in range(t):
            ki = k[:, :, i]            # (B,H,Dk)
            vi = v[:, :, i]
            qi = q[:, :, i]
            bi = be[:, :, i]
            wi = wr[:, :, i]

            read = torch.einsum("bhkd,bhk->bhd", S, ki)
            delta = (vi - read) * wi                       # value-side write
            decay = 1.0 - bi * ki.abs()                    # key-side erase
            S = S * decay.unsqueeze(-1) + torch.einsum(
                "bhk,bhd->bhkd", ki, delta
            )
            outs.append(torch.einsum("bhkd,bhk->bhd", S, qi))

        y = torch.stack(outs, dim=2)                       # (B,H,T,Dv)
        y = y.transpose(1, 2).reshape(b, t, -1)
        return self.norm(x + self.out(y))


# --------------------------------------------------------------------------
# Sliding-window attention
# --------------------------------------------------------------------------


class SlidingWindowAttention(nn.Module):
    """Exact attention over the recent window. Causal, always.

    The mask is built to be strictly lower-triangular within the window.
    A packet is a point-in-time object; if this layer could see forward
    even one step, the leakage protection upstream would be decorative.
    """

    def __init__(self, cfg: TrunkConfig):
        super().__init__()
        self.h = cfg.n_heads
        self.dh = cfg.d_model // cfg.n_heads
        self.w = cfg.window
        self.qkv = nn.Linear(cfg.d_model, 3 * cfg.d_model, bias=False)
        self.out = nn.Linear(cfg.d_model, cfg.d_model, bias=False)
        self.norm = nn.LayerNorm(cfg.d_model)

    def _mask(self, t: int, device) -> torch.Tensor:
        idx = torch.arange(t, device=device)
        dist = idx[:, None] - idx[None, :]
        return (dist >= 0) & (dist < self.w)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, d = x.shape
        q, k, v = self.qkv(x).chunk(3, dim=-1)
        shape = lambda z: z.view(b, t, self.h, self.dh).transpose(1, 2)
        q, k, v = shape(q), shape(k), shape(v)
        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.dh)
        att = att.masked_fill(~self._mask(t, x.device), float("-inf"))
        y = (att.softmax(dim=-1) @ v).transpose(1, 2).reshape(b, t, d)
        return self.norm(x + self.out(y))


# --------------------------------------------------------------------------
# Temporal graph branch
# --------------------------------------------------------------------------


class TemporalGraphBranch(nn.Module):
    """Order ancestry, venues, instruments.

    One round of masked message passing per layer. Kept small on purpose:
    the graph is here to carry structure the sequence view loses, not to
    become a second model.
    """

    def __init__(self, cfg: TrunkConfig):
        super().__init__()
        d = cfg.d_model
        self.venue = nn.Embedding(cfg.n_venues, d)
        self.instrument = nn.Embedding(cfg.n_instruments, d)
        self.msg = nn.Linear(2 * d, d)
        self.norm = nn.LayerNorm(d)

    def forward(
        self,
        x: torch.Tensor,
        venue_id: torch.Tensor,       # (B,T) long
        instrument_id: torch.Tensor,  # (B,T) long
        parent: torch.Tensor,         # (B,T) long, -1 for root
    ) -> torch.Tensor:
        h = x + self.venue(venue_id) + self.instrument(instrument_id)
        b, t, d = h.shape
        idx = parent.clamp(min=0)
        gathered = torch.gather(h, 1, idx.unsqueeze(-1).expand(b, t, d))
        gathered = gathered * (parent >= 0).unsqueeze(-1).to(h.dtype)
        return self.norm(x + self.msg(torch.cat([h, gathered], dim=-1)))


# --------------------------------------------------------------------------
# Typed heads
# --------------------------------------------------------------------------


class TypedHeads(nn.Module):
    """Emits exactly the fields the decision contract expects.

    Bounds are enforced here by construction (sigmoid, tanh, softplus)
    rather than left to the validator. The validator still checks --
    two independent guarantees, because a head that learns to saturate
    is a different bug from a head that emits NaN.
    """

    def __init__(self, cfg: TrunkConfig):
        super().__init__()
        d = cfg.d_model
        self.p_up = nn.Linear(d, 1)
        self.size = nn.Linear(d, 1)
        self.regime = nn.Linear(d, cfg.n_regimes)
        self.contradiction = nn.Linear(d, 1)
        self.sigma = nn.Linear(d, 1)
        self.evidence = nn.Linear(d, 1)  # per-step relevance score

    def forward(self, h: torch.Tensor) -> dict[str, torch.Tensor]:
        pooled = h[:, -1]  # decision is made at the packet's as_of step
        return {
            "p_up": torch.sigmoid(self.p_up(pooled)).squeeze(-1),
            "size": torch.tanh(self.size(pooled)).squeeze(-1),
            "regime_logits": self.regime(pooled),
            "contradiction": torch.sigmoid(self.contradiction(pooled)).squeeze(-1),
            "sigma": F.softplus(self.sigma(pooled)).squeeze(-1),
            "evidence_scores": self.evidence(h).squeeze(-1),
        }


# --------------------------------------------------------------------------
# Trunk
# --------------------------------------------------------------------------


class Trunk(nn.Module):
    def __init__(self, cfg: TrunkConfig):
        super().__init__()
        self.cfg = cfg
        self.encoder = FieldEncoder(cfg)
        self.graph = TemporalGraphBranch(cfg)
        self.attn = nn.ModuleList(
            [SlidingWindowAttention(cfg) for _ in range(cfg.n_layers)]
        )
        self.mem = nn.ModuleList(
            [GatedDeltaCell(cfg) for _ in range(cfg.n_layers)]
            if cfg.use_delta_memory
            else []
        )
        self.ff = nn.ModuleList(
            [
                nn.Sequential(
                    nn.LayerNorm(cfg.d_model),
                    nn.Linear(cfg.d_model, cfg.d_ff_mult * cfg.d_model),
                    nn.GELU(),
                    nn.Linear(cfg.d_ff_mult * cfg.d_model, cfg.d_model),
                )
                for _ in range(cfg.n_layers)
            ]
        )
        self.heads = TypedHeads(cfg)

    def represent(
        self,
        numeric: torch.Tensor,
        categorical: torch.Tensor,
        venue_id: torch.Tensor,
        instrument_id: torch.Tensor,
        parent: torch.Tensor,
        qsv: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Hidden states. Exposed separately so teacher supervision can
        attach to intermediate representations without the heads."""
        h = self.encoder(numeric, categorical, qsv)
        h = self.graph(h, venue_id, instrument_id, parent)
        for i, attn in enumerate(self.attn):
            h = attn(h)
            if self.mem:
                h = self.mem[i](h)
            h = h + self.ff[i](h)
        return h

    def forward(self, *args, **kw) -> dict[str, torch.Tensor]:
        return self.heads(self.represent(*args, **kw))
