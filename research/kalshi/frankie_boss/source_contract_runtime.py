"""Bind attested Frankie source conventions to exact runtime prefixes; no forward/labels."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .forecast_session import ForecastSession, PriceObservation
from .forecast_heads import KnotPolicy
from .rolling_forecast import ForecastTarget
from .native_forecast_refresh import session_registry_hash
from .frankie_principal_adapter import canonical, digest, file_witness, _write, _checked_receipt
from .frankie_dipole_classroom_adapter import DipoleClassroomPrincipalAdapter
from .frankie_source_mapping import bind_prefix


def load_contract(path, expected_sha256):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:
        raise ValueError('principal source contract differs from independent pin')
    body=json.loads(raw)
    trading = body.get('schema') == 'FRANKIE_TRADING_DAY_SOURCE_CONTRACT_V1'
    count = body.get('cycle_count') if trading else 19
    if (body.get('schema') not in ('FRANKIE_OWN_SOURCE_CONTRACT_V1', 'FRANKIE_TRADING_DAY_SOURCE_CONTRACT_V1')
            or type(count) is not int or count < 1 or len(body.get('cycles', [])) != count):
        raise ValueError('complete principal-authored source contract required')
    if trading:
        from .trading_day_schedule import _hash
        _hash(body.get('source_manifest_hash'), 'source_contract.source_manifest_hash')
        day = body.get('trading_day')
        if type(day) is not str or len(day) != 8 or not day.isdigit():
            raise ValueError('source_contract.trading_day required')
        if [c.get('cycle_index') for c in body['cycles']] != list(range(count)):
            raise ValueError('source contract cycle indices must cover the declared roster')
    for name in ('convention','calendar','timing_policy','query_policy'):
        if digest(body[name])!=body[name+'_hash']:
            raise ValueError('principal policy bytes differ from authored hash')
    if (body['convention']['usd_per_price_unit']!=1.0 or body['convention']['actual_ng_contract_multiplier'] is not None):
        raise ValueError('this development contract requires explicit non-exchange units')
    return body


def bind_cycle(contract_path, expected_contract_sha256, cycle_index, prefix):
    """The host supplies an independently verified schedule prefix, never inferred here."""
    contract=load_contract(contract_path,expected_contract_sha256)
    if type(cycle_index) is not int or not 0<=cycle_index<len(contract['cycles']):
        raise ValueError('valid chronological cycle index required')
    cycle=contract['cycles'][cycle_index]
    raw=cycle['source_prefix']
    expected={'through_cursor':raw['source_cursor'],'as_of':raw['receive_cutoff_ns'],
              'source_as_of':raw['event_cutoff_ns']}
    if cycle['cycle_index']!=cycle_index or any(prefix.get(k)!=v for k,v in expected.items()):
        raise ValueError('runtime prefix differs from authored exact cursor or causal clocks')
    if prefix.get('group_index',cycle['historical_group_index'])!=cycle['historical_group_index']:
        raise ValueError('runtime group differs from preserved cutoff')
    source_hash=prefix.get('source_hash')
    if not isinstance(source_hash,str) or len(source_hash)!=64 or any(c not in '0123456789abcdef' for c in source_hash):
        raise ValueError('verified runtime source prefix hash required')
    record=dict(cycle['forecast_session'])
    if record['source_hash'] not in (None,source_hash):
        raise ValueError('runtime hash conflicts with already-authored binding')
    record['source_hash']=source_hash
    for field in ('prior_close','opening'):
        record[field]=None if record[field] is None else PriceObservation(**record[field])
    record['known_marks']=tuple(PriceObservation(**mark) for mark in record['known_marks'])
    record['knot_policy']=KnotPolicy(**record['knot_policy'])
    session=ForecastSession(**record)
    session.validate_for_publication()
    if (session.event_cutoff_ns,session.receive_cutoff_ns)!=(expected['source_as_of'],expected['as_of']):
        raise ValueError('authored session differs from prefix clocks')
    target=ForecastTarget(session.instrument,session.session_id+':close',session.close_ns)
    sessions=((target,session),)
    split={'schema':'FRANKIE_AUTHORED_NEXT_CUTOFF_SPLIT_V1','contract_sha256':expected_contract_sha256,
        'rule':'cycle i learns only through next cutoff; resulting model cannot serve before feedback availability',
        'cycles':[{'cycle_index':c['cycle_index'],'as_of':c['source_prefix']['receive_cutoff_ns'],
            'through_cursor':c['source_prefix']['source_cursor'],'learning_cutoff_ns':c['learning_cutoff_ns'],
            'learning_through_source_cursor':c['learning_through_source_cursor']} for c in contract['cycles']]}
    pending = contract.get('forecast_mode') == 'whole_day_next_session'
    if pending:
        split = dict(schema='FRANKIE_WHOLE_DAY_PENDING_OUTCOMES_SPLIT_V1',
            contract_sha256=expected_contract_sha256, forecast_target=contract['forecast_target'],
            rule='retain forecast and classroom; native learning awaits verified target-day outcomes')
    return {'sessions':sessions,'expected_sessions_hash':session_registry_hash(sessions),
        **({'forecast_mode':'whole_day_next_session', 'forecast_target':contract['forecast_target'],
            'feedback_status':'pending_target_outcomes'} if pending else {}),
        **({'trading_day':contract['trading_day'], 'cycle_count':contract['cycle_count'],
            'source_manifest_hash':contract['source_manifest_hash'],
            'authored_contract_json':Path(contract_path).read_bytes().decode('utf-8')} if 'trading_day' in contract else {}),
        **expected,'source_hash':source_hash,'learning_cutoff_ns':cycle['learning_cutoff_ns'],
        'learning_through_source_cursor':cycle['learning_through_source_cursor'],
        'timing_policy_hash':contract['timing_policy_hash'],'query_policy_hash':contract['query_policy_hash'],
        'split_hash':digest(split),'split':split,'contract_sha256':expected_contract_sha256,
        'cycle_index':cycle_index,'path_query_offsets_ns':tuple(cycle['path_query_offsets_ns']),
        'development_units':contract['convention']['usd_basis']}


def principal_inputs(config):
    """The same explicit admission inputs for host construction and response recording."""
    single = config.get('single_run')
    mapping = config.get('mapping') if single is None else None
    delivery = config.get('delivery_receipt') if single is None else None
    return dict(
        mapping_directory=str(Path(mapping['path']).parent) if mapping else None,
        expected_mapping_sha256=mapping['sha256'] if mapping else None,
        receiver_root=config['receiver_root'], receiver_commit=config['receiver_commit'],
        admission=config.get('principal_admission'),
        retained_directory=str(Path(config['retained_witnesses']['path']).parent),
        expected_retained_witnesses_sha256=config['retained_witnesses']['sha256'],
        delivery_receipt=delivery['path'] if delivery else None,
        expected_delivery_file_sha256=delivery['sha256'] if delivery else None,
        result_path=config['calculation_result']['path'],
        calculation_pins=config.get('calculation_pins'), single_run=single,
        joined_teacher=config.get('joined_teacher'))


def make_principal_adapter(*, binding, handoff_directory, expected_manifest_sha256,
        boss_journal_path, source_journal_checkpoint, mapping_directory, expected_mapping_sha256,
        receiver_root, receiver_commit, python, directory, retained_directory,
        expected_retained_witnesses_sha256, delivery_receipt, expected_delivery_file_sha256,
        result_path, classroom_package, session_executor=None, adapter_class=None, admission=None, shared_knowledge=None,
        calculation_pins=None, single_run=None, joined_teacher=None):
    """Build the per-prefix receiver pins plus mandatory Dipole classroom.

    Each cycle gets its own directory. All expected hashes/checkpoints are supplied
    by the host's retained trusted receipts; this helper does not mint controller
    completion, mapping equivalence, historical authorship, principal labels, or
    Dipole targets. The classroom package must already be bound to this cutoff by
    the host from the governed teacher attachment. The adapter class is an explicit
    runtime dependency so the final reviewed classroom cannot be swapped by module
    rebinding between preparation and recovery.
    """
    if shared_knowledge is not None:
        from .dipole_shared_knowledge import validate_descriptor
        shared_knowledge=validate_descriptor(shared_knowledge)
        if classroom_package['pre_message'].get('shared_knowledge')!=shared_knowledge:
            raise ValueError('principal and classroom shared knowledge differ')
    elif classroom_package['pre_message'].get('shared_knowledge') is not None:
        raise ValueError('shared classroom knowledge requires an explicit principal binding')
    if calculation_pins is None:
        if binding.get('forecast_mode') == 'whole_day_next_session':
            raise ValueError('whole-day principal requires its retained calculation pin')
        pin_render={}
    else:
        if (type(calculation_pins) is not dict or set(calculation_pins)!={'path','bytes','sha256'}
                or file_witness(calculation_pins['path'])!={k:calculation_pins[k] for k in ('bytes','sha256')}):
            raise ValueError('principal calculation pin differs from the host witness')
        pin_render={'calculation-pins':calculation_pins['path']}
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    manifest_path=Path(handoff_directory)/'manifest.json'
    if file_witness(manifest_path)['sha256']!=expected_manifest_sha256:
        raise ValueError('exported manifest differs from trusted export receipt')
    manifest=json.loads(manifest_path.read_bytes())
    source=manifest['source']
    if any(source[k]!=binding[v] for k,v in (('prefix_hash','source_hash'),('through_cursor','through_cursor'),
            ('as_of','as_of'),('source_as_of','source_as_of'))):
        raise ValueError('controller export differs from authored runtime cycle')
    if manifest['agent_commit']!=receiver_commit:
        raise ValueError('export names a different receiver commit')
    if single_run is not None:
        if (binding.get('forecast_mode') != 'whole_day_next_session'
                or admission != {'mode': 'single_run', 'output_validation': 'after_execution'}
                or shared_knowledge is None):
            raise ValueError('single-run needs explicit admission and the shared research snapshot')
        from .frankie_principal_adapter import load_cycle_calculation_pin
        def read(witness):
            if file_witness(witness['path']) != {k: witness[k] for k in ('bytes', 'sha256')}:
                raise ValueError('single-run input differs from its retained witness')
            return json.loads(Path(witness['path']).read_bytes())
        calculations = read(single_run['calculations_receipt'])
        source_binding = read(single_run['source_binding'])
        source_pin = load_cycle_calculation_pin(binding['cycle_index'], calculation_pins['path'])['source_binding']
        if (calculations.get('schema') != 'FRANKIE_MONDAY_CALCULATIONS_V1'
                or calculations.get('status') != 'calculations_retained'
                or calculations['source_binding'] != single_run['source_binding']
                or calculations['calculation_pins'] != calculation_pins
                or source_binding['source'] != source_pin
                or source_pin['trading_day'] != binding['trading_day']
                or source_pin['manifest_hash'] != binding['source_manifest_hash']
                or source_pin['source_prefix_hash'] != binding['source_hash']
                or source_pin['record_count'] != binding['through_cursor'] + 1):
            raise ValueError('completed calculations do not cover this entire bound source')
        derivation = read(calculations['derivation'])
        bedrock = derivation.get('bedrock') or {}
        producer_receipt = read(bedrock['receipt'])
        if (derivation.get('failure_count') != 0
                or derivation.get('source_binding') != source_binding
                or derivation.get('input_records') != source_pin['record_count']
                or bedrock.get('records') != source_pin['record_count']
                or bedrock.get('result') != calculations['result']
                or bedrock.get('ledgers') != calculations['ledgers']
                or producer_receipt.get('identity', {}).get('run_id') !=
                   Path(single_run['calculations_receipt']['path']).parent.name + '-cycle-00'):
            raise ValueError('single-run calculation identity, coverage or failures differ')
        retained = Path(retained_directory)
        witness_path = retained / 'retained-witnesses.json'
        if file_witness(witness_path)['sha256'] != expected_retained_witnesses_sha256:
            raise ValueError('retained section witness changed')
        sections = {name.split('contract_section_')[1].removesuffix('.json'): witness
            for name, witness in json.loads(witness_path.read_bytes())['files'].items()
            if '/contract_section_' in name}
        read(single_run['knowledge_base'])
        from .dipole_shared_knowledge import load_snapshot, descriptor
        shared = single_run['shared_knowledge']
        snapshot = load_snapshot(shared['directory'], shared['snapshot_hash'])
        if descriptor(snapshot) != shared_knowledge:
            raise ValueError('single-run principal and teacher sources differ')
        retained_inputs = dict(calculations_receipt=single_run['calculations_receipt'],
            source_binding=single_run['source_binding'], calculation_pins=calculation_pins,
            derivation=calculations['derivation'], producer_receipt=bedrock['receipt'], result=calculations['result'],
            digest=calculations['digest'], digest_proof=calculations['digest_proof'],
            knowledge_base=single_run['knowledge_base'],
            knowledge_manifest=dict(path=str(snapshot.directory / 'MANIFEST.json'),
                                    **file_witness(snapshot.directory / 'MANIFEST.json')))
        for name, witness in calculations['ledgers'].items():
            retained_inputs['ledger:' + name] = {k: witness[k] for k in ('path', 'bytes', 'sha256')}
        pins = dict(schema='FRANKIE_SINGLE_RUN_PREPARATION_PINS_V1',
            expected_manifest_sha256=expected_manifest_sha256, boss_source=source,
            contract_sha256=binding['contract_sha256'], retained_inputs=retained_inputs,
            source_journal_checkpoint=source_journal_checkpoint)
        pins_path = directory / 'preparation-pins.json'
        if pins_path.exists():
            if pins_path.read_bytes() != canonical(pins):
                raise ValueError('retained single-run preparation pins differ')
        else:
            _write(pins_path, pins)
        feedback_contract = {k: v for k, v in binding.items() if k != 'sessions'}
        feedback_contract['sessions'] = [{'target': asdict(t), 'session': asdict(s)}
                                         for t, s in binding['sessions']]
        from .dipole_classroom_integration import IntegratedDipoleClassroomPrincipalAdapter
        if adapter_class is not IntegratedDipoleClassroomPrincipalAdapter:
            raise ValueError('single-run requires the integrated mandatory classroom')
        return adapter_class(receiver_root=receiver_root, receiver_commit=receiver_commit, python=python,
            admission=admission, cycle_index=binding['cycle_index'], directory=directory,
            preparation={'pins_path': str(pins_path), 'expected_pins_sha256': digest(pins)},
            render={'knowledge-manifest': str(snapshot.directory / 'MANIFEST.json'),
                    'calculation-pins': calculation_pins['path']},
            protected_files={}, section_evidence=sections, feedback_contract=feedback_contract,
            classroom_package=classroom_package, session_executor=session_executor,
            shared_knowledge=shared_knowledge, joined_teacher=joined_teacher)
    mapping_file=directory/'bound-mapping.json'
    if mapping_file.exists():
        bound=json.loads(mapping_file.read_bytes())
        if (bound.get('boss_source')!=source or bound.get('mapping_sha256')!=expected_mapping_sha256
                or bound.get('journal_checkpoint')!=source_journal_checkpoint):
            raise ValueError('retained mapping binding differs')
    else:
        bind_prefix(mapping_directory=mapping_directory,expected_mapping_sha256=expected_mapping_sha256,
            boss_journal_path=boss_journal_path,journal_checkpoint=source_journal_checkpoint,
            boss_source=source,output_path=mapping_file)
    retained=Path(retained_directory)
    witness_path=retained/'retained-witnesses.json'
    if file_witness(witness_path)['sha256']!=expected_retained_witnesses_sha256:
        raise ValueError('retained evidence witness file differs from host pin')
    witnesses={name: witness for name, witness in json.loads(witness_path.read_bytes())['files'].items()
        if name != 'FROZEN_MEMORY_A_20211003.json'}
    for witness in witnesses.values():
        if file_witness(witness['path'])!={k:witness[k] for k in ('bytes','sha256')}:
            raise ValueError('historical principal evidence changed')
    if file_witness(delivery_receipt)['sha256']!=expected_delivery_file_sha256:
        raise ValueError('redelivery bytes differ from host pin')
    delivered=_checked_receipt(delivery_receipt)
    result=json.loads(Path(result_path).read_bytes())
    identity=result['layers']['identity_receipt']
    agent={'run_id':identity['run_id'],'arm':identity['arm'],'source_day':binding.get('trading_day', '20211003'),
        'source_manifest_hash':identity['source_manifest_hash'],
        'delivery_manifest_sha256':delivered['manifest_sha256'],
        'delivery_receipt_sha256':delivered['receipt_sha256'],'result_hash':result['result_hash']}
    mapping_witness=file_witness(mapping_file)
    pins={'schema':'FRANKIE_BOSS_PREPARATION_PINS_V1','mode':'attributed_input',
        'pin_origin':{'authority':'Codex host verified controller export and full source mapping',
            'method':'independently pinned exporter manifest, source journal checkpoint, and full wire mapping',
            'reference':binding['contract_sha256']},
        'expected_manifest_sha256':expected_manifest_sha256,'expected_boss_commit':manifest['boss_commit'],
        'expected_agent_commit':receiver_commit,'controller_checkpoint':manifest['controller_checkpoint'],
        'native_checkpoint':manifest['native_checkpoint'],'boss_source':source,'agent':agent,
        'provenance':{'authority':'Codex host full mapping and actual source journal verification',
            'method':'EXACT_WIRE_BYTES_AND_ACTUAL_BOSS_PREFIX',
            'mapping_artifact_sha256':mapping_witness['sha256'],'mapping_artifact_bytes':mapping_witness['bytes']},
        'result_file_sha256':file_witness(result_path)['sha256'],
        'delivery_file_sha256':expected_delivery_file_sha256}
    pins_path=directory/'preparation-pins.json'
    if pins_path.exists():
        if pins_path.read_bytes()!=canonical(pins):raise ValueError('retained preparation pins differ')
    else:_write(pins_path,pins)
    sections={name.split('contract_section_')[1].removesuffix('.json'):witness
        for name,witness in witnesses.items() if '/contract_section_' in name}
    feedback_contract={k:v for k,v in binding.items() if k!='sessions'}
    feedback_contract['sessions']=[{'target':asdict(target),'session':asdict(session)} for target,session in binding['sessions']]
    adapter_class = DipoleClassroomPrincipalAdapter if adapter_class is None else adapter_class
    if type(adapter_class) is not type or not issubclass(adapter_class, DipoleClassroomPrincipalAdapter):
        raise ValueError('principal adapter class must preserve the mandatory Dipole classroom contract')
    return adapter_class(receiver_root=receiver_root,receiver_commit=receiver_commit,python=python,admission=admission,
        cycle_index=binding['cycle_index'],
        directory=directory,preparation={'pins_path':str(pins_path),'expected_pins_sha256':digest(pins),
            'result_path':str(Path(result_path).resolve()),'delivery_receipt':str(Path(delivery_receipt).resolve()),
            'mapping_artifact':str(mapping_file)},
        render={'retained-prompt':witnesses['sunday_spawn_prompt.md']['path'],
            'retained-prompt-sha256':witnesses['sunday_spawn_prompt.md']['sha256'],
            'knowledge-receipt':witnesses['KNOWLEDGE_RECEIPT.json']['path'],
            'knowledge-receipt-sha256':witnesses['KNOWLEDGE_RECEIPT.json']['sha256'],
            'knowledge-bundle-sha256':witnesses['KNOWLEDGE_BUNDLE.md']['sha256'], **pin_render},
        protected_files={},
        section_evidence=sections,feedback_contract=feedback_contract,
        classroom_package=classroom_package,session_executor=session_executor,
        **({'shared_knowledge':shared_knowledge} if shared_knowledge is not None else {}),
        **({'joined_teacher':joined_teacher} if joined_teacher is not None else {}))


def metadata_for_binding(binding, *, state_defects_and_gaps_reported):
    """Explicit development abstention metadata, without manufacturing market plays."""
    from datetime import datetime,timedelta,timezone
    from zoneinfo import ZoneInfo
    from .frankie_contract import BLD1_FIELDS
    if type(state_defects_and_gaps_reported) not in (tuple,list) or any(type(v) is not str for v in state_defects_and_gaps_reported):
        raise ValueError('host must supply its known source defects explicitly')
    result=[]
    for target,session in binding['sessions']:
        close=(datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(microseconds=session.close_ns//1000)).astimezone(ZoneInfo('America/New_York'))
        value={'specialist':'REAL_TIME_FRANKIE','group':'A_MEMORY','date':close.strftime('%Y%m%d'),
            'reasoning':('Native BOSS development forecast under Frankie source contract '+binding['contract_sha256']+
                '. Same-source analytical anchors and explicit 1.0 development numeraire; not exchange contract P&L. '
                'Historical 18-section evidence retained; Memory A is not required. No broker action or calibrated performance claim.'),
            'plays_fired':[],'plays_stood_down':[],
            'state_defects_and_gaps_reported':list(state_defects_and_gaps_reported),'disposition':'ABSTAIN'}
        for field in BLD1_FIELDS:
            if field.name in value:field.validate(value[field.name])
        result.append((target.digest,value))
    return tuple(result)
