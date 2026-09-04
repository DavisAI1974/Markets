"""
OD/QSV dipole geometry as a teacher representation.

This is the novel claim in the stack and the only part of it that is not
adoption of someone else's result. Brain-guided NARF showed that
supervising intermediate representations can add reasoning gains beyond
label training. Replacing fMRI with market-operator geometry is a
hypothesis, not an established finding.

So the harness is built so that the hypothesis CANNOT be reported alone.
run_experiment() raises unless every control arm has been executed, and
it raises again unless every control arm is PROVEN to be what it claims
to be on the first real batch (see verify_controls). This is not
ceremony -- an auxiliary loss almost always moves validation metrics a
little, and without valid controls you cannot distinguish "dipole
geometry carries real structure" from "any auxiliary regression target
regularizes this trunk."

Arms
----
    none        no auxiliary loss at all. The floor.
    plain_aux   auxiliary head predicting a random-but-FIXED linear
                projection of the model's NUMERIC INPUTS. Controls for
                "extra learnable gradient signal helps". Built by
                PlainAuxProjection, which never receives the dipole
                tensor, so it cannot leak it.
    shuffled    real dipole targets, DERANGED across the batch (no row
                keeps its own target). Destroys the input-target
                correspondence, keeps the marginal distribution exactly.
                The strongest control.
    random      targets resampled from noise each step. Controls for
                "any dense target helps".
    dipole      the hypothesis.

Production targets arrive as dipole_target.DipoleTarget (schema, provenance,
causal receipt, per-entry state). to_batch_fields() yields the "dipole" and
"dipole_mask" keys the runner consumes; the auxiliary loss is masked to
PRESENT entries and coverage is reported per arm.

The claim survives only if dipole beats ALL FOUR, and beats the best
control by more than the spread among the controls themselves. A KILL
here is a clean negative and belongs in MASTER_DISCOVERIES with the
others.

Defect history (kept on purpose)
--------------------------------
2026-09-04. The original plain_aux computed
    dipole @ W * 0.0 + dipole.mean(dim=1).expand_as(dipole)
and make_targets() never received the inputs at all, so the documented
"projection of the inputs" was impossible from day one. The surviving
term was the per-sequence time-mean of the REAL dipole target, i.e. the
control leaked the target's DC component. The original shuffled arm used
torch.randperm, which can return the identity permutation. Both are
pinned by tests/test_teacher_controls.py. The rule this file now follows
is the same one odcore/leakage.py enforces upstream: a control's
independence from the target is asserted in code, not in a docstring.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Callable, Literal, Mapping, NamedTuple

import torch
import torch.nn as nn
import torch.nn.functional as F

try:  # Package import in Markets.
    from .dipole_target import masked_mse, validate_mask
except ImportError:  # Direct execution with this directory on PYTHONPATH.
    from dipole_target import masked_mse, validate_mask

__all__ = [
    "ARMS",
    "Arm",
    "ArmResult",
    "ExperimentReport",
    "PlainAuxProjection",
    "TeacherHead",
    "Targets",
    "derangement",
    "make_targets",
    "run_experiment",
    "verify_controls",
]

Arm = Literal["none", "plain_aux", "shuffled", "random", "dipole"]
ARMS: tuple[str, ...] = ("none", "plain_aux", "shuffled", "random", "dipole")
CONTROL_ARMS: tuple[str, ...] = ("plain_aux", "shuffled", "random")


class TeacherHead(nn.Module):
    """Projects trunk hidden states into the teacher representation space."""

    def __init__(self, d_model: int, teacher_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Linear(d_model, teacher_dim),
        )

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        return self.net(h)


# ------------------------------------------------------------ controls


class PlainAuxProjection:
    """Fixed random linear map from the NUMERIC INPUTS to teacher space.

    Constructed from (n_numeric, teacher_dim, seed) only. It has no code
    path that accepts the dipole tensor, which is the structural guarantee
    that this control cannot leak the target. Scaled by 1/sqrt(n_numeric)
    so target variance tracks input variance rather than growing with
    width. Weights are generated on CPU for device-independent determinism
    and moved to the input's device at call time.
    """

    def __init__(self, n_numeric: int, teacher_dim: int, seed: int = 0):
        if n_numeric < 1 or teacher_dim < 1:
            raise ValueError("PlainAuxProjection needs positive widths")
        g = torch.Generator(device="cpu").manual_seed(seed)
        self.n_numeric = n_numeric
        self.teacher_dim = teacher_dim
        self.seed = seed
        self.weight = torch.randn(n_numeric, teacher_dim, generator=g) / math.sqrt(
            n_numeric
        )

    def __call__(self, numeric: torch.Tensor) -> torch.Tensor:
        if numeric.shape[-1] != self.n_numeric:
            raise ValueError(
                f"numeric width {numeric.shape[-1]} != projection n_numeric "
                f"{self.n_numeric}"
            )
        w = self.weight.to(device=numeric.device, dtype=numeric.dtype)
        return numeric.detach() @ w


def derangement(n: int, generator: torch.Generator) -> torch.Tensor:
    """Permutation of range(n) with NO fixed points (Sattolo's algorithm).

    Sattolo produces a uniformly random single n-cycle, so perm[i] != i for
    every i by construction. Generated on CPU regardless of where the data
    lives, so the same seed gives the same permutation on CPU and GPU.
    """
    if n < 2:
        raise ValueError(
            f"shuffled control cannot destroy correspondence in a batch of "
            f"{n}; need batch size >= 2"
        )
    perm = list(range(n))
    for i in range(n - 1, 0, -1):
        j = int(torch.randint(0, i, (1,), generator=generator))  # j in [0, i-1]
        perm[i], perm[j] = perm[j], perm[i]
    out = torch.tensor(perm, dtype=torch.long)
    if bool((out == torch.arange(n)).any()):  # cannot happen; kept as a tripwire
        raise RuntimeError("derangement produced a fixed point")
    return out


class Targets(NamedTuple):
    values: torch.Tensor   # (B, T, K)
    mask: torch.Tensor     # (B, T, K), 1.0 where the auxiliary loss applies


def make_targets(
    arm: str,
    *,
    numeric: torch.Tensor,
    dipole: torch.Tensor,
    generator: torch.Generator,
    plain_aux: PlainAuxProjection,
    dipole_mask: torch.Tensor | None = None,
) -> Targets | None:
    """Target construction per arm.

    numeric is (B, T, n_numeric); dipole is (B, T, K); dipole_mask is
    (B, T, K) from DipoleTarget.mask, or None for a synthetic run (treated
    as all-present). generator must be a CPU generator: all randomness is
    drawn on CPU and moved to dipole.device, the device-independence
    contract.

    Mask policy (see dipole_target.py): plain_aux, random and dipole share
    the real mask so the loss covers identical positions. shuffled derangs
    values and mask TOGETHER, preserving the joint marginal including
    missingness. run_experiment reports aux_coverage so the difference is
    visible.
    """
    if generator.device.type != "cpu":
        raise ValueError("make_targets requires a CPU generator for determinism")
    if dipole_mask is None:
        mask = torch.ones_like(dipole)
    else:
        if dipole_mask.shape != dipole.shape:
            raise ValueError(
                f"dipole_mask {tuple(dipole_mask.shape)} must match dipole "
                f"{tuple(dipole.shape)}"
            )
        mask = validate_mask(dipole_mask, "dipole_mask").to(
            device=dipole.device, dtype=dipole.dtype
        )
    if arm == "none":
        return None
    if arm == "dipole":
        return Targets(dipole, mask)
    if arm == "shuffled":
        perm = derangement(dipole.shape[0], generator).to(dipole.device)
        return Targets(dipole[perm], mask[perm])
    if arm == "random":
        noise = torch.randn(dipole.shape, generator=generator)
        return Targets(noise.to(device=dipole.device, dtype=dipole.dtype), mask)
    if arm == "plain_aux":
        target = plain_aux(numeric)
        if target.shape != dipole.shape:
            raise ValueError(
                f"plain_aux target shape {tuple(target.shape)} != dipole shape "
                f"{tuple(dipole.shape)}; teacher_dim mismatch"
            )
        return Targets(target, mask)
    raise ValueError(f"unknown arm {arm!r}")


def _clone_generator(g: torch.Generator) -> torch.Generator:
    c = torch.Generator(device="cpu")
    c.set_state(g.get_state())
    return c


def verify_controls(
    batch: Mapping[str, torch.Tensor],
    generator: torch.Generator,
    plain_aux: PlainAuxProjection,
) -> None:
    """Prove, on a real batch, that each control is what it claims to be.

    plain_aux  invariant to the dipole tensor; sensitive to the inputs.
    random     invariant to the dipole tensor's values.
    shuffled   no row keeps its own target; multiset of rows preserved.

    Raises RuntimeError on the first violation. run_experiment() calls this
    before any gradient step, so an invalid control cannot produce a
    result-bearing run. Uses cloned generators so it consumes no randomness
    from the training stream.
    """
    numeric, dipole = batch["numeric"], batch["dipole"]
    dmask = batch.get("dipole_mask")
    if numeric.shape[:-1] != dipole.shape[:-1]:
        raise RuntimeError("numeric and dipole disagree on (B, T)")
    if not torch.isfinite(dipole).all():
        raise RuntimeError("dipole target contains non-finite values")
    fake = torch.randn(dipole.shape, generator=_clone_generator(generator)).to(
        device=dipole.device, dtype=dipole.dtype
    )

    def mk(arm, *, dip, num=numeric):
        return make_targets(
            arm, numeric=num, dipole=dip, dipole_mask=dmask,
            generator=_clone_generator(generator), plain_aux=plain_aux,
        ).values

    # plain_aux: target-blind, input-sensitive.
    a = mk("plain_aux", dip=dipole)
    if not torch.equal(a, mk("plain_aux", dip=fake)):
        raise RuntimeError("plain_aux control depends on the dipole target (leak)")
    if torch.allclose(a, mk("plain_aux", dip=dipole, num=numeric + 1.0)):
        raise RuntimeError("plain_aux control is insensitive to the inputs")

    # random: target-blind.
    if not torch.equal(mk("random", dip=dipole), mk("random", dip=fake)):
        raise RuntimeError("random control depends on the dipole target's values")

    # shuffled: correspondence destroyed, marginals kept.
    s = mk("shuffled", dip=dipole)
    kept = [i for i in range(dipole.shape[0]) if torch.equal(s[i], dipole[i])]
    if dmask is not None:
        sm = make_targets(
            "shuffled", numeric=numeric, dipole=dipole, dipole_mask=dmask,
            generator=_clone_generator(generator), plain_aux=plain_aux,
        ).mask
        if not torch.equal(sm, dmask.to(sm)[derangement(dipole.shape[0], _clone_generator(generator)).to(sm.device)]):
            raise RuntimeError("shuffled control did not derange mask with values")
    if kept:
        raise RuntimeError(f"shuffled control kept rows {kept} in place")
    if not torch.equal(
        torch.sort(s.flatten(1), dim=0).values,
        torch.sort(dipole.flatten(1), dim=0).values,
    ):
        raise RuntimeError("shuffled control changed the marginal distribution")


# ------------------------------------------------------------- results


@dataclass
class ArmResult:
    arm: str
    task_loss: float
    aux_loss: float
    val_metric: float
    seed: int
    init_digest: str = ""   # sha256 of initial params; equal across arms per seed
    aux_coverage: float = 1.0  # fraction of (B,T,K) entries the aux loss covered


@dataclass
class ExperimentReport:
    results: list[ArmResult] = field(default_factory=list)

    def by_arm(self) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {a: [] for a in ARMS}
        for r in self.results:
            out[r.arm].append(r.val_metric)
        return out

    def verdict(self, margin: float = 0.0) -> tuple[bool, str]:
        """PASS only if dipole beats every control by more than the
        spread among the controls themselves."""
        agg = {
            a: (sum(v) / len(v)) for a, v in self.by_arm().items() if v
        }
        missing = [a for a in ARMS if a not in agg]
        if missing:
            raise RuntimeError(
                f"cannot render a verdict: control arms never ran: {missing}"
            )
        controls = {a: m for a, m in agg.items() if a != "dipole"}
        best_control = min(controls.values())      # lower val loss is better
        control_spread = max(controls.values()) - min(controls.values())
        gain = best_control - agg["dipole"]
        if gain <= 0:
            return False, (
                f"KILL: dipole {agg['dipole']:.5f} does not beat best control "
                f"{best_control:.5f}. Clean negative -- log it."
            )
        if gain <= max(margin, control_spread):
            return False, (
                f"KILL: dipole gain {gain:.5f} is within the control spread "
                f"{control_spread:.5f}. Indistinguishable from generic "
                f"auxiliary regularization."
            )
        return True, (
            f"dipole gain {gain:.5f} exceeds control spread {control_spread:.5f}. "
            f"Not proof -- grounds for a larger run."
        )


def _param_digest(*modules: nn.Module) -> str:
    h = hashlib.sha256()
    for m in modules:
        for name, p in sorted(m.state_dict().items()):
            h.update(name.encode())
            h.update(p.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def _represent_kwargs(b: Mapping[str, torch.Tensor], require_qsv_mask: bool) -> dict:
    qsv = b.get("qsv")
    qsv_mask = b.get("qsv_mask")
    if require_qsv_mask and qsv is not None and qsv_mask is None:
        raise ValueError(
            "batch carries qsv values without qsv_mask; present-zero, missing "
            "and ablated would be indistinguishable. Supply qsv_mask or pass "
            "require_qsv_mask=False for a synthetic smoke run."
        )
    return dict(qsv=qsv, qsv_mask=qsv_mask)


# ------------------------------------------------------------ harness


def run_experiment(
    build_model: Callable[[], nn.Module],
    build_teacher: Callable[[], TeacherHead],
    batches: list[Mapping[str, torch.Tensor]],
    val_batches: list[Mapping[str, torch.Tensor]],
    seeds: tuple[int, ...] = (0, 1, 2),
    aux_weight: float = 0.1,
    lr: float = 1e-3,
    arms: tuple[str, ...] = ARMS,
    plain_aux_seed: int = 0,
    require_qsv_mask: bool = True,
) -> ExperimentReport:
    """Runs every arm under every seed. Refuses partial runs. Refuses
    invalid controls. Proves paired initialization across arms.

    Multiple seeds are not optional either: a single-seed gain on a small
    trunk is noise with a story attached.
    """
    missing = set(ARMS) - set(arms)
    if missing:
        raise ValueError(
            f"refusing to run without controls {sorted(missing)}; "
            f"the hypothesis is not interpretable without them"
        )
    if not batches:
        raise ValueError("refusing to run with no training batches")

    first = batches[0]
    plain_aux = PlainAuxProjection(
        n_numeric=first["numeric"].shape[-1],
        teacher_dim=first["dipole"].shape[-1],
        seed=plain_aux_seed,
    )
    for b in batches:
        _represent_kwargs(b, require_qsv_mask)   # fail fast, before any step

    report = ExperimentReport()
    for arm in arms:
        for seed in seeds:
            torch.manual_seed(seed)
            gen = torch.Generator(device="cpu").manual_seed(seed + 9973)
            if arm in CONTROL_ARMS:
                verify_controls(first, gen, plain_aux)
            model = build_model()
            teacher = build_teacher()
            digest = _param_digest(model, teacher)
            params = list(model.parameters()) + list(teacher.parameters())
            opt = torch.optim.AdamW(params, lr=lr)

            model.train()
            last_task = last_aux = 0.0
            cov_sum = cov_n = 0.0
            for b in batches:
                opt.zero_grad()
                h = model.represent(
                    b["numeric"], b["categorical"], b["venue_id"],
                    b["instrument_id"], b["parent"],
                    **_represent_kwargs(b, require_qsv_mask),
                )
                out = model.heads(h)
                task = F.binary_cross_entropy(out["p_up"], b["label"])
                targets = make_targets(
                    arm, numeric=b["numeric"], dipole=b["dipole"],
                    dipole_mask=b.get("dipole_mask"),
                    generator=gen, plain_aux=plain_aux,
                )
                if targets is None:
                    aux = torch.zeros((), device=task.device)
                else:
                    aux = masked_mse(teacher(h), targets.values, targets.mask)
                    cov_sum += float(targets.mask.mean()); cov_n += 1
                (task + aux_weight * aux).backward()
                opt.step()
                last_task, last_aux = float(task.detach()), float(aux.detach())

            model.eval()
            with torch.no_grad():
                vals = []
                for b in val_batches:
                    out = model(
                        b["numeric"], b["categorical"], b["venue_id"],
                        b["instrument_id"], b["parent"],
                        **_represent_kwargs(b, require_qsv_mask),
                    )
                    vals.append(float(F.binary_cross_entropy(out["p_up"], b["label"])))
            report.results.append(
                ArmResult(
                    arm, last_task, last_aux, sum(vals) / len(vals), seed, digest,
                    aux_coverage=(cov_sum / cov_n) if cov_n else 1.0,
                )
            )

    # Paired-seed proof: every arm started from the same weights per seed.
    by_seed: dict[int, set[str]] = {}
    for r in report.results:
        by_seed.setdefault(r.seed, set()).add(r.init_digest)
    bad = {s: d for s, d in by_seed.items() if len(d) != 1}
    if bad:
        raise RuntimeError(
            f"arms did not share initialization for seeds {sorted(bad)}; "
            f"the comparison is not paired"
        )
    return report
