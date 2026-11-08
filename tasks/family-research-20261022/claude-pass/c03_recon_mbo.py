"""Record-level order-book reconstruction of a pinned DBN MBO member (GLBX.MDP3, one instrument).
Applies A/C/M/R in sequence; T and F do not change displayed state (a fill is followed by C or M).
Emits, per record: the state around it (touch before/after), the record's distance from its side's
touch BEFORE it applies, the resting size of the order before it applies, and near-depth sums.
Also exposes `Book` for case traces with per-order queue positions.
No fee, slippage or execution assumption.  Usage: c03_recon_mbo.py <parquet> <out.parquet>"""
import sys, numpy as np, pandas as pd
TICK = 1_000_000          # 0.001 in raw 1e-9 units
BASE = 0                  # price index = raw / 1e6 (0.001 ticks); far-off orders exist (0.100 .. 9.000)
NPX = 10001
UNDEF = 9223372036854775807

class Book:
    def __init__(self, track_queue=False):
        self.reset(); self.track_queue = track_queue
    def reset(self):
        self.sz = [[0]*NPX, [0]*NPX]      # side 0 = bid, 1 = ask ; size by price index
        self.cn = [[0]*NPX, [0]*NPX]      # order count by price index
        self.orders = {}                   # oid -> [side, pidx, size]
        self.q = [dict(), dict()] if getattr(self, 'track_queue', False) else None
        self.best = [-1, NPX]              # best bid idx, best ask idx
    def _fix(self, side):
        if side == 0:
            b = self.best[0]
            while b >= 0 and self.sz[0][b] <= 0: b -= 1
            self.best[0] = b
        else:
            a = self.best[1]
            while a < NPX and self.sz[1][a] <= 0: a += 1
            self.best[1] = a
    def add(self, oid, side, pidx, size):
        self.orders[oid] = [side, pidx, size]
        self.sz[side][pidx] += size; self.cn[side][pidx] += 1
        if side == 0 and pidx > self.best[0]: self.best[0] = pidx
        if side == 1 and pidx < self.best[1]: self.best[1] = pidx
        if self.q is not None: self.q[side].setdefault(pidx, {})[oid] = size
    def remove_qty(self, oid, qty):
        o = self.orders.get(oid)
        if o is None: return None
        side, pidx, rest = o
        take = min(qty, rest)
        self.sz[side][pidx] -= take; o[2] = rest - take
        if o[2] <= 0:
            self.cn[side][pidx] -= 1; del self.orders[oid]
            if self.q is not None: self.q[side].get(pidx, {}).pop(oid, None)
        elif self.q is not None: self.q[side][pidx][oid] = o[2]
        if (side == 0 and pidx == self.best[0]) or (side == 1 and pidx == self.best[1]): self._fix(side)
        return rest
    def modify(self, oid, side, pidx, size):
        o = self.orders.get(oid)
        if o is None:
            self.add(oid, side, pidx, size); return None
        oside, opidx, rest = o
        if opidx == pidx and size <= rest:      # size-down at same price keeps priority
            self.sz[oside][pidx] -= rest - size; o[2] = size
            if self.q is not None: self.q[oside][pidx][oid] = size
            if size <= 0: self.remove_qty(oid, 0)
            if (oside == 0 and pidx == self.best[0]) or (oside == 1 and pidx == self.best[1]): self._fix(oside)
        else:                                   # price change or size up: loses priority
            self.remove_qty(oid, rest); self.add(oid, side, pidx, size)
        return rest
    def touch(self):
        b, a = self.best
        if b < 0 or a >= NPX: return (None, 0, 0, None, 0, 0)
        return (b, self.sz[0][b], self.cn[0][b], a, self.sz[1][a], self.cn[1][a])

def run(df):
    ts = df['ts_recv'].to_numpy(); act = df['action'].to_numpy(); side = df['side'].to_numpy()
    px = df['price'].to_numpy(); sz = df['size'].to_numpy(); oid = df['order_id'].to_numpy(); fl = df['flags'].to_numpy()
    n = len(df); B = Book()
    out = {k: np.full(n, -1, dtype=np.int64) for k in
           ['bb_b','ba_b','bsz_b','asz_b','bb_a','ba_a','bsz_a','asz_a','bn_a','an_a','dist','rest_b','near_bid5','near_ask5','near_bid10','near_ask10']}
    for i in range(n):
        a = act[i]; s = side[i]
        bb, ba = B.best
        out['bb_b'][i] = bb; out['ba_b'][i] = ba
        out['bsz_b'][i] = B.sz[0][bb] if bb >= 0 else 0
        out['asz_b'][i] = B.sz[1][ba] if ba < NPX else 0
        if a == 'R':
            B.reset()
        elif a in ('A', 'C', 'M') and px[i] != UNDEF or (a == 'C' and oid[i] in B.orders):
            sd = 0 if s == 'B' else 1
            pidx = int((px[i] - BASE) // TICK) if px[i] != UNDEF else -1
            if a == 'A':
                B.add(oid[i], sd, pidx, int(sz[i]))
            elif a == 'C':
                o = B.orders.get(oid[i])
                if o is not None:
                    sd = o[0]; pidx = o[1]
                    # distance from own side touch, in ticks, before apply
                    out['dist'][i] = (bb - pidx) if sd == 0 else (pidx - ba)
                    out['rest_b'][i] = o[2]
                B.remove_qty(oid[i], int(sz[i]))
            elif a == 'M':
                o = B.orders.get(oid[i])
                if o is not None: out['rest_b'][i] = o[2]
                B.modify(oid[i], sd, pidx, int(sz[i]))
            if a in ('A', 'M') and out['dist'][i] == -1:
                out['dist'][i] = (bb - pidx) if sd == 0 else (pidx - ba)
        t = B.touch()
        out['bb_a'][i] = -1 if t[0] is None else t[0]; out['ba_a'][i] = NPX if t[3] is None else t[3]
        out['bsz_a'][i] = t[1]; out['asz_a'][i] = t[4]; out['bn_a'][i] = t[2]; out['an_a'][i] = t[5]
        if (fl[i] & 128):       # F_LAST: near-depth only at group closes (cheap)
            if t[0] is not None:
                b0, a0 = t[0], t[3]
                out['near_bid5'][i] = sum(B.sz[0][max(b0-4,0):b0+1]); out['near_ask5'][i] = sum(B.sz[1][a0:a0+5])
                out['near_bid10'][i] = sum(B.sz[0][max(b0-9,0):b0+1]); out['near_ask10'][i] = sum(B.sz[1][a0:a0+10])
    res = pd.DataFrame(out)
    res.insert(0, 'ts_recv', ts); res.insert(1, 'action', act); res.insert(2, 'side', side)
    res['px_idx'] = np.where(px == UNDEF, -1, (px - BASE) // TICK); res['size'] = sz; res['order_id'] = oid; res['flags'] = np.array([int(x) for x in fl], dtype=np.int64)
    return res

if __name__ == '__main__':
    df = pd.read_parquet(sys.argv[1]).reset_index()
    res = run(df); res.to_parquet(sys.argv[2]); print(res.shape)
