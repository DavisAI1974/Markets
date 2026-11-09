"""Enrich the reconstructed record table with order-level classes and build as-of window sums.
Classes per record (side-relative; bid=B / ask=A of the resting order):
  add_touch   A with dist in {0,-1}   (at the touch or improving it)
  add_near    A with dist 1..4        (1-4 ticks from touch)
  add_far     A with dist >= 5
  fill_qty    F quantity (resting order executed); trade_qty T quantity by aggressor side
  rm_fill     C whose order_id had an F in the same group (fill-linked removal)
  rm_cancel   C with no F for that order in the group, split by dist: touch / near / far
  mod_touch/mod_other  M by dist
Group = records up to and including a F_LAST (flags&128) record.  A group is known at its close record's ts_recv.
Everything is as-of: window sums only use records in groups closed by the cutoff.  No cost assumption."""
import numpy as np, pandas as pd

def enrich(R):
    R = R.copy()
    R['ts'] = R.ts_recv.astype('int64')
    last = (R['flags'].astype('int64') & 128) > 0
    R['grp'] = last.shift(1, fill_value=False).cumsum()          # group index (0-based) of each record
    R['is_last'] = last
    # fill-linked removals: C whose order had an F earlier in the same group
    f_key = R.loc[R.action == 'F', ['grp', 'order_id']].drop_duplicates()
    f_key['fl'] = 1
    R = R.merge(f_key, on=['grp', 'order_id'], how='left')
    R['fill_linked'] = (R.action == 'C') & (R.fl == 1)
    R.drop(columns='fl', inplace=True)
    R = R.sort_index() if R.index.is_monotonic_increasing else R
    side_b = R.side == 'B'; side_a = R.side == 'A'
    d = R.dist; q = R['size'].astype('int64')
    cls = {}
    for s, m in (('b', side_b), ('a', side_a)):
        isadd = (R.action == 'A') & m
        cls[f'add_touch_{s}'] = np.where(isadd & d.isin([0, -1]), q, 0)
        cls[f'add_near_{s}'] = np.where(isadd & d.between(1, 4), q, 0)
        cls[f'add_far_{s}'] = np.where(isadd & (d >= 5), q, 0)
        cls[f'fill_{s}'] = np.where((R.action == 'F') & m, q, 0)
        isc = (R.action == 'C') & m
        cls[f'rm_fill_{s}'] = np.where(isc & R.fill_linked, q, 0)
        cls[f'rm_cx_touch_{s}'] = np.where(isc & ~R.fill_linked & (d == 0), q, 0)
        cls[f'rm_cx_near_{s}'] = np.where(isc & ~R.fill_linked & d.between(1, 4), q, 0)
        cls[f'rm_cx_far_{s}'] = np.where(isc & ~R.fill_linked & (d >= 5), q, 0)
        ism = (R.action == 'M') & m
        cls[f'mod_touch_{s}'] = np.where(ism & (d <= 0), 1, 0)
        cls[f'mod_other_{s}'] = np.where(ism & (d > 0), 1, 0)
        cls[f'n_add_touch_{s}'] = np.where(isadd & d.isin([0, -1]), 1, 0)
    # T aggressor lots: side A = seller aggressor (hit bids), side B = buyer aggressor, N unknown
    isT = R.action == 'T'
    # wire side N: classify by trade price against the action-time midpoint (the retained classifier's rule);
    # price == midpoint stays unclassified.  Wire side B/A is kept as given.  px_idx and touch are in 0.001 ticks.
    # prior completed-group close midpoint (previous F_LAST record's touch after apply)
    close_idx = np.where(last.to_numpy(), np.arange(len(R)), -1)
    prev_close = pd.Series(close_idx).where(lambda x: x >= 0).shift(1).ffill()
    prev_close = prev_close.where(~last.to_numpy() | True)
    # for a record inside group g the prior close is the last F_LAST strictly before the group's first record
    grp_first = R.groupby('grp').cumcount() == 0
    first_pos = pd.Series(np.where(grp_first, np.arange(len(R)), np.nan)).ffill()
    pc = (first_pos - 1).astype('Int64')
    bbp = np.where(pc.fillna(-1) >= 0, R.bb_a.to_numpy()[pc.fillna(0).astype(int)], np.nan)
    bap = np.where(pc.fillna(-1) >= 0, R.ba_a.to_numpy()[pc.fillna(0).astype(int)], np.nan)
    midb = pd.Series((bbp + bap) / 2.0, index=R.index)
    n_buy = isT & (R.side == 'N') & (R.px_idx > midb); n_sell = isT & (R.side == 'N') & (R.px_idx < midb)
    # primary aggressor lots use the wire side only (this matches the retained ROOT 60 s operands for 654/656 of 694
    # families); side-N lots are kept separately, split by the prior-close midpoint rule, and are NOT added to the primary.
    cls['trade_sellagg'] = np.where(isT & (R.side == 'A'), q, 0)
    cls['trade_buyagg'] = np.where(isT & (R.side == 'B'), q, 0)
    cls['trade_unk'] = np.where(isT & (R.side == 'N'), q, 0)
    cls['trade_N_above_mid'] = np.where(n_buy, q, 0)
    cls['trade_N_below_mid'] = np.where(n_sell, q, 0)
    cls['trade_wire_buy'] = np.where(isT & (R.side == 'B'), q, 0)
    cls['trade_wire_sell'] = np.where(isT & (R.side == 'A'), q, 0)
    cls['n_trade'] = np.where(isT, 1, 0)
    C = pd.DataFrame(cls, index=R.index)
    return R, C

class Windows:
    """cumulative sums for as-of window queries"""
    def __init__(self, R, C):
        self.R = R; self.cols = list(C.columns)
        self.cum = np.vstack([np.concatenate([[0], np.cumsum(C[c].to_numpy())]) for c in self.cols])
        self.ts = R.ts.to_numpy(); self.last_idx = np.where(R.is_last.to_numpy())[0]
        self.last_ts = self.ts[self.last_idx]
    def cut(self, cutoff_ns):
        """index of last record in a group closed with ts <= cutoff (inclusive end)"""
        j = np.searchsorted(self.last_ts, cutoff_ns, side='right') - 1
        return self.last_idx[j] if j >= 0 else -1
    def sums(self, cutoff_ns, w_ns):
        e = self.cut(cutoff_ns)
        s = np.searchsorted(self.ts, cutoff_ns - w_ns, side='right')   # records strictly after cutoff-w
        s = min(s, e + 1)
        return dict(zip(self.cols, self.cum[:, e + 1] - self.cum[:, s])), e
