"""Discrete graph diffusion tests. Never assert continuum Neumann applicability."""
import math
from .core import LocalityError
from .graph_boundary import FluxDomain, conservative_step, stable_explicit_dt, total_mass


def checked_step(domain: FluxDomain, field: dict[str, float], dt: float,
                 outward_flux: dict[str, float] | None = None) -> dict[str, float]:
    limit = stable_explicit_dt(domain)
    if not math.isfinite(dt) or dt <= 0 or dt > limit:
        raise LocalityError("explicit graph step violates monotone stability limit")
    next_field = conservative_step(domain, field, dt, outward_flux)
    if any(not math.isfinite(v) for v in next_field.values()):
        raise LocalityError("non-finite graph state")
    expected = total_mass(domain, field) - dt * sum((outward_flux or {}).values())
    actual = total_mass(domain, next_field)
    if not math.isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-12):
        raise LocalityError("graph mass balance failure")
    return next_field


def graph_energy(domain: FluxDomain, field: dict[str, float]) -> float:
    if set(field) != set(domain.volumes) or any(not math.isfinite(x) for x in field.values()):
        raise LocalityError("invalid graph field")
    return 0.5 * sum(edge.conductance * (field[edge.a] - field[edge.b]) ** 2
                     for edge in domain.edges)
