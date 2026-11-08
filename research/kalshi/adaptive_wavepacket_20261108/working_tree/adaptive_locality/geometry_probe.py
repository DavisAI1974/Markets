"""Offline operator-geometry diagnostics from Basic_equations dipole research.

Two DISTINCT questions:
* The algebraic vector (-1,-1,+2)/sqrt(6) on (Ha^2,Hb^2,Ha*Hb)
  equals -(Ha-Hb)^2 / sqrt(6), an identity. Proximity to this
  null direction can occur in unconnected equal-entropy channels:
  it is NOT evidence of coupling.
* A static fitted curve Ha^2 = a + b*(Ha*Hb) + c*(Ha*Hb)^2
  may have descriptive, out-of-sample utility. It is not necessarily
  a causal law or a physical geometric boundary.

Every input frame, including rank defects and outliers, is retained
and marked for research. Never replace source events with this curve.
No Frankie, BuildMap runtime, network, Neumann or scientific job calls.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Sequence

from .core import LocalityError, _digest
from .information import InfoFrame, validate_series
from .coupling import _qr_fit, _predict_sse

LINEAR=("const","HaHb")
QUADRATIC=("const","HaHb","HaHb2")


@dataclass(frozen=True)
class GeometryPoint:
    clock: int
    raw_identity: str
    original_evidence_ids: tuple[str,...]
    ha: float
    hb: float
    ha_squared: float | None
    hb_squared: float | None
    ha_hb: float | None
    squared_entropy_difference: float | None
    quadratic_residual: float | None
    status: str
    reason: str
    residual_exceeds_tolerance: bool | None = None
    outside_frozen_support: bool | None = None
    frozen_support_x_excess: float | None = None
    frozen_support_y_excess: float | None = None


def _basis_condition_audit(training_rows: Sequence[tuple[float, ...]]) -> dict:
    """Independent 3-column design audit, not a physical geometry metric.

    Constant, x, x²: after centering x and x², the two-column
    correlation determines the standardized design singular spectrum.
    Report near-rank problems even when fitting conservatively abstains.
    No raw rows are removed.
    """
    n=len(training_rows)
    x=[row[1] for row in training_rows]
    z=[row[2] for row in training_rows]
    mx=math.fsum(x)/n
    mz=math.fsum(z)/n
    sx=math.sqrt(math.fsum((v-mx)**2 for v in x)/n)
    sz=math.sqrt(math.fsum((v-mz)**2 for v in z)/n)
    if not (math.isfinite(sx) and math.isfinite(sz)):
        return {"estimated_rank":None,"standardized_condition":None,
                "x_x2_correlation":None,"reason":"NONFINITE_FEATURE_SCALE"}
    if sx<=1e-12 or sz<=1e-12:
        return {"estimated_rank":1 if sx<=1e-12 and sz<=1e-12 else 2,
                "standardized_condition":None,"x_x2_correlation":None,
                "reason":"CONSTANT_OPERATOR_COLUMN"}
    rho=math.fsum((a-mx)*(b-mz) for a,b in zip(x,z))/(n*sx*sz)
    if not math.isfinite(rho):
        return {"estimated_rank":None,"standardized_condition":None,
                "x_x2_correlation":None,"reason":"NONFINITE_COLUMN_CORRELATION"}
    rho=max(-1.,min(1.,rho))
    small=max(0.,1.-abs(rho))
    # This is a condition estimate for the standardized design, NOT the
    # raw coefficients, source dynamics, or physical geometric space.
    condition=(math.sqrt((1.+abs(rho))/small) if small>1e-15 else None)
    rank=2 if small<=1e-12 else 3
    return {"estimated_rank":rank,"standardized_condition":condition,
            "x_x2_correlation":rho,
            "reason":"NEAR_DEPENDENT_QUADRATIC_BASIS" if rank<3
                     else "CONDITION_ESTIMATE_ONLY"}


def _finite_square(v: float) -> float | None:
    result=v*v
    return result if math.isfinite(result) else None


def geometric_dipole_probe(frames: Sequence[InfoFrame], target: str,
                           donor: str, *, tolerance:float=0.01,
                           min_gain:float=0.10) -> dict:
    """Conservative algebraic-space probe with chronological holdout.

    Outlier status is diagnostic only; no frame is removed from the result,
    the training fit, or later scientific calculations. No feature means,
    time averaging, source compression or equation-to-physical-law claim.
    """
    frames=tuple(frames)
    names=validate_series(frames,min_frames=24)
    if target==donor or target not in names or donor not in names:
        raise LocalityError("two distinct calibrated operator channels required")
    if not math.isfinite(tolerance) or tolerance<0 or not 0<min_gain<1:
        raise LocalityError("invalid geometry acceptance thresholds")
    n=len(frames)
    split=int(n*0.65)
    points=[]
    rows=[]
    issue_ids=[]
    for frame in frames:
        vals=dict(frame.entropy)
        a=float(vals[target])
        b=float(vals[donor])
        a2=_finite_square(a)
        b2=_finite_square(b)
        ab=a*b
        difference2=_finite_square(a-b)
        ok=(a2 is not None and b2 is not None and math.isfinite(ab)
            and difference2 is not None and math.isfinite(ab*ab))
        if not ok:
            issue_ids.append(frame.raw_identity)
        points.append(GeometryPoint(frame.clock,frame.raw_identity,
                                    frame.raw_evidence_ids,a,b,a2,b2,
                                    ab if math.isfinite(ab) else None,
                                    difference2,None,
                                    "READY_FOR_GEOMETRIC_RESEARCH" if ok else "RESEARCH_HOLD",
                                    "RAW_OBSERVABLE_OVERFLOW" if not ok else "ALL_ORIGINAL_VALUES_PRESERVED"))
        if ok:
            rows.append((1.,ab,ab*ab))
    evidence=_digest({"frames":[f.identity() for f in frames],
                      "target":target,"donor":donor})
    basis_audit=_basis_condition_audit(rows[:split]) if not issue_ids else None
    algebraic_degeneracy_flags=[]
    if not issue_ids:
        train_donor=[p.hb for p in points[:split]]
        donor_span=max(train_donor)-min(train_donor)
        donor_scale=max(1.,*(abs(v) for v in train_donor))
        if donor_span<=1e-12*donor_scale:
            algebraic_degeneracy_flags.append("CONSTANT_TRAIN_DONOR_HB")
        if all(p.ha==p.hb for p in points):
            algebraic_degeneracy_flags.append("EXACT_EQUAL_ENTROPY_HA_HB")
    fitted=None
    linear_sse=None
    quad_sse=None
    gain=None
    status="RESEARCH_HOLD"
    reason="RANK_OR_NUMERICAL_INVESTIGATION_REQUIRED"
    # Do not fit a subset if any original data are unsupported. Preserve
    # ALL records rather than silently dropping out-of-range or outlier points.
    if not issue_ids:
        try:
            linear=_qr_fit([r[:2] for r in rows[:split]],
                           [p.ha_squared for p in points[:split]],LINEAR)
            quadratic=_qr_fit(rows[:split],
                              [p.ha_squared for p in points[:split]],QUADRATIC)
            y=[p.ha_squared for p in points[split:]]
            linear_sse=_predict_sse(linear,[r[:2] for r in rows[split:]],y)
            quad_sse=_predict_sse(quadratic,rows[split:],y)
            if not math.isfinite(linear_sse) or not math.isfinite(quad_sse):
                raise LocalityError("nonfinite geometric holdout residual")
            if linear_sse<=1e-14:
                reason="LINEAR_BASELINE_ALREADY_EXPLAINS_HOLDOUT"
                status="RESEARCH_HOLD"
            else:
                gain=(linear_sse-quad_sse)/linear_sse
                status=("EXPLORATORY_ALGEBRAIC_PATTERN_ONLY" if gain>=min_gain
                        else "NO_ADDITIONAL_QUADRATIC_SUPPORT")
                reason="OPERATOR_SPACE_CURVE_NOT_PHYSICAL_CAUSAL_GEOMETRY"
            fitted=quadratic.coefficients
            coeff=[v for _,v in fitted]
            # Algebraically perfect points may still be outliers. Measure
            # BOTH equation residual and extrapolation far beyond frozen
            # training support. No point is removed from fitting or reporting.
            train_x=[r[1] for r in rows[:split]]
            train_y=[p.ha_squared for p in points[:split]]
            x_lo,x_hi=min(train_x),max(train_x)
            y_lo,y_hi=min(train_y),max(train_y)
            x_span=x_hi-x_lo
            y_span=y_hi-y_lo
            updated=[]
            for p,r in zip(points,rows):
                residual=p.ha_squared-math.fsum(a*b for a,b in zip(coeff,r))
                if not math.isfinite(residual):
                    raise LocalityError("nonfinite per-point geometric residual")
                # 3-range extension is a conservative synthetic diagnostic,
                # not an estimator of scientific statistical significance.
                # At constant/zero support span, review any actual departure.
                outside_x=(r[1] < x_lo-3*x_span or r[1] > x_hi+3*x_span)
                outside_y=(p.ha_squared < y_lo-3*y_span or
                           p.ha_squared > y_hi+3*y_span)
                outlier=abs(residual)>tolerance or outside_x or outside_y
                point_reason=("STATIC_CURVE_LARGE_RESIDUAL_RESEARCH" if abs(residual)>tolerance
                              else "OUTSIDE_TRAINING_SUPPORT_RESEARCH" if outside_x or outside_y
                              else "NOT_AN_EQUIVALENCE_OR_CALCULATION_DROP")
                updated.append(GeometryPoint(p.clock,p.raw_identity,
                    p.original_evidence_ids,p.ha,p.hb,p.ha_squared,
                    p.hb_squared,p.ha_hb,p.squared_entropy_difference,
                    residual,"RESEARCH_REVIEW_OUTLIER" if outlier else "RETAINED",
                    point_reason,
                residual_exceeds_tolerance=abs(residual)>tolerance,
                outside_frozen_support=outside_x or outside_y,
                frozen_support_x_excess=max(x_lo-r[1],0.,r[1]-x_hi),
                frozen_support_y_excess=max(y_lo-p.ha_squared,0.,p.ha_squared-y_hi)))
            points=updated
            # With Hb constant and nonzero, Ha²=(HaHb)²/Hb² by
            # algebra alone; a perfect holdout fit is NOT a discovery.
            if ("CONSTANT_TRAIN_DONOR_HB" in algebraic_degeneracy_flags
                and status!="RESEARCH_HOLD"):
                status="RESEARCH_HOLD"
                reason="CONSTANT_DONOR_QUADRATIC_IS_ALGEBRAIC_REPARAMETERIZATION"
            if (basis_audit and basis_audit["standardized_condition"] is not None
                and basis_audit["standardized_condition"]>1e6):
                status="RESEARCH_HOLD"
                reason="ILL_CONDITIONED_OPERATOR_BASIS_RESEARCH_HOLD"
        except (LocalityError,ArithmeticError,OverflowError) as error:
            status="RESEARCH_HOLD"
            reason="RANK_OR_NUMERICAL_INVESTIGATION_REQUIRED:"+str(error)
            # Never publish partial/invalid coefficients as science.
            fitted=None
            linear_sse=quad_sse=gain=None
    if issue_ids:
        reason="ONE_OR_MORE_ORIGINAL_OBSERVABLES_REQUIRE_NUMERICAL_REVIEW"
    source_ids=tuple(p.raw_identity for p in points)
    valid_identity_points=(p for p in points if
                           p.ha_squared is not None and p.hb_squared is not None
                           and p.ha_hb is not None and
                           p.squared_entropy_difference is not None)
    max_identity_roundoff=max((abs((-p.ha_squared-p.hb_squared+2*p.ha_hb)
                                  +p.squared_entropy_difference)
                               for p in valid_identity_points),default=None)
    if len(source_ids)!=n or source_ids!=tuple(f.raw_identity for f in frames):
        raise LocalityError("source frame conservation failure")
    return {"schema":1,"kind":"OFFLINE_GEOMETRIC_DIPOLE_DIAGNOSTIC",
        "source_identity":frames[0].source_identity,
        "calibration_identity":frames[0].calibration_identity,
        "target":target,"donor":donor,"evidence_identity":evidence,
        "trust":"UNSIGNED_OPERATOR_GEOMETRY_RESEARCH_ONLY",
        "status":status,"reason":reason,"train_frames":split,
        "test_frames":n-split,"linear_holdout_sse":linear_sse,
        "quadratic_holdout_sse":quad_sse,"quadratic_gain":gain,
        "quadratic_coefficients":fitted,
        "design_basis_audit":basis_audit,
        "algebraic_degeneracy_flags":tuple(algebraic_degeneracy_flags),
        "static_curve_is_not_a_forecast_of_future_entropy":True,
        "max_equal_entropy_identity_float_residual":max_identity_roundoff,
        "large_residual_point_count":sum(p.residual_exceeds_tolerance is True for p in points),
        "frozen_support_novelty_point_count":sum(p.outside_frozen_support is True for p in points),
        "points":tuple(points),"original_frame_count":n,
        "preserved_frame_identities":source_ids,
        "research_review_count":sum(p.status in ("RESEARCH_HOLD","RESEARCH_REVIEW_OUTLIER")
                                    for p in points),
        "squared_difference_identity":"-Ha^2-Hb^2+2HaHb == -(Ha-Hb)^2",
        "identity_is_algebra_not_coupling":True,
        "physical_boundary_condition_supported":False,
        "scientific_jobs_eliminated":0,"frames_dropped":0,
        "averaged_or_flattened_original_data":False,
        "limitations":(
            "The equal-entropy null direction is a universal algebraic identity and may arise in pure noise.",
            "A constant donor makes a quadratic curve exact by reparameterization; this is not a predictive interaction.",
            "The static curve can be estimator-, regime- and fit-dependent, even with high heldout R2.",
            "Each outlier/underidentified fit must be retained for scientific investigation.",
            "This does not establish continuum geometry, a Neumann PDE, or causality.",
        )}
