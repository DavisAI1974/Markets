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
from .coupling import discover_coupling, dipole_window_probe
from .level2_coupling import discover_level2_balance_links
from .research_holds import (
    ResearchHoldRegistry, preserve_geometric_holds,
    preserve_geometric_predictive_controls,
    preserve_full_raw_five_step_holds, preserve_full_raw_level2_holds)


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


def _archive_originals(raw_frames, bins, registry, archive_prefix, *, max_frames):
    """Shared admission: validate the contract, archive raw then derived, return both."""
    raw=tuple(raw_frames)
    if (not archive_prefix or not isinstance(bins,FixedBins) or
        bins.source_identity!=registry.source_identity or
        bins.identity()!=registry.contract_identity or
        not raw or type(max_frames) is not int or max_frames<2 or
        any(not isinstance(r,RawFrame) or
            r.source_identity!=registry.source_identity for r in raw)):
        raise LocalityError("complete source-bound raw input and bounded review policy required")
    original_name=archive_prefix+"-unmodified-raw"
    if len(raw)>max_frames:
        raw_digest=registry.archive_partitioned(original_name,raw)["manifest_digest"]
    else:
        raw_digest=registry.archive(original_name,raw)
    information=tuple(derive_information(r,bins) for r in raw)
    info_name=archive_prefix+"-derived-information"
    if len(raw)>max_frames:
        info_digest=registry.archive_partitioned(info_name,information)["manifest_digest"]
    else:
        info_digest=registry.archive(info_name,information)
    return raw,information,original_name,raw_digest,info_name,info_digest


def _hold_factory(registry, original_name, raw_digest, info_digest, holds, *, extra):
    def hold(issue: str, *, detail: dict) -> str:
        case_id=_digest({"original_raw_archive":raw_digest,
                         "information_archive":info_digest,
                         "reason":issue,**extra})
        registry.hold(case_id,original_name,reason=issue,
                      details={"original_raw_archive_digest":raw_digest,
                               "derived_archive_digest":info_digest,
                               "disposition":"RETAIN_FOR_FURTHER_INSPECTION",
                               **detail})
        holds.append(case_id)
        return case_id
    return hold


def _review_frames_hold(information, hold):
    bad=tuple({"clock":f.clock,"raw_identity":f.raw_identity,"status":f.status,
               "reasons":f.review_reasons} for f in information if f.status!="READY")
    if bad:
        hold("INFORMATION_UNVERIFIED_INPUT_NO_FIT",detail={"review_clock_reasons":bad})
    return bool(bad)


def archive_first_five_step_review(raw_frames: Sequence[RawFrame], bins: FixedBins,
                                   registry: ResearchHoldRegistry, *,
                                   archive_prefix: str, max_frames: int=12000,
                                   min_gain: float=0.15, null_margin: float=0.08,
                                   max_nodes: int=12) -> dict:
    """PG-1: archive originals, THEN run the five-step probe; every refusal is a hold.

    `discover_coupling` raises on non-READY frames, schema changes, duplicate
    evidence ids across frames, non-monotone clocks, too few frames or too many
    nodes. Each of those is now a retained research case on an already
    archived raw series instead of an exception on nothing.
    """
    raw,information,original_name,raw_digest,info_name,info_digest=_archive_originals(
        raw_frames,bins,registry,archive_prefix,max_frames=max_frames)
    holds=[]
    hold=_hold_factory(registry,original_name,raw_digest,info_digest,holds,
                       extra={"kind":"FIVE_STEP"})
    report=None
    receipt=None
    if not _review_frames_hold(information,hold):
        try:
            report=discover_coupling(information,min_gain=min_gain,
                                     null_margin=null_margin,max_nodes=max_nodes)
            receipt=preserve_full_raw_five_step_holds(
                report,information,raw,bins,registry,
                archive_name=archive_prefix+"-five-step")
            holds.extend(receipt["research_case_ids"])
        except (LocalityError,ArithmeticError,OverflowError) as exc:
            hold("FIVE_STEP_UNVERIFIED_NO_VALID_FIT",
                 detail={"reason":f"{type(exc).__name__}: {exc}",
                         "full_raw_count":len(raw)})
    if not holds:
        hold("FIVE_STEP_AWAITING_INDEPENDENT_SCIENTIFIC_VERIFICATION",
             detail={"source":"all-original-raw-and-derived-values-retained"})
    return {"schema":1,"kind":"OFFLINE_ARCHIVE_FIRST_FIVE_STEP_REVIEW",
            "trust":"ALL_RESULTS_RESEARCH_ONLY_NO_INDEPENDENT_SCIENTIFIC_ACCEPTANCE",
            "status":"RETAINED_FOR_FURTHER_INSPECTION",
            "source_identity":registry.source_identity,
            "calibration_identity":registry.contract_identity,
            "original_raw_frames":len(raw),"retained_information_frames":len(information),
            "original_raw_archive_name":original_name,"original_raw_archive_digest":raw_digest,
            "derived_information_archive_name":info_name,
            "derived_information_archive_digest":info_digest,
            "report":report,"archive_receipt":receipt,
            "research_case_ids":tuple(holds),
            "original_frames_dropped":0,"averaged_or_smoothed_original_values":False,
            "scientific_jobs_eliminated":0}


def archive_first_level2_review(raw_frames: Sequence[RawFrame], bins: FixedBins,
                                registry: ResearchHoldRegistry, *,
                                archive_prefix: str, max_frames: int=12000,
                                window: int=40, stride: int=4, max_nodes: int=12,
                                min_gain: float=0.15, null_margin: float=0.08,
                                max_channels: int=36, max_windows: int=12000) -> dict:
    """PG-1: archive originals, then Level 1 windows, then Level 2 links; holds on refusal."""
    raw,information,original_name,raw_digest,info_name,info_digest=_archive_originals(
        raw_frames,bins,registry,archive_prefix,max_frames=max_frames)
    holds=[]
    hold=_hold_factory(registry,original_name,raw_digest,info_digest,holds,
                       extra={"kind":"LEVEL2","window":window,"stride":stride})
    windows=None
    report=None
    receipt=None
    if not _review_frames_hold(information,hold):
        try:
            windows=dipole_window_probe(information,window=window,stride=stride,
                                        max_nodes=max_nodes)
            registry.archive(archive_prefix+"-level1-windows",windows)
        except (LocalityError,ArithmeticError,OverflowError) as exc:
            hold("LEVEL1_WINDOWS_UNVERIFIED_NO_VALID_FIT",
                 detail={"reason":f"{type(exc).__name__}: {exc}","full_raw_count":len(raw)})
        if windows is not None:
            try:
                report=discover_level2_balance_links(
                    windows,source_identity=registry.source_identity,
                    calibration_identity=registry.contract_identity,
                    min_gain=min_gain,null_margin=null_margin,
                    max_channels=max_channels,max_windows=max_windows)
                receipt=preserve_full_raw_level2_holds(
                    report,information,raw,bins,registry,
                    archive_name=archive_prefix+"-level2")
                holds.extend(receipt["research_case_ids"])
            except (LocalityError,ArithmeticError,OverflowError) as exc:
                hold("LEVEL2_UNVERIFIED_NO_VALID_FIT",
                     detail={"reason":f"{type(exc).__name__}: {exc}",
                             "level1_window_count":len(windows)})
    if not holds:
        hold("LEVEL2_AWAITING_INDEPENDENT_SCIENTIFIC_VERIFICATION",
             detail={"source":"all-original-raw-and-derived-values-retained"})
    return {"schema":1,"kind":"OFFLINE_ARCHIVE_FIRST_LEVEL2_REVIEW",
            "trust":"ALL_RESULTS_RESEARCH_ONLY_NO_INDEPENDENT_SCIENTIFIC_ACCEPTANCE",
            "status":"RETAINED_FOR_FURTHER_INSPECTION",
            "source_identity":registry.source_identity,
            "calibration_identity":registry.contract_identity,
            "original_raw_frames":len(raw),"retained_information_frames":len(information),
            "original_raw_archive_name":original_name,"original_raw_archive_digest":raw_digest,
            "derived_information_archive_name":info_name,
            "derived_information_archive_digest":info_digest,
            "level1_windows":windows,"report":report,"archive_receipt":receipt,
            "research_case_ids":tuple(holds),
            "original_frames_dropped":0,"averaged_or_smoothed_original_values":False,
            "scientific_jobs_eliminated":0}
