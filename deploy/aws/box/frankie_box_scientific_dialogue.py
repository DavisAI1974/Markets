"""Scientific teacher/Frankie dialogue through the existing durable session transport."""
import importlib
import json

def run_task(session, cache, *, role, phase, sources, reading_receipt,
             task_instruction, parse_final, request_hash, task_id,
             classroom_module, staged_module):
    """Retained exact-range retrieval over an immutable source inventory."""
    C=classroom_module
    science=importlib.import_module('research.kalshi.frankie_boss.dipole_scientific_review')
    request={'scientific_request_hash':request_hash}
    retained=dict(sources)
    reading=reading_receipt
    def call(name, prompt, parser, role):
        filename = 'science-call-' + science.digest(dict(name=name,prompt=prompt)) + '.json'
        saved = cache.load(filename,prompt)
        if saved is not None:
            science.validate_call(saved['record'],role=role,request_hash=request['scientific_request_hash'])
            return parser(saved['record']['response_text']),saved['record']
        def checked(text):
            try: return parser(text)
            except (ValueError,TypeError,KeyError) as error:
                raise C.ClassroomOutput(str(error)) from error
        parsed, transport = session._classroom_call(name,prompt,checked,'boss')
        actual = staged_module.retained_exchange(session,transport,prompt,role=role,
                                                request_hash=request['scientific_request_hash'])
        record=dict(role=role,request_hash=request['scientific_request_hash'],prompt=prompt,
            response_text=actual['response']['content'],
            transport=dict(job_id=actual['provider_job']['id'],status='COMPLETED',incomplete=False,
                prompt_sha256=actual['prompt']['sha256'],response_sha256=actual['response']['sha256']))
        science.validate_call(record,role=role,request_hash=request['scientific_request_hash'])
        parsed=parser(record['response_text'])
        cache.save(filename,prompt,dict(record=record))
        return parsed,record

    def interact(item, role, base_prompt, parse_final, extra_sources):
        available = dict(retained, **extra_sources)
        catalog=[dict(source_id=key, bytes=len(raw),sha256=science.hashlib.sha256(raw).hexdigest())
                 for key,raw in available.items()]
        index_id='source-index'
        available[index_id]=b''.join(science.canonical(item)+b'\n' for item in catalog)
        navigation={'reading_plan_hash':reading['plan_hash'],
            'source_index':dict(source_id=index_id,bytes=len(available[index_id]),
                               sha256=science.hashlib.sha256(available[index_id]).hexdigest()),
            'source_count':len(catalog),
            'instruction':'Read source-index to locate all full sources, staged assessments and completed exchanges. Exact byte ranges remain available; this index is navigation, not replacement knowledge.'}
        current = dict(navigation=navigation)
        turns=[]
        seen=set()
        def parse(text):
            value=json.loads(text)
            if type(value) is dict and set(value)=={'read_requests'}:
                asks=value['read_requests']
                if type(asks) is not list or not asks:
                    raise ValueError('nonempty read_requests required')
                for ask in asks:
                    if (type(ask) is not dict or set(ask)!={'source_id','start','end'}
                            or ask['source_id'] not in available
                            or type(ask['start']) is not int or type(ask['end']) is not int
                            or not 0 <= ask['start'] < ask['end'] <= len(available[ask['source_id']])):
                        raise ValueError('exact existing source range required')
                return value
            return dict(final=parse_final(text))
        while True:
            prompt=base_prompt(current)
            prompt+= ('\nBefore your final answer, retrieve task-specific evidence using '
                '{"read_requests":[{"source_id":"<catalog id>","start":0,"end":1000}]}. '
                'Offsets are UTF-8 bytes and must land on character boundaries. Ask for smaller ranges if a request '
                'does not fit the physical context. Every original source and prior exchange remains available. '
                'Reading assessments are navigation aids, not replacement evidence.\n')
            identity=role+'-'+phase+'-'+science.digest(dict(item=item['item_id'],prompt=prompt))[:24]
            if session._input_tokens(prompt) > 87000:
                raise ValueError('task instruction exceeds the physical context; full evidence remains retained')
            parsed,record=call('scientific-'+identity,prompt,parse,role)
            if 'final' in parsed:
                if not turns:
                    raise ValueError('a final assessment requires task-specific evidence retrieval; source delivery is not comprehension')
                return parsed['final'],record,turns
            query_hash=science.digest(parsed)
            if query_hash in seen:
                raise ValueError('scientific retrieval repeated the same request without progress; exchanges retained')
            seen.add(query_hash)
            turns.append(record)
            chunks=[]
            for ask in parsed['read_requests']:
                raw=available[ask['source_id']][ask['start']:ask['end']]
                try:
                    text=raw.decode('utf-8',errors='strict')
                except UnicodeError:
                    chunks.append(dict(request=ask,error='range cuts a UTF-8 character; revise byte endpoints'))
                    continue
                chunks.append(dict(request=ask,sha256=science.hashlib.sha256(raw).hexdigest(),content=text))
            next_context=dict(navigation=navigation,requested_ranges=chunks,
                              previous_request_hash=query_hash)
            # Measure the final wrapped prompt, with an allowance for the same retrieval instruction.
            if session._input_tokens(base_prompt(next_context)+prompt[prompt.rfind('\nBefore your final answer'):]) > 87000:
                next_context=dict(navigation=navigation,range_request=parsed,
                    error='Requested ranges plus the task exceed context. Request smaller ranges; nothing was clipped.')
            current=next_context
            turn_id='dialogue:'+role+':'+item['item_id']+':'+str(len(turns))
            available[turn_id]=science.canonical(record)
            catalog.append(dict(source_id=turn_id,bytes=len(available[turn_id]),
                sha256=science.hashlib.sha256(available[turn_id]).hexdigest()))
            available[index_id]=b''.join(science.canonical(item)+b'\n' for item in catalog)
            navigation['source_index'].update(bytes=len(available[index_id]),
                sha256=science.hashlib.sha256(available[index_id]).hexdigest())
            navigation['source_count']=len(catalog)


    parsed,call,turns=interact({'item_id':task_id},role,task_instruction,parse_final,{})
    return dict(parsed=parsed,call=call,context_calls=turns)


def run(session, correction, *, root, cache, classroom_module, staged_module):
    """Read the shared snapshot and full run, then retain review and reply jobs.

    Requests for evidence address exact UTF-8 byte ranges of pinned sources.
    No source is shortened to fit a synthesis. Earlier exchanges stay readable
    by source id, including every staged assessment and retrieval turn.
    """
    C = classroom_module
    science = importlib.import_module('research.kalshi.frankie_boss.dipole_scientific_review')
    knowledge = importlib.import_module('research.kalshi.frankie_boss.dipole_shared_knowledge')
    request = science.validate_request(correction['scientific_review_request'])
    descriptor = knowledge.validate_descriptor(request['shared_knowledge'])
    snapshot = knowledge.load_snapshot(root / 'request' / 'shared-knowledge' / descriptor['snapshot_hash'],
                                       expected_snapshot_hash=descriptor['snapshot_hash'])
    if knowledge.descriptor(snapshot) != descriptor:
        raise ValueError('box scientific knowledge differs from the host classroom snapshot')
    sources = []
    for record in descriptor['sources']:
        piece = knowledge.read_source(snapshot, record['source_id'], byte_start=0, byte_count=max(1,record['bytes']))
        if piece['start'] != 0 or piece['end'] != record['bytes'] or piece['eof'] is not True:
            raise ValueError('shared knowledge source is incomplete')
        content = piece['content'].encode('utf-8')
        sources.append(dict(source_id=record['source_id'], content=content,
                            sha256=record['sha256'], bytes=record['bytes']))
    for source_id, body in (('initial-response', request['initial_response']),
                            ('fact-review', request['fact_review']),
                            ('learning-history', request['learning_history'])):
        sources.append(dict(source_id=source_id, content=science.canonical(body)))
    reading = staged_module.consume_sources(session, sources, 'scientific_teacher', 'full-run-scientific-review',
        descriptor['snapshot_hash'], request['scientific_request_hash'], cache, request['instruction'])
    retained = {x['source_id']: x['content'] for x in sources}
    for part in reading['parts']:
        retained['reading-assessment:' + part['part_id']] = part['assessment'].encode('utf-8')

    reviews=[]
    for item in science.request_items(request):
        outcome=run_task(session,cache,role='scientific_teacher',phase='scientific-review',
            sources=retained,reading_receipt=reading,request_hash=request['scientific_request_hash'],
            task_id=item['item_id'],classroom_module=C,staged_module=staged_module,
            task_instruction=lambda context:science.review_prompt(request,item,context),
            parse_final=lambda text:science.parse_review(text,request,item))
        reviews.append(dict(review=outcome['parsed'],teacher_call=outcome['call'],
                            teacher_context_calls=outcome['context_calls']))
        retained['teacher-review:'+item['item_id']]=science.canonical(outcome['parsed'])
    result=science.exchange(request,reading=reading,reviews=reviews)
    replies=[]
    for item,entry in zip(science.request_items(request),reviews):
        outcome=run_task(session,cache,role='principal',phase='scientific-reply',
            sources=retained,reading_receipt=reading,request_hash=request['scientific_request_hash'],
            task_id=item['item_id'],classroom_module=C,staged_module=staged_module,
            task_instruction=lambda context:science.reply_prompt(request,item,entry['review'],context),
            parse_final=lambda text:science.parse_reply(text,item))
        replies.append(dict(parsed=outcome['parsed'],call=outcome['call']))
        entry['frankie_context_calls']=outcome['context_calls']
        retained['frankie-scientific-reply:'+item['item_id']]=science.canonical(outcome['parsed'])
    # Rebind additional retained retrieval turns before attaching the replies.
    result['reviews']=reviews
    result['exchange_hash']=science.digest({k:v for k,v in result.items() if k!='exchange_hash'})
    return science.attach_reply(request,result,replies)
