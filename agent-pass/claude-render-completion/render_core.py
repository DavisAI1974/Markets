"""Clock and missingness helpers for rendering saved Claude lifecycle arrays."""
import math
def relative_seconds(value,anchor):
    return None if value is None else (int(value)-int(anchor))/1_000_000_000
def display_values(values):
    return [float(x) for x in values]
def lifecycle_markers(seconds,ratio,birth,polarity):
    pairs=[(int(s),float(v)*polarity) for s,v in zip(seconds,ratio)]
    lookup={s:i for i,(s,v) in enumerate(pairs)}
    i=lookup.get(birth)
    after=[(s-birth,v) for s,v in pairs if s>=birth]
    def first(pred):
        return next((s for s,v in after if pred(v)),None)
    onset=None
    if i is not None and math.isfinite(pairs[i][1]) and math.isclose(pairs[i][1],1,rel_tol=1e-5,abs_tol=1e-8):
        j=i
        while j>0 and pairs[j][0]-pairs[j-1][0]==1 and math.isclose(pairs[j-1][1],1,rel_tol=1e-5,abs_tol=1e-8): j-=1
        onset=pairs[j][0]-birth
    end=first(lambda v: math.isfinite(v) and v<1-1e-12)
    flip=first(lambda v: math.isfinite(v) and v<0)
    empty=first(lambda v: not math.isfinite(v))
    # An unobserved flip/empty remains unresolved; no finite tail is invented.
    unresolved=flip is None or empty is None
    horizon=1260 if unresolved else max(160,max(flip,empty)+60)
    return dict(run_onset_s=onset,run_end_s=end,first_flip_s=flip,first_empty_s=empty,
                tail_unresolved=unresolved,window_end_s=min(1260,horizon),
                window_capped=horizon>1260)

def candidate_labels(row):
    operands=row.get("recorded_operands",{})
    birth=row.get("birth_second")
    source="birth_second"
    if birth is None:
        episode_ns=row.get("original_episode",{}).get("birth_recv_ns")
        event=operands.get("event_second")
        if episode_ns is None or event is None:
            raise ValueError("No explicit original birth clock")
        if int(episode_ns)!=int(event)*1_000_000_000:
            raise ValueError("Original episode and event-second clocks disagree")
        birth=int(event);source="original_episode.birth_recv_ns + recorded_operands.event_second"
    available=row.get("available_second",operands.get("available_second"))
    return dict(birth_second=int(birth),available_second=None if available is None else int(available),
                birth_clock_source=source,live_recognition_allowed=row.get("input_disposition")!="finalize_only_no_live_recognition")

def prebirth_cutoff(saved,birth_second):
    # Negative coverage values are an explicit unavailable sentinel.
    return int(birth_second)*1_000_000_000-1 if saved in (None,"") or int(saved)<0 else int(saved)
