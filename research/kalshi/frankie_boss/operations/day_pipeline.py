"""The unattended day pipeline, beginning to end (SPEC_UNATTENDED_DAILY_PIPELINE_20260916.md).

Seven idempotent stages, each gated by the receipt of the one before it, each writing ONE small
JSON receipt under runs/<DAY>/ (git is the record; no data). A failed stage stops the chain and
leaves the receipts of the stages that passed; the next dispatch resumes from the first stage
whose receipt is missing. The result-bearing stage (cycles) runs only under an explicit go
naming the day's source manifest hash; without it the chain stops there with a HOLD receipt.
Nothing here holds a credential: the AWS pair comes from the environment of the runner, and the
host reads its own credentials the way it already does.

    python day_pipeline.py --configuration pipeline.json --day 20211004 [--go <manifest_hash>] [--until <stage>]
    python day_pipeline.py --configuration pipeline.json --day 20211004 --host-stop     (the always() step)

Host stages run a script over SSM. That script must end with one line `PIPELINE_RECEIPT {json}`
carrying the gate fields listed in GATES; the orchestrator parses that line and nothing else.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
import importlib.util
import subprocess
import sys
import time

SCHEMA = 'FRANKIE_DAY_PIPELINE_RECEIPT_V1'
STAGES = ('stage-sources', 'host-start', 'ingest', 'schedule-prefixes', 'cycles', 'package-upload', 'snapshot-stop')
RESULT_BEARING = 'cycles'
GATES = {   # the fields the stage's receipt must carry for the next stage to run
    'stage-sources': ('manifest', 'manifest_hash', 'records'),
    'host-start': ('ssm_online',),
    'ingest': ('journal_count', 'journal_hash', 'compact_sha256'),
    'schedule-prefixes': ('prefix_count', 'prefixes_sha256'),
    'cycles': ('cycles_completed', 'cycles_total'),
    'package-upload': ('upload_manifest_sha256',),
    'snapshot-stop': ('snapshot_id', 'host_state'),
}
MARKER = 'PIPELINE_RECEIPT '
MIN_PARALLELISM_SHARE = 0.5   # busy CPUs must be at least half the dedicated worker CPUs (first run: 0.97)


class StageRefused(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def subprocess_runner(argv, *, timeout):
    """Default runner: argv -> (returncode, stdout). Never echoes the environment."""
    done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return done.returncode, done.stdout + ('\nSTDERR: ' + done.stderr if done.stderr else '')


def receipt_line(output):
    """The host script's final PIPELINE_RECEIPT line, or the last JSON line a runner tool prints."""
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
        if line.startswith('{') and line.endswith('}'):
            try:
                return json.loads(line)
            except ValueError:
                continue
    raise StageRefused('stage produced no receipt line')


class DayPipeline:
    def __init__(self, configuration, day, *, runner=subprocess_runner, runs_root='runs', now=time.time, cycle_limit=None):
        self.c, self.day, self.run, self.now = dict(configuration), str(day), runner, now
        if not self.day.isdigit() or len(self.day) != 8:
            raise ValueError('day must be YYYYMMDD')
        self.directory = Path(runs_root) / self.day
        declaration = self.c.get('trading_day_schedule')
        self.declaration = declaration
        self.cycle_count = 19
        if declaration is not None:
            if (declaration.get('trading_day') != self.day
                    or type(declaration.get('step_count')) is not int or declaration['step_count'] < 1
                    or type(declaration.get('source_record_count')) is not int or declaration['source_record_count'] < 1
                    or any(not isinstance(declaration.get(k), str) or len(declaration[k]) != 64
                           or any(c not in '0123456789abcdef' for c in declaration[k])
                           for k in ('schedule_sha256', 'source_manifest_hash'))):
                raise ValueError('trading_day_schedule needs the pinned day, counts and full hashes')
            self.cycle_count = declaration['step_count']
        if cycle_limit is None:
            cycle_limit = self.cycle_count
        if type(cycle_limit) is not int or not 1 <= cycle_limit <= self.cycle_count:
            raise ValueError('cycle_limit must be within the declared schedule' if declaration is not None
                             else 'cycle_limit must be from 1 through 19')
        self.cycle_limit = cycle_limit
        self.python = self.c.get('python', sys.executable)
        self._pending_mode()

    # ---- receipts -------------------------------------------------------------------------
    def path(self, stage):
        return self.directory / f'{STAGES.index(stage):02d}-{stage}.json'

    def receipt(self, stage):
        path = self.path(stage)
        if not path.exists():
            return None
        value = json.loads(path.read_bytes())
        if value.get('schema') != SCHEMA or value.get('day') != self.day or value.get('stage') != stage:
            raise StageRefused(f'{path} is not the receipt of {stage} for {self.day}')
        return value

    def write(self, stage, gate, *, command):
        previous = STAGES[STAGES.index(stage) - 1] if STAGES.index(stage) else None
        record = dict(schema=SCHEMA, day=self.day, stage=stage, at=self.now(), gate=gate,
                      command=[str(part) for part in command],
                      previous_receipt_sha256=(hashlib.sha256(canonical(self.receipt(previous))).hexdigest()
                                               if previous else None))
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.path(stage).open('xb') as handle:     # a receipt is written once; never overwritten
            handle.write(json.dumps(record, indent=1, sort_keys=True).encode() + b'\n')
        return record

    def require(self, stage):
        """The gate: the previous stage's receipt exists and carries every field its gate names."""
        index = STAGES.index(stage)
        if index == 0:
            return None
        previous = STAGES[index - 1]
        record = self.receipt(previous)
        if record is None:
            raise StageRefused(f'{stage} needs the {previous} receipt first')
        missing = [name for name in GATES[previous] if name not in record['gate']]
        if missing:
            raise StageRefused(f'{previous} receipt lacks gate fields {missing}')
        return record

    # ---- stages -----------------------------------------------------------------------------
    def _ssm(self, script_key, timeout):
        """The host stage's SSM command, or None when the configuration declares no script for it.

        The script file is sent verbatim, so everything per-run reaches it as a prepended PowerShell
        assignment: Day always, plus whatever host_variables declares (the host's roots live in the
        configuration, which main() scans, and never as a literal inside a script).
        """
        script = (self.c.get('host_scripts') or {}).get(script_key)
        if not script:
            return None
        command = [self.python, self.c['ssm_run'], '--instance', self.c['instance'], '--region', self.c['region'],
                   '--script', script, '--timeout', str(timeout), '--set', f'Day={self.day}']
        for name, value in sorted((self.c.get('host_variables') or {}).items()):
            if (self.declaration is not None and script_key == 'cycles' and name.lower() in
                    ('preparedconfigurationpath', 'preparedconfigurationsha256',
                     'requirepreparedconfiguration', 'expectedtradingdayschedulesha256',
                     'pendingreturn', 'resumewaitsha256', 'day', 'cyclelimit')):
                continue
            command += ['--set', f'{name}={value}']
        if script_key in ('cycles', 'schedule_prefixes'):
            command += ['--set', f'CycleLimit={self.cycle_limit}']
        return command

    def _ec2(self, action, *extra):
        return [self.python, self.c['ec2_host'], '--instance', self.c['instance'], '--region', self.c['region'], action, *extra]

    def commands(self):
        c = self.c
        return {
            'stage-sources': [self.python, c['stage_block_sources'], '--block', c['block'], '--days', self.day,
                              '--archive', c['archive'], '--bucket', c['bucket'],
                              '--out', str(Path(c['blocks_dir']) / f'BLOCK_{self.day}_SOURCE_MANIFEST.json')],
            'host-start': self._ec2('start'),
            'ingest': self._ssm('ingest', c.get('ingest_timeout', 6 * 3600)),
            'schedule-prefixes': self._ssm('schedule_prefixes', c.get('prefix_timeout', 2 * 3600)),
            'cycles': self._ssm('cycles', c.get('cycles_timeout', 12 * 3600)),
            'package-upload': [self.python, c['upload_restore_set'], '--bucket', c['bucket'],
                               '--prefix', f"{c['restore_prefix']}/{self.day}", '--log', str(self.directory / 'upload.log')],
            'snapshot-stop': self._ec2('snapshot', '--label', self.day),
        }

    def _prepared_gate(self, value):
        def full_hash(v):
            return isinstance(v, str) and len(v) == 64 and all(c in '0123456789abcdef' for c in v)
        config = value.get('configuration')
        count = value.get('prefix_count')
        if (value.get('day') != self.day
                or value.get('source_records') != self.declaration['source_record_count']
                or value.get('schedule_sha256') != self.declaration['schedule_sha256']
                or type(count) is not int or not self.cycle_limit <= count <= self.cycle_count
                or not full_hash(value.get('prefixes_sha256'))
                or not isinstance(config, dict)
                or not isinstance(config.get('path'), str) or not config['path'].strip()
                or not full_hash(config.get('sha256'))
                or type(config.get('bytes')) is not int or config['bytes'] < 1):
            raise StageRefused('prepared configuration receipt differs from the declared day, schedule or file')
        return {k: value[k] for k in ('prefix_count', 'prefixes_sha256', 'day',
                                     'source_records', 'schedule_sha256', 'configuration')}

    def gate_of(self, stage, output):
        value = receipt_line(output) if stage not in ('host-start', 'snapshot-stop') else {}
        if stage == 'stage-sources':
            if value.get('status') != 'block_sources_staged':
                raise StageRefused('stage_block_sources did not report block_sources_staged')
            # stage_block_sources prints total_mbo_records; the other two names are older spellings.
            # A missing count must refuse here, because a null records field is 'present' to require().
            records = next((value[name] for name in ('total_mbo_records', 'records', 'mbo_records') if value.get(name) is not None), None)
            if records is None:
                raise StageRefused('stage-sources receipt line carries no source record count')
            return dict(manifest=value['manifest'], manifest_hash=value['manifest_hash'], records=records)
        if stage == 'host-start':
            if 'SSM Online' not in output:
                raise StageRefused('host did not reach SSM Online')
            return dict(ssm_online=True)
        if stage == 'snapshot-stop':
            snapshot = next((word for word in output.split() if word.startswith('snap-')), None)
            if snapshot is None or 'completed' not in output:
                raise StageRefused('snapshot did not complete')
            return dict(snapshot_id=snapshot, host_state='snapshotted')
        if self.declaration is not None and stage == 'schedule-prefixes':
            return self._prepared_gate(value)
        if self.declaration is not None and stage == 'cycles':
            if (value.get('status') != 'all_scheduled_cycles_complete'
                    or value.get('day') != self.day or self.cycle_limit != self.cycle_count
                    or any(type(value.get(k)) is not int or value[k] != self.cycle_count
                           for k in ('cycles_completed', 'cycles_total', 'requested_cycles'))):
                raise StageRefused('completed cycles receipt differs from the declared day and roster')
        gate = {name: value.get(name) for name in GATES[stage]}
        if any(gate[name] is None for name in gate):
            raise StageRefused(f'{stage} receipt line lacks {[n for n in gate if gate[n] is None]}')
        if stage == 'schedule-prefixes' and gate['prefix_count'] < min(self.c.get('minimum_prefixes', self.cycle_count), self.cycle_limit):
            raise StageRefused('fewer prefixes than the day requires')
        if stage == 'cycles' and gate['cycles_completed'] != gate['cycles_total']:
            raise StageRefused('cycles incomplete; resume with the same run directory')
        if stage == 'ingest':
            # Same dedication gate as the recorded runner job: busy CPUs vs dedicated worker CPUs.
            workers, wall, seconds = value.get('worker_cpus') or [], value.get('wall_seconds'), value.get('worker_cpu_seconds')
            if not workers or not wall or seconds is None:
                raise StageRefused('host ingest receipt carries no worker CPU dedication evidence')
            gate.update(worker_cpus=list(workers), wall_seconds=wall, parallelism=round(seconds / wall, 3))
            if gate['parallelism'] < MIN_PARALLELISM_SHARE * len(workers):
                raise StageRefused(f"workers collapsed: {gate['parallelism']} CPUs busy for {len(workers)} dedicated worker CPUs")
            self.reconcile_ingest(gate['journal_count'])
        return gate

    def reconcile_ingest(self, count):
        """An ingest receipt is about THIS day only if it reduced the records this day staged.

        The journal job is pinned to one snapshot request, so a receipt from another day's
        reduction is verified, self-consistent, well formed and about the wrong source. No field
        check can see that; only this comparison against a count built by a different step, from
        different bytes, can. (S108 hole #8: consistency was never the test.)
        """
        staged = self.receipt('stage-sources')
        if staged is None:
            raise StageRefused('ingest cannot be reconciled: this day has no stage-sources receipt')
        expected = staged['gate']['records']
        if count != expected:
            raise StageRefused(f'ingest receipt reduced {count} records; {self.day} staged {expected}. '
                               'The journal job reduces the snapshot named in its pinned request, not the staged day.')


    # Pending is evidence, never the completion gate at 04-cycles.json.
    def _pending_mode(self):
        enabled = self.c.get('pending_return', False)
        if type(enabled) is not bool:
            raise StageRefused('pending_return must be a boolean')
        if not enabled:
            return False
        pins = self.c.get('workflow_run')
        fields = {'run_id', 'run_directory', 'boss_commit', 'configuration_sha256', 'schedule_sha256'}
        if (self.declaration is None or type(pins) is not dict or set(pins) != fields
                or any(type(pins[k]) is not str or not pins[k] for k in fields)
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', pins['run_id'])
                or not re.fullmatch('[0-9a-f]{40}', pins['boss_commit'])
                or any(not re.fullmatch('[0-9a-f]{64}', pins[k])
                       for k in ('configuration_sha256', 'schedule_sha256'))):
            raise StageRefused('pending continuation requires an explicit schedule and workflow_run pins')
        return True

    def _wait_gate(self, value, requested):
        pins = self.c['workflow_run']
        prepared = self._prepared_gate(self.receipt('schedule-prefixes')['gate'])
        wait = value.get('wait_receipt')
        digest = value.get('receipt_sha256')
        if (value.get('status') not in ('workflow_wait', 'workflow_attention')
                or value.get('day') != self.day
                or type(requested) is not int or not 1 <= requested <= self.cycle_limit
                or value.get('requested_cycles') != requested
                or type(value.get('requested_cycles')) is not int
                or value.get('cycles_total') != self.cycle_count
                or type(value.get('cycles_total')) is not int
                or value.get('prepared_configuration_sha256') != prepared['configuration']['sha256']
                or value.get('schedule_sha256') != prepared['schedule_sha256']
                or any(value.get(k) != pins[k] for k in ('run_id', 'run_directory'))
                or type(wait) is not dict
                or type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest)
                or hashlib.sha256(canonical(wait)).hexdigest() != digest
                or type(value.get('receipt_path')) is not str or not value['receipt_path']):
            raise StageRefused('pending receipt differs from the declared run, schedule or prepared configuration')
        fields = {'schema', 'state', 'kind', 'run_id', 'run_directory', 'cycle_index', 'request_id',
                  'configuration_sha256', 'boss_commit', 'schedule_sha256', 'job_id', 'artifacts', 'receipt_id'}
        if (set(wait) != fields or wait['schema'] != 'FRANKIE_WORKFLOW_WAIT_V1'
                or wait['state'] not in ('WAIT', 'ATTENTION')
                or value['status'] != ('workflow_wait' if wait['state'] == 'WAIT' else 'workflow_attention')
                or wait['kind'] not in ('readiness', 'service_resume', 'principal', 'principal_correction', 'same_job')
                or (wait['kind'] == 'same_job') != (wait['state'] == 'ATTENTION')
                or (wait['kind'] == 'same_job' and wait['job_id'] is None)
                or any(wait[k] != pins[k] for k in pins)
                or type(wait['cycle_index']) is not int or not 0 <= wait['cycle_index'] < requested
                or wait['request_id'] != f"{pins['run_id']}-cycle-{wait['cycle_index']:02d}"
                or (wait['job_id'] is not None and (type(wait['job_id']) is not str
                    or not re.fullmatch('[0-9a-f]{64}', wait['job_id'])))
                or wait['receipt_id'] != hashlib.sha256(canonical(
                    {k: v for k, v in wait.items() if k != 'receipt_id'})).hexdigest()
                or type(wait['artifacts']) is not dict or not wait['artifacts']):
            raise StageRefused('pending receipt identity or retained context binding differs')
        relative = f"execution/cycle-{wait['cycle_index']:02d}"
        required = {'host-identity.c15.json', relative + '/host-preparation.c15.json',
                    relative + '/actual-critic-request.json'}
        if wait['kind'] in ('principal', 'principal_correction'):
            required |= {relative + '/request-plan.c15.json', relative + '/principal/session-request.json'}
        if wait['kind'] == 'principal_correction':
            required.add(relative + '/principal/classroom-correction-request.json')
        if wait['kind'] == 'service_resume':
            required.add(relative + '/host-service.c15.json')
        path_type = PureWindowsPath if PureWindowsPath(pins['run_directory']).drive else PurePosixPath
        root = path_type(pins['run_directory'])
        receipt_path = path_type(value['receipt_path'])
        if (not required <= wait['artifacts'].keys() or not root.is_absolute()
                or '..' in root.parts or '..' in receipt_path.parts
                or receipt_path != root / relative / 'workflow-wait' / (wait['kind'] + '.json')):
            raise StageRefused('pending receipt path or required retained artifacts differ')
        for name, witness in wait['artifacts'].items():
            if (type(name) is not str or not name or name.startswith('/')
                    or '\\' in name or any(part in ('', '.', '..') for part in name.split('/'))
                    or type(witness) is not dict or set(witness) != {'sha256', 'bytes'}
                    or type(witness['bytes']) is not int or witness['bytes'] < 0
                    or type(witness['sha256']) is not str
                    or not re.fullmatch('[0-9a-f]{64}', witness['sha256'])):
                raise StageRefused('pending retained artifact witness is invalid')
        return value

    @staticmethod
    def _metadata():
        # The sibling is stdlib-only; importing the package would load model code.
        spec = importlib.util.spec_from_file_location('pipeline_wait_metadata',
                    Path(__file__).with_name('workflow_wait.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @classmethod
    def _retain(cls, path, record):
        try:
            cls._metadata()._publish(path, record)
        except (ValueError, OSError) as error:
            raise StageRefused('retained pending metadata publication refused: ' + str(error)) from error
        return record

    def pending(self):
        """Validate the complete immutable chain, refusing ambiguous/foreign history."""
        records = {}
        config_hash = hashlib.sha256(canonical(self.c)).hexdigest()
        previous_hash = hashlib.sha256(canonical(self.receipt('schedule-prefixes'))).hexdigest()
        for path in sorted(self.directory.glob('04-cycles-wait-*.json')):
            if path.is_symlink():
                raise StageRefused('pending metadata must not be a link')
            try: raw = self._metadata()._read(path)
            except (ValueError, OSError) as error:
                raise StageRefused('retained pending metadata read refused') from error
            try: record = json.loads(raw)
            except ValueError:
                raise StageRefused('pending metadata is incomplete') from None
            if (type(record) is not dict or raw != canonical(record)
                    or set(record) != {'schema', 'day', 'stage', 'status', 'gate', 'configuration_sha256',
                                       'previous_receipt_sha256', 'previous_wait_sha256', 'requested_cycles'}
                    or record['schema'] != SCHEMA or record['day'] != self.day or record['stage'] != 'cycles'
                    or record['status'] not in ('WAIT', 'ATTENTION')
                    or record['configuration_sha256'] != config_hash
                    or record['previous_receipt_sha256'] != previous_hash):
                raise StageRefused('retained pending configuration or preparation changed')
            value = self._wait_gate(record['gate'], record['requested_cycles'])
            digest = value['receipt_sha256']
            if (path.name != f'04-cycles-wait-{digest}.json'
                    or record['status'] != value['wait_receipt']['state'] or digest in records):
                raise StageRefused('pending receipt filename or state differs')
            records[digest] = record
        parent = None
        visited = set()
        last = None
        while True:
            children = [(key, item) for key, item in records.items()
                        if item['previous_wait_sha256'] == parent]
            if not children:
                break
            if len(children) != 1 or children[0][0] in visited:
                raise StageRefused('pending receipt chain is ambiguous')
            parent, last = children[0]
            visited.add(parent)
        if len(visited) != len(records):
            raise StageRefused('pending receipt chain is incomplete or contradictory')
        return last

    def _write_wait(self, value, requested, prior):
        value = self._wait_gate(value, requested)
        digest = value['receipt_sha256']
        if prior is not None and prior['gate']['receipt_sha256'] == digest:
            if prior['gate'] != value:
                raise StageRefused('replayed pending receipt wrapper changed')
            return prior
        record = dict(schema=SCHEMA, day=self.day, stage='cycles', status=value['wait_receipt']['state'],
            gate=value, requested_cycles=requested,
            configuration_sha256=hashlib.sha256(canonical(self.c)).hexdigest(),
            previous_receipt_sha256=hashlib.sha256(canonical(self.receipt('schedule-prefixes'))).hexdigest(),
            previous_wait_sha256=None if prior is None else prior['gate']['receipt_sha256'])
        self._retain(self.directory / f'04-cycles-wait-{digest}.json', record)
        self.pending()
        return record

    def run_stage(self, stage, *, go=None, resume_wait=None):
        if self.receipt(stage) is not None:
            return 'present'
        self.require(stage)
        if stage == 'ingest' and self.c.get('ingest_on', 'runner') != 'host':
            # The gold-standard journal stack runs as the workflow's own job on the runner and is recorded
            # with --record; only ingest_on: host runs it over SSM on the declared host.
            raise StageRefused('ingest runs as the workflow journal job; record its receipt with --record ingest '
                               '(set ingest_on: host in the configuration to run it over SSM instead)')
        if stage == RESULT_BEARING:
            expected = self.receipt('stage-sources')['gate']['manifest_hash']
            if go != expected:
                hold = self.directory / f'{STAGES.index(stage):02d}-{stage}.HOLD.json'
                hold.write_bytes(json.dumps(dict(schema=SCHEMA, day=self.day, stage=stage, status='HOLD',
                    reason='no go naming this day\'s source manifest hash; data plane only',
                    manifest_hash=expected, at=self.now()), indent=1, sort_keys=True).encode() + b'\n')
                return 'hold'
        if self.declaration is not None and stage in ('stage-sources', 'ingest'):
            raise StageRefused('the trading-day source manifest and completed ingestion are recorded externally; no UTC restaging or re-ingest')
        pending_mode = stage == 'cycles' and self._pending_mode()
        prior = None
        requested = self.cycle_limit
        if stage == 'cycles':
            if pending_mode:
                prior = self.pending()
            elif resume_wait is not None or any(self.directory.glob('04-cycles-wait-*.json')):
                raise StageRefused('retained pending run requires pending_return mode')
            if prior is not None:
                if resume_wait is None:
                    return 'wait' if prior['status'] == 'WAIT' else 'attention'
                if (resume_wait != prior['gate']['receipt_sha256']
                        or prior['status'] != 'WAIT'):
                    raise StageRefused('exact resumable WAIT receipt required; ATTENTION needs reconciliation')
                waiting = prior['gate']['wait_receipt']
                requested = (prior['requested_cycles']
                             if 'workflow-execution-scope.json' in waiting['artifacts']
                             else waiting['cycle_index'] + 1)
            elif resume_wait is not None:
                raise StageRefused('resume requires a retained WAIT receipt; it cannot launch a new run')
        if pending_mode and self.c.get('workflow_automation') is not None:
            # Automated events cannot create a run or supply the owner's release.
            bridge_spec = importlib.util.spec_from_file_location('pipeline_event_release',
                                Path(__file__).with_name('workflow_event_bridge.py'))
            bridge = importlib.util.module_from_spec(bridge_spec)
            bridge_spec.loader.exec_module(bridge)
            if prior is None or not bridge.verify_release(self, prior['gate']['wait_receipt']):
                return 'hold'
        command = self.commands()[stage]
        if command is None:
            raise StageRefused(f'the configuration declares no host script for {stage}')
        if self.declaration is not None and stage == 'cycles':
            prepared = self._prepared_gate(self.receipt('schedule-prefixes')['gate'])
            configuration = prepared['configuration']
            command += ['--set', 'RequirePreparedConfiguration=1',
                        '--set', 'PreparedConfigurationPath=' + configuration['path'],
                        '--set', 'PreparedConfigurationSha256=' + configuration['sha256'],
                        '--set', 'ExpectedTradingDayScheduleSha256=' + prepared['schedule_sha256']]
        if pending_mode:
            command = [f'CycleLimit={requested}' if part == f'CycleLimit={self.cycle_limit}' else part
                       for part in command]
            command += ['--set', 'PendingReturn=1']
            if resume_wait is not None:
                command += ['--set', 'ResumeWaitSha256=' + resume_wait]
        code, output = self.run(command, timeout=self.c.get('stage_timeout', 13 * 3600))
        if code != 0:
            raise StageRefused(f'{stage} exited {code}: {output}')
        if stage == 'cycles':
            value = receipt_line(output)
            if value.get('status') in ('workflow_wait', 'workflow_attention'):
                if not pending_mode:
                    raise StageRefused('pending receipt requires opt-in pending_return')
                record = self._write_wait(value, requested, prior)
                return 'wait' if record['status'] == 'WAIT' else 'attention'
            if value.get('status') == 'requested_cycles_complete':
                if (any(type(value.get(k)) is not int for k in ('cycles_total', 'cycles_completed', 'requested_cycles'))
                        or value.get('day') != self.day or value.get('cycles_total') != self.cycle_count
                        or value.get('cycles_completed') != requested
                        or value.get('requested_cycles') != requested
                        or requested == self.cycle_count):
                    raise StageRefused('partial cycles receipt differs from the requested batch')
                path = self.directory / f'04-cycles-batch-{requested:02d}.json'
                if path.exists():
                    if json.loads(path.read_bytes())['gate'] != value:
                        raise StageRefused('retained partial cycles receipt changed')
                else:
                    record = dict(schema=SCHEMA, day=self.day, stage=stage, status='PARTIAL',
                                  gate=value, at=self.now(), command=command,
                                  previous_receipt_sha256=hashlib.sha256(canonical(self.receipt('schedule-prefixes'))).hexdigest())
                    with path.open('xb') as handle:
                        handle.write(canonical(record) + b'\n')
                return 'partial'
        self.write(stage, self.gate_of(stage, output), command=command)
        return 'done'

    def resume(self, *, go=None, until=None, resume_wait=None):
        """From the first stage without a receipt; stops at the first refusal or at HOLD."""
        if resume_wait is not None:
            # A receipt event carries authority only for the waiting cycle stage.
            # Earlier stages must already exist; later stages remain separate actions.
            for previous in STAGES[:STAGES.index('cycles')]:
                if self.receipt(previous) is None:
                    raise StageRefused('same-run resume requires all preceding receipts')
                self.require(previous)
            return {'cycles': self.run_stage('cycles', go=go, resume_wait=resume_wait)}
        outcome = {}
        for stage in STAGES:
            outcome[stage] = self.run_stage(stage, go=go, resume_wait=resume_wait if stage == 'cycles' else None)
            if outcome[stage] in ('hold', 'partial', 'wait', 'attention') or stage == until:
                break
        return outcome

    def record_external(self, stage, receipt_path):
        """A stage that ran as its own workflow job (the gold-standard journal stack on the GitHub runner)
        records its receipt here; the gate reads the job's verification receipt, never a claim."""
        if self.receipt(stage) is not None:
            return 'present'
        self.require(stage)
        raw = Path(receipt_path).read_bytes()
        value = json.loads(raw)
        if stage == 'stage-sources' and self.declaration is not None:
            from research.kalshi.frankie_boss.block_source_scope import block_source_scope
            block_source_scope(value, expected_manifest_hash=self.declaration['source_manifest_hash'])
            if (value.get('trading_day') != self.day
                    or value.get('total_mbo_records') != self.declaration['source_record_count']):
                raise StageRefused('source manifest differs from the declared trading day')
            gate = dict(manifest=str(receipt_path), manifest_hash=value['manifest_hash'],
                        records=value['total_mbo_records'], receipt_sha256=hashlib.sha256(raw).hexdigest())
        elif (stage == 'ingest' and self.declaration is not None
                and value.get('schema') == 'FRANKIE_VERIFIED_RECOVERED_INGESTION_V1'):
            from research.kalshi.frankie_boss.recovered_ingestion import load_recovered_ingestion
            pin=dict(path=str(Path(receipt_path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            try:
                recovered=load_recovered_ingestion(pin)
            except (ValueError,KeyError,OSError) as error:
                raise StageRefused('independent recovery admission failed: '+str(error)) from error
            value=recovered.receipt
            if (value['trading_day']!=self.day or value['manifest_hash']!=self.declaration['source_manifest_hash']
                    or value['record_count']!=self.declaration['source_record_count']):
                raise StageRefused('verified recovery differs from declared trading day')
            gate=dict(journal_count=value['record_count'],journal_entries=value['journal_count'],
                journal_hash=value['journal_hash'],compact_sha256=recovered.container['sha256'],
                receipt_sha256=pin['sha256'],recovered_ingestion=recovered.provenance)
        elif stage == 'ingest' and self.declaration is not None:
            if (value.get('schema') != 'BOSS_BLOCK_INGESTION_RECEIPT_V1'
                    or value.get('writer') != 'compact' or value.get('session_policy') != 'cme_trading_day'
                    or value.get('trading_day') != self.day
                    or value.get('manifest_hash') != self.declaration['source_manifest_hash']
                    or value.get('record_count') != self.declaration['source_record_count']
                    or value.get('journal_count') != 2 * self.declaration['source_record_count']
                    or [s.get('session_id') for s in value.get('sessions', [])] != [self.day]):
                raise StageRefused('ingestion receipt differs from the declared trading day')
            gate = dict(journal_count=value['record_count'], journal_entries=value['journal_count'],
                        journal_hash=value.get('journal_hash'), compact_sha256=value.get('journal_sha256'),
                        receipt_sha256=hashlib.sha256(raw).hexdigest())
        elif stage == 'ingest':
            if value.get('schema') != 'FRANKIE_COMBINED_JOURNAL_EXECUTION_V1' or value.get('status') != 'verified':
                raise StageRefused('journal stack receipt is not a verified FRANKIE_COMBINED_JOURNAL_EXECUTION_V1')
            completion = value.get('completion') or {}
            workers = value.get('worker_cpus') or []
            wall, worker_seconds = value.get('wall_seconds'), value.get('worker_cpu_seconds')
            # CPU dedication is measured, not assumed: worker CPU seconds per wall second is the number of
            # CPUs that were actually busy at once. The first run: 2,079 / 715 = 2.9 on 3 workers.
            parallelism = round(worker_seconds / wall, 3) if wall and worker_seconds is not None else None
            if not workers or parallelism is None:
                raise StageRefused('journal stack receipt carries no worker CPU dedication evidence')
            if parallelism < MIN_PARALLELISM_SHARE * len(workers):
                raise StageRefused(f'workers collapsed: {parallelism} CPUs busy for {len(workers)} dedicated worker CPUs')
            gate = dict(journal_count=completion.get('count', value.get('source_records')),
                        journal_hash=completion.get('journal_hash', completion.get('head_hash', value.get('completion_digest'))),
                        compact_sha256=value.get('compact_sha256'),
                        journal_entries=value.get('journal_entries'), github_run_id=value.get('github_run_id'),
                        parent_cpu=value.get('parent_cpu'), worker_cpus=list(workers), parallelism=parallelism,
                        wall_seconds=wall, receipt_sha256=hashlib.sha256(raw).hexdigest())
        else:
            raise StageRefused(f'{stage} has no external receipt form')
        if any(gate[name] is None for name in GATES[stage]):
            raise StageRefused(f'{stage} receipt lacks {[n for n in GATES[stage] if gate[n] is None]}')
        if stage == 'ingest':
            self.reconcile_ingest(gate['journal_count'])
        self.write(stage, gate, command=['record', stage, str(receipt_path)])
        return 'done'

    def host_stop(self):
        """The always() step: stop the host whatever happened; the stop is its own small receipt."""
        code, output = self.run(self._ec2('stop'), timeout=1200)
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / 'host-stop.json').write_bytes(json.dumps(dict(schema=SCHEMA, day=self.day, stage='host-stop',
            at=self.now(), returncode=code, stopped='stopped' in output), indent=1, sort_keys=True).encode() + b'\n')
        if code != 0:
            raise StageRefused('host stop failed: ' + output[-1000:])

    def ensure_host_online(self):
        """A historical startup receipt does not describe today's EC2 power state."""
        code, output = self.run(self._ec2('start'), timeout=1200)
        if code != 0 or 'SSM Online' not in output:
            raise StageRefused('host restart did not reach SSM Online')

    def stop_compute(self):
        """Try both stops independently, including when the native stop fails."""
        failure = None
        try:
            self.host_stop()
        except Exception as error:
            failure = error
        ingest = self.c.get('ingest_runner')
        if ingest:
            command = [self.python, self.c['ec2_host'], '--instance', ingest['instance'],
                       '--region', ingest['region'], 'stop']
            try:
                code, output = self.run(command, timeout=1200)
                stopped = code == 0 and 'stopped' in output
                self.directory.mkdir(parents=True, exist_ok=True)
                (self.directory / 'ingest-runner-stop.json').write_bytes(canonical(dict(
                    schema=SCHEMA, day=self.day, stage='ingest-runner-stop', at=self.now(),
                    instance=ingest['instance'], region=ingest['region'], returncode=code,
                    stopped=stopped)) + b'\n')
                if not stopped:
                    raise StageRefused('ingest runner stop failed')
            except Exception as error:
                if failure is None:
                    failure = error
        if failure is not None:
            raise failure


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--day', required=True)
    parser.add_argument('--go', default=None, help="the day's source manifest hash; without it the chain stops before cycles")
    parser.add_argument('--until', default=None, choices=STAGES)
    parser.add_argument('--resume-wait', default=None, help='exact retained WAIT receipt hash; no new execution authority')
    parser.add_argument('--host-stop', action='store_true')
    parser.add_argument('--stop-compute', action='store_true')
    parser.add_argument('--ensure-host-online', action='store_true')
    parser.add_argument('--record', default=None, choices=STAGES, help='record a stage that ran as its own job')
    parser.add_argument('--from', dest='receipt_from', default=None, help="that job's verification receipt")
    parser.add_argument('--runs-root', default='runs')
    parser.add_argument('--cycles', type=int, default=None)
    args = parser.parse_args(argv)
    configuration = json.loads(Path(args.configuration).read_bytes())
    if any(word in json.dumps(configuration).lower() for word in ('secret', 'api_key', 'password', 'token')):
        raise SystemExit('pipeline configuration must contain no credential')
    pipeline = DayPipeline(configuration, args.day, runs_root=args.runs_root, cycle_limit=args.cycles)
    if args.host_stop:
        pipeline.host_stop()
        return 0
    try:
        if args.stop_compute:
            pipeline.stop_compute()
            return 0
        if args.ensure_host_online:
            pipeline.ensure_host_online()
            return 0
        if args.record:
            print(json.dumps(dict(status='ok', day=args.day, stages={args.record: pipeline.record_external(args.record, args.receipt_from)})), flush=True)
            return 0
        outcome = pipeline.resume(go=args.go, until=args.until, resume_wait=args.resume_wait)
    except StageRefused as error:
        print(json.dumps(dict(status='stage_refused', error=str(error))), flush=True)
        return 2
    print(json.dumps(dict(status='ok', day=args.day, stages=outcome)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
