"""Executable receiver and agent-session boundary for new BOSS feedback.

The session executor is supplied by the authorized host, never inferred from an
installed CLI. Historical section evidence is reused with its original hashes;
only the feedback is newly authored. This module computes no market labels.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

try:
    from .native_forecast_learning import FrankieFeedback, SessionFeedback, TimingLabel, ValueLabel
except ImportError:
    from native_forecast_learning import FrankieFeedback, SessionFeedback, TimingLabel, ValueLabel

FROZEN_MEMORY_SHA256 = '4a47b09d5b19a9165c570f9432d2f3190a657843009536d5dad9a6bd99d83f4a'

# Greg Davis, 2026-09-20: "we will make this info available to Frankie going forward on the Sunday runs
# and all subsequent calc findings. We will not hide this." The committed, append-only run-findings
# ledger is rendered into every prompt this adapter renders, exact bytes, witnessed in the request
# attachment; Frankie's own prior lessons (the coordinator's lessons store) are rendered beside it.
# The frozen Memory A and the eighteen historical sections are untouched: this is a separate block.
RUN_FINDINGS_PATH = Path(__file__).resolve().parent / 'knowledge' / 'RUN_FINDINGS.md'
RUN_FINDINGS_SIDECAR = 'run-findings-witness.json'

SECTIONS = ('4.0', '4.0b') + tuple(f'4.{i}' for i in range(1, 17))

# The ten append-only output ledgers the native ingestion registry expects Frankie to file (the
# 2026-09-16 crosswalk of the A_MEMORY recalculation run 33746436209 lists them OUTPUT_PENDING, and
# the first Sunday run filed none): they are his calculations, filed as lesson entries.
OUTPUT_LEDGERS = (
    'output_candidate_discoveries', 'output_first_locks_and_no_locks', 'output_frankie_reasoning_movie',
    'output_probability_movie', 'output_state_and_state_delta_movie', 'output_knowledge_retrieval_receipts',
    'output_negative_sparse_inconclusive_ledger', 'output_provider_invocation_response_receipts',
    'output_answer_wall_access_receipts', 'output_source_state_manifest_code_model_run_hashes')

# The calculation set Frankie must derive himself on each cycle's rows: the layers of the native
# ingestion registry (registry sha256 239a1480..., A_MEMORY arm, crosswalk of run 33746436209 on
# 2026-09-16) that were CALCULATED on August 28 (Greg, 2026-09-20: "don't look at who did them but look
# at the ones that were done"). Each group is a registry group_id and its layer_ids, verbatim; the
# frozen learned structure is the comparison set, never the substitute.
REGISTRY_CALCULATION_SET = (
    ('order_lifecycle', ('order_lifecycle_adds', 'order_lifecycle_cancels', 'order_lifecycle_modifies',
                         'order_lifecycle_replaces', 'order_lifecycle_trades', 'order_lifecycle_fills',
                         'order_lifecycle_clears', 'order_identity_transitions', 'contract_session_roll_state')),
    ('full_book_fifo_queue', ('full_bid_ask_depth', 'price_level_and_order_counts', 'fifo_queues',
                              'queue_age_and_survival', 'queue_concentration', 'orders_and_volume_ahead',
                              'spread_and_depth_imbalance', 'complete_state_reset_bootstrap_receipts')),
    ('microstructure_mechanics', ('mechanics_actions_by_side_and_level', 'aggressor_and_native_signed_flow',
                                  'depletion_and_replenishment', 'resilience_and_recovery',
                                  'churn_and_queue_turnover', 'price_and_book_path',
                                  'missingness_and_integrity_flags')),
    ('legacy_observable_crosswalk', ('legacy_price', 'legacy_native_signed_flow', 'legacy_per_second_roll20',
                                     'legacy_book_imbalance', 'legacy_structure_observables')),
    ('derived_geometry', ('derived_roll20_and_dipole_state', 'derived_d_family_geometry',
                          'derived_open_world_predecessor_state', 'derived_ancestry_gaps',
                          'derived_unresolved_age_chain_trajectory', 'derived_price_flow_book_paths',
                          'derived_v4_mechanics_fifo_features', 'derived_feature_availability_timestamps')),
    ('prebirth_opportunity', ('prebirth_predecessor_at_risk_state', 'prebirth_unresolved_chain_extension_state',
                              'prebirth_ancestry_successor_opportunity',
                              'prebirth_stopped_chain_false_context_controls',
                              'prebirth_negative_opportunity_cases')),
    ('causal_clocks', ('clock_event_time', 'clock_receive_time', 'clock_event_known_by',
                       'clock_feature_availability', 'clock_prospective_discovery_confirmation',
                       'clock_model_evaluation', 'clock_lock_time')),
)
FROZEN_LEARNED_STRUCTURE = (
    'learned_d_structures_and_families', 'learned_dipoles_and_geometry', 'learned_pair_triplet_recurrence',
    'learned_chains_extensions_reappearances_ancestry', 'phase1_discoveries_structural_falsifiers',
    'phase2_findings_modules_timing_pox_negatives', 'predecessor_ancestry_unresolved_chain_state',
    'historical_timing_lifespan_context', 'learned_structure_proposal_index_material')
CALCULATION_ACCOUNTING_LEDGER = 'calculation_accounting'

RUN_ANALYSIS_INSTRUCTION = (
    'Print your own run analysis in the session output and retain the same Markdown text '
    'as a separate entry in lessons. Cover how this run has gone so far, your assessment '
    'of the new BOSS and its actual attributed output, what the retained calculations '
    'measured, and what those calculations found. Cite the relevant section hashes and '
    'current run evidence. Distinguish observed results from your interpretation; name '
    'failures, unavailable observations, uncertainties, and useful next lessons. Do not '
    'claim later cycles or learning steps have completed before their evidence exists. '
    'Cite the retained eighteen sections with their original hashes as provenance. Keep this new '
    'analysis separate from frozen Memory A and the eighteen historical sections. '
    + 'THE CALCULATIONS ARE YOURS, NOT THE RUNNER\'S (Greg Davis, standing rule, restated 2026-09-20): '
    'on this cycle\'s delivered rows, derive yourself the exhaustion chains with their extensions, '
    'reappearances and ancestry, the D structures and families, the dipoles and geometry, the pair and '
    'triplet recurrences, and the pre-birth opportunities; compare what you derive with the retained '
    'sections and the frozen learned structure, and learn from every difference; the retained sections '
    'are provenance, never a substitute for your own derivation. THE REQUIRED SET IS THE REGISTRY, not a '
    'summary of it: the calculation layers of the native ingestion registry that the August 28 '
    'recalculation (run 33746436209, A_MEMORY arm) carried, each derived by you on this cycle\'s rows, '
    'group by group and layer by layer: '
    + '; '.join(group + ' (' + ', '.join(layers) + ')' for group, layers in REGISTRY_CALCULATION_SET)
    + '. Compare every derivation with the frozen learned structure layers (' + ', '.join(FROZEN_LEARNED_STRUCTURE)
    + ') and with the retained sections. File ONE accounting entry in lessons, a JSON object whose "ledger" '
    'field is "' + CALCULATION_ACCOUNTING_LEDGER + '", listing every layer above with its status: derived '
    '(with where the derivation is written), compared (with what differed), or could_not (with the reason); '
    'no layer is omitted and no layer is delegated to a runner. File the ten append-only output '
    'ledgers of the native ingestion registry as separate entries in lessons, each a JSON object whose '
    '"ledger" field is the registry name: ' + ', '.join(OUTPUT_LEDGERS) + '. A ledger you cannot fill '
    'is filed with its reason, never omitted. Every lesson entry is rendered back to you in each later '
    'cycle; write them to be learned from. '
)


class PrincipalNotDispatched(RuntimeError):
    """No adapter request exists: the host provably has not dispatched a session."""


class PrincipalPending(RuntimeError):
    """An existing session must finish or supply its retained response; never retry."""


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()


def json_form(value):
    """The identity a durable record carries: its own canonical JSON, re-read.

    Live request and correction objects hold tuples (the c15 loader preserves them) that
    canonical JSON writes as lists, so a durable file can never equal the live object by
    Python equality. Every comparison of a retained file against a live object goes through
    this form; digests are unaffected because they already hash the canonical bytes.
    """
    return json.loads(canonical(value))


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_witness(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('regular evidence file required')
    count, hashed = 0, hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            count += len(block)
            hashed.update(block)
    return {'bytes': count, 'sha256': hashed.hexdigest()}


def _write(path, body):
    with Path(path).open('xb') as handle:
        handle.write(canonical(body))
        handle.flush()
        os.fsync(handle.fileno())


def _checked_receipt(path):
    body = json.loads(Path(path).read_bytes())
    if body.get('receipt_sha256') != digest({k: v for k, v in body.items() if k != 'receipt_sha256'}):
        raise ValueError('receipt self hash differs')
    return body


def rebind_delivery_receipt(original, expected_original_sha256, local_directory, output):
    """Attest a new local delivery by rehashing every original plaintext witness.

    Original receipt bytes are retained and independently pinned. The new receipt
    explicitly cites those bytes and does not impersonate the historical fetch.
    """
    if file_witness(original)['sha256'] != expected_original_sha256:
        raise ValueError('original delivery receipt differs from independent pin')
    prior = _checked_receipt(original)
    body = json.loads(canonical(prior))
    local = Path(local_directory).resolve()
    for entry in body['ledgers'].values():
        target = local / entry['file']
        if target.parent != local:
            raise ValueError('ledger path escapes delivery directory')
        witness = file_witness(target)
        if witness != {'bytes': entry['plain_bytes_expected'], 'sha256': entry['plain_sha256_expected']}:
            raise ValueError(f'plaintext ledger differs: {target.name}')
        entry.update(local_path=str(target), plain_bytes_observed=witness['bytes'],
                     plain_sha256_observed=witness['sha256'], status='VERIFIED')
    for name, entry in body['objects'].items():
        target = local / name
        if target.parent != local:
            raise ValueError('object path escapes delivery directory')
        witness = file_witness(target)
        if witness['bytes'] != entry['content_length_expected']:
            raise ValueError(f'delivery object size differs: {name}')
        expected = entry.get('sha256_expected') or entry.get('sha256_observed')
        if expected and expected != witness['sha256']:
            raise ValueError(f'delivery object hash differs: {name}')
        entry.update(local_path=str(target), bytes_observed=witness['bytes'],
                     sha256_observed=witness['sha256'], status='VERIFIED')
    body['out_dir'] = str(local)
    body['local_redelivery'] = {'method': 'rehash_retained_plaintext_and_objects',
        'original_receipt_file_sha256': expected_original_sha256,
        'original_receipt_sha256': prior['receipt_sha256']}
    body['receipt_sha256'] = digest({k: v for k, v in body.items() if k != 'receipt_sha256'})
    _write(output, body)
    return body


def retained_knowledge(receipt_path, receipt_sha256, bundle_path, bundle_sha256):
    """Verify historical bytes directly; never rebuild from post-Sunday checkout."""
    if file_witness(receipt_path)['sha256'] != receipt_sha256:
        raise ValueError('retained knowledge receipt bytes differ')
    receipt = _checked_receipt(receipt_path)
    witness = file_witness(bundle_path)
    if witness != {'bytes': receipt['model_visible_context_bytes'],
                   'sha256': receipt['model_visible_context_sha256']} or witness['sha256'] != bundle_sha256:
        raise ValueError('retained knowledge bundle bytes differ')
    seeds = [a for a in receipt['artifacts'] if a['id'] == 'seed_a_memory_20260902']
    if len(seeds) != 1 or seeds[0]['sha256'] != FROZEN_MEMORY_SHA256 or seeds[0]['bytes'] != 166700:
        raise ValueError('only the frozen pre-Sunday Memory A is admissible')
    bundle = Path(bundle_path).read_bytes()
    marker = ('===== BEGIN KNOWLEDGE seed_a_memory_20260902 ' + FROZEN_MEMORY_SHA256 + ' =====\n').encode()
    if bundle.count(marker) != 1:
        raise ValueError('frozen prior memory missing from retained bundle')
    seed = bundle.split(marker, 1)[1].split(b'===== END KNOWLEDGE seed_a_memory_20260902 =====', 1)[0]
    if not any(len(raw) == 166700 and hashlib.sha256(raw).hexdigest() == FROZEN_MEMORY_SHA256
               for raw in (seed, seed[:-1])):
        raise ValueError('embedded frozen Memory A bytes differ')
    return receipt


OUTPUT_BUNDLE_GATE_VALIDATED = 'VALIDATED'          # receiver prepare_boss_attachment.OUTPUT_BUNDLE_GATE_*
OUTPUT_BUNDLE_GATE_NOT_PRESENTED = 'NOT_PRESENTED'
CURRENT_RECEIVER_REQUIRED_LEDGERS = 32              # receiver 2ebb8ce8: 30 + what_he_learned + in_his_own_words
SEALED_PROOF_SCHEMA = 'FRANKIE_SEALED_ABSENCE_PROOF_V1'
SEALED_UNPROVEN = 'UNPROVEN'
ADMISSION_UNDECLARED = 'UNDECLARED'
MEMORY_A_ATTESTATION = ('Greg Davis, 2026-09-17: the frozen pre-Sunday Memory A seed is declared VALID as served. '
    'The crosswalk status DEGENERATE_PROOF_SAME_AS_SUBJECT is an accounted input status (the seed proves itself by '
    'design, D86/D88) and gates nothing; no validation day or separate source day exists or is required.')


def admission_policy(admission, *, retained_prompt):
    """The per-run admission on the BOSS boundary (audit finding 4): declared, never inferred.

    output_bundle: {'principal_artifact', 'outputs_dir'} (the receiver validates the principal's
    output ledgers against the artifact citing them) or the literal 'NOT_PRESENTED', the declared
    historical policy. sealed_proof: a FRANKIE_SEALED_ABSENCE_PROOF_V1 path, or the literal
    'UNPROVEN' under the same historical rule. The historical literals are admissible only with a
    retained prompt: a newly rendered run is never exempt. None is ADMISSION_UNDECLARED, which
    every use (prepare, request, recover) refuses; it exists so a retained configuration that
    predates the policy fails at use with the exact missing declaration named.
    """
    if admission is None:
        return ADMISSION_UNDECLARED
    if type(admission) is not dict or set(admission) != {'output_bundle', 'sealed_proof'}:
        raise ValueError('principal admission must declare output_bundle and sealed_proof explicitly')
    bundle, sealed = admission['output_bundle'], admission['sealed_proof']
    if bundle != OUTPUT_BUNDLE_GATE_NOT_PRESENTED and not (type(bundle) is dict
            and {'principal_artifact', 'outputs_dir'} <= set(bundle)
            and set(bundle) <= {'principal_artifact', 'outputs_dir', 'output_ledger_count'}
            and all(type(bundle[key]) is str and bundle[key] for key in ('principal_artifact', 'outputs_dir'))
            and type(bundle.get('output_ledger_count', 32)) is int
            and bundle.get('output_ledger_count', 32) in (30, 32)):
        raise ValueError('output_bundle must name principal_artifact and outputs_dir, or declare NOT_PRESENTED')
    producer = (type(sealed) is dict and set(sealed) == {'producer', 'repo_root', 'repo_commit'}
        and sealed['producer'] == 'native_sealed_absence'
        and type(sealed['repo_root']) is str and bool(sealed['repo_root'])
        and type(sealed['repo_commit']) is str and len(sealed['repo_commit']) == 40
        and all(c in '0123456789abcdef' for c in sealed['repo_commit']))
    if producer and not retained_prompt:
        raise ValueError('sealed proof producer requires the retained prompt route')
    if sealed != SEALED_UNPROVEN and not producer and not (type(sealed) is str and sealed):
        raise ValueError('sealed_proof must be a FRANKIE_SEALED_ABSENCE_PROOF_V1 path, or declare UNPROVEN')
    if not retained_prompt and (bundle == OUTPUT_BUNDLE_GATE_NOT_PRESENTED or sealed == SEALED_UNPROVEN):
        raise ValueError('a newly rendered principal run is never exempt: NOT_PRESENTED/UNPROVEN are admissible '
                         'only with a retained prompt')
    return {'output_bundle': bundle if bundle == OUTPUT_BUNDLE_GATE_NOT_PRESENTED else dict(bundle),
            'sealed_proof': sealed}


def sealed_absence(path):
    """Verify a receiver-produced sealed-absence proof; its witness travels in the attachment."""
    if path == SEALED_UNPROVEN:
        return {'status': 'SEALED_UNPROVEN'}
    proof = json.loads(Path(path).read_bytes())
    if (type(proof) is not dict or proof.get('schema') != SEALED_PROOF_SCHEMA or proof.get('all_absent') is not True
            or type(proof.get('tokens_checked')) is not int or proof['tokens_checked'] <= 0
            or type(proof.get('receipt_sha256')) is not str or len(proof['receipt_sha256']) != 64):
        raise ValueError('sealed-absence proof must be FRANKIE_SEALED_ABSENCE_PROOF_V1 with every sealed token absent')
    return {'status': 'PROVEN', 'path': str(Path(path).resolve()), 'tokens_checked': proof['tokens_checked'],
            'receipt_sha256': proof['receipt_sha256'], **file_witness(path)}


class FrankiePrincipalAdapter:
    """Durable outbox/inbox around a real frozen receiver and authorized session.

    preparation: kwargs accepted by frozen prepare_boss_attachment CLI (except
    directory/output_directory, supplied here). render: explicit emitter CLI
    arguments including pinned pre-Sunday knowledge-receipt. protected_files and
    section_evidence map names to {path, bytes, sha256} independently trusted by
    the host. session_executor(request) may dispatch a host agent and return its
    response, or be None for an outbox consumed by the host's session tools.
    """
    def __init__(self, *, receiver_root, receiver_commit, python, directory,
                 preparation, render, protected_files, section_evidence,
                 feedback_contract, session_executor=None, admission=None):
        self.receiver_root = Path(receiver_root).resolve()
        self.receiver_commit = receiver_commit
        self.python = str(python)
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.directory.is_relative_to(self.receiver_root):
            raise ValueError('principal evidence must be outside frozen receiver checkout')
        self.preparation, self.render = dict(preparation), dict(render)
        for key in ('knowledge-receipt', 'knowledge-receipt-sha256', 'knowledge-bundle-sha256'):
            if not self.render.get(key):
                raise ValueError('explicit pinned pre-Sunday knowledge receipt and bundle required')
        common_render = {'knowledge-receipt', 'knowledge-receipt-sha256', 'knowledge-bundle-sha256'}
        if self.render.get('retained-prompt'):
            if set(self.render) - common_render - {'retained-prompt', 'retained-prompt-sha256'}:
                raise ValueError('unexpected retained-prompt configuration')
            if not self.render.get('retained-prompt-sha256'):
                raise ValueError('retained prompt independent hash required')
        else:
            if set(self.render) - common_render - {'result', 'delivery-receipt', 'stream-receipt',
                    'outputs-receipt', 'sealed-proof', 'ledger-dir', 'evidence-uri'}:
                raise ValueError('unexpected emitter configuration')
            for render_key, preparation_key in (('result', 'result_path'), ('delivery-receipt', 'delivery_receipt')):
                if preparation_key not in self.preparation:
                    raise ValueError('preparation result and delivery paths required')
                supplied = self.render.get(render_key, self.preparation[preparation_key])
                if Path(supplied).resolve() != Path(self.preparation[preparation_key]).resolve():
                    raise ValueError('emitter paths differ from receiver preparation')
                self.render[render_key] = str(Path(supplied).resolve())
        if set(section_evidence) != set(SECTIONS) or not protected_files:
            raise ValueError('all 18 preserved sections and frozen memory witnesses required')
        self.protected_files = protected_files
        self.section_evidence = section_evidence
        self.feedback_contract = json.loads(canonical(feedback_contract))
        self.session_executor = session_executor
        self.admission = admission_policy(admission, retained_prompt=bool(self.render.get('retained-prompt')))
        if self.admission != ADMISSION_UNDECLARED and self.admission['sealed_proof'] != SEALED_UNPROVEN \
                and not self.render.get('retained-prompt'):
            # The emitter receives the same proof the attachment witnesses (emit_frankie_spawn --sealed-proof).
            supplied = self.render.get('sealed-proof', self.admission['sealed_proof'])
            if Path(supplied).resolve() != Path(self.admission['sealed_proof']).resolve():
                raise ValueError('emitter sealed-proof differs from the declared admission')
            self.render['sealed-proof'] = str(Path(supplied).resolve())

    def _config_hash(self):
        return digest({'receiver_root': str(self.receiver_root), 'receiver_commit': self.receiver_commit,
            'python': self.python, 'preparation': {k: str(v) for k, v in self.preparation.items()},
            'render': {k: str(v) for k, v in self.render.items()},
            'protected_files': self.protected_files, 'section_evidence': self.section_evidence,
            'feedback_contract': self.feedback_contract, 'admission': self.admission, 'mechanism': 'AGENT_SESSION'})

    def _code(self):
        try:
            observed = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.receiver_root, text=True,
                                               stderr=subprocess.STDOUT).strip()
        except (subprocess.CalledProcessError, OSError) as error:
            # Finding 8: a restored receiver worktree without its parent repository reads an empty HEAD.
            raise ValueError('frozen receiver checkout is not a git repository at ' + str(self.receiver_root)
                             + '; restore the receiver parent repository at the pinned commit before any '
                             'principal request') from error
        if observed != self.receiver_commit:
            raise ValueError('frozen receiver commit differs')
        changed = subprocess.check_output(['git', 'status', '--porcelain', '--', 'research'], cwd=self.receiver_root, text=True)
        if changed.strip():
            raise ValueError('frozen receiver sources changed')

    def _files(self):
        for witness in list(self.protected_files.values()) + list(self.section_evidence.values()):
            if file_witness(witness['path']) != {k: witness[k] for k in ('bytes', 'sha256')}:
                raise ValueError('frozen memory or preserved section evidence changed')

    def _run(self, module, args):
        self._code()
        command = [self.python, '-m', 'research.kalshi.frankie_raw_mbo_benchmark.' + module]
        for name, value in args.items():
            flag = '--' + name.replace('_', '-')
            command.extend([flag] if value is True else [flag, str(value)])
        result = subprocess.run(command, cwd=self.receiver_root, capture_output=True, check=False)
        if result.returncode:
            raise ValueError(f'{module} refused: ' + result.stderr.decode('utf-8', errors='replace')[-2000:])
        self._code()

    def _declared(self):
        if self.admission == ADMISSION_UNDECLARED:
            raise ValueError('principal admission undeclared: the host configuration must carry principal_admission '
                             '(output_bundle: principal_artifact + outputs_dir or NOT_PRESENTED; sealed_proof: path or UNPROVEN)')
        return self.admission

    def _check_output_bundle_gate(self, receipt):
        """The receiver's gate must match the declared policy; VALIDATED means every current ledger."""
        gate = receipt.get('output_bundle_gate')
        bundle = self._declared()['output_bundle']
        if bundle == OUTPUT_BUNDLE_GATE_NOT_PRESENTED:
            if gate != {'status': OUTPUT_BUNDLE_GATE_NOT_PRESENTED}:
                raise ValueError('receiver output-bundle gate differs from the declared historical NOT_PRESENTED policy')
            return
        if type(gate) is not dict or gate.get('status') != OUTPUT_BUNDLE_GATE_VALIDATED:
            raise ValueError('receiver preparation did not validate the principal output bundle')
        expected = bundle.get('output_ledger_count', CURRENT_RECEIVER_REQUIRED_LEDGERS)
        required, ledgers = gate.get('required_ledger_ids'), gate.get('ledgers')
        if (type(required) is not list or len(set(required)) != expected
                or type(ledgers) is not dict or set(ledgers) != set(required)):
            raise ValueError(f'the declared receiver policy requires all {expected} output ledgers validated')

    def _memory_witness(self):
        """Finding 5: BOSS's own receipt over the frozen Memory A files it serves.

        Produced by BOSS from the served bytes, independently of the seed's self-hashes, so its
        file identity is never the subject's own; binding it into the knowledge receipt's
        a_memory_prior_package_proof layer is the receiver-side step that clears
        DEGENERATE_PROOF_SAME_AS_SUBJECT.
        """
        record = {'schema': 'FRANKIE_BOSS_MEMORY_A_WITNESS_V1', 'produced_by': 'BOSS principal adapter',
            'operator_attestation': MEMORY_A_ATTESTATION,
            'files': {name: dict(path=str(Path(w['path']).resolve()), **file_witness(w['path']))
                      for name, w in self.protected_files.items()},
            'knowledge_receipt_sha256': self.render['knowledge-receipt-sha256'],
            'knowledge_bundle_sha256': self.render['knowledge-bundle-sha256']}
        record['receipt_sha256'] = digest(record)
        return record

    def _admission_record(self):
        declared = self._declared()
        sealed = declared['sealed_proof']
        if type(sealed) is dict:
            proof = self.directory / 'sealed-proof.json'
            prompt = self.directory / 'prompt.md'
            if not prompt.is_file():
                raise ValueError('actual composed principal prompt required before sealed proof')
            args = dict(prompt=prompt, knowledge_receipt=self.render['knowledge-receipt'],
                knowledge_bundle=Path(self.render['knowledge-receipt']).parent / 'KNOWLEDGE_BUNDLE.md',
                delivery_receipt=self.preparation['delivery_receipt'], output=proof,
                repo_root=sealed['repo_root'], repo_commit=sealed['repo_commit'])
            if proof.exists(): args['verify_existing'] = True
            self._run('native_sealed_absence', args)
            sealed = str(proof)
        witness = self._memory_witness()
        path = self.directory / 'memory-a-witness.json'
        if path.exists():
            if json.loads(path.read_bytes()) != witness:
                raise ValueError('retained Memory A witness differs from the served frozen memory')
        else:
            _write(path, witness)
        return {'output_bundle_policy': OUTPUT_BUNDLE_GATE_NOT_PRESENTED
                    if declared['output_bundle'] == OUTPUT_BUNDLE_GATE_NOT_PRESENTED else OUTPUT_BUNDLE_GATE_VALIDATED,
                'sealed_absence': sealed_absence(sealed),
                'memory_a_witness_sha256': witness['receipt_sha256']}

    def prepare(self, handoff_directory):
        self._files()
        admission = None if type(self._declared()['sealed_proof']) is dict else self._admission_record()
        config = {'config_hash': self._config_hash()}
        config_path = self.directory / 'adapter-config.json'
        if config_path.exists():
            if json.loads(config_path.read_bytes()) != config:
                raise ValueError('retained principal configuration differs')
        else:
            _write(config_path, config)
        handoff_directory = str(Path(handoff_directory).resolve())
        prepared = self.directory / 'receiver'
        receipt_file = prepared / 'preparation-receipt.json'
        if prepared.exists() and not receipt_file.exists():
            if prepared.is_symlink() or prepared.resolve().parent != self.directory:
                raise ValueError('unsafe partial receiver directory')
            retained = self.directory / ('receiver.partial-' + uuid.uuid4().hex)
            prepared.rename(retained)  # preserve incomplete evidence; never overwrite/delete
        if not receipt_file.exists():
            bundle = self._declared()['output_bundle']
            policy = {'without_output_bundle': True} if bundle == OUTPUT_BUNDLE_GATE_NOT_PRESENTED else dict(bundle)
            self._run('prepare_boss_attachment', dict(self.preparation,
                directory=handoff_directory, output_directory=prepared, **policy))
        receipt = _checked_receipt(receipt_file)
        if receipt['input_paths']['directory'] != handoff_directory:
            raise ValueError('retained receiver receipt belongs to another handoff')
        self._check_preparation(receipt)
        bundle = Path(self.render['knowledge-receipt']).parent / 'KNOWLEDGE_BUNDLE.md'
        retained_knowledge(self.render['knowledge-receipt'], self.render['knowledge-receipt-sha256'],
                           bundle, self.render['knowledge-bundle-sha256'])
        prompt = self.directory / 'prompt.md'
        if not prompt.exists():
            if self.render.get('retained-prompt'):
                self._render_retained(prompt, prepared)
            else:
                self._run('emit_frankie_spawn', dict({k:v for k,v in self.render.items() if k not in ('knowledge-receipt-sha256', 'knowledge-bundle-sha256')}, output=prompt,
                    **{'boss-attachment-request': prepared / 'attachment-request.json'}))
        knowledge_bundle = Path(self.render['knowledge-receipt']).parent / 'KNOWLEDGE_BUNDLE.md'
        if admission is None:
            admission = self._admission_record()
        attachment = {'config_hash': self._config_hash(), 'preparation_receipt': receipt, 'prompt': str(prompt),
            'knowledge_bundle': str(knowledge_bundle), 'knowledge_bundle_witness': file_witness(knowledge_bundle),
            'prompt_witness': file_witness(prompt), 'section_evidence': self.section_evidence,
            'protected_files': self.protected_files, 'feedback_contract': self.feedback_contract,
            'admission': admission}
        # The run-findings witness exists only for prompts rendered with the ledger block; a prompt
        # rendered before it (cycle 0 of the 20211003 run) carries no sidecar and its retained
        # attachment stays byte-identical.
        sidecar = self.directory / RUN_FINDINGS_SIDECAR
        if sidecar.exists():
            attachment['run_findings_witness'] = json.loads(sidecar.read_bytes())
        attachment['attachment_hash'] = digest(attachment)
        return attachment

    def _receiver_input_block(self, prepared):
        self._code()
        # Existing frozen verifier remains authoritative; this code only transports its bytes.
        program = ("import sys; from research.kalshi.frankie_raw_mbo_benchmark.native_boss_attachment "
            "import load_request,verify_attachment; "
            "v=verify_attachment(load_request(sys.argv[1]),result_path=sys.argv[2],delivery_receipt=sys.argv[3]); "
            "sys.stdout.buffer.write(v.input_block().encode('utf-8'))")
        result = subprocess.run([self.python, '-c', program, str(prepared / 'attachment-request.json'),
            str(self.preparation['result_path']), str(self.preparation['delivery_receipt'])],
            cwd=self.receiver_root, capture_output=True)
        if result.returncode:
            raise ValueError('frozen receiver refused retained-prompt attachment: ' +
                result.stderr.decode('utf-8', errors='replace')[-2000:])
        self._code()
        return result.stdout

    def _render_retained(self, prompt, prepared):
        prior = Path(self.render['retained-prompt'])
        if file_witness(prior)['sha256'] != self.render['retained-prompt-sha256']:
            raise ValueError('retained historical prompt bytes differ')
        bundle = Path(self.render['knowledge-receipt']).parent / 'KNOWLEDGE_BUNDLE.md'
        retained_knowledge(self.render['knowledge-receipt'], self.render['knowledge-receipt-sha256'],
                           bundle, self.render['knowledge-bundle-sha256'])
        original = prior.read_bytes()
        original_copy = self.directory / 'historical-prompt.md'
        if original_copy.exists():
            if original_copy.read_bytes() != original:
                raise ValueError('saved historical prompt changed')
        else:
            with original_copy.open('xb') as handle:
                handle.write(original)
        block = self._receiver_input_block(prepared)
        findings = self._run_findings_block()
        prefix = ("# Current authorized continuation\n"
            "Sunday 2021-10-03 is the sole source and run day. No separate source day or October 1 "
            "prerequisite applies. Reuse completed principal-authored sections with their original "
            "authorship; author the new source convention, BOSS feedback and run analysis. Preserve frozen "
            "pre-Sunday Memory A; store new lessons separately. The original historical prompt follows "
            "unchanged for provenance, followed by the newly verified BOSS attributed input. Its "
            "multi-day sequencing is overridden by this current single-day instruction.\n"
            "Actual local delivery: " + str(self.preparation['delivery_receipt']) + "\n"
            "Feedback contract: " + canonical(self.feedback_contract).decode() + "\n\n"
            + RUN_ANALYSIS_INSTRUCTION + "\n\n").encode()
        heading = b"# Preserved historical principal prompt (exact bytes follow)\n"
        with Path(prompt).open('xb') as handle:
            handle.write(prefix + findings + heading + original + block)
            handle.flush()
            os.fsync(handle.fileno())

    def _run_findings_block(self):
        """Never hidden (Greg, 2026-09-20): the run-findings ledger, exact bytes, and Frankie's own prior
        lessons available at or before this cycle's as_of, rendered whole (no limit). The ledger's
        witness is saved beside the prompt so the attachment pins it on every later reconstruction."""
        ledger_path = Path(self.render.get('run-findings') or RUN_FINDINGS_PATH)
        ledger = ledger_path.read_bytes()
        witness = dict(file_witness(ledger_path), path=str(ledger_path))
        try:
            from .c15_journal import unpack
        except ImportError:
            from c15_journal import unpack
        import sqlite3
        as_of = self.feedback_contract.get('as_of') if isinstance(self.feedback_contract, dict) else None
        lessons_path = Path(self.directory).resolve().parents[2] / 'lessons.sqlite'
        rendered = []
        if lessons_path.is_file() and type(as_of) is int:
            db = sqlite3.connect(lessons_path.as_uri() + '?mode=ro', uri=True)
            try:
                rows = db.execute('SELECT request, available_ns, payload FROM lessons WHERE available_ns<=? '
                                  'ORDER BY available_ns, request', (as_of,)).fetchall()
            finally:
                db.close()
            for request, available_ns, raw in rows:
                record = unpack(json.loads(raw))
                rendered.append(f'## Prior lesson: request {request}, available_ns {available_ns}\n'
                                + json.dumps(record, indent=1, sort_keys=True, default=str) + '\n')
        lessons_text = ''.join(rendered) if rendered else '(none recorded before this cycle)\n'
        _write(Path(self.directory) / RUN_FINDINGS_SIDECAR, witness)
        return (('# Run findings ledger (operator-recorded, never hidden; exact bytes of '
                 + ledger_path.name + ', sha256 ' + witness['sha256'] + ')\n').encode()
                + ledger
                + ('\n# Prior lessons recorded by earlier cycles (lessons store, available at or before as_of '
                   + str(as_of) + ')\n').encode()
                + lessons_text.encode() + b'\n')

    def _check_preparation(self, receipt):
        self._code()
        if receipt['executing_agent_commit'] != self.receiver_commit:
            raise ValueError('preparation ran a different receiver commit')
        pins = Path(self.preparation['pins_path'])
        if file_witness(pins)['sha256'] != self.preparation['expected_pins_sha256']:
            raise ValueError('independent preparation pins changed')
        if receipt['pins_file'] != file_witness(pins):
            raise ValueError('retained preparation belongs to different pins')
        for name, path in (('result', self.preparation['result_path']),
                           ('delivery_receipt', self.preparation['delivery_receipt']),
                           ('mapping', self.preparation['mapping_artifact'])):
            if file_witness(path) != receipt['inputs'][name]:
                raise ValueError('prepared input file changed')
        handoff = Path(receipt['input_paths']['directory'])
        if file_witness(handoff / 'manifest.json') != receipt['inputs']['manifest']:
            raise ValueError('prepared manifest changed')
        manifest = json.loads((handoff / 'manifest.json').read_bytes())
        for item in manifest['files']:
            member = handoff / item['path']
            if member.resolve().parent != handoff.resolve() or file_witness(member) != {
                    'bytes': item['bytes'], 'sha256': item['sha256']}:
                raise ValueError('prepared BOSS attachment member changed')
        for name, witness in receipt['outputs'].items():
            if file_witness(self.directory / 'receiver' / name) != witness:
                raise ValueError('receiver preparation output changed')
        self._check_output_bundle_gate(receipt)

    def _request(self, request_id, attachment):
        self._files()
        if attachment.get('config_hash') != self._config_hash():
            raise ValueError('principal configuration differs from retained attachment')
        if attachment.get('attachment_hash') != digest({k: v for k, v in attachment.items() if k != 'attachment_hash'}):
            raise ValueError('attachment record changed')
        if file_witness(attachment['prompt']) != attachment['prompt_witness']:
            raise ValueError('principal prompt changed')
        if file_witness(attachment['knowledge_bundle']) != attachment['knowledge_bundle_witness']:
            raise ValueError('principal knowledge bundle changed')
        self._check_preparation(attachment['preparation_receipt'])
        if attachment.get('admission') != self._admission_record():
            raise ValueError('principal admission (output bundle, sealed absence, Memory A witness) changed since preparation')
        return {'schema': 'FRANKIE_BOSS_SESSION_REQUEST_V1', 'request_id': request_id,
            'attachment': attachment, 'mechanism': 'AGENT_SESSION', 'admission': attachment['admission'],
            'instruction': ('Read the full delivered causal evidence and actual BOSS attributed input. '
                'Reuse the preserved Frankie-authored 18-section evidence with its original authorship as '
                'provenance; never substitute runner findings for your own calculations. This authorized run '
                'is Sunday only and requires no separate source day. Preserve Memory A. Author new '
                'feedback and lessons against feedback_contract; use null for unavailable values. '
                'Cite every retained section hash. Supply feedback without principal_receipt_hash, '
                'lessons, sections (section ID to retained SHA256), session_id and '
                'model_identity_as_reported_by_session. The host attests actual session identity. '
                + RUN_ANALYSIS_INSTRUCTION)}

    def execute(self, request_id, attachment):
        request = self._request(request_id, attachment)
        path = self.directory / 'session-request.json'
        if path.exists():
            if json.loads(path.read_bytes()) != json_form(request):
                raise ValueError('session request identity changed')
            recovered = self.recover(request_id, attachment)
            if recovered is not None:
                return recovered
            raise PrincipalPending('existing principal intent has no completed response; do not resubmit')
        _write(path, request)  # durable intent before the session tool/remote call
        if self.session_executor is None:
            raise PrincipalPending(f'authorized host session must consume {path}')
        dispatched = self.session_executor(request)
        response_path = self.directory / 'session-response.json'
        if response_path.exists():
            # A host waiter may receive the response through the separately
            # locked, validating recorder. Never overwrite that immutable record.
            if json.loads(response_path.read_bytes()) != dispatched:
                raise ValueError('recorded principal response differs from host return')
            self._attest_host(dispatched['response'], dispatched['host_attestation'], request)
        else:
            self.record_session_response(dispatched['response'], host_attestation=dispatched['host_attestation'])
        return self.recover(request_id, attachment)

    def _attest_host(self, response, host_attestation, request):
        if (not isinstance(response, dict) or not isinstance(host_attestation, dict) or
                any(not isinstance(response.get(k),str) or not response[k].strip()
                    for k in ('session_id','model_identity_as_reported_by_session'))):
            raise ValueError('actual session identity and host attestation are required')
        expected = {'schema': 'FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1', 'mechanism': 'AGENT_SESSION',
            'request_sha256': digest(request), 'response_sha256': digest(response),
            'session_id': response['session_id'],
            'model_identity_as_reported_by_session': response['model_identity_as_reported_by_session']}
        if any(host_attestation.get(k) != v for k,v in expected.items()):
            raise ValueError('host attestation does not bind the actual request/response/session')
        record = host_attestation.get('host_record')
        if not isinstance(record, dict) or set(record) != {'path', 'bytes', 'sha256'}:
            raise ValueError('independent host session record witness required')
        if file_witness(record['path']) != {k:record[k] for k in ('bytes', 'sha256')}:
            raise ValueError('host session record bytes changed')
        host_record = json.loads(Path(record['path']).read_bytes())
        if any(host_record.get(k) != v for k,v in expected.items()) or not host_record.get('host_authority'):
            raise ValueError('host record does not attest this session response')
        return host_attestation

    def record_session_response(self, response, *, host_attestation):
        """Host-only: require its own retained dispatch/output witness, not model claims."""
        request_path = self.directory / 'session-request.json'
        if not request_path.exists():
            raise PrincipalNotDispatched('response cannot precede durable principal intent')
        self._files()
        request = json.loads(request_path.read_bytes())
        self._attest_host(response, host_attestation, request)
        _write(self.directory / 'session-response.json', {'response':response, 'host_attestation':host_attestation})

    def recover(self, request_id, attachment):
        request_path, response_path = (self.directory / name for name in ('session-request.json', 'session-response.json'))
        if not request_path.exists():
            raise PrincipalNotDispatched('no adapter request exists; no session was dispatched')
        if not response_path.exists():
            raise PrincipalPending('durable request exists without a response; wait for that session')
        request = self._request(request_id, attachment)
        if json.loads(request_path.read_bytes()) != json_form(request):
            raise ValueError('retained principal intent differs')
        retained = json.loads(response_path.read_bytes())
        response = retained['response']
        host_attestation = self._attest_host(response, retained['host_attestation'], request)
        for name in ('session_id', 'model_identity_as_reported_by_session'):
            if not isinstance(response.get(name), str) or not response[name].strip():
                raise ValueError('actual agent session identity is required')
        if response.get('request_sha256') != digest(request):
            raise ValueError('session response does not attest this exact request')
        if response.get('sections') != {k: v['sha256'] for k, v in self.section_evidence.items()}:
            raise ValueError('all 18 preserved section hashes must be cited exactly')
        receipt = {'schema': 'FRANKIE_BOSS_SESSION_RECEIPT_V1', 'mechanism': 'AGENT_SESSION',
            'session_id': response['session_id'],
            'model_identity_as_reported_by_session': response['model_identity_as_reported_by_session'],
            'request_sha256': digest(request), 'response_sha256': digest(response),
            'attachment_hash': attachment['attachment_hash'], 'host_attestation_hash': digest(host_attestation)}
        receipt['receipt_sha256'] = digest(receipt)
        feedback = dict(response['feedback'])
        if 'principal_receipt_hash' in feedback:
            raise ValueError('principal must not mint its own host receipt hash')
        feedback['principal_receipt_hash'] = receipt['receipt_sha256']
        return {'feedback': feedback, 'lessons': response['lessons'], 'principal_receipt': receipt,
                'admission': request['admission']}

    def verify(self, envelope, request_id, input_hash, source_hash, learning_cutoff_ns):
        request = json.loads((self.directory / 'session-request.json').read_bytes())
        trusted = self.recover(request_id, request['attachment'])
        if trusted != envelope:
            raise ValueError('feedback envelope differs from retained session response')
        body = envelope['feedback']
        if (body['request_id'], body['input_hash'], body['source_hash']) != (request_id, input_hash, source_hash):
            raise ValueError('principal feedback request/input/source binding differs')
        if type(body['available_ns']) is not int or not 0 <= body['available_ns'] <= learning_cutoff_ns:
            raise ValueError('principal feedback is not causally available')
        sessions = tuple(SessionFeedback(session_id=s['session_id'],
            timing=tuple(TimingLabel(**v) for v in s['timing']),
            gap=ValueLabel(**s['gap']) if s['gap'] is not None else None,
            path=tuple(ValueLabel(**v) for v in s['path'])) for s in body['sessions'])
        return FrankieFeedback(**dict(body, sessions=sessions))
