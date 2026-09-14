"""Single-writer controller transitions beside, never inside, native evidence."""
import json
import hashlib
try:
    from .c15_journal import EvidenceJournal, evidence_hash, pack, unpack
except ImportError:
    from c15_journal import EvidenceJournal, evidence_hash, pack, unpack

SCHEMA = 'BOSS_FRANKIE_CONTROLLER_JOURNAL_V1'


def _copy(value):
    return unpack(pack(value))


def _critic_links(state, payload):
    from research.kalshi.frankie_boss.granite_context import parse_native_context, build_native_prompt, score_native
    from research.kalshi.frankie_boss.granite_shadow import GraniteIdentity, ShadowRequest
    intent = state['critic_intent']
    config = state['intent']['configuration']
    try:
        if set(payload) != {'intent_hash','receipt'}:
            raise ValueError('invalid critic completion fields')
        receipt = payload['receipt']
        if set(receipt) != {'shadow','config_hash','call_hash','provider_json','error_type'}:
            raise ValueError('invalid service receipt fields')
        shadow = receipt['shadow']
        if set(shadow) != {'request','status','response','verdict'}:
            raise ValueError('invalid shadow receipt fields')
        request = ShadowRequest(**{**shadow['request'],
            'identity':GraniteIdentity(**shadow['request']['identity'])})
        snapshot = parse_native_context(intent['snapshot_text'],expected_hash=intent['snapshot_hash'])
        prompt = build_native_prompt(snapshot)
        call_hash = hashlib.sha256(json.dumps(dict(config_hash=receipt['config_hash'],
            request_hash=request.request_hash),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        if (receipt['config_hash'] != config['critic_config_hash'] or receipt['call_hash'] != call_hash
                or request.request_id != intent['attempt_id']
                or request.identity.identity_hash != config['critic_identity_hash']
                or type(request.timeout_seconds) not in (int,float)
                or request.timeout_seconds != config['critic_timeout']
                or request.snapshot_text != snapshot.text or request.snapshot_hash != snapshot.hash
                or request.prompt_text != prompt.text or intent['prompt_text'] != prompt.text):
            raise ValueError('critic completion differs from durable request')
        body = json.loads(snapshot.text)
        source = state['intent']['request']
        if (unpack(body['receipt']) != intent['context'] or body['packet_hash'] != intent['packet_hash']
                or body['source_as_of'] != source['source_as_of']
                or intent['context']['as_of'] != source['as_of']
                or intent['context']['source_prefix_hash'] != source['source_hash']):
            raise ValueError('critic snapshot differs from controller source intent')
        if shadow['status'] not in ('accepted','rejected','timeout','transport_error','malformed_response','binding_mismatch'):
            raise ValueError('unsupported stored critic status')
        if shadow['status'] in ('accepted','rejected'):
            response = shadow['response']
            if (set(response) != {'request_hash','identity_hash','text'}
                    or response['request_hash'] != request.request_hash
                    or response['identity_hash'] != config['critic_identity_hash']):
                raise ValueError('critic response identity mismatch')
            _,verdict = score_native(response['text'],snapshot)
            if shadow['verdict'] != verdict.name or (shadow['status'] == 'accepted') != (verdict.name == 'L4'):
                raise ValueError('stored critic status differs from parser verdict')
    except (KeyError,TypeError,json.JSONDecodeError) as exc:
        raise ValueError('malformed stored critic completion') from exc


def _result_links(state, key, payload):
    if payload.get('request_id') != key or payload.get('request_hash') != state['request_hash']:
        raise ValueError('combined result request identity mismatch')
    native = state['native']
    if not native['publications']:
        if (set(payload) != {'request_id','request_hash','status','records'}
                or payload['status'] != 'idle' or payload['records'] != ()):
            raise ValueError('idle result must contain no publications')
        return
    if (set(payload) != {'request_id','request_hash','status','records','critic','critic_hash','native_checkpoint'}
            or evidence_hash(payload['critic']) != evidence_hash(state['critic_result'])
            or payload['critic_hash'] != evidence_hash(state['critic_result'])
            or payload['native_checkpoint'] != native['checkpoint']
            or type(payload['records']) is not tuple or len(payload['records']) != len(native['publications'])):
        raise ValueError('combined result differs from durable native/critic completion')
    try:
        from .frankie_category_free import CategoryFreeRecord
    except ImportError:
        from frankie_category_free import CategoryFreeRecord
    all_native = True
    for record,publication in zip(payload['records'],native['publications']):
        if (type(record) is not dict or set(record) != {'target','revision','publication_hash',
                'artifact_digest','record_json','record_digest'} or
                any(record[k] != publication[k] for k in publication)):
            raise ValueError('combined record differs from native publication')
        try:
            raw = json.loads(record['record_json'])
            stamp = raw['stamp']
            checked = CategoryFreeRecord(json.dumps(raw['payload']),stamp['artifact_digest'],
                stamp['publication_hash'],stamp['reproduction_status'])
            if (checked.to_json() != record['record_json'] or checked.digest != record['record_digest']
                    or (checked.artifact_digest is not None and
                        (checked.artifact_digest != publication['artifact_digest']
                         or checked.publication_hash != publication['publication_hash']))):
                raise ValueError('combined Frankie record identity mismatch')
            all_native = all_native and checked.artifact_digest is not None
        except (KeyError,TypeError,json.JSONDecodeError) as exc:
            raise ValueError('malformed combined Frankie record') from exc
    expected = 'complete' if state['critic_result']['receipt']['shadow']['status'] == 'accepted' and all_native else 'incomplete'
    if payload['status'] != expected:
        raise ValueError('combined result status differs from native/critic evidence')


class ControllerJournal:
    def __init__(self, path, *, create=False, checkpoint=None):
        if type(create) is not bool or create == (checkpoint is not None):
            raise ValueError('create new journal or supply trusted checkpoint')
        self.journal = EvidenceJournal(path, create=create)
        self._requests = {}
        self._failed = False
        try:
            if checkpoint is not None:
                if (type(checkpoint) is not dict or set(checkpoint) != {'schema','count','head_hash'}
                        or checkpoint['schema'] != SCHEMA or type(checkpoint['count']) is not int
                        or checkpoint['count'] < 0 or type(checkpoint['head_hash']) is not str
                        or len(checkpoint['head_hash']) != 64):
                    raise ValueError('invalid controller checkpoint')
                self.journal.verify(count=checkpoint['count'], head_hash=checkpoint['head_hash'])
                for entry in self.journal.entries():
                    if entry['kind'] != SCHEMA:
                        raise ValueError('unknown controller journal entry')
                    self._transition(entry['payload'], commit=True)
        except Exception:
            self.journal.close()
            raise

    def _active(self):
        if self._failed:
            raise ValueError('controller journal uncertain; restore trusted checkpoint')
        try:
            self.journal.verify(count=self.journal.count,head_hash=self.journal.head_hash)
        except Exception:
            self._failed = True
            raise

    def _transition(self, event, *, commit):
        if type(event) is not dict or set(event) != {'request_id','request_hash','step','payload'}:
            raise ValueError('malformed controller event')
        key, step, payload = event['request_id'], event['step'], event['payload']
        if type(key) is not str or not key.strip() or type(payload) is not dict:
            raise ValueError('explicit request ID and payload required')
        previous = self._requests.get(key)
        state = _copy(previous) if previous is not None else None
        if step == 'INTENT':
            if state is not None or evidence_hash(payload) != event['request_hash']:
                raise ValueError('duplicate or corrupt controller intent')
            state = dict(request_hash=event['request_hash'], intent=payload, native=None,
                         critic_intent=None, critic_result=None, result=None, attempts=())
        else:
            if state is None or state['request_hash'] != event['request_hash'] or state['result'] is not None:
                raise ValueError('controller transition lacks matching unfinished intent')
            if step == 'NATIVE_COMPLETE':
                if state['native'] is not None or set(payload) != {'publications','checkpoint'}:
                    raise ValueError('native completion transition invalid')
                state['native'] = payload
            elif step == 'CRITIC_INTENT':
                old = state['critic_intent']
                if (state['native'] is None or not state['native']['publications']
                        or state['critic_result'] is not None
                        or type(payload.get('attempt_id')) is not str or not payload['attempt_id'].strip()
                        or payload['attempt_id'] in state['attempts']
                        or payload.get('supersedes') != (old['attempt_id'] if old else None)):
                    raise ValueError('critic attempt requires explicit unknown-call recovery identity')
                state['critic_intent'] = payload
                state['attempts'] += (payload['attempt_id'],)
            elif step == 'CRITIC_RESULT':
                if (state['critic_intent'] is None or state['critic_result'] is not None
                        or payload.get('intent_hash') != evidence_hash(state['critic_intent'])):
                    raise ValueError('critic result does not bind current attempt')
                _critic_links(state,payload)
                state['critic_result'] = payload
            elif step == 'RESULT':
                if (state['native'] is None or
                        (state['native']['publications'] and state['critic_result'] is None)):
                    raise ValueError('combined result requires native and critic completion')
                _result_links(state,key,payload)
                state['result'] = payload
            else:
                raise ValueError('unknown controller transition')
        if commit:
            self._requests[key] = _copy(state)

    def _append(self, event):
        self._active()
        event = _copy(event)
        self._transition(event, commit=False)
        self._failed = True
        self.journal.append(SCHEMA, event)
        self._transition(event, commit=True)
        self._failed = False

    def begin(self, request_id, payload):
        self._active()
        digest = evidence_hash(payload)
        if request_id in self._requests:
            if self._requests[request_id]['request_hash'] != digest:
                raise ValueError('request ID reused with changed inputs')
        else:
            self._append(dict(request_id=request_id,request_hash=digest,step='INTENT',payload=payload))
        return self.state(request_id)

    def state(self, request_id):
        self._active()
        return _copy(self._requests[request_id])

    def record(self, request_id, step, payload):
        self._append(dict(request_id=request_id,request_hash=self._requests[request_id]['request_hash'],
                          step=step,payload=payload))
        return self.state(request_id)

    def checkpoint(self):
        self._active()
        return dict(schema=SCHEMA,count=self.journal.count,head_hash=self.journal.head_hash)

    def close(self):
        self.journal.close()
