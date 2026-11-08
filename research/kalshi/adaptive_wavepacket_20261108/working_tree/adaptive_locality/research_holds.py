"""Transactional offline research-hold journal: unresolved never means discarded.

Keep exact original serializable evidence in a content-verified archive, and
link each rank, outlier, missingness or control failure to that immutable
archive. The journal can mark investigated/resolved, but cannot delete,
replace, average, or erase original evidence.

No services, scheduling, scientific calculations, or production integration.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path
import json
import sqlite3
from typing import Sequence
from .core import LocalityError, _digest


def _plain(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(k): _plain(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [_plain(v) for v in value]
    return value


class ResearchHoldRegistry:
    def __init__(self, path: str | Path, *, source_identity: str,
                 contract_identity: str, max_archive_bytes: int=32*1024*1024):
        if not source_identity or not contract_identity or max_archive_bytes<1:
            raise LocalityError("source, contract, and bounded archive required")
        self.source_identity=source_identity
        self.contract_identity=contract_identity
        self.max_archive_bytes=max_archive_bytes
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(str(self.path),timeout=30,isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA busy_timeout=30000")
        # SQLite ignores PRAGMA foreign_keys changes while a transaction is
        # active. Enforce references *before* creating any archive/case.
        self.db.execute("PRAGMA foreign_keys=ON")
        with self._tx():
            self.db.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
            self.db.execute("""CREATE TABLE IF NOT EXISTS archives(
                archive_name TEXT PRIMARY KEY,sha256 TEXT NOT NULL,
                evidence_json TEXT NOT NULL
            )""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS cases(
                case_id TEXT PRIMARY KEY,archive_name TEXT NOT NULL,
                reason TEXT NOT NULL,detail_json TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN
                ('RESEARCH_HOLD','UNDER_REVIEW','RETAIN_SEPARATE','REVIEWED_NO_SUPPRESSION')),
                FOREIGN KEY(archive_name) REFERENCES archives(archive_name)
            )""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS changes(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,state TEXT NOT NULL,
                reviewer TEXT NOT NULL,reason TEXT NOT NULL,
                previous_hash TEXT NOT NULL,entry_hash TEXT NOT NULL
            )""")
            expected={"source":source_identity,"contract":contract_identity,"schema":"1"}
            existing=dict(self.db.execute("SELECT k,v FROM meta"))
            if existing and existing!=expected:
                raise LocalityError("research-hold source/contract mismatch")
            for k,v in expected.items():
                self.db.execute("INSERT OR IGNORE INTO meta VALUES (?,?)",(k,v))

    @contextmanager
    def _tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.close()

    def close(self):
        self.db.close()

    def archive(self, archive_name: str, evidence: Sequence[object]) -> str:
        if not archive_name or not evidence:
            raise LocalityError("archive name and complete original evidence required")
        raw={"source_identity":self.source_identity,
             "contract_identity":self.contract_identity,
             "records":[_plain(v) for v in evidence]}
        data=json.dumps(raw,sort_keys=True,separators=(",",":"),allow_nan=False)
        if len(data.encode())>self.max_archive_bytes:
            raise LocalityError("archive exceeds bounded local limit; repartition with separate manifests, never discard")
        digest=_digest(raw)
        with self._tx():
            row=self.db.execute("SELECT sha256 FROM archives WHERE archive_name=?",
                                (archive_name,)).fetchone()
            if row:
                if row[0]!=digest:
                    raise LocalityError("immutable original evidence conflict")
                return digest
            self.db.execute("INSERT INTO archives VALUES (?,?,?)",
                            (archive_name,digest,data))
        return digest

    def read_archive(self, archive_name: str) -> dict:
        row=self.db.execute("SELECT sha256,evidence_json FROM archives WHERE archive_name=?",
                            (archive_name,)).fetchone()
        if not row:
            raise LocalityError("unknown evidence archive")
        try:
            raw=json.loads(row[1])
        except ValueError as exc:
            raise LocalityError("torn evidence archive") from exc
        if raw.get("source_identity")!=self.source_identity or raw.get("contract_identity")!=self.contract_identity:
            raise LocalityError("research evidence source mismatch")
        if _digest(raw)!=row[0]:
            raise LocalityError("original research evidence digest mismatch")
        return raw

    def _append(self,case_id,state,reason,reviewer):
        parent=self.db.execute("SELECT entry_hash FROM changes ORDER BY seq DESC LIMIT 1").fetchone()
        previous=parent[0] if parent else "GENESIS"
        entry=_digest({"case":case_id,"state":state,"reason":reason,
                       "reviewer":reviewer,"previous":previous})
        self.db.execute("""INSERT INTO changes(case_id,state,reviewer,reason,
            previous_hash,entry_hash) VALUES (?,?,?,?,?,?)""",
                        (case_id,state,reviewer,reason,previous,entry))

    def hold(self, case_id: str, archive_name: str, *, reason: str,
             details: dict, reviewer: str="automatic-research-triage") -> str:
        if not case_id or not archive_name or not reason or not reviewer:
            raise LocalityError("complete research case metadata required")
        if not isinstance(details,dict):
            raise LocalityError("case details must be structured")
        text=json.dumps(_plain(details),sort_keys=True,separators=(",",":"),allow_nan=False)
        with self._tx():
            archive=self.db.execute("SELECT 1 FROM archives WHERE archive_name=?",
                                    (archive_name,)).fetchone()
            if not archive:
                raise LocalityError("missing original evidence archive")
            old=self.db.execute("""SELECT archive_name,reason,detail_json,state
                FROM cases WHERE case_id=?""",(case_id,)).fetchone()
            if old:
                if old[:3]!=(archive_name,reason,text):
                    raise LocalityError("conflicting immutable research case")
                return "ALREADY_RETAINED"
            self.db.execute("""INSERT INTO cases(case_id,archive_name,reason,detail_json,state)
                VALUES (?,?,?,?,'RESEARCH_HOLD')""",
                (case_id,archive_name,reason,text))
            self._append(case_id,"RESEARCH_HOLD",reason,reviewer)
        return "RETAINED_FOR_RESEARCH"

    def review(self, case_id: str, *, state: str, reason: str, reviewer: str) -> None:
        if state not in ("UNDER_REVIEW","RETAIN_SEPARATE","REVIEWED_NO_SUPPRESSION"):
            raise LocalityError("invalid non-destructive review state")
        if not reason or not reviewer:
            raise LocalityError("reason/reviewer required")
        with self._tx():
            row=self.db.execute("SELECT state FROM cases WHERE case_id=?",
                                (case_id,)).fetchone()
            if not row:
                raise LocalityError("unknown research hold")
            self.db.execute("UPDATE cases SET state=? WHERE case_id=?",(state,case_id))
            self._append(case_id,state,reason,reviewer)

    def get(self, case_id: str) -> dict:
        row=self.db.execute("SELECT archive_name,reason,detail_json,state FROM cases WHERE case_id=?",
                            (case_id,)).fetchone()
        if not row:
            raise LocalityError("unknown research case")
        original=self.read_archive(row[0])
        return {"case_id":case_id,"archive_name":row[0],"reason":row[1],
                "details":json.loads(row[2]),"state":row[3],
                "original_evidence":original,
                "scientific_jobs_eliminated":0}

    def verify(self) -> bool:
        """Verify archives, linked history, current states and referential links.

        Detects accidental or partial corruption, NOT independently signed,
        adversarial tamper resistance: database writers can rewrite hashes.
        """
        if self.db.execute("PRAGMA foreign_keys").fetchone()[0]!=1:
            raise LocalityError("research archive foreign-key enforcement disabled")
        if self.db.execute("PRAGMA foreign_key_check").fetchall():
            raise LocalityError("orphaned research evidence linkage")
        for archive, in self.db.execute("SELECT archive_name FROM archives"):
            self.read_archive(archive)
        cases={case:(archive,reason,state)
               for case,archive,reason,state in self.db.execute(
                   "SELECT case_id,archive_name,reason,state FROM cases")}
        last="GENESIS"
        historical={}
        for case,state,reviewer,reason,previous,digest in self.db.execute(
                "SELECT case_id,state,reviewer,reason,previous_hash,entry_hash FROM changes ORDER BY seq"):
            check=_digest({"case":case,"state":state,"reason":reason,
                           "reviewer":reviewer,"previous":last})
            if previous!=last or digest!=check:
                raise LocalityError("tampered research hold ledger")
            if case not in cases:
                raise LocalityError("review references missing research case")
            if case not in historical:
                if state!="RESEARCH_HOLD" or reason!=cases[case][1]:
                    raise LocalityError("case creation history or reason conflict")
            elif state=="RESEARCH_HOLD":
                raise LocalityError("unexpected recreation of research case")
            historical[case]=state
            last=digest
        if (set(historical)!=set(cases) or
            any(historical[case]!=cases[case][2] for case in cases)):
            raise LocalityError("case state diverges from immutable review history")
        return True

    def counts(self):
        states=dict(self.db.execute("SELECT state,COUNT(*) FROM cases GROUP BY state"))
        archive_count=self.db.execute("SELECT COUNT(*) FROM archives").fetchone()[0]
        return {"archives":archive_count,"cases":sum(states.values()),
                "states":states,"original_evidence_dropped":0,
                "scientific_jobs_eliminated":0}


def preserve_level2_holds(report: dict, registry: ResearchHoldRegistry,
                          *, archive_name: str) -> dict:
    """Persist EVERY Level 1 input once, then link each unresolved fit/issue."""
    if (report.get("source_identity")!=registry.source_identity or
        report.get("calibration_identity")!=registry.contract_identity or
        report.get("scientific_jobs_eliminated")!=0 or
        report.get("input_windows_dropped")!=0):
        raise LocalityError("incompatible or destructive Level 2 research report")
    original=report.get("retained_original_windows")
    if not isinstance(original,tuple) or len(original)!=report.get("original_window_count"):
        raise LocalityError("incomplete original window set")
    digest=registry.archive(archive_name,original)
    cases=[]
    for i,issue in enumerate(report["unresolved_research_items"]):
        case_id=_digest({"analysis":report["evidence_identity"],"issue_index":i,
                         "issue":issue})
        reason=issue["reason"]
        registry.hold(case_id,archive_name,reason=reason,
                      details={"issue":issue,"analysis":report["evidence_identity"],
                               "archive_digest":digest})
        cases.append(case_id)
    return {"archive_name":archive_name,"archive_digest":digest,
            "retained_windows":len(original),"research_case_ids":tuple(cases),
            "cases":len(cases),"scientific_jobs_eliminated":0}


def preserve_five_step_holds(report: dict, original_information_frames: Sequence[object],
                             registry: ResearchHoldRegistry, *,
                             archive_name: str) -> dict:
    """Archive the COMPLETE derived-information input including held fits.

    The upstream immutable RawFrames must additionally be archived by the
    caller if locally available; an InfoFrame only contains raw identities,
    not the original raw measurement values.
    """
    if (report.get("source_identity")!=registry.source_identity or
        report.get("calibration_identity")!=registry.contract_identity or
        report.get("scientific_jobs_eliminated")!=0):
        raise LocalityError("incompatible research report")
    frames=tuple(original_information_frames)
    if (len(frames)!=report.get("frames") or
        tuple(getattr(f,"raw_identity",None) for f in frames)!=
                tuple(report.get("raw_source_frame_identities",()))):
        raise LocalityError("not the exact original information series")
    digest=registry.archive(archive_name,frames)
    case_ids=[]
    for result in report.get("results",()):
        if not result.status.startswith("ABSTAIN"):
            continue
        case_id=_digest({"report":_digest(report.get("raw_source_frame_identities")),
                         "target":result.target,"donor":result.donor,
                         "status":result.status,"archive":digest})
        registry.hold(case_id,archive_name,reason=result.status,
                      details={"target":result.target,"donor":result.donor,
                               "source_frames":result.source_frames,
                               "calibration":registry.contract_identity,
                               "archive_digest":digest})
        case_ids.append(case_id)
    return {"retained_frames":len(frames),"archive_digest":digest,
            "research_case_ids":tuple(case_ids),
            "rank_and_abstention_cases":len(case_ids),
            "scientific_jobs_eliminated":0}


def preserve_geometric_holds(report: dict, information_frames: Sequence[object],
                             raw_frames: Sequence[object], bins: object,
                             registry: ResearchHoldRegistry, *,
                             archive_name: str) -> dict:
    """Preserve full upstream measurements, derived observables and geometry.

    Reject mismatched or missing raw data. Unlike archival of InfoFrames
    alone, this binds the exact ordered source RawFrames and frozen bins to
    independently re-derived information observables. No network, science
    suppression, or production connections are involved.
    """
    from .information import RawFrame, InfoFrame, FixedBins, derive_information
    if not isinstance(bins, FixedBins) or bins.identity()!=registry.contract_identity:
        raise LocalityError("missing or incompatible frozen calibration for raw evidence")
    frames=tuple(information_frames)
    raw=tuple(raw_frames)
    points=tuple(report.get("points",()))
    if (report.get("kind")!="OFFLINE_GEOMETRIC_DIPOLE_DIAGNOSTIC" or
        report.get("source_identity")!=registry.source_identity or
        report.get("calibration_identity")!=registry.contract_identity or
        bins.source_identity!=registry.source_identity or
        report.get("scientific_jobs_eliminated")!=0 or
        report.get("frames_dropped")!=0 or
        report.get("averaged_or_flattened_original_data") is not False or
        len(frames)!=len(raw) or len(frames)!=len(points) or
        len(frames)!=report.get("original_frame_count") or not frames):
        raise LocalityError("incomplete or destructive geometric source/report")
    evidence=_digest({"frames":[f.identity() for f in frames
                                if isinstance(f,InfoFrame)],
                      "target":report.get("target"),"donor":report.get("donor")})
    if evidence!=report.get("evidence_identity"):
        raise LocalityError("geometric report does not bind exact information values")
    if tuple(f.raw_identity for f in frames)!=tuple(report.get("preserved_frame_identities",())):
        raise LocalityError("information frame lineage mismatch")
    complete=[]
    for i,(f,r,p) in enumerate(zip(frames,raw,points)):
        if not isinstance(f,InfoFrame) or not isinstance(r,RawFrame):
            raise LocalityError("full original RawFrame and derived InfoFrame required")
        if r.source_identity!=registry.source_identity or f.source_identity!=registry.source_identity:
            raise LocalityError("original source identity mismatch")
        if f.clock!=r.clock or f.raw_identity!=r.identity():
            raise LocalityError("upstream RawFrame identity/clock mismatch")
        if f.raw_evidence_ids!=tuple(s.evidence_id for s in r.samples) or f.raw_count!=len(r.samples):
            raise LocalityError("original ordered measurement identities mismatch")
        if derive_information(r,bins)!=f:
            raise LocalityError("derived information inconsistent with frozen original measurements")
        if (p.clock!=f.clock or p.raw_identity!=f.raw_identity or
            p.original_evidence_ids!=f.raw_evidence_ids or
            p.ha!=dict(f.entropy).get(report["target"]) or
            p.hb!=dict(f.entropy).get(report["donor"])):
            raise LocalityError("geometric point does not bind same source measurement")
        complete.append({"index":i,"raw_frame":r,"information_frame":f,
                         "geometry_point":p})
    digest=registry.archive(archive_name,tuple(complete))
    case_ids=[]
    if report["status"]=="RESEARCH_HOLD":
        reason="GEOMETRY_GLOBAL:"+report["reason"]
        case_id=_digest({"geometry":evidence,"archive":digest,"reason":reason})
        registry.hold(case_id,archive_name,reason=reason,
                      details={"evidence":evidence,"archive_digest":digest,
                               "raw_frame_count":len(raw),
                               "design_basis_audit":report.get("design_basis_audit")})
        case_ids.append(case_id)
    for i,p in enumerate(points):
        if p.status not in ("RESEARCH_HOLD","RESEARCH_REVIEW_OUTLIER"):
            continue
        reason="GEOMETRY_POINT:"+p.reason
        case_id=_digest({"geometry":evidence,"archive":digest,"index":i,
                         "raw_identity":p.raw_identity,"reason":reason})
        registry.hold(case_id,archive_name,reason=reason,
                      details={"index":i,"clock":p.clock,
                               "raw_identity":p.raw_identity,"status":p.status,
                               "archive_digest":digest,
                               "residual":p.quadratic_residual,
                               "frozen_support_novelty":p.outside_frozen_support})
        case_ids.append(case_id)
    return {"archive_name":archive_name,"archive_digest":digest,
            "retained_full_raw_frames":len(raw),
            "retained_information_frames":len(frames),
            "retained_geometry_points":len(points),
            "research_case_ids":tuple(case_ids),"cases":len(case_ids),
            "original_measurements_dropped":0,"scientific_jobs_eliminated":0}


def preserve_rejected_geometric_inputs(raw_frames: Sequence[object],
                                       bins: object, registry: ResearchHoldRegistry,
                                       *, archive_name: str,
                                       reason: str) -> dict:
    """Retain inputs that could NOT safely enter the geometric fitting API.

    This creates a research case without pretending an invalid/missing
    information series was fitted; complete raw records remain inspectable.
    """
    from .information import RawFrame, FixedBins
    raw=tuple(raw_frames)
    if (not raw or not reason or
        not isinstance(bins,FixedBins) or
        bins.identity()!=registry.contract_identity or
        bins.source_identity!=registry.source_identity or
        any(not isinstance(r,RawFrame) or
            r.source_identity!=registry.source_identity for r in raw)):
        raise LocalityError("rejected geometry research requires exact raw source and frozen calibration")
    digest=registry.archive(archive_name,raw)
    case_id=_digest({"archive":digest,"reason":reason,"kind":"REJECTED_GEOMETRY_INPUT"})
    registry.hold(case_id,archive_name,reason="GEOMETRY_INPUT_REJECTED:"+reason,
                  details={"archive_digest":digest,"raw_frame_count":len(raw),
                           "calibration":bins.identity()})
    return {"archive_name":archive_name,"archive_digest":digest,
            "retained_full_raw_frames":len(raw),"research_case_ids":(case_id,),
            "original_measurements_dropped":0,"scientific_jobs_eliminated":0}


def preserve_geometric_predictive_controls(report: dict,
                                           information_frames: Sequence[object],
                                           raw_frames: Sequence[object],
                                           bins: object,
                                           registry: ResearchHoldRegistry, *,
                                           archive_name: str) -> dict:
    """Bind every negative, rank, positive or conflicting split to raw evidence.

    Archive one per-frame record (with original IDs/values/directions) and a
    report manifest. Every split gets a research case even when promising:
    this is an auditable observation, never a claim of causal equivalence.
    """
    from .information import RawFrame, InfoFrame, FixedBins, derive_information
    frames=tuple(information_frames)
    raw=tuple(raw_frames)
    splits=tuple(report.get("splits",()))
    if (report.get("kind")!="OFFLINE_GEOMETRY_PREDICTIVE_CONTROLS" or
        report.get("source_identity")!=registry.source_identity or
        report.get("calibration_identity")!=registry.contract_identity or
        not isinstance(bins,FixedBins) or
        bins.identity()!=registry.contract_identity or
        bins.source_identity!=registry.source_identity or
        report.get("scientific_jobs_eliminated")!=0 or
        report.get("frames_dropped")!=0 or
        report.get("raw_observations_averaged_or_smoothed") is not False or
        not frames or not splits or
        len(frames)!=len(raw) or
        len(frames)!=report.get("original_frame_count")):
        raise LocalityError("incompatible predictive controls or incomplete raw evidence")
    evidence=_digest({"frames":[f.identity() for f in frames
                                if isinstance(f,InfoFrame)],
                      "target":report.get("target"),"donor":report.get("donor")})
    if (evidence!=report.get("evidence_identity") or
        tuple(f.raw_identity for f in frames)!=tuple(report.get("preserved_frame_identities",()))):
        raise LocalityError("predictive control evidence identity mismatch")
    records=[]
    for i,(f,r) in enumerate(zip(frames,raw)):
        if not isinstance(f,InfoFrame) or not isinstance(r,RawFrame):
            raise LocalityError("full raw and derived information frames required")
        if (r.source_identity!=registry.source_identity or f.clock!=r.clock or
            f.raw_identity!=r.identity() or
            tuple(s.evidence_id for s in r.samples)!=f.raw_evidence_ids or
            derive_information(r,bins)!=f):
            raise LocalityError("predictive controls do not match upstream raw values")
        records.append({"kind":"RAW_AND_INFORMATION_FRAME","index":i,
                        "raw_frame":r,"information_frame":f})
    for split in splits:
        if (split.original_training_frame_identities!=
            tuple(f.raw_identity for f in frames
                  if split.train_cutoff_clock>f.clock and
                  f.clock>=frames[report["past_lag"]].clock)
            or split.original_testing_frame_identities!=
            tuple(f.raw_identity for f in frames
                  if f.clock>=split.train_cutoff_clock)):
            # Explicitly reject clipped/reordered or fabricated split lineage.
            raise LocalityError("predictive split provenance mismatch")
    records.append({"kind":"PREDICTIVE_CONTROL_REPORT","report":report})
    digest=registry.archive(archive_name,tuple(records))
    cases=[]
    for i,split in enumerate(splits):
        reason="GEOMETRY_PREDICTIVE_SPLIT:"+split.status
        case_id=_digest({"evidence":evidence,"archive":digest,"index":i,
                         "clock":split.train_cutoff_clock,"status":split.status})
        registry.hold(case_id,archive_name,reason=reason,
                      details={"index":i,"clock":split.train_cutoff_clock,
                               "rank_or_confound_reason":split.reason,
                               "archive_digest":digest,"source":evidence,
                               "geometry_gain":split.geometry_gain,
                               "past_donor_gain":split.past_donor_gain})
        cases.append(case_id)
    return {"archive_name":archive_name,"archive_digest":digest,
            "retained_full_raw_frames":len(raw),
            "retained_information_frames":len(frames),
            "retained_predictive_splits":len(splits),
            "research_case_ids":tuple(cases),"cases":len(cases),
            "scientific_jobs_eliminated":0,"original_measurements_dropped":0}



def _verify_complete_raw_information(raw_frames: Sequence[object],
                                     information_frames: Sequence[object],
                                     bins: object,
                                     registry: ResearchHoldRegistry) -> tuple:
    """Verify every exact original RawFrame against each reported InfoFrame."""
    from .information import RawFrame, InfoFrame, FixedBins, derive_information
    raw=tuple(raw_frames)
    info=tuple(information_frames)
    if (not isinstance(bins,FixedBins) or
        bins.source_identity!=registry.source_identity or
        bins.identity()!=registry.contract_identity or
        not info or len(raw)!=len(info)):
        raise LocalityError("full original RawFrame and calibration series required")
    complete=[]
    for index,(r,f) in enumerate(zip(raw,info)):
        if not isinstance(r,RawFrame) or not isinstance(f,InfoFrame):
            raise LocalityError("complete raw and derived frame identity required")
        if (r.source_identity!=registry.source_identity or
            f.source_identity!=registry.source_identity or
            f.calibration_identity!=registry.contract_identity or
            f.clock!=r.clock or f.raw_identity!=r.identity() or
            f.raw_count!=len(r.samples) or
            f.raw_evidence_ids!=tuple(sample.evidence_id for sample in r.samples) or
            f!=derive_information(r,bins)):
            raise LocalityError("original raw measurements do not reproduce information frame")
        complete.append({"index":index,"raw_frame":r,
                         "information_frame":f})
    return tuple(complete)


def preserve_full_raw_five_step_holds(report:dict,
                                     information_frames:Sequence[object],
                                     raw_frames:Sequence[object],
                                     bins:object,
                                     registry:ResearchHoldRegistry, *,
                                     archive_name:str) -> dict:
    """Archive all upstream RawFrames, ALL directional results, even 'no support'.

    This is the stronger, *full original source* companion to the legacy
    preserve_five_step_holds, which archived derived InfoFrames only. No fit
    status (including a candidate) can silently become scientific acceptance.
    """
    frames=tuple(information_frames)
    if (report.get("method")!="AGNOSTIC_FIVE_STEP_PROBE" or
        report.get("source_identity")!=registry.source_identity or
        report.get("calibration_identity")!=registry.contract_identity or
        report.get("scientific_jobs_eliminated")!=0 or
        len(frames)!=report.get("frames") or
        report.get("result_count")!=len(report.get("results",())) or
        tuple(f.raw_identity for f in frames)!=
            tuple(report.get("raw_source_frame_identities",())) or
        report.get("evidence_identity")!=_digest({
            "frames":[f.identity() for f in frames],
            "method":"AGNOSTIC_FIVE_STEP_PROBE"})):
        raise LocalityError("five-step report is not bound to the exact information series")
    complete=_verify_complete_raw_information(raw_frames,frames,bins,registry)
    original_ids=tuple(f.raw_identity for f in frames)
    lineage_issues=[]
    for index,result in enumerate(report["results"]):
        if result.scientific_jobs_eliminated!=0:
            raise LocalityError("directional five-step job suppression prohibited")
        if result.target==result.donor or tuple(result.source_frames)!=original_ids:
            lineage_issues.append(index)
    records=complete+({"kind":"COMPLETE_FIVE_STEP_REPORT","report":report,
                       "unverified_result_lineage_indices":tuple(lineage_issues)},)
    digest=registry.archive(archive_name,records)
    cases=[]
    for index,result in enumerate(report["results"]):
        reason=("FIVE_STEP_SOURCE_LINEAGE_CONFLICT:" if index in lineage_issues
                else "FIVE_STEP_UNVERIFIED_RESULT:")+result.status
        case_id=_digest({"analysis":report["evidence_identity"],
                         "archive":digest,"index":index,
                         "target":result.target,"donor":result.donor})
        registry.hold(case_id,archive_name,reason=reason,
                      details={"result_index":index,"status":result.status,
                               "direction":(result.target,result.donor),
                               "lineage_conflict":index in lineage_issues,
                               "archive_digest":digest,
                               "disposition":"RETAIN_FOR_FURTHER_INSPECTION"})
        cases.append(case_id)
    return {"archive_name":archive_name,"archive_digest":digest,
            "retained_full_raw_frames":len(complete),
            "retained_five_step_results":len(report["results"]),
            "unverified_lineage_conflict_count":len(lineage_issues),
            "research_case_ids":tuple(cases),"cases":len(cases),
            "original_observations_dropped":0,"scientific_jobs_eliminated":0}


def preserve_full_raw_level2_holds(report:dict,
                                  information_frames:Sequence[object],
                                  raw_frames:Sequence[object],
                                  bins:object,
                                  registry:ResearchHoldRegistry, *,
                                  archive_name:str) -> dict:
    """Bind Level 2 pair-window/link archive to every original raw measurement.

    Every observed and unverified link, conflicting clock, issue, and the
    exact full input history is saved, including windows that cannot be fit.
    """
    from dataclasses import asdict
    frames=tuple(information_frames)
    original=tuple(report.get("retained_original_windows",()))
    if (report.get("kind")!="OFFLINE_LEVEL2_UNSMOOTHED_BALANCE_LINKS" or
        report.get("source_identity")!=registry.source_identity or
        report.get("calibration_identity")!=registry.contract_identity or
        report.get("scientific_jobs_eliminated")!=0 or
        report.get("input_windows_dropped")!=0 or
        report.get("rank_deficiencies_dropped")!=0 or
        not original or len(original)!=report.get("original_window_count") or
        len(report.get("links",()))!=report.get("tested_link_count") or
        len(report.get("unresolved_research_items",()))!=report.get("unresolved_count") or
        report.get("evidence_identity")!=_digest({
            "source":registry.source_identity,
            "calibration":registry.contract_identity,
            "windows":[asdict(w) for w in original]})):
        raise LocalityError("Level 2 report does not bind complete original windows")
    complete=_verify_complete_raw_information(raw_frames,frames,bins,registry)
    frame_ids=tuple(f.raw_identity for f in frames)
    starts={identity:index for index,identity in enumerate(frame_ids)}
    lineage_issues=[]
    for index,window in enumerate(original):
        ids=tuple(window.source_frames)
        if window.scientific_jobs_eliminated!=0:
            raise LocalityError("Level 2 scientific job suppression prohibited")
        if (not ids or ids[0] not in starts or
            tuple(frame_ids[starts[ids[0]]:starts[ids[0]]+len(ids)])!=ids):
            # A mismatched source window is itself an important research
            # observation. Archive the full conflicting result, do NOT drop.
            lineage_issues.append(index)
    records=(complete+({"kind":"COMPLETE_LEVEL2_REPORT","report":report,
                        "unverified_window_lineage_indices":tuple(lineage_issues)},))
    digest=registry.archive(archive_name,records)
    cases=[]
    for index,issue in enumerate(report["unresolved_research_items"]):
        reason="LEVEL2_UNRESOLVED_INPUT:"+issue["reason"]
        case_id=_digest({"report":report["evidence_identity"],"archive":digest,
                         "issue_index":index})
        registry.hold(case_id,archive_name,reason=reason,
                      details={"issue_index":index,"issue":issue,
                               "archive_digest":digest,
                               "disposition":"RETAIN_FOR_FURTHER_INSPECTION"})
        cases.append(case_id)
    for index in lineage_issues:
        reason="LEVEL2_ORIGINAL_WINDOW_SOURCE_LINEAGE_CONFLICT"
        case_id=_digest({"report":report["evidence_identity"],"archive":digest,
                         "window_index":index,"reason":reason})
        registry.hold(case_id,archive_name,reason=reason,
                      details={"window_index":index,"archive_digest":digest,
                               "disposition":"RETAIN_FOR_FURTHER_INSPECTION"})
        cases.append(case_id)
    for index,link in enumerate(report["links"]):
        reason="LEVEL2_UNVERIFIED_LINK:"+link.status
        case_id=_digest({"report":report["evidence_identity"],"archive":digest,
                         "link_index":index})
        registry.hold(case_id,archive_name,reason=reason,
                      details={"link_index":index,"target":link.target_balance,
                               "donor":link.donor_balance,
                               "link_status":link.status,"reason":link.reason,
                               "archive_digest":digest,
                               "disposition":"RETAIN_FOR_FURTHER_INSPECTION"})
        cases.append(case_id)
    return {"archive_name":archive_name,"archive_digest":digest,
            "retained_full_raw_frames":len(complete),
            "retained_original_windows":len(original),
            "retained_level2_links":len(report["links"]),
            "retained_unresolved_items":len(report["unresolved_research_items"]),
            "unverified_window_lineage_count":len(lineage_issues),
            "research_case_ids":tuple(cases),"cases":len(cases),
            "original_observations_dropped":0,"scientific_jobs_eliminated":0}
