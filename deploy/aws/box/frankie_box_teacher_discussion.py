"""Two teaching roles discuss shared research through the existing durable transport."""
import importlib


def run(session,request,base,sources,*,cache,classroom_module,staged_module,run_task):
    S=importlib.import_module('research.kalshi.frankie_boss.dipole_scientific_review')
    D=importlib.import_module('research.kalshi.frankie_boss.dipole_teacher_discussion')
    S.validate_exchange(request,base)
    shared=list(sources)+[dict(source_id='classroom-exchange',content=S.canonical(base))]
    reading=staged_module.consume_sources(session,shared,D.BOSS_ROLE,'boss-teacher-shared-research',
        request['shared_knowledge']['snapshot_hash'],request['scientific_request_hash'],cache,
        'Read every shared research source and the complete classroom teacher/Frankie conversation. '
        'This is an added scientific responsibility of the original BOSS teacher. Preserve its representation '
        'supervision, mathematical targets, masks, controls and training responsibilities. Assess mechanisms '
        'and evidence, including ordinary and failed findings. A second occurrence is not the only scientific '
        'validation route. Retain uncertainty and disagreement; do not equate agreement with trading value.')
    retained={x['source_id']:x['content'] for x in shared}
    for part in reading['parts']:
        retained['boss-reading-assessment:'+part['part_id']]=part['assessment'].encode()
    entries=[]
    for item,review in zip(S.request_items(request),base['reviews']):
        prior=D.initial_turn(review)
        retained['teacher-discussion-input:'+item['item_id']]=S.canonical(prior)
        boss=run_task(session,cache,role=D.BOSS_ROLE,phase='boss-teacher-review',
            sources=retained,reading_receipt=reading,request_hash=request['scientific_request_hash'],
            task_id=item['item_id'],classroom_module=classroom_module,staged_module=staged_module,
            task_instruction=lambda context:D.teacher_prompt(request,item,D.BOSS_ROLE,prior,context),
            parse_final=lambda text:D.parse_teacher(text,request,item,prior))
        retained['boss-teacher:'+item['item_id']]=S.canonical(boss['parsed'])
        classroom=run_task(session,cache,role=D.CLASSROOM_ROLE,phase='classroom-teacher-reply',
            sources=retained,reading_receipt=base['reading'],request_hash=request['scientific_request_hash'],
            task_id=item['item_id'],classroom_module=classroom_module,staged_module=staged_module,
            task_instruction=lambda context:D.teacher_prompt(request,item,D.CLASSROOM_ROLE,boss['parsed'],context),
            parse_final=lambda text:D.parse_teacher(text,request,item,boss['parsed']))
        retained['classroom-teacher:'+item['item_id']]=S.canonical(classroom['parsed'])
        final=D.final_turn(boss['parsed'],classroom['parsed'])
        retained['teacher-discussion-final:'+item['item_id']]=S.canonical(final)
        frankie=run_task(session,cache,role='principal',phase='frankie-teacher-discussion-reply',
            sources=retained,reading_receipt=reading,request_hash=request['scientific_request_hash'],
            task_id=item['item_id'],classroom_module=classroom_module,staged_module=staged_module,
            task_instruction=lambda context:D.frankie_prompt(request,item,final,context),
            parse_final=lambda text:D.parse_frankie(text,item,final))
        retained['frankie-teacher-discussion:'+item['item_id']]=S.canonical(frankie['parsed'])
        entries.append(dict(item_id=item['item_id'],boss_teacher=boss,
            classroom_teacher=classroom,frankie=frankie))
    return D.attach(request,base,reading=reading,entries=entries)
