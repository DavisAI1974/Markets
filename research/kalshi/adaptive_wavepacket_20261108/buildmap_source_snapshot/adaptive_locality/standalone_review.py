"""Offline admission-and-archive entry point: persist raw evidence BEFORE fitting.

A blocked information frame, rank failure, nonfinite operator or insufficient
predictive support is a saved scientific RESEARCH_HOLD, not a discarded event.
No source data is shortened. No production or BuildMap runtime dependency.
The caller supplies complete already-validated RawFrames and frozen bins; data
rejected before RawMember/RawFrame creation must be archived by its importer.
"""
from __future__ import annotations

from typing import Sequence

from .core import LocalityError, _digest
from .information import RawFrame, FixedBins, derive_information
from .geometry_probe import geometric_dipole_probe
from .geometry_validation import geometric_predictive_controls
from .research_holds import (
    ResearchHoldRegistry, preserve_geometric_holds,
    preserve_geometric_predictive_controls)


def archive_first_geometric_review(raw_frames: Sequence[RawFrame],
                                   bins: FixedBins,
                                   registry: ResearchHoldRegistry,
                                   target: str, donor: str, *,
                                   archive_prefix: str,
                                   max_frames: int=12000) -> dict:
    """Archive originals, then run both bounded diagnostics when admissible.

    The raw archive is committed first. Every unavailable fit is explicitly
    linked to a research-hold case; a fit that succeeds can still return
    RESEARCH_HOLD. No laboratory condition authorizes science suppression.
    """
    raw=tuple(raw_frames)
    if (not archive_prefix or not isinstance(bins,FixedBins) or
        bins.source_identity!=registry.source_identity or
        bins.identity()!=registry.contract_identity or
        not raw or type(max_frames) is not int or max_frames<64 or
        any(not isinstance(r,RawFrame) or
            r.source_identity!=registry.source_identity for r in raw) or
        not target or not donor or target==donor):
        raise LocalityError("complete source-bound raw input and bounded review policy required")
    original_name=archive_prefix+"-unmodified-raw"
    raw_digest=registry.archive(original_name,raw)
    information=tuple(derive_information(r,bins) for r in raw)
    # The full information series, including REVIEW_REQUIRED frames, is also
    # archived before fit. This is NOT a fit gate that deletes observations.
    info_name=archive_prefix+"-derived-information"
    info_digest=registry.archive(info_name,information)
    holds=[]
    def hold(issue: str, *, detail: dict) -> str:
        case_id=_digest({"original_raw_archive":raw_digest,
                         "information_archive":info_digest,
                         "target":target,"donor":donor,"reason":issue})
        registry.hold(case_id,original_name,reason=issue,
                      details={"original_raw_archive_digest":raw_digest,
                               "derived_archive_digest":info_digest,
                               "disposition":"RETAIN_FOR_FURTHER_INSPECTION",
                               **detail})
        holds.append(case_id)
        return case_id

    static=None
    predicted=None
    static_receipt=None
    predictive_receipt=None
    if any(frame.status!="READY" for frame in information):
        hold("INFORMATION_UNVERIFIED_INPUT_NO_FIT",
             detail={"review_clock_reasons":tuple(
                 {"clock":frame.clock,"raw_identity":frame.raw_identity,
                  "status":frame.status,"reasons":frame.review_reasons}
                 for frame in information if frame.status!="READY")})
    else:
        try:
            static=geometric_dipole_probe(information,target,donor)
            static_receipt=preserve_geometric_holds(
                static,information,raw,bins,registry,
                archive_name=archive_prefix+"-static-geometry")
            holds.extend(static_receipt["research_case_ids"])
        except (LocalityError,ArithmeticError,OverflowError) as exc:
            hold("STATIC_GEOMETRY_UNVERIFIED_NO_VALID_FIT",
                 detail={"reason":str(exc),"full_raw_count":len(raw)})
        if len(raw)<64:
            hold("PREDICTIVE_GEOMETRY_INSUFFICIENT_CHRONOLOGICAL_SUPPORT",
                 detail={"full_raw_count":len(raw),"required_min_frames":64})
        elif len(raw)>max_frames:
            hold("PREDICTIVE_GEOMETRY_BOUNDED_CPU_BUDGET",
                 detail={"full_raw_count":len(raw),"max_frames":max_frames,
                         "next_action":"Explicit lossless source-bound partition for independent review"})
        else:
            try:
                predicted=geometric_predictive_controls(
                    information,target,donor,max_frames=max_frames)
                predictive_receipt=preserve_geometric_predictive_controls(
                    predicted,information,raw,bins,registry,
                    archive_name=archive_prefix+"-predictive-controls")
                holds.extend(predictive_receipt["research_case_ids"])
            except (LocalityError,ArithmeticError,OverflowError) as exc:
                hold("PREDICTIVE_GEOMETRY_UNVERIFIED_NO_VALID_FIT",
                     detail={"reason":str(exc),"full_raw_count":len(raw)})
    if len(holds)==0:
        # A fully fitted report with no alerts is still unverified science;
        # archive a research case, never auto-promote to causal acceptance.
        hold("GEOMETRY_AWAITING_INDEPENDENT_SCIENTIFIC_VERIFICATION",
             detail={"source":"all-original-raw-and-derived-values-retained"})
    return {
        "schema":1,"kind":"OFFLINE_ARCHIVE_FIRST_GEOMETRIC_REVIEW",
        "trust":"ALL_RESULTS_RESEARCH_ONLY_NO_INDEPENDENT_SCIENTIFIC_ACCEPTANCE",
        "status":"RETAINED_FOR_FURTHER_INSPECTION",
        "source_identity":registry.source_identity,
        "calibration_identity":registry.contract_identity,
        "target":target,"donor":donor,
        "original_raw_frames":len(raw),"retained_information_frames":len(information),
        "original_raw_archive_name":original_name,
        "original_raw_archive_digest":raw_digest,
        "derived_information_archive_name":info_name,
        "derived_information_archive_digest":info_digest,
        "static_report":static,"predictive_report":predicted,
        "static_archive_receipt":static_receipt,
        "predictive_archive_receipt":predictive_receipt,
        "research_case_ids":tuple(holds),
        "original_frames_dropped":0,
        "averaged_or_smoothed_original_values":False,
        "scientific_jobs_eliminated":0,
        "limitations":(
            "RawFrame constructor rejects invalid pre-admission data; importer must archive that original separately.",
            "SQLite is local evidence storage, not independently signed protection against hostile tampering.",
            "All successful fits remain unverified candidate relationships awaiting independent science.",
            "No real continuum geometry, Neumann boundary, causality, or job equivalence has been demonstrated.",
        ),
    }
