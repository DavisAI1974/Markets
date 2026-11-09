"""Date-parameterised paths for the Claude pass (Tier 2, conditions-only chain).
A date is the string YYYYMMDD of the UTC member (one pinned DBN tape = one UTC day, one instrument).
Large derived files (raw/recon/grid/seconds parquet, groups npz) live in WORK and are NOT committed; every script
that needs them regenerates them from the tape.  Small tables go to tables/<date>/ and are committed.
The date is a file label only: no script turns it into a feature."""
import os
WORK = os.environ.get('OD_WORK', '/home/claude/work/derived')
HERE = os.path.dirname(os.path.abspath(__file__))
DATES = ['20231001', '20231002', '20231003', '20231016', '20231017', '20231018']
def raw(d): return f'{WORK}/raw_{d}.parquet'
def recon(d): return f'{WORK}/recon_{d}.parquet'
def groups(d): return f'{WORK}/groups_{d}.npz'
def big(d, name): return f'{WORK}/{name}_{d}.parquet'
def tab(d, name):
    p = f'{HERE}/tables/{d}'; os.makedirs(p, exist_ok=True); return f'{p}/{name}'
def date_arg(argv=None):
    import sys
    a = (argv or sys.argv)[1] if len(argv or sys.argv) > 1 else None
    assert a in DATES, f'first argument must be a date label in {DATES}'
    return a

def closed_mask(recv_ns, times_ns, trade_ns, gap_s=1800, warm_s=600):
    """True where a time falls inside a closed-market stretch.  A stretch starts at a group close followed by no completed group for >= gap_s,
    and ends warm_s after the FIRST TRADE PRINT at or after the next group close (orders can rest, cross or lock before matching starts, so the
    next group close is not yet an open market).  warm_s keeps trailing windows from mixing with the stale book.
    Data-defined: reads only gaps in the group-close sequence and the trade-print times; no calendar clock."""
    import numpy as np
    recv = np.asarray(recv_ns); t = np.asarray(times_ns); tr = np.sort(np.asarray(trade_ns)); out = np.zeros(len(t), dtype=bool)
    for k in np.where(np.diff(recv) >= gap_s * 10**9)[0]:
        j = np.searchsorted(tr, recv[k + 1], side='left'); open_ns = tr[j] if j < len(tr) else recv[-1]
        out |= (t >= recv[k]) & (t < open_ns + warm_s * 10**9)
    return out

# ---- three-day additions: one UTC-day session per run; the session's tapes are the prior-evening member and its own member
SESS = os.environ.get('OD_SESS', '20231018')
SESS_TAPES = {'20231002': ('20231001', '20231002'), '20231003': ('20231002', '20231003'), '20231017': ('20231016', '20231017'), '20231018': ('20231017', '20231018')}
TAPES = SESS_TAPES[SESS]
RC = f'{HERE}/../replay-comparison/{SESS}'
CAND = f'{RC}/candidate-inputs.jsonl.gz'
AFTER = f'{RC}/flow-book-discovery-v1/dipole-after-recognition.csv.gz'
EVENTS = f'{RC}/research-atlas-v2/dipole-weakening-events.csv'
TABD = f'{HERE}/tables/dipole/{SESS}'; os.makedirs(TABD, exist_ok=True)
CW = f'{WORK}/{SESS}'; os.makedirs(CW, exist_ok=True)
if SESS == '20231018':   # Oct 18's own candidate inputs and Codex tables sit at the task root (the replication check of the original pass)
    CAND = f'{HERE}/../october18-candidate-inputs.jsonl.gz'; AFTER = f'{HERE}/../flow-book-discovery-v1/dipole-after-recognition.csv.gz'; EVENTS = f'{HERE}/../research-atlas-v2/dipole-weakening-events.csv'
