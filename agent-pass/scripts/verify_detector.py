from common import *
from part1b import detect
import importlib.util,sys
p=ROOT/'cache/native_candidate_pinned.py';p.write_bytes(blob('research/kalshi/frankie_raw_mbo_benchmark/native_candidate.py','2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134'))
spec=importlib.util.spec_from_file_location('native_pinned',p);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
rng=np.random.default_rng(14)
fixtures={'plateau':np.r_[np.full(1000,.1),np.ones(100),np.full(1000,.2)],'quiet':np.r_[np.full(950,np.nan),rng.choice([-.9,0,.9,np.nan],2050)],'variable':rng.choice([-.95,-.5,0,.2,.8,1,np.nan],3000)}
for name,v in fixtures.items():
 F=pd.DataFrame(dict(second=np.arange(10000,10000+len(v)),ratio=v));ours,_=detect(F);ref,_=mod.detect(v,first_second=10000,continuity_segment=0)
 assert len(ours)==len(ref),(name,len(ours),len(ref))
 for a,b in zip(ours.to_dict('records'),ref):
  for k,v in a.items():
   if k in ('window_open','competing_peaks'):continue
   want=getattr(b,'event_second' if k=='birth_second' else k)
   assert v==want,(name,k,v,want)
 print(name,len(ref),'identical recovered operands and clocks')
