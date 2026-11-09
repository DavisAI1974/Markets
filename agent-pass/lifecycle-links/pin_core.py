"""Lossless clock extraction and provenance roles; no market calculations."""
from bisect import bisect_right
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
NS=10**9
EPOCH_MIN=946684800*NS
EPOCH_MAX=4102444800*NS
SECOND_FIELDS={"second","birth_second","available_second","available_second_recorded","available_second_recovered",
               "life_end_second","event_second","exact_second","lifecycle_start_second"}
RELATIVE_FIELDS={"t0","onset","confirm","next_t0","seed_known_s","archived_recognition_s"}
def exact_int(value):
    if value is None or value=="" or isinstance(value,bool):return None
    if isinstance(value,int):return value
    if isinstance(value,float):
        if abs(value)>2**53:raise ValueError("Unsafe floating point timestamp")
        return int(value) if value.is_integer() else None
    try:
        d=Decimal(str(value))
        return int(d) if d.is_finite() and d==d.to_integral_value() else None
    except (InvalidOperation,ValueError):return None
def utc_ns(value):
    sec,nano=divmod(value,NS)
    return datetime.fromtimestamp(sec,timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")+f".{nano:09d}Z"
def select_index(times,when):return bisect_right(times,when)-1
def clock_role(field):
    f=field.lower()
    if "published" in f:return "declared_publication"
    if "event_ns" in f or "ts_event" in f:return "event"
    if "known" in f or "available" in f or "availability" in f:return "known_by"
    if "recognition" in f:return "recognition"
    if "receive" in f or "recv" in f or "ts_recv" in f:return "receive"
    if "cut" in f:return "sample_cut"
    if "label" in f or f.split(".")[-1] in SECOND_FIELDS:return "second_label"
    if "end" in f or "confirm" in f or "outcome" in f or "return" in f:return "endpoint"
    if "day0" in f:return "session_origin"
    return "source_timestamp"
def flatten(row,prefix=""):
    for key,value in row.items():
        path=f"{prefix}.{key}" if prefix else key
        if isinstance(value,dict):yield from flatten(value,path)
        elif isinstance(value,list) and value and isinstance(value[0],dict):
            for j,v in enumerate(value):
                if isinstance(v,dict):yield from flatten(v,f"{path}[{j}]")
        else:yield path,value
def extract_clocks(row,ccode=False):
    result=[];fixes=[];overrides={}
    day0=exact_int(row.get("day0_epoch_s"))
    t0=exact_int(row.get("t0"))
    if ccode and day0 is not None and t0 is not None:
        for field in ("info_horizon_local_s","info_horizon_refractory_s"):
            offset=exact_int(row.get(field))
            if offset is not None:
                key=field+"_epoch_s";correct=day0+t0+offset;old=exact_int(row.get(key))
                overrides[key]=correct
                if old!=correct:fixes.append(dict(field=key,original=str(old),corrected=str(correct),formula="day0_epoch_s + t0 + "+field))
    values=dict(flatten(row));values.update(overrides)
    if ccode and day0 is not None:
        for field in RELATIVE_FIELDS:
            v=exact_int(row.get(field))
            if v is not None:values.setdefault(field+"_epoch_s",day0+v)
    for field,value in values.items():
        leaf=field.split(".")[-1]
        is_ns=leaf.endswith("_ns") or leaf in ("ts_event","ts_recv")
        is_s=leaf.endswith("_epoch_s") or leaf in SECOND_FIELDS
        if not (is_ns or is_s):continue
        # Elapsed intervals are not absolute clocks, even when their unit is ns.
        if is_ns and re.search(r"(^|_)(duration|gap|age|latency|delay|since|delta|offset|warning|remaining|elapsed)(_|$)",leaf):continue
        try:v=exact_int(value)
        except ValueError:
            fixes.append(dict(field=field,original=str(value),corrected=None,formula="unusable_unsafe_float_clock"));continue
        if v is None:continue
        ns=v*(NS if is_s else 1)
        if not EPOCH_MIN<=ns<EPOCH_MAX:continue
        result.append(dict(field=field,ns=ns,utc=utc_ns(ns),role=clock_role(field),
                           derivation=("corrected_event_relative_horizon" if field in overrides else "epoch_seconds_times_1e9" if is_s else "original_integer_ns")))
    return result,fixes

def layer_fields(fields):
    out={}
    for field in fields:
        f=field.lower();leaf=f.split(".")[-1];ids=[]
        def add(*names):
            for n in names:
                if n not in ids:ids.append(n)
        if leaf.endswith("_ns") or leaf.endswith("_epoch_s") or leaf in SECOND_FIELDS:
            r=clock_role(field)
            add({"event":"clock_event_time","receive":"clock_receive_time","known_by":"clock_event_known_by",
                 "recognition":"clock_prospective_discovery_confirmation"}.get(r,"derived_feature_availability_timestamps"))
        elif re.search(r"(^|_)(id|ordinal|cursor|index|day|session|source|revision|sha256|hash|instrument)(_|$)",f):
            add("raw_source_identity_provenance_clocks_integrity")
        if any(x in f for x in ("missing","censor","undefined","disposition","coverage","valid","available","good")):
            add("missingness_and_integrity_flags")
        if any(x in f for x in ("native_buy","native_sell","fresh_buy","fresh_sell","wire","aggressor","trade_b","trade_a","flow","roll_buy","roll_sell","classified_lots","expired_buy","expired_sell")):
            add("aggressor_and_native_signed_flow")
        if any(x in f for x in ("roll","ratio","net_recurrence")):add("legacy_per_second_roll20","derived_roll20_and_dipole_state")
        if any(x in f for x in ("bid_size","ask_size","depth","touch_lots","full_size")):add("full_bid_ask_depth")
        if any(x in f for x in ("bid_orders","ask_orders","order_count","price_level")):add("price_level_and_order_counts")
        if any(x in f for x in ("spread","imbalance","book_t0")):add("spread_and_depth_imbalance")
        if any(x in f for x in ("price","midpoint","mid_","bid_raw","ask_raw")) or f in ("bid","ask","mid"):add("price_and_book_path")
        for token,name in [("add","order_lifecycle_adds"),("cancel","order_lifecycle_cancels"),("modify","order_lifecycle_modifies"),
                           ("replace","order_lifecycle_replaces"),("fill","order_lifecycle_fills"),("clear","order_lifecycle_clears")]:
            if re.search(r"(^|_)"+token+r"(_|s|$)",f):add(name)
        if f in ("action","side","size","flags","order_id","sequence"):add("native_acmrtfn_messages")
        if "trade" in f and "clock" not in f:add("order_lifecycle_trades")
        if any(x in f for x in ("family","geometry","structure")):add("derived_d_family_geometry")
        if any(x in f for x in ("predecessor","prev","next","ancestry")):add("derived_open_world_predecessor_state")
        if any(x in f for x in ("candidate","dipole","birth","polarity","orientation","baseline","threshold","prominence","magnitude")):
            add("derived_roll20_and_dipole_state")
        if any(x in f for x in ("queue","fifo","ahead")):add("fifo_queues")
        if any(x in f for x in ("recover","resilien")):add("resilience_and_recovery")
        if any(x in f for x in ("replenish","deplet","refill")):add("depletion_and_replenishment")
        if any(x in f for x in ("surviv","order_age")):add("queue_age_and_survival")
        if any(x in f for x in ("outcome","later_move","aftermath","future","mfe","mae","move_","return_","pnl")):
            add("later_outcome_reveal")
        if not ids:ids=["UNMAPPED_FIELD_RETAINED"]
        out[field]=ids
    return out
