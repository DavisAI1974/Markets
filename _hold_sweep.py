import numpy as np
from _liquidity_dive import build_channels, median_spread_bps
from odcore import quiet_floor
from odcore.maker_book import simulate_arm
from _maker_flip_floor import opposing_mask
PCK={"eth_coinbase":1,"sol_coinbase":1,"doge_coinbase":1,"xrp_coinbase":1}
HOLDS=[1,5,10,20,50]
print(f"{'cell':<14}{'half_sp':>9}  signal   "+"".join(f"h={h:<7}" for h in HOLDS))
for cell,K in PCK.items():
    p=f"/tmp/{cell}_book.jsonl.gz"
    ch,g=build_channels(p,K,20)
    imb=ch["depth_imb"]; mid=np.asarray(g["mid"],float)
    bb,ba=np.asarray(g["bidK"][1],float),np.asarray(g["askK"][1],float)
    buy,sell=np.asarray(g["buy"],float),np.asarray(g["sell"],float)
    n=len(mid); cut=int(n*0.6); hs=median_spread_bps(p)/2.0
    quiet=(buy+sell)<=0; qf=quiet_floor.fit(imb,quiet,train_frac=0.6)
    gate=qf.gate(imb,1.5); opp=opposing_mask(imb,mid,30); sgn=np.sign(imb)
    floor_sig=np.where(gate,sgn,0.0); both_sig=np.where(gate&opp,sgn,0.0)
    s=lambda a:np.asarray(a)[cut:n]
    def g_(sig,h): return simulate_arm(s(sig),s(mid),s(bb),s(ba),s(buy),s(sell),fill_window=10,hold=h,queue_frac=1.0,half_spread_bps=hs,fee_bps=0.0).gross_per_fill_bps
    for nm,sig in [("floor",floor_sig),("both ",both_sig)]:
        print(f"{cell:<14}{hs:>9.4f}  {nm}   "+"".join(f"{g_(sig,h):>+8.3f} " for h in HOLDS))
