"""Explicit authoritative B1 refresh plus required configured Granite critic."""
from dataclasses import asdict
import hashlib
import inspect
import json
import math
from pathlib import Path
import threading

try:
    from .c15_journal import evidence_hash, pack, unpack
    from .forecast_artifact import DecoderSnapshot
    from .native_forecast_refresh import native_execution_hash
except ImportError:
    from c15_journal import evidence_hash, pack, unpack
    from forecast_artifact import DecoderSnapshot
    from native_forecast_refresh import native_execution_hash


def native_model_pin(bridge):
    """Inspect effective model identity; an independent caller must trust the pin."""
    return evidence_hash(dict(native=bridge.context._model_hash(),
        execution=native_execution_hash(bridge.context.model),
        decoder=DecoderSnapshot.capture(bridge.decoder).digest))


class FrankieForecastController:
    def __init__(self, *, enabled=False, legacy=None, bridge=None, journal=None,
                 critic=None, expected_native_hash=None, expected_critic_config_hash=None,
                 expected_critic_identity_hash=None, context_encoding='native_v1', event=None):
        if type(enabled) is not bool:
            raise ValueError('explicit boolean enable flag required')
        self.enabled, self.legacy = enabled, legacy
        if not enabled:
            return
        if event is not None and not callable(event):
            raise ValueError('controller event must be callable')
        self.event = event
        from research.kalshi.frankie_boss.granite_context_route import context_route
        self.context_encoding = context_route(context_encoding).encoding
        if (critic is None or getattr(critic, 'enabled', False) is not True
                or not callable(getattr(critic, context_route(self.context_encoding).method, None))):
            raise ValueError('enabled critic for selected context encoding required')
        self.bridge, self.journal, self.critic = bridge, journal, critic
        self.expected_native_hash = expected_native_hash
        self.expected_critic_config_hash = expected_critic_config_hash
        self.expected_critic_identity_hash = expected_critic_identity_hash
        self._busy = threading.Lock()
        self._validate_pins()

    def _observe(self, phase, **values):
        """Operational phase only; no prompts, market values or credentials."""
        if self.event is not None:
            self.event(dict(phase=phase, **values))

    def _validate_pins(self):
        try:
            from .forecast_contract import sha256_digest
        except ImportError:
            from forecast_contract import sha256_digest
        for name,value in (('native',self.expected_native_hash),('critic config',self.expected_critic_config_hash),
                           ('critic identity',self.expected_critic_identity_hash)):
            sha256_digest(value,name)
        timeout = self.critic.request_timeout
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('critic timeout must be explicit finite positive number')
        if (self.critic.enabled is not True or
                self.critic.config_hash != self.expected_critic_config_hash or
                self.critic.identity.identity_hash != self.expected_critic_identity_hash):
            raise ValueError('critic differs from independently trusted pins')
        if native_model_pin(self.bridge) != self.expected_native_hash:
            raise ValueError('native model differs from independently trusted pin')

    def _configuration(self):
        from research.kalshi.frankie_boss.granite_context_route import context_route
        route = context_route(self.context_encoding)
        route.validate_identity(self.critic.identity)
        source = inspect.getsourcefile(type(self.critic))
        if source is None:
            raise ValueError('critic implementation source identity required')
        return dict(context_encoding=self.context_encoding,
            native_hash=self.expected_native_hash,critic_config_hash=self.expected_critic_config_hash,
            critic_identity_hash=self.expected_critic_identity_hash,
            critic_timeout=self.critic.request_timeout,
            targets=tuple(asdict(t) for t in self.bridge.targets),policy=asdict(self.bridge.policy),
            entity=self.bridge.context.entity,
            code={name:Path(__file__).with_name(name).read_bytes() for name in
                  ('frankie_controller.py','controller_journal.py','granite_context.py',
                   'granite_context_compact.py','granite_context_route.py','granite_shadow.py')},
            transport_code=Path(source).read_bytes())

    def _snapshot(self, publications, *, as_of, source_as_of, source_hash, through_cursor):
        from research.kalshi.frankie_boss import granite_context as mapper
        try:
            from .forecast_artifact import NativeForecastArtifact
            from .frankie_forecast_consumer import _computation_binding
        except ImportError:
            from forecast_artifact import NativeForecastArtifact
            from frankie_forecast_consumer import _computation_binding
        runner = self.bridge.context
        tokens,info,input_hash,_,context = runner._prepare(as_of, through_cursor)
        receipt = mapper.ContextReceipt(**info,input_hash=input_hash,model_hash=runner._model_hash())
        if receipt.source_prefix_hash != source_hash:
            raise ValueError('critic context differs from requested source')
        packet = None
        for pub in publications:
            artifact = NativeForecastArtifact.from_payload(pub.selected.forecast_artifact,
                                                           expected_digest=pub.selected.candidate_id)
            binding = _computation_binding(artifact)
            candidate = pub.selected
            if (candidate.as_of != as_of or candidate.source_as_of != source_as_of
                    or candidate.source_hash != source_hash or candidate.model_hash != self.expected_native_hash
                    or artifact.input_hash != input_hash or
                    pack(binding['context']) != pack(asdict(receipt))):
                raise ValueError('native publication and critic context disagree')
            current_packet = binding['recurrence']['packet_hash']
            if packet is not None and packet != current_packet:
                raise ValueError('publications do not share one critic input packet')
            packet = current_packet
        qsv_binding = None
        if runner.qsv is not None:
            _,_,qsv_binding = runner.qsv.attach(context,expected_hash=runner.expected_qsv_hash,
                                               device=tokens['qsv'].device)
        snapshot = mapper.map_native_context(tokens=tokens,receipt=receipt,entity=runner.entity,
            registry=runner.model.trunk.registry,expected_input_hash=input_hash,
            expected_packet_hash=packet,source_as_of=source_as_of,expected_qsv_binding=qsv_binding)
        from research.kalshi.frankie_boss.granite_context_route import context_route
        route = context_route(self.context_encoding)
        encoded = route.encode(snapshot)
        return encoded,route.build_prompt(encoded),asdict(receipt),packet,snapshot.hash

    def _critic_result(self, receipt, *, snapshot, prompt, attempt_id):
        from research.kalshi.frankie_boss.granite_context_route import context_route
        shadow = receipt.shadow
        request = shadow.request
        if (receipt.config_hash != self.expected_critic_config_hash
                or request.identity.identity_hash != self.expected_critic_identity_hash
                or request.request_id != attempt_id or request.snapshot_hash != snapshot.hash
                or request.snapshot_text != snapshot.text or request.prompt_text != prompt.text
                or type(request.timeout_seconds) not in (int,float)
                or request.timeout_seconds != self.critic.request_timeout):
            raise ValueError('critic receipt differs from exact requested context/configuration')
        expected_call = hashlib.sha256(json.dumps(dict(config_hash=receipt.config_hash,
            request_hash=request.request_hash),sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()
        if receipt.call_hash != expected_call:
            raise ValueError('critic call hash differs from configured request')
        if shadow.status not in ('accepted','rejected','timeout','transport_error','malformed_response','binding_mismatch'):
            raise ValueError('unsupported critic status')
        if shadow.status in ('accepted','rejected'):
            response = shadow.response
            if (response is None or response.request_hash != request.request_hash
                    or response.identity_hash != self.expected_critic_identity_hash):
                raise ValueError('critic response lacks exact request identity')
            _,verdict = context_route(self.context_encoding).score(response.text,snapshot)
            if shadow.verdict != verdict.name or (shadow.status == 'accepted') != (verdict.name == 'L4'):
                raise ValueError('critic status differs from independently parsed output')
        return asdict(receipt)

    async def refresh(self, *, request_id=None, sessions=None, expected_sessions_hash=None,
                      arm_hash=None, as_of=None, source_as_of=None, source_hash=None,
                      through_cursor=None, metadata=None, material=False, recovery_attempt_id=None):
        if not self.enabled:
            return self.legacy()
        if not self._busy.acquire(blocking=False):
            raise ValueError('controller already has a run in flight')
        try:
            self._observe('source_validation', through_cursor=through_cursor)
            return await self._refresh(request_id=request_id,sessions=sessions,
                expected_sessions_hash=expected_sessions_hash,arm_hash=arm_hash,as_of=as_of,
                source_as_of=source_as_of,source_hash=source_hash,through_cursor=through_cursor,
                metadata=metadata,material=material,recovery_attempt_id=recovery_attempt_id)
        except Exception:
            try:
                self._observe('request_failed', through_cursor=through_cursor)
            except Exception:
                pass  # Preserve the original failure, including diagnostic I/O failure.
            raise
        finally:
            self._busy.release()

    async def _refresh(self, *, request_id, sessions, expected_sessions_hash, arm_hash,
                       as_of, source_as_of, source_hash, through_cursor, metadata,
                       material, recovery_attempt_id):
        try:
            from .native_forecast_refresh import session_registry_hash
            from .forecast_contract import sha256_digest
            from .frankie_contract import BLD1_FIELDS, BLD1_FIELD_NAMES
            from .frankie_forecast_consumer import consume_forecast
        except ImportError:
            from native_forecast_refresh import session_registry_hash
            from forecast_contract import sha256_digest
            from frankie_contract import BLD1_FIELDS, BLD1_FIELD_NAMES
            from frankie_forecast_consumer import consume_forecast
        self._validate_pins()
        config = self._configuration()
        if (type(request_id) is not str or not request_id.strip()
                or type(through_cursor) is not int or through_cursor < 0
                or type(as_of) is not int or type(source_as_of) is not int
                or source_as_of > as_of or type(material) is not bool
                or session_registry_hash(sessions) != expected_sessions_hash
                or type(metadata) is not tuple or len(metadata) != len(sessions)):
            raise ValueError('explicit request, cursor, complete sessions and metadata required')
        for name,value in (('source',source_hash),('arm',arm_hash),('sessions',expected_sessions_hash)):
            sha256_digest(value,name)
        active = tuple(t for t in self.bridge.targets if t.target_ns > as_of)
        if tuple(t for t,_ in sessions) != active:
            raise ValueError('all active targets required in registry order')
        for target,session in sessions:
            session.validate_for_publication()
            self.bridge.policy.interval(target.target_ns-as_of)
            if (target.instrument != session.instrument or target.target_ns != session.close_ns
                    or (session.event_cutoff_ns,session.receive_cutoff_ns,session.source_hash)
                    != (source_as_of,as_of,source_hash)):
                raise ValueError('session differs from native request target or causal source')
        required = set(BLD1_FIELD_NAMES)-{'guessed_net_usd','overnight_gap_usd','path_p50_curve','confidence'}
        owned_metadata = []
        for pair,(target,_) in zip(metadata,sessions):
            if (type(pair) is not tuple or len(pair) != 2 or pair[0] != target.digest
                    or type(pair[1]) is not dict or set(pair[1]) != required):
                raise ValueError('exact complete per-target Frankie metadata required')
            copied = unpack(pack(pair[1]))
            for field in BLD1_FIELDS:
                if field.name in copied:
                    field.validate(copied[field.name])
            owned_metadata.append((pair[0],copied))
        native_args = dict(sessions=sessions,expected_sessions_hash=expected_sessions_hash,arm_hash=arm_hash,
            as_of=as_of,source_as_of=source_as_of,source_hash=source_hash,
            through_cursor=through_cursor,material=material)
        intent = dict(schema='BOSS_FRANKIE_CONTROLLER_V1',configuration=config,
            request={**native_args,'sessions':tuple((asdict(t),asdict(s)) for t,s in sessions)},
            metadata=tuple(owned_metadata))
        state = self.journal.begin(request_id,intent)
        if state['result'] is not None:
            self._observe('completed_result_reused', through_cursor=through_cursor,
                          status=state['result']['status'])
            return state['result']
        source = self.bridge.context.builder.journal
        source_state = source.count,source.head_hash

        def unchanged():
            self._validate_pins()
            source.verify(count=source_state[0],head_hash=source_state[1])
            if self._configuration() != config or (source.count,source.head_hash) != source_state:
                raise ValueError('controller source or configuration changed during attempt')

        if state['native'] is None:
            self._observe('native_reasoning', through_cursor=through_cursor)
            publications = self.bridge.update(**native_args)
            unchanged()
            state = self.journal.record(request_id,'NATIVE_COMPLETE',dict(
                publications=tuple(dict(publication_hash=p.receipt_hash,artifact_digest=p.selected.candidate_id,
                    target=asdict(p.selected.target),revision=p.revision) for p in publications),
                checkpoint=self.bridge.book.checkpoint()))
        publications = tuple(self.bridge.book.publication(p['publication_hash']) for p in state['native']['publications'])
        self._observe('native_complete', through_cursor=through_cursor, count=len(publications))
        if not publications:
            result = dict(request_id=request_id,request_hash=state['request_hash'],status='idle',records=())
            self.journal.record(request_id,'RESULT',result)
            self._observe('output_persisted', through_cursor=through_cursor, count=0, status='idle')
            return result
        snapshot,prompt,context_receipt,packet_hash,native_snapshot_hash = self._snapshot(publications,as_of=as_of,
            source_as_of=source_as_of,source_hash=source_hash,through_cursor=through_cursor)
        unchanged()
        if state['critic_result'] is None:
            previous = state['critic_intent']
            if previous is not None and recovery_attempt_id is None:
                raise ValueError('critic completion unknown; explicit recovery attempt required')
            attempt_id = recovery_attempt_id or evidence_hash(dict(request_id=request_id,request_hash=state['request_hash']))
            critic_intent = dict(attempt_id=attempt_id,supersedes=previous['attempt_id'] if previous else None,
                context_encoding=self.context_encoding,native_snapshot_hash=native_snapshot_hash,
                snapshot_hash=snapshot.hash,snapshot_text=snapshot.text,prompt_text=prompt.text,
                context=context_receipt,packet_hash=packet_hash,config_hash=self.expected_critic_config_hash,
                identity_hash=self.expected_critic_identity_hash)
            self._observe('critic_request', through_cursor=through_cursor)
            state = self.journal.record(request_id,'CRITIC_INTENT',critic_intent)
            from research.kalshi.frankie_boss.granite_context_route import context_route
            method = getattr(self.critic, context_route(self.context_encoding).method)
            receipt = await method(snapshot,request_id=attempt_id)
            unchanged()
            payload = self._critic_result(receipt,snapshot=snapshot,prompt=prompt,attempt_id=attempt_id)
            state = self.journal.record(request_id,'CRITIC_RESULT',dict(
                intent_hash=evidence_hash(critic_intent),receipt=payload))
        critic = state['critic_result']
        self._observe('critic_complete', through_cursor=through_cursor,
                      status=critic['receipt']['shadow']['status'])
        metadata_map = dict(owned_metadata)
        records = []
        all_native = True
        for publication in publications:
            record = consume_forecast(enabled=True,legacy=None,book=self.bridge.book,
                publication_hash=publication.receipt_hash,metadata=metadata_map[publication.selected.target.digest])
            records.append(dict(target=asdict(publication.selected.target),revision=publication.revision,
                publication_hash=publication.receipt_hash,artifact_digest=publication.selected.candidate_id,
                record_json=record.to_json(),record_digest=record.digest))
            all_native = all_native and record.artifact_digest is not None
        unchanged()
        result = dict(request_id=request_id,request_hash=state['request_hash'],
            status='complete' if critic['receipt']['shadow']['status'] == 'accepted' and all_native else 'incomplete',
            records=tuple(records),critic=critic,critic_hash=evidence_hash(critic),
            native_checkpoint=state['native']['checkpoint'])
        self.journal.record(request_id,'RESULT',result)
        self._observe('output_persisted', through_cursor=through_cursor,
                      count=len(records), status=result['status'])
        return result
