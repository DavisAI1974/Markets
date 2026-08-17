"""Runtime copy of the validated job-specific NOVA NG exhaustion adapter.

Canonical Markets S3 data remains authoritative. This module preserves the exact
validated packet contract while Nova-Optimizer repository write access is unavailable.
It does not use NOVA's generic lossy key-shortening rules.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

SCHEMA_ID = "nova.markets.ng_exhaustion.v1"
CODEC_ID = "nova.markets.ng_exhaustion.lossless.v1"
SCALES = ("3t", "5t", "8t", "13t")

KEY_TO_ALIAS = {
    "event_id":"e","session_id":"d","t0":"o","family":"f","post_state":"s",
    "state_confirmed":"sc","confirmed_at_s":"ca","elapsed_s":"t","runways":"r",
    "baseline_total_s":"bt","remaining_s":"rm","elapsed_since_t0_s":"et",
    "remaining_fraction":"rf","baseline_exhausted":"be","confidence":"cf","base":"b",
    "kind":"k","modifier":"m","basis":"bs","microstructure_confirmation":"mc",
    "confidence_modifier":"cm","data_gap_status":"g","reason_codes":"x",
    "falsifier_status":"z","future_price_accessed":"fp","classifier_sha256":"h",
    "classifier_distances":"cd","normalized_exhaustion_curve":"nc",
    "3t":"3","5t":"5","8t":"8","13t":"13",
}
ALIAS_TO_KEY = {v:k for k,v in KEY_TO_ALIAS.items()}
if len(ALIAS_TO_KEY) != len(KEY_TO_ALIAS):
    raise RuntimeError("NG exhaustion alias collision")

# LosslessClockCodec aliases keys only; string values are preserved verbatim.

class ReductionError(ValueError):
    pass

def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False)

def sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()

def _validate_finite(value: Any, path: str = "$") -> None:
    if isinstance(value,float) and not math.isfinite(value):
        raise ReductionError(f"non-finite float at {path}")
    if isinstance(value,list):
        for i,v in enumerate(value): _validate_finite(v,f"{path}[{i}]")
    elif isinstance(value,dict):
        for k,v in value.items(): _validate_finite(v,f"{path}.{k}")

def validate_clock_output(out: Mapping[str,Any]) -> None:
    required = {"event_id","session_id","t0","family","post_state","state_confirmed","confirmed_at_s",
                "elapsed_s","runways","microstructure_confirmation","confidence_modifier","data_gap_status",
                "reason_codes","falsifier_status","future_price_accessed","classifier_sha256",
                "classifier_distances","normalized_exhaustion_curve"}
    missing, extra = required-set(out), set(out)-required
    if missing or extra: raise ReductionError(f"V0 clock schema drift: missing={sorted(missing)} extra={sorted(extra)}")
    if out["family"] not in {"A","B","C"}: raise ReductionError("invalid family")
    if out["future_price_accessed"] is not False: raise ReductionError("future_price_accessed must be false")
    if set(out["runways"]) != set(SCALES): raise ReductionError("runway scale drift")
    for scale in SCALES:
        rw=out["runways"][scale]
        req={"baseline_total_s","remaining_s","elapsed_since_t0_s","remaining_fraction","baseline_exhausted","confidence","basis"}
        if set(rw)!=req: raise ReductionError(f"runway schema drift at {scale}")
        if rw["remaining_s"] is not None and float(rw["remaining_s"]) < 0: raise ReductionError(f"negative remaining runway at {scale}")
        if rw["baseline_total_s"] is not None and float(rw["baseline_total_s"]) < 0: raise ReductionError(f"negative baseline at {scale}")
        if set(rw["confidence"])!={"base","kind","modifier"}: raise ReductionError(f"confidence schema drift at {scale}")
    _validate_finite(dict(out))

class LosslessClockCodec:
    @classmethod
    def _encode(cls,v):
        if isinstance(v,dict):
            out={}
            for k,item in v.items():
                if k not in KEY_TO_ALIAS: raise ReductionError(f"unmapped V0 key: {k!r}")
                out[KEY_TO_ALIAS[k]]=cls._encode(item)
            return out
        if isinstance(v,list): return [cls._encode(x) for x in v]
        if isinstance(v,str): return v
        return v
    @classmethod
    def _decode(cls,v):
        if isinstance(v,dict):
            out={}
            for k,item in v.items():
                if k not in ALIAS_TO_KEY: raise ReductionError(f"unknown V0 alias: {k!r}")
                out[ALIAS_TO_KEY[k]]=cls._decode(item)
            return out
        if isinstance(v,list): return [cls._decode(x) for x in v]
        if isinstance(v,str): return v
        return v
    @classmethod
    def pack(cls,clock_output: Mapping[str,Any]) -> str:
        src=dict(clock_output); validate_clock_output(src)
        payload=_canonical_json({"v":CODEC_ID,"p":cls._encode(src)})
        if _canonical_json(cls.unpack(payload)) != _canonical_json(src): raise ReductionError("lossless round-trip mismatch")
        return payload
    @classmethod
    def unpack(cls,payload: str) -> dict[str,Any]:
        try: outer=json.loads(payload)
        except json.JSONDecodeError as e: raise ReductionError(f"invalid codec JSON: {e}") from e
        if set(outer)!={"v","p"} or outer["v"]!=CODEC_ID: raise ReductionError("lossless codec envelope drift")
        out=cls._decode(outer["p"]); validate_clock_output(out); return out

@dataclass(frozen=True)
class Provenance:
    bucket:str; key:str; sha256:str; classifier_sha256:str
    def validate(self):
        if not self.bucket or not self.key: raise ReductionError("S3 bucket/key required")
        for label,v in (("source",self.sha256),("classifier",self.classifier_sha256)):
            if len(v)!=64 or any(c not in "0123456789abcdef" for c in v.lower()): raise ReductionError(f"invalid {label} sha256")
    @property
    def ref(self):
        self.validate(); raw=f"s3://{self.bucket}/{self.key}|{self.sha256}|{self.classifier_sha256}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

def protected_projection(out: Mapping[str,Any]) -> dict[str,Any]:
    validate_clock_output(out)
    return {
        "event_id":out["event_id"],"session_id":out["session_id"],"t0":out["t0"],"family":out["family"],
        "post_state":out["post_state"],"state_confirmed":out["state_confirmed"],
        "confirmed_at_s":out["confirmed_at_s"],"elapsed_s":out["elapsed_s"],
        "runways":{scale:{"baseline_total_s":out["runways"][scale]["baseline_total_s"],
                           "remaining_s":out["runways"][scale]["remaining_s"],
                           "baseline_exhausted":out["runways"][scale]["baseline_exhausted"],
                           "basis":out["runways"][scale]["basis"],
                           "confidence_base":out["runways"][scale]["confidence"]["base"]} for scale in SCALES},
        "microstructure_confirmation":out["microstructure_confirmation"],
        "confidence_modifier":out["confidence_modifier"],"data_gap_status":list(out["data_gap_status"]),
        "reason_codes":list(out["reason_codes"]),"falsifier_status":out["falsifier_status"],
        "future_price_accessed":out["future_price_accessed"],"classifier_sha256":out["classifier_sha256"],
    }

_STATE_PACK={"A-fast-collapse":"F","A-persistent":"P","A_STATE_PENDING":"Q","A_STATE_UNAVAILABLE":"U","B_UNRESOLVED":"B","C_SCALE_TRANSITION_PROVISIONAL":"C"}; _STATE_UNPACK={v:k for k,v in _STATE_PACK.items()}
_MICRO_PACK={"same_side":"S","mixed":"M","opposite":"O","unavailable":"U"}; _MICRO_UNPACK={v:k for k,v in _MICRO_PACK.items()}
_MOD_PACK={"stronger":"+","neutral":"0","weaker":"-","degraded_unavailable":"?"}; _MOD_UNPACK={v:k for k,v in _MOD_PACK.items()}
_BASE_PACK={"validated":"V","low":"L","low_to_moderate":"LM","unavailable":"U"}; _BASE_UNPACK={v:k for k,v in _BASE_PACK.items()}
_BASIS_PACK={"frozen_reveal_A-fast-collapse":"AF","frozen_reveal_A-persistent":"AP","frozen_reveal_B_UNRESOLVED":"B","frozen_reveal_C_SCALE_TRANSITION_PROVISIONAL":"C","A_STATE_PENDING":"Q","A_STATE_UNAVAILABLE":"U"}; _BASIS_UNPACK={v:k for k,v in _BASIS_PACK.items()}
_REASON_PACK={"A_STATE_LEGAL_GATE_PRE60":"G60","A_STATE_FROZEN_61D_CLASSIFIER":"A61","A_CLASSIFIER_INPUT_UNAVAILABLE":"AIU","MICROSTRUCTURE_CONFIDENCE_UP":"MU","MICROSTRUCTURE_CONFIDENCE_NEUTRAL":"MN","MICROSTRUCTURE_CONFIDENCE_DOWN":"MD","MICROSTRUCTURE_UNAVAILABLE":"MX","B_UNRESOLVED_LOW_CONFIDENCE_FALLBACK":"BF","C_PROVISIONAL_SCALE_TRANSITION_FALLBACK":"CF"}; _REASON_UNPACK={v:k for k,v in _REASON_PACK.items()}
_FALS_PACK={"NOT_EVALUATED_WITHOUT_REALIZED_ENDPOINT":"N"}; _FALS_UNPACK={v:k for k,v in _FALS_PACK.items()}
_GAP_PACK={"microstructure":"M","a_classifier_window":"A"}; _GAP_UNPACK={v:k for k,v in _GAP_PACK.items()}

def _enc(v): return _canonical_json(v)
def _dec(s):
    try:return json.loads(s)
    except json.JSONDecodeError as e: raise ReductionError(f"invalid packed atom {s!r}") from e

class FrankieRunwayPacket:
    COLUMNS=("event","session","t0","family","state","confirmed","confirmed_at","elapsed","micro","modifier","3t","5t","8t","13t","gaps","reasons","falsifier","fp")
    @classmethod
    def _pack_row(cls,p):
        try: state=_STATE_PACK[p["post_state"]]; micro=_MICRO_PACK[p["microstructure_confirmation"]]; mod=_MOD_PACK[p["confidence_modifier"]]; fals=_FALS_PACK[p["falsifier_status"]]
        except KeyError as e: raise ReductionError(f"unmapped model enum: {e}") from e
        rr=[]
        for scale in SCALES:
            rw=p["runways"][scale]
            try:basis=_BASIS_PACK[rw["basis"]]; base=_BASE_PACK[rw["confidence_base"]]
            except KeyError as e: raise ReductionError(f"unmapped runway enum: {e}") from e
            rem = "-" if rw["remaining_s"] is None else repr(float(rw["remaining_s"]))
            total = "-" if rw["baseline_total_s"] is None else repr(float(rw["baseline_total_s"]))
            exhausted = "-" if rw["baseline_exhausted"] is None else str(int(bool(rw["baseline_exhausted"])))
            rr.append(f"{rem}/{total}/{exhausted}/{basis}/{base}")
        reasons=[]
        for x in p["reason_codes"]:
            if x not in _REASON_PACK: raise ReductionError(f"unmapped reason code: {x}")
            reasons.append(_REASON_PACK[x])
        gaps=[]
        for x in p["data_gap_status"]:
            if x not in _GAP_PACK: raise ReductionError(f"unmapped data gap: {x}")
            gaps.append(_GAP_PACK[x])
        fields=[_enc(p["event_id"]),_enc(p["session_id"]),_enc(p["t0"]),p["family"],state,"1" if p["state_confirmed"] else "0","-" if p["confirmed_at_s"] is None else repr(float(p["confirmed_at_s"])),repr(float(p["elapsed_s"])),micro,mod,*rr,",".join(gaps) if gaps else "-",",".join(reasons) if reasons else "-",fals,"0"]
        return "\t".join(fields)
    @classmethod
    def _unpack_row(cls,line,classifier_sha):
        f=line.rstrip("\n").split("\t")
        if len(f)!=len(cls.COLUMNS): raise ReductionError("model packet column drift")
        event,session,origin,fam,state,confirmed,cat,elapsed,micro,mod,r3,r5,r8,r13,gaps,reasons,fals,fp=f
        if fam not in {"A","B","C"} or state not in _STATE_UNPACK or micro not in _MICRO_UNPACK or mod not in _MOD_UNPACK or fals not in _FALS_UNPACK or fp!="0": raise ReductionError("invalid model packet token")
        def rw(s):
            p=s.split("/")
            if len(p)!=5 or p[2] not in {"0","1","-"} or p[3] not in _BASIS_UNPACK or p[4] not in _BASE_UNPACK: raise ReductionError("invalid runway token")
            return {"baseline_total_s":None if p[1]=="-" else float(p[1]),"remaining_s":None if p[0]=="-" else float(p[0]),"baseline_exhausted":None if p[2]=="-" else p[2]=="1","basis":_BASIS_UNPACK[p[3]],"confidence_base":_BASE_UNPACK[p[4]]}
        gapv=[] if gaps=="-" else [_GAP_UNPACK[x] for x in gaps.split(",")]
        reasonv=[] if reasons=="-" else [_REASON_UNPACK[x] for x in reasons.split(",")]
        return {"event_id":_dec(event),"session_id":_dec(session),"t0":_dec(origin),"family":fam,"post_state":_STATE_UNPACK[state],"state_confirmed":confirmed=="1","confirmed_at_s":None if cat=="-" else float(cat),"elapsed_s":float(elapsed),"runways":{scale:rw(tok) for scale,tok in zip(SCALES,(r3,r5,r8,r13))},"microstructure_confirmation":_MICRO_UNPACK[micro],"confidence_modifier":_MOD_UNPACK[mod],"data_gap_status":gapv,"reason_codes":reasonv,"falsifier_status":_FALS_UNPACK[fals],"future_price_accessed":False,"classifier_sha256":classifier_sha}
    @classmethod
    def pack_batch(cls,outputs:Sequence[Mapping[str,Any]],provenance:Provenance)->str:
        provenance.validate()
        if not outputs: raise ReductionError("empty output batch")
        proj=[protected_projection(o) for o in outputs]
        if any(p["classifier_sha256"]!=provenance.classifier_sha256 for p in proj): raise ReductionError("classifier SHA differs from provenance")
        header={"schema":SCHEMA_ID,"src_ref":provenance.ref,"s3":f"s3://{provenance.bucket}/{provenance.key}","source_sha256":provenance.sha256,"classifier_sha256":provenance.classifier_sha256,"columns":cls.COLUMNS,"future_price_accessed":False}
        payload="\n".join(["#!"+_canonical_json(header),*(cls._pack_row(p) for p in proj)])+"\n"
        restored=cls.unpack_batch(payload)["rows"]
        if len(restored)!=len(proj): raise ReductionError("model row count mismatch")
        for i,(a,b) in enumerate(zip(proj,restored)):
            if _canonical_json(a)!=_canonical_json(b): raise ReductionError(f"protected round-trip mismatch row {i}")
        return payload
    @classmethod
    def unpack_batch(cls,payload:str):
        lines=payload.splitlines()
        if not lines or not lines[0].startswith("#!"): raise ReductionError("missing model packet header")
        try:h=json.loads(lines[0][2:])
        except json.JSONDecodeError as e: raise ReductionError("invalid model packet header") from e
        req={"schema","src_ref","s3","source_sha256","classifier_sha256","columns","future_price_accessed"}
        if set(h)!=req or h["schema"]!=SCHEMA_ID or tuple(h["columns"])!=cls.COLUMNS or h["future_price_accessed"] is not False: raise ReductionError("model packet header/schema drift")
        if len(h["source_sha256"])!=64 or len(h["classifier_sha256"])!=64: raise ReductionError("model packet hash drift")
        return {"header":h,"rows":[cls._unpack_row(x,h["classifier_sha256"]) for x in lines[1:] if x]}

def compare_reduction(clock_output:Mapping[str,Any], provenance:Provenance):
    canonical=_canonical_json(dict(clock_output)); lossless=LosslessClockCodec.pack(clock_output); packet=FrankieRunwayPacket.pack_batch([clock_output],provenance)
    def s(x): return {"bytes":len(x.encode()),"approx_tokens":len(x)//4}
    a,b,c=s(canonical),s(lossless),s(packet)
    return {"canonical":a,"lossless_codec":b,"frankie_packet":c,"lossless_byte_reduction_pct":round(100*(1-b["bytes"]/a["bytes"]),2),"frankie_byte_reduction_pct":round(100*(1-c["bytes"]/a["bytes"]),2),"frankie_protected_projection_sha256":sha256_json(protected_projection(clock_output))}
