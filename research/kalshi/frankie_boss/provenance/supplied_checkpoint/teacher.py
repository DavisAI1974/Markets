"""
OD/QSV dipole geometry as a teacher representation.

This is the novel claim in the stack and the only part of it that is not
adoption of someone else's result. Brain-guided NARF showed that
supervising intermediate representations can add reasoning gains beyond
label training. Replacing fMRI with market-operator geometry is a
hypothesis, not an established finding.

So the harness is built so that the hypothesis CANNOT be reported alone.
run_experiment() raises unless every control arm has been executed. This
is not ceremony -- an auxiliary loss almost always moves validation
metrics a little, and without the controls you cannot distinguish
"dipole geometry carries real structure" from "any auxiliary regression
target regularizes this trunk."

Arms
----
    none        no auxiliary loss at all. The floor.
    plain_aux   auxiliary head predicting a random-but-FIXED projection
                of the inputs. Controls for "extra gradient signal helps".
    shuffled    real dipole targets, permuted across the batch. Destroys
                the input-target correspondence, keeps the marginal
                distribution exactly. The strongest control.
    random      targets resampled from noise each step. Controls for
                "any dense target helps".
    dipole      the hypothesis.

The claim survives only if dipole beats ALL FOUR, and beats shuffled by
more than the spread among the controls themselves. A KILL here is a
clean negative and belongs in MASTER_DISCOVERIES with the others.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping

import torch
import torch.nn as nn
import torch.nn.functional as F

__all__ = ["Arm", "TeacherHead", "ArmResult", "ExperimentReport", "run_experiment"]

ARMS = ("none", "plain_aux", "shuffled", "random", "dipole")


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


def make_targets(
    arm: str,
    dipole: torch.Tensor,
    generator: torch.Generator,
) -> torch.Tensor | None:
    """Target construction per arm. dipole is (B, T, teacher_dim)."""
    if arm == "none":
        return None
    if arm == "dipole":
        return dipole
    if arm == "shuffled":
        # Permute across batch: same marginals, destroyed correspondence.
        perm = torch.randperm(dipole.shape[0], generator=generator, device=dipole.device)
        return dipole[perm]
    if arm == "random":
        return torch.randn(dipole.shape, generator=generator, device=dipole.device)
    if arm == "plain_aux":
        # Fixed random linear readout of the dipole's own scale, so the
        # target is learnable-but-uninformative rather than noise.
        g = torch.Generator(device="cpu").manual_seed(0)
        w = torch.randn(dipole.shape[-1], dipole.shape[-1], generator=g)
        return dipole.detach() @ w.to(dipole.device) * 0.0 + dipole.mean(
            dim=1, keepdim=True
        ).expand_as(dipole)
    raise ValueError(f"unknown arm {arm!r}")


@dataclass
class ArmResult:
    arm: str
    task_loss: float
    aux_loss: float
    val_metric: float
    seed: int


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


def run_experiment(
    build_model: Callable[[], nn.Module],
    build_teacher: Callable[[], TeacherHead],
    batches: list[Mapping[str, torch.Tensor]],
    val_batches: list[Mapping[str, torch.Tensor]],
    seeds: tuple[int, ...] = (0, 1, 2),
    aux_weight: float = 0.1,
    lr: float = 1e-3,
    arms: tuple[str, ...] = ARMS,
) -> ExperimentReport:
    """Runs every arm under every seed. Refuses partial runs.

    Multiple seeds are not optional either: a single-seed gain on a small
    trunk is noise with a story attached.
    """
    missing = set(ARMS) - set(arms)
    if missing:
        raise ValueError(
            f"refusing to run without controls {sorted(missing)}; "
            f"the hypothesis is not interpretable without them"
        )

    report = ExperimentReport()
    for arm in arms:
        for seed in seeds:
            torch.manual_seed(seed)
            gen = torch.Generator().manual_seed(seed + 9973)
            model = build_model()
            teacher = build_teacher()
            params = list(model.parameters()) + list(teacher.parameters())
            opt = torch.optim.AdamW(params, lr=lr)

            model.train()
            last_task = last_aux = 0.0
            for b in batches:
                opt.zero_grad()
                h = model.represent(
                    b["numeric"], b["categorical"], b["venue_id"],
                    b["instrument_id"], b["parent"], b.get("qsv"),
                )
                out = model.heads(h)
                task = F.binary_cross_entropy(out["p_up"], b["label"])
                targets = make_targets(arm, b["dipole"], gen)
                if targets is None:
                    aux = torch.zeros((), device=task.device)
                else:
                    aux = F.mse_loss(teacher(h), targets)
                (task + aux_weight * aux).backward()
                opt.step()
                last_task, last_aux = float(task.detach()), float(aux.detach())

            model.eval()
            with torch.no_grad():
                vals = []
                for b in val_batches:
                    out = model(
                        b["numeric"], b["categorical"], b["venue_id"],
                        b["instrument_id"], b["parent"], b.get("qsv"),
                    )
                    vals.append(float(F.binary_cross_entropy(out["p_up"], b["label"])))
            report.results.append(
                ArmResult(arm, last_task, last_aux, sum(vals) / len(vals), seed)
            )
    return report
