from research.kalshi.adaptive_wavepacket_20261108.markets_bridge.benchmark_root_native_efficiency import pinned_source
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import ast, hashlib, json, subprocess
base='db96f24f3260bf0d70c763b297c2ba9b84f571a6'
prod='2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134'
adapter='research/ng_exhaustion_mbo_v4_state_adapter_20260820.py'
scratch=Path('E:/tmp/ng-root-bounded-13eb0f6ab')
trees={}
for pin in (base,prod):
    raw=subprocess.check_output(['git','ls-tree','-r','--name-only',pin,'--','deploy/aws/box','research','tests/_producers.py'],text=True)
    trees[pin]=set(raw.splitlines())
trees[base].add(adapter)
B='deploy/aws/box/'
R='research/kalshi/frankie_boss/'
N='research/kalshi/frankie_raw_mbo_benchmark/'
rootfiles=[B+'frankie_box_'+name+'.py' for name in (
'boss_session','bedrock','native_auxiliary','native_checkpoint','native_parallel','projection','progress',
'layer_spool','monday_calculations','experiment_root','root_validate','root_claims','durable','lane_pin','segmented_ledger')]
rootfiles += [R+x+'.py' for x in ('c15_journal','compact_journal','journal_prefix_snapshot','verified_journal_reader','mbo_resume_state','c15_observer','parallel_teacher','mbo_source','operations/ingest_block_sources')]
rootfiles += [R+'knowledge/CYCLE_CALCULATION_PINS.json',adapter]
nativefiles=[x for x in trees[prod] if x.startswith(N) and '/' not in x[len(N):] and x.endswith('.py') and ('native_' in x or 'a_memory_' in x or x.endswith('/__init__.py'))]
nativefiles += [adapter,'research/kalshi/plant_calendar.py','research/kalshi/flow_calendar.py','research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json']
def stage(key):
    pin,path=key
    out=(scratch/'producers' if pin==prod else scratch)/path
    out.parent.mkdir(parents=True,exist_ok=True)
    src=pinned_source(pin,path)
    out.write_bytes(src.encode())
    return key,src
def module_at(path,m):
    here=path.rsplit('/',1)[0]
    return [m.replace('.','/')+'.py',m.replace('.','/')+'/__init__.py',here+'/'+m.replace('.','/')+'.py',B+m+'.py','research/kalshi/'+m+'.py']
def dependencies(key,src):
    pin,path=key
    if not path.endswith('.py'):
        return set()
    here=path.rsplit('/',1)[0]
    local=set()
    for n in ast.walk(ast.parse(src)):
        mods=[]
        if isinstance(n,ast.Import):
            mods=[x.name for x in n.names]
        elif isinstance(n,ast.ImportFrom):
            if n.level:
                p=here.split('/')
                prefix='.'.join(p[:len(p)+1-n.level])
                mod=prefix+('.'+n.module if n.module else '')
            else:
                mod=n.module or ''
            mods=[mod,*[mod+'.'+x.name for x in n.names]]
        for mod in mods:
            for f in module_at(path,mod):
                if not f.startswith(('research/','deploy/aws/box/')) or f.startswith(('research/refrag/','research/kalshi/frankie_boss/tests/')): continue
                pick=prod if f.startswith(N) else pin
                if f in trees[pick] and not (f==adapter and pick==base and path.startswith(N)):
                    local.add((pick,f))
                    break
    return local
wanted={(base,x) for x in rootfiles if x in trees[base]} | {(prod,x) for x in nativefiles if x in trees[prod]}
done={}
with ThreadPoolExecutor(max_workers=14) as pool:
    for _ in range(4):
        batch=wanted-done.keys()
        if not batch: break
        print('stage',len(batch),flush=True)
        for key,src in pool.map(stage,sorted(batch)):
            done[key]=hashlib.sha256(src.encode()).hexdigest()
            wanted.update(dependencies(key,src))
(scratch/'source-manifest.json').write_text(json.dumps([dict(pin=k[0],path=k[1],sha256=v) for k,v in sorted(done.items())],indent=2))
print('verified',len(done),'remaining',sorted(wanted-done.keys()),flush=True)
