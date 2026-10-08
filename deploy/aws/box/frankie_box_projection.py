"""Ordered, resumable projection of sealed native ledgers into exact gzip JSON.

Fourteen CPU processes parse/project/encode independent byte ranges. Each range
retains one compressed block archive and a verified receipt. Publication joins
gzip members in source order without unpacking, re-encoding or expanding rows.
Scientific calculators and the pinned crosswalk are unchanged.
"""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import threading
import time
import zlib

import frankie_box_bedrock as B
from frankie_box_finalization import file_identity

CHUNK = 64 << 20
PENDING = 28
_STATE = None


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    raw = encoded(value) + b'\n'
    with Path(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if Path(path).read_bytes() != raw:
        raise ValueError('projection receipt readback differs')
    fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _initialize(queue, barrier, configuration):
    global _STATE
    cpu = queue.get(timeout=30)
    os.sched_setaffinity(0, {cpu})
    if os.sched_getaffinity(0) != {cpu}:
        raise ValueError('projection helper affinity differs')
    _STATE = configuration
    barrier.wait(timeout=60)


def _ready():
    return dict(pid=os.getpid(), cpu=next(iter(os.sched_getaffinity(0))))


class Workers:
    def __init__(self, configuration=None, cpus=None):
        # Session 6 (Greg, 2026-10-08: "We definitely need CPUs in every step of this ending process of root"): the pool
        # is sized from the lane this process holds (frankie_box_lane_pin: FRANKIE_LANE_CPUS / the affinity, placed by
        # physical core), not the constant fourteen helpers on CPUs 2-15 with the coordinator on CPU 1 that left 17 of
        # a2's 32 lane CPUs idle for the whole member and lifecycle read. The coordinator takes the first CPU of the core
        # order, every other lane CPU one pinned helper. Placement only: the jobs are the same fixed CHUNK byte ranges,
        # and a range archive's bytes do not depend on which helper writes it or on how many there are.
        import frankie_box_lane_pin as lane_pin
        self.owner = threading.get_native_id()
        self.original = os.sched_getaffinity(self.owner)
        lane = sorted(cpus) if cpus is not None else lane_pin.lane_cpus()
        if len(lane) > 1:
            coordinator, helper_cpus, basis = lane_pin.placement(len(lane) - 1, lane)
        else:
            coordinator, helper_cpus, basis = lane[0], [lane[0]], 'a single-CPU lane: the helper shares the coordinator CPU'
        helper_cpus = list(helper_cpus)
        self.lane, self.coordinator, self.basis = list(lane), coordinator, basis
        self.pending = 2 * len(helper_cpus)
        ctx = multiprocessing.get_context('spawn')
        self.queue, self.barrier = ctx.Queue(), ctx.Barrier(len(helper_cpus))
        for cpu in helper_cpus:
            self.queue.put(cpu)
        os.sched_setaffinity(self.owner, {coordinator})
        if os.sched_getaffinity(self.owner) != {coordinator}:
            raise ValueError('projection coordinator affinity differs')
        self.pool = ProcessPoolExecutor(len(helper_cpus), mp_context=ctx, initializer=_initialize,
                                       initargs=(self.queue,self.barrier,configuration))
        # The initializer barrier guarantees every helper process is started.
        try:
            starts = [self.pool.submit(_ready) for _ in range(len(helper_cpus))]
            for future in starts:
                future.result()
            self.helpers = sorted([dict(pid=p.pid, cpu=next(iter(os.sched_getaffinity(p.pid))))
                                   for p in self.pool._processes.values()],key=lambda p:p['cpu'])
            if [p['cpu'] for p in self.helpers] != sorted(helper_cpus):
                raise ValueError('projection process assignment readback differs')

        except BaseException:
            self.close()
            raise

    def ordered(self, function, items):
        source, pending, exhausted = iter(items), deque(), False
        while pending or not exhausted:
            while len(pending) < self.pending and not exhausted:
                try:
                    item = next(source)
                except StopIteration:
                    exhausted = True
                else:
                    pending.append(self.pool.submit(function,item))
            if pending:
                yield pending.popleft().result()

    def receipt(self):
        # reserved_cpu was the constant 0 of the fixed CPU 1-15 layout; the lane layout reserves none (session 6)
        return dict(coordinator_cpu=self.coordinator,reserved_cpu=None,helpers=self.helpers,
                    maximum_pending=self.pending,affinity_readback_verified=True,
                    lane=self.lane,placement_basis=self.basis)

    def close(self):
        try:
            self.pool.shutdown(wait=True,cancel_futures=True)
        finally:
            self.queue.close()
            self.queue.join_thread()
            os.sched_setaffinity(self.owner,self.original)


def _range(job):
    kind, index, start, end = job
    cfg = _STATE
    pin = cfg['ledgers'][kind]
    source = Path(pin['path'])
    root = Path(cfg['root']) / kind
    base = root / ('range-%06d' % index)
    receipt_path = base.with_suffix('.json')
    binding = dict(plan=cfg['plan'],kind=kind,index=index,start=start,end=end)
    if receipt_path.exists():
        value = json.loads(receipt_path.read_bytes())
        path = Path(value['archive']['path'])
        if (value['binding'] != binding or path.parent != root or not path.name.startswith(base.name+'-')
                or path.suffix != '.blocks'
                or path.stat().st_size != value['archive']['bytes']
                or sha(path) != value['archive']['sha256']):
            raise ValueError('retained projection range differs')
        return value
    # A failed unreceipted range is preserved; a new attempt gets its own name.
    import uuid
    archive = base.with_name(base.name+'-'+uuid.uuid4().hex).with_suffix('.blocks')
    before = file_identity(source)
    if list(before) != cfg['identities'][kind]:
        raise ValueError('sealed projection input identity changed')
    streams, data, counts, absent, sections = {}, {}, {}, {}, {}
    def append(name,row):
        if name not in streams:
            streams[name] = zlib.compressobj(1,zlib.DEFLATED,31)
            data[name],counts[name] = [],0
        raw = (b',\n' if counts[name] else b'') + encoded(row)
        part = streams[name].compress(raw)
        if part:
            data[name].append(part)
        counts[name] += 1
    total = 0
    with source.open('rb') as stream:
        if start:
            stream.seek(start-1)
            if stream.read(1) != b'\n':
                stream.readline()
        actual_start = stream.tell()
        while stream.tell() < end:
            raw = stream.readline()
            if not raw:
                break
            if not raw.strip():
                raise ValueError('blank native ledger row')
            row = json.loads(raw)
            total += 1
            if kind == 'member':
                key = dict(group_index=row.get('group_index'),ts_recv_ns=row.get('ts_recv_ns'),
                           f_last_ts_recv_ns=(row.get('clocks') or {}).get('f_last_ts_recv_ns'))
                for name,paths in cfg['member_paths'].items():
                    projected = dict(key)
                    for path in paths:
                        found,value = B.select_path(row,path)
                        if found:
                            projected[path] = value
                        else:
                            misses = absent.setdefault(name,{})
                            misses[path] = misses.get(path,0)+1
                    append(name,projected)
            else:
                section = row.get('emitting_section')
                for name in cfg['section_layers'].get(section,[]):
                    append(name,row)
                    counter = sections.setdefault(name,{})
                    counter[section] = counter.get(section,0)+1
        actual_end = stream.tell()
    if file_identity(source) != before:
        raise ValueError('projection ledger changed during range read')
    if shutil.disk_usage(root).free < 20<<30:
        raise OSError('projection disk reserve reached; all previous ranges retained')
    fragments,hashed,size = {},hashlib.sha256(),0
    with archive.open('xb') as output:
        for name in streams:
            data[name].append(streams[name].flush())
            width,digest = 0,hashlib.sha256()
            for block in data[name]:
                output.write(block)
                digest.update(block);hashed.update(block)
                width += len(block)
            fragments[name] = dict(offset=size,bytes=width,sha256=digest.hexdigest(),rows=counts[name])
            size += width
        output.flush()
        os.fsync(output.fileno())
    if sha(archive) != hashed.hexdigest():
        raise ValueError('compressed projection archive readback differs')
    value = dict(binding=binding,actual_start=actual_start,actual_end=actual_end,rows=total,
                 archive=dict(path=str(archive),bytes=size,sha256=hashed.hexdigest()),
                 fragments=fragments,absent=absent,sections=sections,
                 worker=_ready(),source_identity=list(before),readback_verified=True)
    # Canonical path is only in the receipt; immutable attempt files survive failure.
    save(receipt_path,value)
    return value


def _copy_fragment(output,entry):
    hashed,remaining = hashlib.sha256(),entry['bytes']
    with Path(entry['path']).open('rb') as source:
        source.seek(entry['offset'])
        while remaining:
            block = source.read(min(1<<20,remaining))
            if not block:
                raise ValueError('projection fragment truncated')
            output.write(block);hashed.update(block);remaining-=len(block)
    if hashed.hexdigest() != entry['sha256']:
        raise ValueError('projection fragment changed during publication')


def _publish(job):
    path,metadata,arrays = job
    path = Path(path)
    if path.exists():
        raise FileExistsError('existing projected layer is preserved')
    with path.open('xb') as output:
        output.write(gzip.compress(b'{',compresslevel=1,mtime=0))
        for index,key in enumerate(sorted(metadata.keys() | arrays.keys())):
            output.write(gzip.compress((b',' if index else b'')+encoded(key)+b':',
                                       compresslevel=1,mtime=0))
            if key in arrays:
                output.write(gzip.compress(b'[',compresslevel=1,mtime=0))
                emitted = False
                for entry in arrays[key]:
                    if emitted:
                        output.write(gzip.compress(b',\n',compresslevel=1,mtime=0))
                    _copy_fragment(output,entry)
                    emitted = True
                output.write(gzip.compress(b']',compresslevel=1,mtime=0))
            else:
                output.write(gzip.compress(encoded(metadata[key]),compresslevel=1,mtime=0))
        output.write(gzip.compress(b'}\n',compresslevel=1,mtime=0))
        output.flush();os.fsync(output.fileno())
    return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path),
                encoding='gzip-json',fields=sorted(metadata.keys() | arrays.keys()),
                **{k:metadata[k] for k in ('status','producer','reason','count','partial')})


def project(receipt,layers,crosswalk,out_dir,progress):
    root = Path(out_dir) / '.projection-v2'
    root.mkdir(exist_ok=True)
    pins = {kind:receipt['ledgers'][name] for kind,name in
            (('member','exact_member_rows.jsonl'),('lifecycle','exact_lifecycle_rows.jsonl'))}
    result = json.loads(Path(receipt['result']['path']).read_bytes())
    spec = dict(schema='FRANKIE_COMPRESSED_PROJECTION_V1',chunk_bytes=CHUNK,
                layers=layers,crosswalk=crosswalk,code_sha256=sha(__file__),
                ledgers={k:{x:v[x] for x in ('path','bytes','sha256')} for k,v in pins.items()},
                sections=result['layers']['exact_lifecycle_and_runway_ledger']['section_summaries'],
                averages=result['layers']['averaged_companions'])
    manifest = root/'plan.json'
    if manifest.exists():
        if json.loads(manifest.read_bytes()) != spec:
            raise ValueError('retained projection plan differs')
    else:
        save(manifest,spec)
    plan = sha(manifest)
    cfg = dict(root=str(root),plan=plan,ledgers=pins,
               identities={k:list(file_identity(v['path'])) for k,v in pins.items()},
               member_paths={n:crosswalk[n]['member_paths'] for n in layers if crosswalk[n].get('member_paths')},
               section_layers={})
    for name in layers:
        for section in crosswalk[name].get('lifecycle_sections') or []:
            cfg['section_layers'].setdefault(section,[]).append(name)
    cfg['section_layers'].setdefault('mirror',[]).append('__section_mirror')
    ranges = {}
    workers = Workers(cfg)
    try:
        save(root/('workers-%d.json' % os.getpid()),workers.receipt())
        for kind,pin in pins.items():
            (root/kind).mkdir(exist_ok=True)
            jobs = [(kind,i,start,min(start+CHUNK,pin['bytes']))
                    for i,start in enumerate(range(0,pin['bytes'],CHUNK))]
            ranges[kind],position,count = [],0,0
            progress.update('root-projection-'+kind,total=pin['bytes'])
            for value in workers.ordered(_range,jobs):
                if (value['actual_start'] != position or value['actual_end'] < position
                        or value['source_identity'] != cfg['identities'][kind]):
                    raise ValueError('projection ranges have a gap, overlap or changed source')
                position=value['actual_end'];count+=value['rows']
                ranges[kind].append(value)
                progress.update('root-projection-'+kind,position,pin['bytes'],force=False)
                if shutil.disk_usage(root).free < 20<<30:
                    raise OSError('projection reserve reached; completed compressed ranges retained')
            if position != pin['bytes'] or count != pin['rows']:
                raise ValueError('projection complete ledger row/byte coverage differs')
            save(root/(kind+'-coverage-'+str(os.getpid())+'.json'),
                 dict(bytes=position,rows=count,plan=plan,range_count=len(jobs)))
        span = float(receipt.get('span_seconds') or 0)
        warmup,minimum=receipt.get('candidate_warmup_seconds'),receipt.get('candidate_min_observations')
        traversal={k:receipt.get(k) for k in ('verdict','failed_gates','groups','records','span_seconds',
                                             'candidate_warmup_seconds','candidate_min_observations')}
        traversal['span_seconds']=span
        traversal['failed_gates']=list(receipt.get('failed_gates') or [])
        outputs=[]
        for name in layers:
            record=crosswalk[name]
            entry=dict(layer=name,kind=record.get('kind'),producer=(record['module']+'.'+record['symbol'] if record.get('module') else None),
                       file=record.get('file'),line=record.get('line'),carrier=record.get('carrier'),
                       member_paths=list(record.get('member_paths') or []),
                       lifecycle_sections=list(record.get('lifecycle_sections') or []),
                       fixture_dependent_sections=list(record.get('fixture_dependent_sections') or []),
                       ledgers=list(record.get('ledgers') or []),notes=record.get('notes'),
                       crosswalk_commit=B.PIN_COMMIT,traversal=traversal,absent_paths={},
                       section_counts={s:0 for s in record.get('lifecycle_sections') or []})
            entry['member_count']=sum(r['fragments'].get(name,{}).get('rows',0) for r in ranges['member'])
            entry['lifecycle_count']=sum(r['fragments'].get(name,{}).get('rows',0) for r in ranges['lifecycle'])
            for kind in ranges:
                for r in ranges[kind]:
                    for k,v in r['absent'].get(name,{}).items():
                        entry['absent_paths'][k]=entry['absent_paths'].get(k,0)+v
                    for k,v in r['sections'].get(name,{}).items():
                        entry['section_counts'][k]=entry['section_counts'].get(k,0)+v
            entry['count']=entry['member_count']+entry['lifecycle_count']
            if entry['kind']=='NO_PRODUCER_FOUND':
                entry['status'],entry['reason']='could_not','NO_PRODUCER_FOUND: '+str(entry.get('notes') or 'the crosswalk found no producer')
            else:
                entry['status'],entry['reason']=B.status_of(entry['count'],bool(entry['fixture_dependent_sections']),span,warmup,minimum)
            entry['partial']=[dict(section=s,rows=0,reason=B.status_of(0,True,span,warmup,minimum)[1])
                              for s in entry['fixture_dependent_sections'] if entry['status']=='derived' and entry['section_counts'].get(s,0)==0]
            arrays={field:[dict(path=r['archive']['path'],**r['fragments'][name]) for r in ranges[kind] if name in r['fragments']]
                    for field,kind in (('member_rows','member'),('lifecycle_rows','lifecycle'))}
            outputs.append((name,entry,arrays))
        averages=spec['averages']
        if averages.get('key_alias_form')!='PLAIN':
            raise ValueError('plain companion keys required')
        for name,section_spec in B.SECTION_FILES.items():
            section=section_spec['section'];summary=spec['sections'].get(section)
            entry=dict(layer=name,section=section,kind=section_spec['kind'],producer=section_spec['producer'],
                       file=section_spec['file'],line=section_spec['line'],carrier=section_spec['carrier'],
                       member_paths=[],lifecycle_sections=list(section_spec['lifecycle_sections']),
                       fixture_dependent_sections=[],crosswalk_commit=B.PIN_COMMIT,traversal=traversal,
                       member_rows=[],lifecycle_rows=[],companion_rows=[],first_last_pairs=[],declarations=[],
                       matching_rule=None,summary=summary,section_counts={},absent_paths={},member_count=0,partial=[])
            arrays={}
            if section=='4.2':
                rows=[r for r in averages['rows'] if r.get('section')==section]
                entry['companion_rows']=rows
                entry['first_last_pairs']=list((summary or {}).get('first_last_pairs') or [])
                declarations={}
                for row in rows:
                    declared=dict(measure=row['measure'],kind=row.get('kind'),**(row.get('declaration') or {}))
                    if row['measure'] in declarations and declarations[row['measure']]!=declared:
                        raise ValueError('section 4.2 conflicting declaration')
                    declarations[row['measure']]=declared
                entry['declarations']=[declarations[m] for m in sorted(declarations)]
                entry['count']=len(rows)+len(entry['first_last_pairs']);entry['lifecycle_count']=0
            else:
                mirrors=[(r,'__section_mirror') for r in ranges['lifecycle'] if '__section_mirror' in r['fragments']]
                arrays['lifecycle_rows']=[dict(path=r['archive']['path'],**r['fragments'][n]) for r,n in mirrors];del entry['lifecycle_rows']
                entry['count']=entry['lifecycle_count']=sum(r['fragments'][n]['rows'] for r,n in mirrors)
                entry['section_counts']=dict(mirror=entry['count'])
                entry['matching_rule']=(summary or {}).get('matching_rule')
            entry['status'],entry['reason']=B.status_of(entry['count'],False,span,warmup,minimum)
            outputs.append((name,entry,arrays))
        published={}
        # Publication attempts are isolated; completed range archives remain reusable.
        import uuid
        destination=root/('published-'+uuid.uuid4().hex)
        destination.mkdir()
        jobs=[(str(destination/(name+'.json.gz')),entry,arrays) for name,entry,arrays in outputs]
        progress.update('root-projection-publication',total=len(jobs))
        for (name,entry,arrays),value in zip(outputs,workers.ordered(_publish,jobs)):
            published[name]=value
            progress.update('root-projection-publication',len(published),len(jobs))
        save(destination/'receipt.json',dict(plan=plan,layers=published,workers=workers.receipt()))
        return {n:published[n] for n in layers},{n:published[n] for n in B.SECTION_FILES}
    finally:
        workers.close()
