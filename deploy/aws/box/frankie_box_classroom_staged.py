"""Full-source classroom transport with bounded observation claim pages.

All pages are required. Deterministic joins preserve Frankie's values; only the
host's existing governed teacher grades them. The original teacher is unchanged.
"""
import hashlib
import importlib
import json
import math
from pathlib import Path
import urllib.request
from concurrent.futures import ThreadPoolExecutor

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def cursor_pages(roster,size=128):
    if (type(roster) is not list or not roster or type(size) is not int or size<1
            or any(type(x) is not int or x<0 for x in roster)
            or any(a>=b for a,b in zip(roster,roster[1:]))):
        raise ValueError('complete ordered current cursor roster required')
    return [roster[i:i+size] for i in range(0,len(roster),size)]

def collect_observations(pages,expected_cursors):
    cursor_pages(list(expected_cursors))
    result=[point for page in pages for point in page]
    if any(type(p) is not dict or type(p.get('cursor')) is not int for p in result):
        raise ValueError('integer observation cursors required')
    if [p.get('cursor') for p in result]!=list(expected_cursors):
        raise ValueError('observation pages omit, repeat or reorder current cursors')
    for point in result:
        if (type(point) is not dict or set(point)!={'cursor','state','value','explanation'}
                or point['state'] not in ('PRESENT','MISSING','INVALID','ABLATED')
                or type(point['explanation']) is not str or not point['explanation'].strip()):
            raise ValueError('complete observation claim required')
        if point['state']=='PRESENT':
            if type(point['value']) not in (float,int) or not math.isfinite(point['value']):
                raise ValueError('PRESENT claim requires a finite value')
        elif point['value'] is not None:
            raise ValueError('non-PRESENT claim requires null value')
    return result

def ensure_snapshot(descriptor,root):
    K=importlib.import_module('research.kalshi.frankie_boss.dipole_shared_knowledge')
    descriptor=K.validate_descriptor(descriptor)
    destination=Path(root)/'request'/'shared-knowledge'/descriptor['snapshot_hash']
    if (destination/'MANIFEST.json').exists():
        snapshot=K.load_snapshot(destination,descriptor['snapshot_hash'])
    else:
        def fetch(entry):
            if entry['provenance'].get('repository')!='DavisAI1974/Markets':
                raise ValueError('shared source repository differs')
            import re
            if not re.fullmatch('[0-9a-f]{40}',entry['revision']):
                raise ValueError('shared source needs an immutable commit')
            url='https://raw.githubusercontent.com/DavisAI1974/Markets/'+entry['revision']+'/'+entry['path']
            with urllib.request.urlopen(url,timeout=60) as response:
                return response.read(entry['bytes']+1)
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures={entry['id']:pool.submit(fetch,entry) for entry in descriptor['catalog']['sources']}
            snapshot=K.build_snapshot(descriptor['catalog'],lambda entry:futures[entry['id']].result(),destination)
    if K.descriptor(snapshot)!=descriptor:
        raise ValueError('shared snapshot differs from the host classroom')
    sources=[]
    for entry in descriptor['sources']:
        part=K.read_source(snapshot,entry['source_id'],0,max(1,entry['bytes']))
        if part['end']!=entry['bytes'] or not part['eof']:
            raise ValueError('complete shared source required')
        sources.append(dict(source_id=entry['source_id'],content=part['content'].encode(),
                            sha256=entry['sha256'],bytes=entry['bytes']))
    return sources

def run(session,C,cache,*,root,staged,dialogue):
    visible=C.visible_of(session.request)
    pre=visible['pre_message']
    descriptor=pre['shared_knowledge']
    sources=ensure_snapshot(descriptor,root)
    context={k:v for k,v in pre.items() if k not in ('components','learning_history','shared_knowledge','relationship_review')}
    sources += [dict(source_id='classroom-context',content=canonical(context)),
                dict(source_id='learning-history',content=canonical(pre.get('learning_history'))),
                dict(source_id='current-relation-guidance',content=canonical(pre.get('relationship_review')))]
    for comp in C.components(visible):
        sources.append(dict(source_id='current-component:'+comp['name'],content=canonical(comp)))
    for name in ('merged-notes.md','derivation-digest-full.md'):
        path=session.work/name
        if path.is_file():sources.append(dict(source_id=name,content=path.read_bytes()))
    if pre['mode'] in ('SOCRATIC','VERIFY') and not any(x['source_id']=='derivation-digest-full.md' for x in sources):
        raise ValueError('independent classroom requires complete current evidence')
    reading=staged.consume_sources(session,sources,'principal','classroom-all-sources',
        descriptor['snapshot_hash'],session.request_sha256,cache,
        'Read the complete Dipole research and current classroom evidence. Preserve every source, observation, prior '
        'lesson, correction, failure and uncertainty. Earlier learning remains usable in this knowledge-primed replay. '
        'The original governed teacher role and mathematics remain in place; scientific dialogue is additive.')
    cache.save('staged-reading.json',reading['plan_hash'],dict(receipt=reading))
    retained={x['source_id']:x['content'] for x in sources}
    for part in reading['parts']:
        retained['reading-assessment:'+part['part_id']]=part['assessment'].encode()
    thin=dict(visible,pre_message={k:v for k,v in pre.items() if k!='learning_history'})
    head=C._head(thin,session.cycle,session.request['request_id'])
    calls=[]
    def task(name,instruction,parse):
        result=dialogue.run_task(session,cache,role='principal',phase='classroom',
            sources=retained,reading_receipt=reading,task_instruction=lambda nav:(
                head+'\n'+instruction+'\nSource navigation: '+canonical(nav).decode()),
            parse_final=parse,request_hash=session.request_sha256,task_id=name,
            classroom_module=C,staged_module=staged)
        calls.extend(result['context_calls']+[result['call']])
        retained['classroom-answer:'+name]=canonical(result['parsed'])
        return result['parsed']
    outputs={}
    roster=list(pre['observation_cursor_roster'])
    mode=pre['mode']
    for comp in C.components(visible):
        name=comp['name']
        rights=[p['right'] for p in C.pairs_of(visible,name)]
        observations=None
        if mode!='TEACH':
            pages=[]
            for number,cursors in enumerate(cursor_pages(roster)):
                instruction=('Derive your own current observation claims for '+name+'. Read current-component:'+name+
                    ' and the exact current evidence needed; prior history is available but is not a new current observation. '
                    'Account for exactly these cursors, in order: '+canonical(cursors).decode()+
                    '. Return exactly {"observations":[{"cursor":<integer>,"state":"PRESENT|MISSING|INVALID|ABLATED",'
                    '"value":<finite number for PRESENT, otherwise null>,"explanation":"your own reading"}]}. '
                    'This is one page of a complete review; every page is retained and joined without repairing your values.')
                def parse(text,cursors=cursors):
                    value=json.loads(text)
                    if type(value) is not dict or set(value)!={'observations'}:
                        raise ValueError('observation page object required')
                    return collect_observations([value['observations']],cursors)
                pages.append(task('observations:'+name+':'+str(number),instruction,parse))
            observations=collect_observations(pages,roster)
            retained['model-observations:'+name]=canonical(observations)
        states=C._states_present(comp) if mode=='TEACH' else list(C.STATES)
        schema={field:'nonempty explanation in your own words' for field in C.NARRATIVE}
        schema['state_explanations']={state:'explain this state where it occurs' for state in states}
        schema['pairs']=[dict(right=right,correlation_interpretation='evidence and limitations',developing_structure=None,
                             **({} if mode=='TEACH' else dict(direction_relation='SAME_DIRECTION|OPPOSITE_DIRECTION|UNRESOLVED')))
                         for right in rights]
        if mode!='TEACH':
            schema.update(state_counts={state:0 for state in C.STATES},
                          terminal_state='PRESENT|MISSING|INVALID|ABLATED',direction='RISE|FALL|FLAT|INSUFFICIENT')
        instruction=('Interpret the complete component '+name+' and every listed pair. Read current-component:'+name+
            ', current-relation-guidance and both components of each pair. Your complete prior learning and research '
            'remain available. '+('Teacher values are given; interpret them as taught.' if mode=='TEACH' else
            'Your complete observation claims are at model-observations:'+name+'. Derive your own counts, terminal state and direction; host grading remains independent.')+
            ' Return one JSON object following this schema: '+canonical(schema).decode()+
            '. Do not emit observations again; all observation pages remain retained. Developing structures are null '
            'or explicitly prefixed HYPOTHESIS:. Do not confuse scoped scientific support with trading profitability.')
        def parse(text,comp=comp,rights=rights,observations=observations):
            value=json.loads(text)
            if mode!='TEACH':value=dict(value,observations=observations)
            return C.parse_component(json.dumps(value),comp,rights,mode=mode)
        outputs[name]=task('component:'+name,instruction,parse)
    instruction=C.summary_prompt(thin,outputs,cycle=session.cycle,request_id=session.request['request_id']).split('----- TASK -----\n',1)[1]
    summary=task('summary','Review the complete component answers and all 171 pair interpretations in classroom-answer sources. '+instruction,C.parse_summary)
    built=C.assemble(visible,outputs,summary)
    report=C.validate(visible,built['ledgers'])
    cache.publish(built['ledgers'],C.render_markdown(built['ledgers'],built['dropped_findings']),
        dict(schema='FRANKIE_BOX_CLASSROOM_RECEIPT_V1',report=report,composition=C.COMPOSITION,
            dropped_findings=built['dropped_findings'],calls=calls,staged_reading_plan_hash=reading['plan_hash'],
            teacher_message_hash=pre['teacher_message_hash'],classroom_binding_hash=visible['binding']['classroom_binding_hash']))
    return built['ledgers']
